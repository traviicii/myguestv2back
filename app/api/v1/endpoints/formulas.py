from collections.abc import Sequence
from datetime import timedelta
from typing import Literal
from urllib.parse import quote, unquote, urlparse

from fastapi import APIRouter, Depends, Query, Response
import firebase_admin
from firebase_admin import storage as firebase_storage
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session, load_only, selectinload

from app.api.deps import get_current_user, get_session
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.service_names import format_service_name, normalize_service_key
from app.models import Client, Formula, FormulaImage, FormulaService, Service, User
from app.schemas.formula import (
    FormulaCreate,
    FormulaImageWrite,
    FormulaListResponse,
    FormulaRead,
    FormulaUpdate,
)

router = APIRouter(tags=["formulas"])


def _formula_load_options():
    return (
        selectinload(Formula.images),
        selectinload(Formula.formula_services).selectinload(FormulaService.service),
    )


def _parse_include(value: str | None) -> set[str]:
    if value is None:
        return {"images", "services"}
    parts = [part.strip().lower() for part in value.split(",")]
    return {part for part in parts if part in {"images", "services"}}


def _resolve_fields(value: str | None) -> Literal["full", "lite"]:
    return "lite" if value == "lite" else "full"


def _extract_storage_target(
    public_url: str | None, object_key: str | None
) -> tuple[str | None, str | None]:
    if object_key:
        return None, object_key.lstrip("/")
    if not public_url:
        return None, None

    trimmed = public_url.strip()
    if trimmed.startswith("gs://"):
        path = trimmed[len("gs://") :]
        bucket, _, object_path = path.partition("/")
        return bucket or None, object_path or None

    parsed = urlparse(trimmed)
    if (
        "firebasestorage.googleapis.com" in parsed.netloc
        and "/b/" in parsed.path
        and "/o/" in parsed.path
    ):
        segment = parsed.path.split("/b/", 1)[1]
        bucket = segment.split("/", 1)[0]
        encoded = segment.split("/o/", 1)[1].split("/", 1)[0]
        return bucket or None, unquote(encoded)
    return None, None


def _serialize_formula(
    formula: Formula,
    include_images: bool,
    include_services: bool,
    include_notes: bool,
    image_limit: int | None,
) -> dict:
    images: list[dict] = []
    if include_images:
        image_rows = list(formula.images or [])
        image_rows.sort(key=lambda image: image.id)
        if image_limit is not None:
            image_rows = image_rows[:image_limit]
        images = [
            {
                "id": image.id,
                "formula_id": image.formula_id,
                "storage_provider": image.storage_provider,
                "public_url": _resolve_image_public_url(image),
                "object_key": image.object_key,
                "file_name": image.file_name,
            }
            for image in image_rows
        ]

    services: list[dict] = []
    if include_services:
        service_rows = list(formula.formula_services or [])
        service_rows.sort(key=lambda service: service.position)
        services = [
            {
                "service_id": service.service_id,
                "name": service.name,
                "position": service.position,
                "label_snapshot": service.label_snapshot,
            }
            for service in service_rows
        ]

    return {
        "id": formula.id,
        "client_id": formula.client_id,
        "service_type": formula.service_type,
        "notes": formula.notes if include_notes else None,
        "price_cents": formula.price_cents,
        "service_at": formula.service_at,
        "images": images,
        "services": services,
    }


def _get_owned_client(db: Session, user_id: int, client_id: int) -> Client:
    client = db.scalar(select(Client).where(Client.id == client_id, Client.owner_user_id == user_id))
    if not client:
        raise AppError(404, "client_not_found", "Client not found.")
    return client


def _get_owned_formula(db: Session, user_id: int, formula_id: int) -> Formula:
    stmt = (
        select(Formula)
        .options(*_formula_load_options())
        .join(Client, Client.id == Formula.client_id)
        .where(Formula.id == formula_id, Client.owner_user_id == user_id)
    )
    formula = db.scalar(stmt)
    if not formula:
        raise AppError(404, "formula_not_found", "Formula not found.")
    return formula


def _serialize_formula_read(formula: Formula) -> FormulaRead:
    return FormulaRead.model_validate(
        _serialize_formula(
            formula,
            include_images=True,
            include_services=True,
            include_notes=True,
            image_limit=None,
        )
    )


def _get_next_service_sort_order(db: Session, user_id: int) -> int:
    max_sort_order = db.scalar(
        select(func.max(Service.sort_order)).where(Service.owner_user_id == user_id)
    )
    return max_sort_order + 1 if max_sort_order is not None else 0


def _resolve_or_create_service(db: Session, user_id: int, raw_name: str) -> Service:
    formatted_name = format_service_name(raw_name)
    normalized_name = normalize_service_key(raw_name)
    if not formatted_name or not normalized_name:
        raise AppError(422, "invalid_service_name", "Service name is required.")

    service = db.scalar(
        select(Service).where(
            Service.owner_user_id == user_id,
            Service.normalized_name == normalized_name,
        )
    )
    if service is not None:
        service.is_active = True
        service.name = formatted_name
        return service

    service = Service(
        owner_user_id=user_id,
        name=formatted_name,
        normalized_name=normalized_name,
        sort_order=_get_next_service_sort_order(db, user_id),
        is_active=True,
    )
    db.add(service)
    db.flush()
    return service


def _replace_formula_services(
    db: Session,
    formula: Formula,
    service_sequence: Sequence[Service],
) -> None:
    if formula.id is not None and formula.formula_services:
        formula.formula_services.clear()
        db.flush()
    else:
        formula.formula_services.clear()
    for position, service in enumerate(service_sequence):
        formula.formula_services.append(
            FormulaService(
                service_id=service.id,
                service_label_snapshot=service.name,
                position=position,
            )
        )
    formula.service_type = service_sequence[0].name if service_sequence else None


def _extract_file_name(public_url: str | None, object_key: str | None) -> str | None:
    for value in (public_url, object_key):
        if not value:
            continue
        trimmed = value.strip()
        if not trimmed:
            continue
        parsed = urlparse(trimmed)
        path = parsed.path if parsed.scheme else trimmed
        file_name = unquote(path.rsplit("/", 1)[-1]).strip()
        if file_name:
            return file_name[:255]
    return None


def _normalize_storage_provider(value: str | None) -> str:
    trimmed = (value or "").strip().lower().replace(" ", "_")
    if not trimmed:
        return "firebase"
    return trimmed[:16]


def _resolve_image_public_url(image: FormulaImage) -> str | None:
    provider = (image.storage_provider or "").strip().lower()
    trimmed_public_url = image.public_url.strip() if image.public_url else None
    if provider != "firebase":
        return trimmed_public_url or None
    if trimmed_public_url:
        return trimmed_public_url

    settings = get_settings()
    default_bucket_name = (settings.firebase_storage_bucket or "").strip() or None
    bucket_name, object_path = _extract_storage_target(trimmed_public_url, image.object_key)

    if not object_path:
        return trimmed_public_url or None

    resolved_bucket = bucket_name or default_bucket_name
    if not resolved_bucket:
        return trimmed_public_url or None

    try:
        if not firebase_admin._apps:
            firebase_admin.initialize_app(options={"storageBucket": resolved_bucket})
        blob = firebase_storage.bucket(resolved_bucket).blob(object_path)
        return blob.generate_signed_url(
            version="v4",
            expiration=timedelta(hours=6),
            method="GET",
        )
    except Exception:
        encoded_key = quote(object_path, safe="")
        return f"https://firebasestorage.googleapis.com/v0/b/{resolved_bucket}/o/{encoded_key}?alt=media"


def _replace_formula_images(formula: Formula, image_payloads: Sequence[FormulaImageWrite]) -> None:
    if formula.id is not None and formula.images:
        formula.images.clear()
    else:
        formula.images.clear()

    seen: set[tuple[str, str | None, str | None]] = set()
    for index, payload in enumerate(image_payloads):
        public_url = payload.public_url.strip() if payload.public_url else None
        object_key = payload.object_key.strip() if payload.object_key else None
        file_name = payload.file_name.strip() if payload.file_name else None
        if not public_url and not object_key:
            continue
        dedupe_key = (payload.storage_provider or "", public_url, object_key)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        formula.images.append(
            FormulaImage(
                storage_provider=_normalize_storage_provider(payload.storage_provider),
                public_url=public_url,
                object_key=object_key,
                file_name=file_name
                or _extract_file_name(public_url, object_key)
                or f"image-{index + 1}.jpg",
            )
        )


def _dedupe_ids_preserve_order(ids: Sequence[int]) -> list[int]:
    seen: set[int] = set()
    ordered: list[int] = []
    for value in ids:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def _apply_service_assignment_by_ids(
    db: Session,
    formula: Formula,
    owner_user_id: int,
    service_ids: Sequence[int] | None,
) -> None:
    ordered_ids = _dedupe_ids_preserve_order(service_ids or [])
    if not ordered_ids:
        _replace_formula_services(db, formula, [])
        return

    services = list(
        db.scalars(
            select(Service).where(
                Service.owner_user_id == owner_user_id,
                Service.id.in_(ordered_ids),
            )
        ).all()
    )
    if len(services) != len(ordered_ids):
        raise AppError(400, "invalid_service_ids", "One or more service IDs are invalid.")

    by_id = {service.id: service for service in services}
    ordered_services = [by_id[service_id] for service_id in ordered_ids]
    _replace_formula_services(db, formula, ordered_services)


def _apply_legacy_service_type(
    db: Session,
    formula: Formula,
    owner_user_id: int,
    service_type: str | None,
) -> None:
    if service_type is None or not service_type.strip():
        _replace_formula_services(db, formula, [])
        return
    service = _resolve_or_create_service(db, owner_user_id, service_type)
    _replace_formula_services(db, formula, [service])


@router.get("/clients/{client_id}/formulas", response_model=FormulaListResponse)
def list_client_formulas(
    client_id: int,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    include: str | None = Query(default=None),
    fields: Literal["full", "lite"] = Query(default="full"),
    image_limit: int | None = Query(default=None, ge=0, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> FormulaListResponse:
    _get_owned_client(db, current_user.id, client_id)
    include_set = _parse_include(include)
    include_images = "images" in include_set
    include_services = "services" in include_set
    include_notes = _resolve_fields(fields) == "full"
    options = []
    if include_images:
        options.append(selectinload(Formula.images))
    if include_services:
        options.append(selectinload(Formula.formula_services).selectinload(FormulaService.service))
    if not include_notes:
        options.append(
            load_only(
                Formula.id,
                Formula.client_id,
                Formula.service_type,
                Formula.price_cents,
                Formula.service_at,
            )
        )
    total = db.scalar(select(func.count(Formula.id)).where(Formula.client_id == client_id)) or 0
    stmt = (
        select(Formula)
        .options(*options)
        .where(Formula.client_id == client_id)
        .order_by(desc(Formula.service_at))
        .offset(offset)
        .limit(limit)
    )
    formulas = list(db.scalars(stmt).all())
    return FormulaListResponse(
        total=total,
        limit=limit,
        offset=offset,
        items=[
            FormulaRead.model_validate(
                _serialize_formula(
                    formula,
                    include_images=include_images,
                    include_services=include_services,
                    include_notes=include_notes,
                    image_limit=image_limit,
                )
            )
            for formula in formulas
        ],
    )


@router.get("/formulas", response_model=FormulaListResponse)
def list_formulas(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    include: str | None = Query(default=None),
    fields: Literal["full", "lite"] = Query(default="full"),
    image_limit: int | None = Query(default=None, ge=0, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> FormulaListResponse:
    include_set = _parse_include(include)
    include_images = "images" in include_set
    include_services = "services" in include_set
    include_notes = _resolve_fields(fields) == "full"
    options = []
    if include_images:
        options.append(selectinload(Formula.images))
    if include_services:
        options.append(selectinload(Formula.formula_services).selectinload(FormulaService.service))
    if not include_notes:
        options.append(
            load_only(
                Formula.id,
                Formula.client_id,
                Formula.service_type,
                Formula.price_cents,
                Formula.service_at,
            )
        )
    filters = Client.owner_user_id == current_user.id
    total = (
        db.scalar(
            select(func.count(Formula.id))
            .join(Client, Client.id == Formula.client_id)
            .where(filters)
        )
        or 0
    )
    stmt = (
        select(Formula)
        .options(*options)
        .join(Client, Client.id == Formula.client_id)
        .where(filters)
        .order_by(desc(Formula.service_at))
        .offset(offset)
        .limit(limit)
    )
    formulas = list(db.scalars(stmt).all())
    return FormulaListResponse(
        total=total,
        limit=limit,
        offset=offset,
        items=[
            FormulaRead.model_validate(
                _serialize_formula(
                    formula,
                    include_images=include_images,
                    include_services=include_services,
                    include_notes=include_notes,
                    image_limit=image_limit,
                )
            )
            for formula in formulas
        ],
    )


@router.post("/clients/{client_id}/formulas", response_model=FormulaRead, status_code=201)
def create_formula(
    client_id: int,
    payload: FormulaCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> FormulaRead:
    client = _get_owned_client(db, current_user.id, client_id)
    formula = Formula(
        client_id=client_id,
        notes=payload.notes,
        price_cents=payload.price_cents,
        service_at=payload.service_at,
    )
    db.add(formula)

    if payload.service_ids is not None:
        _apply_service_assignment_by_ids(db, formula, client.owner_user_id, payload.service_ids)
    else:
        _apply_legacy_service_type(db, formula, client.owner_user_id, payload.service_type)
    if payload.images is not None:
        _replace_formula_images(formula, payload.images)

    db.commit()
    formula = _get_owned_formula(db, current_user.id, formula.id)
    return _serialize_formula_read(formula)


@router.get("/formulas/{formula_id}", response_model=FormulaRead)
def get_formula(
    formula_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> FormulaRead:
    formula = _get_owned_formula(db, current_user.id, formula_id)
    return _serialize_formula_read(formula)


@router.patch("/formulas/{formula_id}", response_model=FormulaRead)
def update_formula(
    formula_id: int,
    payload: FormulaUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> FormulaRead:
    formula = _get_owned_formula(db, current_user.id, formula_id)
    payload_values = payload.model_dump(exclude_unset=True)

    if "notes" in payload_values:
        formula.notes = payload_values["notes"]
    if "price_cents" in payload_values:
        formula.price_cents = payload_values["price_cents"]
    if "service_at" in payload_values:
        formula.service_at = payload_values["service_at"]

    owner_user_id = formula.client.owner_user_id
    if "service_ids" in payload_values:
        _apply_service_assignment_by_ids(
            db, formula, owner_user_id, payload_values.get("service_ids")
        )
    elif "service_type" in payload_values:
        _apply_legacy_service_type(
            db, formula, owner_user_id, payload_values.get("service_type")
        )
    if "images" in payload_values:
        _replace_formula_images(formula, payload.images or [])

    db.commit()
    formula = _get_owned_formula(db, current_user.id, formula.id)
    return _serialize_formula_read(formula)


@router.delete("/formulas/{formula_id}", status_code=204)
def delete_formula(
    formula_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> Response:
    formula = _get_owned_formula(db, current_user.id, formula_id)
    db.delete(formula)
    db.commit()
    return Response(status_code=204)

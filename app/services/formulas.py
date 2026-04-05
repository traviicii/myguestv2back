from collections.abc import Sequence
from dataclasses import dataclass
from datetime import timedelta
from typing import Literal
from urllib.parse import quote, unquote, urlparse

import firebase_admin
from firebase_admin import storage as firebase_storage
from sqlalchemy import func, select
from sqlalchemy.orm import Session, load_only, selectinload

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.service_names import format_service_name, normalize_service_key
from app.models import Formula, FormulaImage, FormulaService, Service
from app.schemas.formula import FormulaImageWrite


@dataclass(frozen=True)
class FormulaListShape:
    include_images: bool
    include_services: bool
    include_notes: bool
    options: tuple[object, ...]


def formula_load_options() -> tuple[object, ...]:
    return (
        selectinload(Formula.images),
        selectinload(Formula.formula_services).selectinload(FormulaService.service),
    )


def build_formula_list_shape(
    include: str | None,
    fields: Literal["full", "lite"],
) -> FormulaListShape:
    include_set = _parse_include(include)
    include_images = "images" in include_set
    include_services = "services" in include_set
    include_notes = fields == "full"
    options: list[object] = []
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
    return FormulaListShape(
        include_images=include_images,
        include_services=include_services,
        include_notes=include_notes,
        options=tuple(options),
    )


def serialize_formula(
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


def apply_service_assignment_by_ids(
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


def apply_legacy_service_type(
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


def replace_formula_images(formula: Formula, image_payloads: Sequence[FormulaImageWrite]) -> None:
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


def _parse_include(value: str | None) -> set[str]:
    if value is None:
        return {"images", "services"}
    parts = [part.strip().lower() for part in value.split(",")]
    return {part for part in parts if part in {"images", "services"}}


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
    if image.public_url:
        trimmed = image.public_url.strip()
        if trimmed:
            return trimmed

    provider = (image.storage_provider or "").strip().lower()
    object_key = (image.object_key or "").strip().lstrip("/")
    if provider != "firebase" or not object_key:
        return None

    settings = get_settings()
    bucket_name = (settings.firebase_storage_bucket or "").strip()
    if not bucket_name:
        return None

    try:
        if not firebase_admin._apps:
            firebase_admin.initialize_app(options={"storageBucket": bucket_name})
        blob = firebase_storage.bucket(bucket_name).blob(object_key)
        return blob.generate_signed_url(
            version="v4",
            expiration=timedelta(hours=6),
            method="GET",
        )
    except Exception:
        encoded_key = quote(object_key, safe="")
        return f"https://firebasestorage.googleapis.com/v0/b/{bucket_name}/o/{encoded_key}?alt=media"


def _dedupe_ids_preserve_order(ids: Sequence[int]) -> list[int]:
    seen: set[int] = set()
    ordered: list[int] = []
    for value in ids:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered

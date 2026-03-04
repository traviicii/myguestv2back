from typing import Literal

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_session
from app.core.errors import AppError
from app.core.service_names import format_service_name, normalize_service_key
from app.models import FormulaService, Service, User
from app.schemas.service import ServiceCreate, ServiceListResponse, ServiceRead, ServiceUpdate

router = APIRouter(prefix="/services", tags=["services"])


def _get_owned_service(db: Session, user_id: int, service_id: int) -> Service:
    service = db.scalar(
        select(Service).where(Service.id == service_id, Service.owner_user_id == user_id)
    )
    if not service:
        raise AppError(404, "service_not_found", "Service not found.")
    return service


def _get_next_sort_order(db: Session, user_id: int) -> int:
    max_order = db.scalar(
        select(func.max(Service.sort_order)).where(Service.owner_user_id == user_id)
    )
    return (max_order or 0) + 1


def _get_service_usage_count(db: Session, service_id: int) -> int:
    return (
        db.scalar(
            select(func.count(FormulaService.id)).where(FormulaService.service_id == service_id)
        )
        or 0
    )


@router.get("", response_model=ServiceListResponse)
def list_services(
    active: Literal["true", "false", "all"] = Query(default="true"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> ServiceListResponse:
    stmt = (
        select(Service, func.count(FormulaService.id).label("usage_count"))
        .outerjoin(FormulaService, FormulaService.service_id == Service.id)
        .where(Service.owner_user_id == current_user.id)
        .group_by(Service.id)
    )
    if active == "true":
        stmt = stmt.where(Service.is_active.is_(True))
    elif active == "false":
        stmt = stmt.where(Service.is_active.is_(False))

    rows = list(
        db.execute(stmt.order_by(Service.sort_order.asc(), Service.name.asc())).all()
    )
    items: list[ServiceRead] = []
    for service, usage_count in rows:
        setattr(service, "usage_count", int(usage_count or 0))
        items.append(ServiceRead.model_validate(service))
    return ServiceListResponse(items=items)


@router.post("", response_model=ServiceRead, status_code=201)
def create_service(
    payload: ServiceCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> ServiceRead:
    name = format_service_name(payload.name)
    normalized_name = normalize_service_key(payload.name)
    if not name or not normalized_name:
        raise AppError(422, "invalid_service_name", "Service name is required.")

    existing = db.scalar(
        select(Service).where(
            Service.owner_user_id == current_user.id,
            Service.normalized_name == normalized_name,
        )
    )
    if existing:
        raise AppError(409, "service_name_exists", "A service with this name already exists.")

    service = Service(
        owner_user_id=current_user.id,
        name=name,
        normalized_name=normalized_name,
        sort_order=payload.sort_order
        if payload.sort_order is not None
        else _get_next_sort_order(db, current_user.id),
        default_price_cents=payload.default_price_cents,
        is_active=True,
    )
    db.add(service)
    db.commit()
    db.refresh(service)
    setattr(service, "usage_count", 0)
    return ServiceRead.model_validate(service)


@router.patch("/{service_id}", response_model=ServiceRead)
def update_service(
    service_id: int,
    payload: ServiceUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> ServiceRead:
    service = _get_owned_service(db, current_user.id, service_id)
    payload_values = payload.model_dump(exclude_unset=True)

    if payload.name is not None:
        name = format_service_name(payload.name)
        normalized_name = normalize_service_key(payload.name)
        if not name or not normalized_name:
            raise AppError(422, "invalid_service_name", "Service name is required.")

        conflicting = db.scalar(
            select(Service).where(
                Service.owner_user_id == current_user.id,
                Service.normalized_name == normalized_name,
                Service.id != service.id,
            )
        )
        if conflicting:
            raise AppError(409, "service_name_exists", "A service with this name already exists.")

        service.name = name
        service.normalized_name = normalized_name

    if payload.sort_order is not None:
        service.sort_order = payload.sort_order

    if "default_price_cents" in payload_values:
        service.default_price_cents = payload_values.get("default_price_cents")

    if payload.is_active is not None:
        service.is_active = payload.is_active

    db.commit()
    db.refresh(service)
    setattr(service, "usage_count", _get_service_usage_count(db, service.id))
    return ServiceRead.model_validate(service)


@router.delete("/{service_id}", status_code=204)
def delete_service(
    service_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> Response:
    service = _get_owned_service(db, current_user.id, service_id)
    service.is_active = False
    db.commit()
    return Response(status_code=204)


@router.delete("/{service_id}/permanent", status_code=204)
def permanently_delete_service(
    service_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> Response:
    service = _get_owned_service(db, current_user.id, service_id)
    usage_count = _get_service_usage_count(db, service.id)
    if usage_count > 0:
        raise AppError(
            409,
            "service_in_use",
            "Service is used in appointment logs and cannot be permanently deleted.",
        )
    db.delete(service)
    db.commit()
    return Response(status_code=204)

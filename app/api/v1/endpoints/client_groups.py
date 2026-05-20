from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_session
from app.core.errors import AppError
from app.core.service_names import format_service_name, normalize_service_key
from app.models import ClientGroup, ClientGroupMembership, User
from app.schemas.client_group import (
    ClientGroupCreate,
    ClientGroupListResponse,
    ClientGroupRead,
    ClientGroupUpdate,
)

router = APIRouter(prefix="/client-groups", tags=["client-groups"])


def _format_group_name(value: str) -> str:
    return format_service_name(value)


def _normalize_group_key(value: str) -> str:
    return normalize_service_key(value)


def _get_owned_group(db: Session, user_id: int, group_id: int) -> ClientGroup:
    group = db.scalar(
        select(ClientGroup).where(
            ClientGroup.id == group_id,
            ClientGroup.owner_user_id == user_id,
        )
    )
    if not group:
        raise AppError(404, "client_group_not_found", "Client group not found.")
    return group


def _get_next_sort_order(db: Session, user_id: int) -> int:
    max_order = db.scalar(
        select(func.max(ClientGroup.sort_order)).where(ClientGroup.owner_user_id == user_id)
    )
    return (max_order or 0) + 1


def _get_group_client_count(db: Session, group_id: int) -> int:
    return (
        db.scalar(
            select(func.count(ClientGroupMembership.client_id)).where(
                ClientGroupMembership.group_id == group_id
            )
        )
        or 0
    )


@router.get("", response_model=ClientGroupListResponse)
def list_client_groups(
    active: Literal["true", "false", "all"] = Query(default="true"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> ClientGroupListResponse:
    stmt = (
        select(ClientGroup, func.count(ClientGroupMembership.client_id).label("client_count"))
        .outerjoin(ClientGroupMembership, ClientGroupMembership.group_id == ClientGroup.id)
        .where(ClientGroup.owner_user_id == current_user.id)
        .group_by(ClientGroup.id)
    )
    if active == "true":
        stmt = stmt.where(ClientGroup.archived_at.is_(None))
    elif active == "false":
        stmt = stmt.where(ClientGroup.archived_at.is_not(None))

    rows = list(
        db.execute(stmt.order_by(ClientGroup.sort_order.asc(), ClientGroup.name.asc())).all()
    )
    items: list[ClientGroupRead] = []
    for group, client_count in rows:
        group.client_count = int(client_count or 0)
        items.append(ClientGroupRead.model_validate(group))
    return ClientGroupListResponse(items=items)


@router.post("", response_model=ClientGroupRead, status_code=201)
def create_client_group(
    payload: ClientGroupCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> ClientGroupRead:
    name = _format_group_name(payload.name)
    normalized_name = _normalize_group_key(payload.name)
    if not name or not normalized_name:
        raise AppError(422, "invalid_client_group_name", "Client group name is required.")

    existing = db.scalar(
        select(ClientGroup).where(
            ClientGroup.owner_user_id == current_user.id,
            ClientGroup.normalized_name == normalized_name,
        )
    )
    if existing and existing.archived_at is None:
        raise AppError(
            409,
            "client_group_name_exists",
            "A client group with this name already exists.",
        )
    if existing and existing.archived_at is not None:
        existing.name = name
        if payload.sort_order is not None:
            existing.sort_order = payload.sort_order
        existing.archived_at = None
        db.commit()
        db.refresh(existing)
        existing.client_count = _get_group_client_count(db, existing.id)
        return ClientGroupRead.model_validate(existing)

    group = ClientGroup(
        owner_user_id=current_user.id,
        name=name,
        normalized_name=normalized_name,
        sort_order=payload.sort_order
        if payload.sort_order is not None
        else _get_next_sort_order(db, current_user.id),
        archived_at=None,
    )
    db.add(group)
    db.commit()
    db.refresh(group)
    group.client_count = 0
    return ClientGroupRead.model_validate(group)


@router.patch("/{group_id}", response_model=ClientGroupRead)
def update_client_group(
    group_id: int,
    payload: ClientGroupUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> ClientGroupRead:
    group = _get_owned_group(db, current_user.id, group_id)
    payload_values = payload.model_dump(exclude_unset=True)

    if payload.name is not None:
        name = _format_group_name(payload.name)
        normalized_name = _normalize_group_key(payload.name)
        if not name or not normalized_name:
            raise AppError(422, "invalid_client_group_name", "Client group name is required.")

        conflicting = db.scalar(
            select(ClientGroup).where(
                ClientGroup.owner_user_id == current_user.id,
                ClientGroup.normalized_name == normalized_name,
                ClientGroup.id != group.id,
            )
        )
        if conflicting:
            raise AppError(
                409,
                "client_group_name_exists",
                "A client group with this name already exists.",
            )

        group.name = name
        group.normalized_name = normalized_name

    if payload.sort_order is not None:
        group.sort_order = payload.sort_order

    if "archived" in payload_values:
        group.archived_at = datetime.now(UTC) if payload.archived else None

    db.commit()
    db.refresh(group)
    group.client_count = _get_group_client_count(db, group.id)
    return ClientGroupRead.model_validate(group)


@router.delete("/{group_id}", status_code=204)
def archive_client_group(
    group_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> Response:
    group = _get_owned_group(db, current_user.id, group_id)
    group.archived_at = datetime.now(UTC)
    db.commit()
    return Response(status_code=204)

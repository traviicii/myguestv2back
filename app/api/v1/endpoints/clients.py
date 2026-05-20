# Client CRUD endpoints with pagination and sorting.
# We validate sort/order inputs so the API fails loudly on invalid values.
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import asc, desc, func, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, get_session
from app.core.errors import AppError
from app.core.service_names import format_service_name, normalize_service_key
from app.models import Client, ClientGroup, ClientGroupMembership, User
from app.schemas.client import ClientCreate, ClientListResponse, ClientRead, ClientUpdate

router = APIRouter(prefix="/clients", tags=["clients"])

CLIENT_SORT_MAP = {
    "created_at": Client.created_at,
    "first_name": Client.first_name,
    "last_name": Client.last_name,
}

LEGACY_TYPE_GROUPS = {
    "cut": ["Cut"],
    "color": ["Color"],
    "cut & color": ["Cut", "Color"],
}


def _get_owned_client(db: Session, user_id: int, client_id: int) -> Client:
    # Shared guard: every client access must be scoped to the authenticated user.
    stmt = (
        select(Client)
        .where(Client.id == client_id, Client.owner_user_id == user_id)
        .options(selectinload(Client.groups))
    )
    client = db.scalar(stmt)
    if not client:
        raise AppError(404, "client_not_found", "Client not found.")
    return client


def _legacy_group_names(client_type: str | None) -> list[str]:
    normalized = (client_type or "").strip().lower()
    if not normalized:
        return []
    if normalized in LEGACY_TYPE_GROUPS:
        return LEGACY_TYPE_GROUPS[normalized]
    formatted = format_service_name(client_type or "")
    return [formatted] if formatted else []


def _get_next_group_sort_order(db: Session, user_id: int) -> int:
    max_order = db.scalar(
        select(func.max(ClientGroup.sort_order)).where(ClientGroup.owner_user_id == user_id)
    )
    return (max_order or 0) + 1


def _ensure_group_by_name(db: Session, user_id: int, name: str) -> ClientGroup:
    formatted_name = format_service_name(name)
    normalized_name = normalize_service_key(name)
    group = db.scalar(
        select(ClientGroup).where(
            ClientGroup.owner_user_id == user_id,
            ClientGroup.normalized_name == normalized_name,
        )
    )
    if group:
        if group.archived_at is not None:
            group.archived_at = None
        return group

    group = ClientGroup(
        owner_user_id=user_id,
        name=formatted_name,
        normalized_name=normalized_name,
        sort_order=_get_next_group_sort_order(db, user_id),
    )
    db.add(group)
    db.flush()
    return group


def _get_owned_groups(db: Session, user_id: int, group_ids: list[int]) -> list[ClientGroup]:
    unique_ids = list(dict.fromkeys(group_ids))
    if not unique_ids:
        return []
    groups = list(
        db.scalars(
            select(ClientGroup)
            .where(
                ClientGroup.owner_user_id == user_id,
                ClientGroup.id.in_(unique_ids),
                ClientGroup.archived_at.is_(None),
            )
            .order_by(ClientGroup.sort_order.asc(), ClientGroup.name.asc())
        ).all()
    )
    if len(groups) != len(unique_ids):
        raise AppError(422, "invalid_client_groups", "One or more client groups are invalid.")
    group_by_id = {group.id: group for group in groups}
    return [group_by_id[group_id] for group_id in unique_ids]


def _replace_client_groups(client: Client, groups: list[ClientGroup]) -> None:
    client.group_memberships = [
        ClientGroupMembership(group_id=group.id)
        for group in groups
    ]


def _resolve_client_groups(
    db: Session,
    user_id: int,
    group_ids: list[int] | None,
    legacy_client_type: str | None,
) -> list[ClientGroup] | None:
    if group_ids is not None:
        return _get_owned_groups(db, user_id, group_ids)

    legacy_group_names = _legacy_group_names(legacy_client_type)
    if legacy_group_names:
        return [_ensure_group_by_name(db, user_id, name) for name in legacy_group_names]

    return None


@router.get("", response_model=ClientListResponse)
def list_clients(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    sort: str = Query(default="created_at"),
    order: str = Query(default="desc"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> ClientListResponse:
    # Reject unknown sort fields and order directions so callers get a clear error
    # instead of silently falling back to an unintended default.
    if sort not in CLIENT_SORT_MAP:
        raise AppError(400, "invalid_sort", f"Unsupported sort field: {sort}")
    if order not in {"asc", "desc"}:
        raise AppError(400, "invalid_order", f"Unsupported order direction: {order}")

    sort_column = CLIENT_SORT_MAP[sort]
    ordering = asc(sort_column) if order == "asc" else desc(sort_column)

    # Compute total separately so clients can render pagination UI without
    # a second round-trip.
    total = (
        db.scalar(select(func.count(Client.id)).where(Client.owner_user_id == current_user.id))
        or 0
    )
    stmt = (
        select(Client)
        .where(Client.owner_user_id == current_user.id)
        .options(selectinload(Client.groups))
        .order_by(ordering)
        .offset(offset)
        .limit(limit)
    )
    clients = list(db.scalars(stmt).all())

    return ClientListResponse(
        total=total,
        limit=limit,
        offset=offset,
        items=[ClientRead.model_validate(client) for client in clients],
    )


@router.post("", response_model=ClientRead, status_code=201)
def create_client(
    payload: ClientCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> ClientRead:
    # Keep client creation lean: only create a color chart if/when the user explicitly adds one.
    payload_values = payload.model_dump(exclude={"group_ids"})
    groups = _resolve_client_groups(
        db,
        current_user.id,
        payload.group_ids,
        payload.client_type,
    )
    client = Client(owner_user_id=current_user.id, **payload_values)
    if groups is not None:
        _replace_client_groups(client, groups)
    db.add(client)
    db.commit()
    db.refresh(client)
    return ClientRead.model_validate(client)


@router.get("/{client_id}", response_model=ClientRead)
def get_client(
    client_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> ClientRead:
    client = _get_owned_client(db, current_user.id, client_id)
    return ClientRead.model_validate(client)


@router.patch("/{client_id}", response_model=ClientRead)
def update_client(
    client_id: int,
    payload: ClientUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> ClientRead:
    client = _get_owned_client(db, current_user.id, client_id)
    payload_values = payload.model_dump(exclude_unset=True, exclude={"group_ids"})
    for field, value in payload_values.items():
        setattr(client, field, value)
    if "group_ids" in payload.model_fields_set:
        groups = _resolve_client_groups(
            db,
            current_user.id,
            payload.group_ids,
            None,
        )
        _replace_client_groups(client, groups or [])
    elif "client_type" in payload_values:
        groups = _resolve_client_groups(
            db,
            current_user.id,
            None,
            payload.client_type,
        )
        if groups is not None:
            _replace_client_groups(client, groups)
    db.commit()
    db.refresh(client)
    return ClientRead.model_validate(client)


@router.delete("/{client_id}", status_code=204)
def delete_client(
    client_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> Response:
    client = _get_owned_client(db, current_user.id, client_id)
    db.delete(client)
    db.commit()
    return Response(status_code=204)

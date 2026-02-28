from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import asc, desc, func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_session
from app.core.errors import AppError
from app.models import Client, User
from app.schemas.client import ClientCreate, ClientListResponse, ClientRead, ClientUpdate

router = APIRouter(prefix="/clients", tags=["clients"])

CLIENT_SORT_MAP = {
    "created_at": Client.created_at,
    "first_name": Client.first_name,
    "last_name": Client.last_name,
}


def _get_owned_client(db: Session, user_id: int, client_id: int) -> Client:
    stmt = select(Client).where(Client.id == client_id, Client.owner_user_id == user_id)
    client = db.scalar(stmt)
    if not client:
        raise AppError(404, "client_not_found", "Client not found.")
    return client


@router.get("", response_model=ClientListResponse)
def list_clients(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    sort: str = Query(default="created_at"),
    order: str = Query(default="desc"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> ClientListResponse:
    if sort not in CLIENT_SORT_MAP:
        raise AppError(400, "invalid_sort", f"Unsupported sort field: {sort}")

    sort_column = CLIENT_SORT_MAP[sort]
    ordering = asc(sort_column) if order == "asc" else desc(sort_column)

    total = db.scalar(select(func.count(Client.id)).where(Client.owner_user_id == current_user.id)) or 0
    stmt = (
        select(Client)
        .where(Client.owner_user_id == current_user.id)
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
    client = Client(owner_user_id=current_user.id, **payload.model_dump())
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
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(client, field, value)
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

from datetime import date, datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class ClientCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=64)
    last_name: str = Field(min_length=1, max_length=64)
    email: str | None = None
    phone: str | None = None
    birthday: date | None = None
    client_type: str | None = None
    notes: str | None = None


class ClientUpdate(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=64)
    last_name: str | None = Field(default=None, min_length=1, max_length=64)
    email: str | None = None
    phone: str | None = None
    birthday: date | None = None
    client_type: str | None = None
    notes: str | None = None


class ClientRead(ORMModel):
    id: int
    owner_user_id: int
    first_name: str
    last_name: str
    created_at: datetime
    updated_at: datetime
    email: str | None = None
    phone: str | None = None
    birthday: date | None = None
    client_type: str | None = None
    notes: str | None = None


class ClientListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[ClientRead]

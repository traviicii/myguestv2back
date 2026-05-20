from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class ClientGroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=96)
    sort_order: int | None = None


class ClientGroupUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=96)
    sort_order: int | None = None
    archived: bool | None = None


class ClientGroupRead(ORMModel):
    id: int
    owner_user_id: int
    name: str
    normalized_name: str
    sort_order: int
    archived_at: datetime | None = None
    client_count: int = 0
    created_at: datetime
    updated_at: datetime


class ClientGroupListResponse(BaseModel):
    items: list[ClientGroupRead]

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class ServiceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=96)
    sort_order: int | None = None


class ServiceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=96)
    sort_order: int | None = None
    is_active: bool | None = None


class ServiceRead(ORMModel):
    id: int
    owner_user_id: int
    name: str
    normalized_name: str
    sort_order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ServiceListResponse(BaseModel):
    items: list[ServiceRead]

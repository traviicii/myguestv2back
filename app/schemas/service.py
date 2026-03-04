from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class ServiceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=96)
    sort_order: int | None = None
    default_price_cents: int | None = Field(default=None, ge=0)


class ServiceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=96)
    sort_order: int | None = None
    default_price_cents: int | None = Field(default=None, ge=0)
    is_active: bool | None = None


class ServiceRead(ORMModel):
    id: int
    owner_user_id: int
    name: str
    normalized_name: str
    sort_order: int
    default_price_cents: int | None
    is_active: bool
    usage_count: int
    created_at: datetime
    updated_at: datetime


class ServiceListResponse(BaseModel):
    items: list[ServiceRead]

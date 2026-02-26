from datetime import datetime

from pydantic import BaseModel

from app.schemas.common import ORMModel


class FormulaCreate(BaseModel):
    service_type: str | None = None
    notes: str | None = None
    price_cents: int | None = None
    service_at: datetime


class FormulaUpdate(BaseModel):
    service_type: str | None = None
    notes: str | None = None
    price_cents: int | None = None
    service_at: datetime | None = None


class FormulaImageRead(ORMModel):
    id: int
    formula_id: int
    storage_provider: str
    public_url: str | None = None
    object_key: str | None = None
    file_name: str


class FormulaRead(ORMModel):
    id: int
    client_id: int
    service_type: str | None = None
    notes: str | None = None
    price_cents: int | None = None
    service_at: datetime
    images: list[FormulaImageRead] = []


class FormulaListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[FormulaRead]

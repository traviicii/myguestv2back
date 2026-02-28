from datetime import datetime

from pydantic import BaseModel, model_validator

from app.schemas.common import ORMModel


class FormulaImageWrite(BaseModel):
    storage_provider: str | None = None
    public_url: str | None = None
    object_key: str | None = None
    file_name: str | None = None

    @model_validator(mode="after")
    def validate_reference(self):
        if not (self.public_url and self.public_url.strip()) and not (
            self.object_key and self.object_key.strip()
        ):
            raise ValueError("Each image must include public_url or object_key.")
        return self


class FormulaCreate(BaseModel):
    service_type: str | None = None
    service_ids: list[int] | None = None
    notes: str | None = None
    price_cents: int | None = None
    service_at: datetime
    images: list[FormulaImageWrite] | None = None


class FormulaUpdate(BaseModel):
    service_type: str | None = None
    service_ids: list[int] | None = None
    notes: str | None = None
    price_cents: int | None = None
    service_at: datetime | None = None
    images: list[FormulaImageWrite] | None = None


class FormulaImageRead(ORMModel):
    id: int
    formula_id: int
    storage_provider: str
    public_url: str | None = None
    object_key: str | None = None
    file_name: str


class FormulaServiceRead(ORMModel):
    service_id: int
    name: str
    position: int
    label_snapshot: str


class FormulaRead(ORMModel):
    id: int
    client_id: int
    service_type: str | None = None
    notes: str | None = None
    price_cents: int | None = None
    service_at: datetime
    images: list[FormulaImageRead] = []
    services: list[FormulaServiceRead] = []


class FormulaListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[FormulaRead]

from datetime import datetime

from pydantic import BaseModel

from app.schemas.common import ORMModel


class ColorChartRead(ORMModel):
    id: int
    client_id: int
    created_at: datetime
    updated_at: datetime
    porosity: str | None = None
    hair_texture: str | None = None
    elasticity: str | None = None
    scalp_condition: str | None = None
    natural_level: str | None = None
    desired_level: str | None = None
    contrib_pigment: str | None = None
    gray_front: str | None = None
    gray_sides: str | None = None
    gray_back: str | None = None
    skin_depth: str | None = None
    skin_tone: str | None = None
    eye_color: str | None = None


class ColorChartListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[ColorChartRead]

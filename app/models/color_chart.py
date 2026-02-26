from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin


class ColorChart(Base, TimestampMixin):
    __tablename__ = "color_charts"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(
        ForeignKey("clients.id", ondelete="CASCADE"), unique=True, index=True
    )

    porosity: Mapped[str | None] = mapped_column(String(25), nullable=True)
    hair_texture: Mapped[str | None] = mapped_column(String(25), nullable=True)
    elasticity: Mapped[str | None] = mapped_column(String(25), nullable=True)
    scalp_condition: Mapped[str | None] = mapped_column(String(25), nullable=True)
    natural_level: Mapped[str | None] = mapped_column(String(50), nullable=True)
    desired_level: Mapped[str | None] = mapped_column(String(50), nullable=True)
    contrib_pigment: Mapped[str | None] = mapped_column(String(25), nullable=True)
    gray_front: Mapped[str | None] = mapped_column(String(8), nullable=True)
    gray_sides: Mapped[str | None] = mapped_column(String(8), nullable=True)
    gray_back: Mapped[str | None] = mapped_column(String(8), nullable=True)
    skin_depth: Mapped[str | None] = mapped_column(String(25), nullable=True)
    skin_tone: Mapped[str | None] = mapped_column(String(25), nullable=True)
    eye_color: Mapped[str | None] = mapped_column(String(25), nullable=True)

    client = relationship("Client", back_populates="color_chart")

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin


class Formula(Base, TimestampMixin):
    __tablename__ = "formulas"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), index=True)

    service_type: Mapped[str | None] = mapped_column(String(96), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    price_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    service_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    client = relationship("Client", back_populates="formulas")
    images = relationship("FormulaImage", back_populates="formula", cascade="all, delete-orphan")
    formula_services = relationship(
        "FormulaService",
        back_populates="formula",
        cascade="all, delete-orphan",
        order_by="FormulaService.position",
    )

    @property
    def services(self):
        return self.formula_services

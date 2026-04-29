from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin


class FormulaService(Base, TimestampMixin):
    __tablename__ = "formula_services"
    __table_args__ = (
        UniqueConstraint("formula_id", "service_id", name="uq_formula_services_formula_service"),
        UniqueConstraint("formula_id", "position", name="uq_formula_services_formula_position"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    formula_id: Mapped[int] = mapped_column(
        ForeignKey("formulas.id", ondelete="CASCADE"),
        index=True,
    )
    service_id: Mapped[int] = mapped_column(ForeignKey("services.id"), index=True)
    service_label_snapshot: Mapped[str] = mapped_column(String(96))
    position: Mapped[int] = mapped_column(Integer, default=0)

    formula = relationship("Formula", back_populates="formula_services")
    service = relationship("Service", back_populates="formula_links")

    @property
    def label_snapshot(self) -> str:
        return self.service_label_snapshot

    @property
    def name(self) -> str:
        if self.service is not None:
            return self.service.name
        return self.service_label_snapshot

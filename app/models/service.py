from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin


class Service(Base, TimestampMixin):
    __tablename__ = "services"
    __table_args__ = (UniqueConstraint("owner_user_id", "normalized_name", name="uq_services_owner_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(96))
    normalized_name: Mapped[str] = mapped_column(String(96))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    owner = relationship("User", back_populates="services")
    formula_links = relationship("FormulaService", back_populates="service")

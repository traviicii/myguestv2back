from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin


class FormulaImage(Base, TimestampMixin):
    __tablename__ = "formula_images"

    id: Mapped[int] = mapped_column(primary_key=True)
    formula_id: Mapped[int] = mapped_column(
        ForeignKey("formulas.id", ondelete="CASCADE"),
        index=True,
    )

    storage_provider: Mapped[str] = mapped_column(String(16), default="firebase")
    public_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    object_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    file_name: Mapped[str] = mapped_column(String(255))

    formula = relationship("Formula", back_populates="images")

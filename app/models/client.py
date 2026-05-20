from datetime import date

from sqlalchemy import Date, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin


class Client(Base, TimestampMixin):
    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )

    first_name: Mapped[str] = mapped_column(String(64))
    last_name: Mapped[str] = mapped_column(String(64))
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    birthday: Mapped[date | None] = mapped_column(Date, nullable=True)
    client_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    owner = relationship("User", back_populates="clients")
    group_memberships = relationship(
        "ClientGroupMembership",
        back_populates="client",
        cascade="all, delete-orphan",
    )
    groups = relationship(
        "ClientGroup",
        secondary="client_group_memberships",
        back_populates="clients",
        order_by="ClientGroup.sort_order",
        viewonly=True,
    )
    color_chart = relationship(
        "ColorChart", back_populates="client", uselist=False, cascade="all, delete-orphan"
    )
    formulas = relationship("Formula", back_populates="client", cascade="all, delete-orphan")

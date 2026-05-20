from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin


class ClientGroup(Base, TimestampMixin):
    __tablename__ = "client_groups"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "normalized_name", name="uq_client_groups_owner_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    name: Mapped[str] = mapped_column(String(96))
    normalized_name: Mapped[str] = mapped_column(String(96))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    owner = relationship("User", back_populates="client_groups")
    memberships = relationship(
        "ClientGroupMembership",
        back_populates="group",
        cascade="all, delete-orphan",
    )
    clients = relationship(
        "Client",
        secondary="client_group_memberships",
        back_populates="groups",
        viewonly=True,
    )


class ClientGroupMembership(Base):
    __tablename__ = "client_group_memberships"

    client_id: Mapped[int] = mapped_column(
        ForeignKey("clients.id", ondelete="CASCADE"),
        primary_key=True,
    )
    group_id: Mapped[int] = mapped_column(
        ForeignKey("client_groups.id", ondelete="CASCADE"),
        primary_key=True,
    )

    client = relationship("Client", back_populates="group_memberships")
    group = relationship("ClientGroup", back_populates="memberships")

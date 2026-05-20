"""add client groups

Revision ID: 0006_client_groups
Revises: 0005_service_return_weeks
Create Date: 2026-05-20

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0006_client_groups"
down_revision = "0005_service_return_weeks"
branch_labels = None
depends_on = None


LEGACY_TYPE_GROUPS = {
    "cut": ["Cut"],
    "color": ["Color"],
    "cut & color": ["Cut", "Color"],
}


def _legacy_group_names(value: str | None) -> list[str]:
    normalized = (value or "").strip().lower()
    if not normalized:
        return []
    if normalized in LEGACY_TYPE_GROUPS:
        return LEGACY_TYPE_GROUPS[normalized]
    return [" ".join(part.capitalize() for part in normalized.split())]


def _ensure_group(connection, owner_user_id: int, name: str) -> int:
    normalized_name = name.strip().lower()
    existing = connection.execute(
        sa.text(
            """
            SELECT id FROM client_groups
            WHERE owner_user_id = :owner_user_id
              AND normalized_name = :normalized_name
            """
        ),
        {"owner_user_id": owner_user_id, "normalized_name": normalized_name},
    ).scalar()
    if existing is not None:
        return int(existing)

    max_sort_order = connection.execute(
        sa.text(
            """
            SELECT COALESCE(MAX(sort_order), -1) FROM client_groups
            WHERE owner_user_id = :owner_user_id
            """
        ),
        {"owner_user_id": owner_user_id},
    ).scalar()
    sort_order = int(max_sort_order or -1) + 1
    connection.execute(
        sa.text(
            """
            INSERT INTO client_groups (owner_user_id, name, normalized_name, sort_order)
            VALUES (:owner_user_id, :name, :normalized_name, :sort_order)
            """
        ),
        {
            "owner_user_id": owner_user_id,
            "name": name,
            "normalized_name": normalized_name,
            "sort_order": sort_order,
        },
    )
    group_id = connection.execute(
        sa.text(
            """
            SELECT id FROM client_groups
            WHERE owner_user_id = :owner_user_id
              AND normalized_name = :normalized_name
            """
        ),
        {"owner_user_id": owner_user_id, "normalized_name": normalized_name},
    ).scalar()
    return int(group_id)


def upgrade() -> None:
    op.create_table(
        "client_groups",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=96), nullable=False),
        sa.Column("normalized_name", sa.String(length=96), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id", "normalized_name", name="uq_client_groups_owner_name"),
    )
    op.create_index(
        "ix_client_groups_owner_user_id",
        "client_groups",
        ["owner_user_id"],
        unique=False,
    )

    op.create_table(
        "client_group_memberships",
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["group_id"], ["client_groups.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("client_id", "group_id"),
    )
    op.create_index(
        "ix_client_group_memberships_group_id",
        "client_group_memberships",
        ["group_id"],
        unique=False,
    )

    connection = op.get_bind()
    clients = connection.execute(
        sa.text("SELECT id, owner_user_id, client_type FROM clients WHERE client_type IS NOT NULL")
    ).mappings()
    for client in clients:
        for name in _legacy_group_names(client["client_type"]):
            group_id = _ensure_group(connection, int(client["owner_user_id"]), name)
            connection.execute(
                sa.text(
                    """
                    INSERT INTO client_group_memberships (client_id, group_id)
                    VALUES (:client_id, :group_id)
                    """
                ),
                {"client_id": int(client["id"]), "group_id": group_id},
            )


def downgrade() -> None:
    op.drop_index("ix_client_group_memberships_group_id", table_name="client_group_memberships")
    op.drop_table("client_group_memberships")
    op.drop_index("ix_client_groups_owner_user_id", table_name="client_groups")
    op.drop_table("client_groups")

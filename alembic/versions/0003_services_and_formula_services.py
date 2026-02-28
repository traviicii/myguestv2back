"""add services catalog and formula service links

Revision ID: 0003_services_and_formula_services
Revises: 0002_backfill_v2_from_legacy
Create Date: 2026-02-27

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0003_services_and_formula_services"
down_revision = "0002_backfill_v2_from_legacy"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "formulas",
        "service_type",
        existing_type=sa.String(length=32),
        type_=sa.String(length=96),
        existing_nullable=True,
    )

    op.create_table(
        "services",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=96), nullable=False),
        sa.Column("normalized_name", sa.String(length=96), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id", "normalized_name", name="uq_services_owner_name"),
    )
    op.create_index("ix_services_owner_user_id", "services", ["owner_user_id"], unique=False)
    op.create_index("ix_services_is_active", "services", ["is_active"], unique=False)

    op.create_table(
        "formula_services",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("formula_id", sa.Integer(), nullable=False),
        sa.Column("service_id", sa.Integer(), nullable=False),
        sa.Column("service_label_snapshot", sa.String(length=96), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["formula_id"], ["formulas.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["service_id"], ["services.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("formula_id", "position", name="uq_formula_services_formula_position"),
        sa.UniqueConstraint("formula_id", "service_id", name="uq_formula_services_formula_service"),
    )
    op.create_index("ix_formula_services_formula_id", "formula_services", ["formula_id"], unique=False)
    op.create_index("ix_formula_services_service_id", "formula_services", ["service_id"], unique=False)

    # Build account-level service catalog from existing formula service_type values.
    op.execute(
        """
        WITH distinct_services AS (
            SELECT DISTINCT
                c.owner_user_id,
                trim(regexp_replace(f.service_type, '\s+', ' ', 'g')) AS raw_name
            FROM formulas f
            JOIN clients c ON c.id = f.client_id
            WHERE f.service_type IS NOT NULL
              AND trim(f.service_type) <> ''
        ),
        normalized AS (
            SELECT
                owner_user_id,
                initcap(lower(raw_name)) AS name,
                lower(raw_name) AS normalized_name
            FROM distinct_services
        ),
        ranked AS (
            SELECT
                owner_user_id,
                name,
                normalized_name,
                row_number() OVER (PARTITION BY owner_user_id ORDER BY normalized_name) - 1 AS sort_order
            FROM normalized
        )
        INSERT INTO services (
            owner_user_id,
            name,
            normalized_name,
            sort_order,
            is_active,
            created_at,
            updated_at
        )
        SELECT
            owner_user_id,
            name,
            normalized_name,
            sort_order,
            true,
            now(),
            now()
        FROM ranked
        ON CONFLICT (owner_user_id, normalized_name) DO NOTHING;
        """
    )

    # Backfill one linked service per legacy formula record.
    op.execute(
        """
        INSERT INTO formula_services (
            formula_id,
            service_id,
            service_label_snapshot,
            position,
            created_at,
            updated_at
        )
        SELECT
            f.id,
            s.id,
            trim(regexp_replace(f.service_type, '\s+', ' ', 'g')),
            0,
            now(),
            now()
        FROM formulas f
        JOIN clients c ON c.id = f.client_id
        JOIN services s
          ON s.owner_user_id = c.owner_user_id
         AND s.normalized_name = lower(trim(regexp_replace(f.service_type, '\s+', ' ', 'g')))
        WHERE f.service_type IS NOT NULL
          AND trim(f.service_type) <> ''
        ON CONFLICT (formula_id, service_id) DO NOTHING;
        """
    )


def downgrade() -> None:
    op.drop_index("ix_formula_services_service_id", table_name="formula_services")
    op.drop_index("ix_formula_services_formula_id", table_name="formula_services")
    op.drop_table("formula_services")

    op.drop_index("ix_services_is_active", table_name="services")
    op.drop_index("ix_services_owner_user_id", table_name="services")
    op.drop_table("services")

    op.alter_column(
        "formulas",
        "service_type",
        existing_type=sa.String(length=96),
        type_=sa.String(length=32),
        existing_nullable=True,
    )

"""add default_price_cents to services

Revision ID: 0004_service_default_price_cents
Revises: 0003_services_formula_links
Create Date: 2026-03-04

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0004_service_default_price_cents"
down_revision = "0003_services_formula_links"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "services",
        sa.Column("default_price_cents", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("services", "default_price_cents")

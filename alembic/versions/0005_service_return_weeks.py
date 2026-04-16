"""add default_return_weeks to services

Revision ID: 0005_service_return_weeks
Revises: 0004_service_default_price_cents
Create Date: 2026-04-01

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0005_service_return_weeks"
down_revision = "0004_service_default_price_cents"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "services",
        sa.Column("default_return_weeks", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("services", "default_return_weeks")

"""create v2 schema tables

Revision ID: 0001_create_v2_schema
Revises: 
Create Date: 2026-02-26

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0001_create_v2_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("firebase_uid", sa.String(length=128), nullable=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("first_name", sa.String(length=64), nullable=True),
        sa.Column("last_name", sa.String(length=64), nullable=True),
        sa.Column("photo_url", sa.String(length=1024), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.UniqueConstraint("firebase_uid", name="uq_users_firebase_uid"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=False)
    op.create_index("ix_users_firebase_uid", "users", ["firebase_uid"], unique=False)

    op.create_table(
        "clients",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("first_name", sa.String(length=64), nullable=False),
        sa.Column("last_name", sa.String(length=64), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("birthday", sa.Date(), nullable=True),
        sa.Column("client_type", sa.String(length=32), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_clients_owner_user_id", "clients", ["owner_user_id"], unique=False)

    op.create_table(
        "color_charts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("porosity", sa.String(length=25), nullable=True),
        sa.Column("hair_texture", sa.String(length=25), nullable=True),
        sa.Column("elasticity", sa.String(length=25), nullable=True),
        sa.Column("scalp_condition", sa.String(length=25), nullable=True),
        sa.Column("natural_level", sa.String(length=50), nullable=True),
        sa.Column("desired_level", sa.String(length=50), nullable=True),
        sa.Column("contrib_pigment", sa.String(length=25), nullable=True),
        sa.Column("gray_front", sa.String(length=8), nullable=True),
        sa.Column("gray_sides", sa.String(length=8), nullable=True),
        sa.Column("gray_back", sa.String(length=8), nullable=True),
        sa.Column("skin_depth", sa.String(length=25), nullable=True),
        sa.Column("skin_tone", sa.String(length=25), nullable=True),
        sa.Column("eye_color", sa.String(length=25), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("client_id", name="uq_color_charts_client_id"),
    )
    op.create_index("ix_color_charts_client_id", "color_charts", ["client_id"], unique=False)

    op.create_table(
        "formulas",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("service_type", sa.String(length=32), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("price_cents", sa.Integer(), nullable=True),
        sa.Column("service_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_formulas_client_id", "formulas", ["client_id"], unique=False)
    op.create_index("ix_formulas_service_at", "formulas", ["service_at"], unique=False)

    op.create_table(
        "formula_images",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("formula_id", sa.Integer(), nullable=False),
        sa.Column("storage_provider", sa.String(length=16), nullable=False, server_default="firebase"),
        sa.Column("public_url", sa.Text(), nullable=True),
        sa.Column("object_key", sa.String(length=1024), nullable=True),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["formula_id"], ["formulas.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_formula_images_formula_id", "formula_images", ["formula_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_formula_images_formula_id", table_name="formula_images")
    op.drop_table("formula_images")

    op.drop_index("ix_formulas_service_at", table_name="formulas")
    op.drop_index("ix_formulas_client_id", table_name="formulas")
    op.drop_table("formulas")

    op.drop_index("ix_color_charts_client_id", table_name="color_charts")
    op.drop_table("color_charts")

    op.drop_index("ix_clients_owner_user_id", table_name="clients")
    op.drop_table("clients")

    op.drop_index("ix_users_firebase_uid", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")

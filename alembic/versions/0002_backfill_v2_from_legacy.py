"""backfill v2 tables from legacy tables

Revision ID: 0002_backfill_v2_from_legacy
Revises: 0001_create_v2_schema
Create Date: 2026-02-26

"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "0002_backfill_v2_from_legacy"
down_revision = "0001_create_v2_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) users
    op.execute(
        """
        INSERT INTO users (
          id,
          firebase_uid,
          email,
          first_name,
          last_name,
          photo_url,
          created_at,
          updated_at
        )
        SELECT
          u.id,
          NULLIF(btrim(u.uid), ''),
          lower(u.email),
          NULLIF(u.first_name, ''),
          NULLIF(u.last_name, ''),
          u."photoURL",
          COALESCE(u.date_created, now()),
          COALESCE(u.date_created, now())
        FROM "user" u
        ON CONFLICT (id) DO NOTHING;
        """
    )

    # 2) clients
    op.execute(
        """
        INSERT INTO clients (
          id,
          owner_user_id,
          first_name,
          last_name,
          email,
          phone,
          birthday,
          client_type,
          notes,
          created_at,
          updated_at
        )
        SELECT
          c.id,
          c.user_id,
          c.first_name,
          c.last_name,
          c.email,
          c.phone,
          CASE
            WHEN c.birthday ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' THEN c.birthday::date
            WHEN c.birthday ~ '^[0-9]{1,2}/[0-9]{1,2}/[0-9]{4}$' THEN to_date(c.birthday, 'MM/DD/YYYY')
            ELSE NULL
          END AS birthday,
          c.type,
          c.notes,
          now(),
          now()
        FROM client c
        ON CONFLICT (id) DO NOTHING;
        """
    )

    # 3) color_charts
    op.execute(
        """
        INSERT INTO color_charts (
          id,
          client_id,
          porosity,
          hair_texture,
          elasticity,
          scalp_condition,
          natural_level,
          desired_level,
          contrib_pigment,
          gray_front,
          gray_sides,
          gray_back,
          skin_depth,
          skin_tone,
          eye_color,
          created_at,
          updated_at
        )
        SELECT
          cc.id,
          cc.client_id,
          cc.porosity,
          cc.hair_texture,
          cc.elasticity,
          cc.scalp_condition,
          cc.natural_level,
          cc.desired_level,
          cc.contrib_pigment,
          cc.gray_front,
          cc.gray_sides,
          cc.gray_back,
          cc.skin_depth,
          cc.skin_tone,
          cc.eye_color,
          now(),
          now()
        FROM colorchart cc
        ON CONFLICT (id) DO NOTHING;
        """
    )

    # 4) formulas
    op.execute(
        """
        INSERT INTO formulas (
          id,
          client_id,
          service_type,
          notes,
          price_cents,
          service_at,
          created_at,
          updated_at
        )
        SELECT
          f.id,
          f.client_id,
          f.type,
          f.notes,
          CASE
            WHEN f.price IS NULL OR btrim(f.price) = '' THEN NULL
            WHEN regexp_replace(f.price, '[^0-9.]', '', 'g') = '' THEN NULL
            WHEN regexp_replace(f.price, '[^0-9.]', '', 'g') ~ '^[0-9]+([.][0-9]+)?$'
              THEN round((regexp_replace(f.price, '[^0-9.]', '', 'g')::numeric) * 100)::int
            ELSE NULL
          END AS price_cents,
          CASE
            WHEN f."date" ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'
              THEN (f."date" || ' 00:00:00+00')::timestamptz
            WHEN f."date" ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}[ T][0-9]{2}:[0-9]{2}(:[0-9]{2})?$'
              THEN f."date"::timestamptz
            WHEN f."date" ~ '^[0-9]{1,2}/[0-9]{1,2}/[0-9]{4}$'
              THEN to_timestamp(f."date", 'MM/DD/YYYY')
            ELSE NULL
          END AS service_at,
          COALESCE(f.date_created, now()),
          COALESCE(f.date_created, now())
        FROM formula f
        ON CONFLICT (id) DO NOTHING;
        """
    )

    # 5) formula_images
    op.execute(
        """
        INSERT INTO formula_images (
          id,
          formula_id,
          storage_provider,
          public_url,
          object_key,
          file_name,
          created_at,
          updated_at
        )
        SELECT
          i.id,
          i.formula_id,
          'firebase',
          i."imageURL",
          NULL,
          i.image_name,
          now(),
          now()
        FROM image i
        ON CONFLICT (id) DO NOTHING;
        """
    )

    # 6) Reset sequences after explicit ID inserts
    op.execute(
        """
        SELECT setval(
            pg_get_serial_sequence('users', 'id'),
            COALESCE((SELECT MAX(id) FROM users), 1),
            true
        );
        """
    )
    op.execute(
        """
        SELECT setval(
            pg_get_serial_sequence('clients', 'id'),
            COALESCE((SELECT MAX(id) FROM clients), 1),
            true
        );
        """
    )
    op.execute(
        """
        SELECT setval(
            pg_get_serial_sequence('color_charts', 'id'),
            COALESCE((SELECT MAX(id) FROM color_charts), 1),
            true
        );
        """
    )
    op.execute(
        """
        SELECT setval(
            pg_get_serial_sequence('formulas', 'id'),
            COALESCE((SELECT MAX(id) FROM formulas), 1),
            true
        );
        """
    )
    op.execute(
        """
        SELECT setval(
            pg_get_serial_sequence('formula_images', 'id'),
            COALESCE((SELECT MAX(id) FROM formula_images), 1),
            true
        );
        """
    )


def downgrade() -> None:
    # Keep this intentionally destructive only to v2 tables populated by this revision.
    op.execute("DELETE FROM formula_images")
    op.execute("DELETE FROM formulas")
    op.execute("DELETE FROM color_charts")
    op.execute("DELETE FROM clients")
    op.execute("DELETE FROM users")

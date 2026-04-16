-- Historical archive from the original legacy -> v2 cutover.
-- Template SQL for legacy -> v2 backfill.
-- Use only as reference if reconstructing that migration.

BEGIN;

-- 1) users
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
FROM "user" u;

-- 2) clients
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
    WHEN c.birthday ~ '^\\d{4}-\\d{2}-\\d{2}$' THEN c.birthday::date
    WHEN c.birthday ~ '^\\d{1,2}/\\d{1,2}/\\d{4}$' THEN to_date(c.birthday, 'MM/DD/YYYY')
    ELSE NULL
  END AS birthday,
  c.type,
  c.notes,
  now(),
  now()
FROM client c;

-- 3) color_charts
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
FROM colorchart cc;

-- 4) formulas
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
    WHEN f."date" ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' THEN (f."date" || ' 00:00:00+00')::timestamptz
    WHEN f."date" ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}[ T][0-9]{2}:[0-9]{2}(:[0-9]{2})?$'
      THEN f."date"::timestamptz
    WHEN f."date" ~ '^[0-9]{1,2}/[0-9]{1,2}/[0-9]{4}$' THEN to_timestamp(f."date", 'MM/DD/YYYY')
    ELSE NULL
  END AS service_at,
  COALESCE(f.date_created, now()),
  COALESCE(f.date_created, now())
FROM formula f;

-- 5) formula_images
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
FROM image i;

-- 6) Reset sequences after explicit ID insert
SELECT setval(pg_get_serial_sequence('users', 'id'), COALESCE((SELECT MAX(id) FROM users), 1), true);
SELECT setval(pg_get_serial_sequence('clients', 'id'), COALESCE((SELECT MAX(id) FROM clients), 1), true);
SELECT setval(pg_get_serial_sequence('color_charts', 'id'), COALESCE((SELECT MAX(id) FROM color_charts), 1), true);
SELECT setval(pg_get_serial_sequence('formulas', 'id'), COALESCE((SELECT MAX(id) FROM formulas), 1), true);
SELECT setval(pg_get_serial_sequence('formula_images', 'id'), COALESCE((SELECT MAX(id) FROM formula_images), 1), true);

COMMIT;

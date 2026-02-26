-- Step 3 smoke checks for RESTORE DB after v2 migrations.
-- Run with:
-- psql "$RESTORE_DATABASE_URL" -f docs/sql/step3_restore_smoke_checks.sql

\echo '=== Legacy tables still present ==='
SELECT to_regclass('public."user"') AS legacy_user,
       to_regclass('public.client') AS legacy_client,
       to_regclass('public.colorchart') AS legacy_colorchart,
       to_regclass('public.formula') AS legacy_formula,
       to_regclass('public.image') AS legacy_image;

\echo '=== V2 tables present ==='
SELECT to_regclass('public.users') AS v2_users,
       to_regclass('public.clients') AS v2_clients,
       to_regclass('public.color_charts') AS v2_color_charts,
       to_regclass('public.formulas') AS v2_formulas,
       to_regclass('public.formula_images') AS v2_formula_images;

\echo '=== Alembic v2 head ==='
SELECT version_num FROM alembic_version_v2;

\echo '=== Transitional UID rows (should be 7 currently) ==='
SELECT COUNT(*) AS transitional_uid_rows
FROM users
WHERE firebase_uid IS NULL;

\echo '=== Top users by client counts ==='
SELECT u.id, u.email, COUNT(c.id) AS client_count
FROM users u
LEFT JOIN clients c ON c.owner_user_id = u.id
GROUP BY u.id, u.email
ORDER BY client_count DESC, u.id
LIMIT 20;

\echo '=== Formula image provider distribution ==='
SELECT storage_provider, COUNT(*) AS count
FROM formula_images
GROUP BY storage_provider
ORDER BY count DESC;

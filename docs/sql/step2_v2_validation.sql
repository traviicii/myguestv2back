-- Validate legacy -> v2 backfill results (run on restore DB after alembic upgrade head)

\echo '=== Legacy vs v2 table counts ==='
SELECT 'user -> users' AS mapping, (SELECT COUNT(*) FROM "user") AS legacy_count, (SELECT COUNT(*) FROM users) AS v2_count
UNION ALL
SELECT 'client -> clients', (SELECT COUNT(*) FROM client), (SELECT COUNT(*) FROM clients)
UNION ALL
SELECT 'colorchart -> color_charts', (SELECT COUNT(*) FROM colorchart), (SELECT COUNT(*) FROM color_charts)
UNION ALL
SELECT 'formula -> formulas', (SELECT COUNT(*) FROM formula), (SELECT COUNT(*) FROM formulas)
UNION ALL
SELECT 'image -> formula_images', (SELECT COUNT(*) FROM image), (SELECT COUNT(*) FROM formula_images)
ORDER BY mapping;

\echo '=== Users with null firebase_uid in v2 (expected transitional rows) ==='
SELECT COUNT(*) AS null_firebase_uid_count
FROM users
WHERE firebase_uid IS NULL;

\echo '=== V2 orphan checks ==='
SELECT COUNT(*) AS orphan_clients_owner
FROM clients c
LEFT JOIN users u ON u.id = c.owner_user_id
WHERE u.id IS NULL;

SELECT COUNT(*) AS orphan_color_charts_client
FROM color_charts cc
LEFT JOIN clients c ON c.id = cc.client_id
WHERE c.id IS NULL;

SELECT COUNT(*) AS orphan_formulas_client
FROM formulas f
LEFT JOIN clients c ON c.id = f.client_id
WHERE c.id IS NULL;

SELECT COUNT(*) AS orphan_images_formula
FROM formula_images fi
LEFT JOIN formulas f ON f.id = fi.formula_id
WHERE f.id IS NULL;

\echo '=== Type conversion sanity ==='
SELECT COUNT(*) AS null_service_at_count FROM formulas WHERE service_at IS NULL;
SELECT COUNT(*) AS null_price_cents_count FROM formulas WHERE price_cents IS NULL;

\echo '=== Spot check legacy formula -> v2 formula ==='
SELECT f.id, f."date" AS legacy_date, v.service_at, f.price AS legacy_price, v.price_cents
FROM formula f
JOIN formulas v ON v.id = f.id
ORDER BY f.id
LIMIT 20;

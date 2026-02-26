-- Step 1 preflight checks for legacy schema quality.
-- Run this against LIVE and RESTORED databases and compare results.

\echo '=== Row counts ==='
SELECT 'user' AS table_name, COUNT(*) AS row_count FROM "user"
UNION ALL SELECT 'client', COUNT(*) FROM client
UNION ALL SELECT 'colorchart', COUNT(*) FROM colorchart
UNION ALL SELECT 'formula', COUNT(*) FROM formula
UNION ALL SELECT 'image', COUNT(*) FROM image
ORDER BY table_name;

\echo '=== User UID checks ==='
SELECT COUNT(*) AS null_or_blank_uid_count
FROM "user"
WHERE uid IS NULL OR btrim(uid) = '';

SELECT uid, COUNT(*) AS duplicate_count
FROM "user"
WHERE uid IS NOT NULL AND btrim(uid) <> ''
GROUP BY uid
HAVING COUNT(*) > 1
ORDER BY duplicate_count DESC, uid;

\echo '=== User email checks ==='
SELECT lower(email) AS email_norm, COUNT(*) AS duplicate_count
FROM "user"
GROUP BY lower(email)
HAVING COUNT(*) > 1
ORDER BY duplicate_count DESC, email_norm;

\echo '=== Orphan FK checks ==='
SELECT COUNT(*) AS orphan_client_user
FROM client c
LEFT JOIN "user" u ON u.id = c.user_id
WHERE u.id IS NULL;

SELECT COUNT(*) AS orphan_colorchart_client
FROM colorchart cc
LEFT JOIN client c ON c.id = cc.client_id
WHERE c.id IS NULL;

SELECT COUNT(*) AS orphan_colorchart_user
FROM colorchart cc
LEFT JOIN "user" u ON u.id = cc.user_id
WHERE u.id IS NULL;

SELECT COUNT(*) AS orphan_formula_client
FROM formula f
LEFT JOIN client c ON c.id = f.client_id
WHERE c.id IS NULL;

SELECT COUNT(*) AS orphan_image_formula
FROM image i
LEFT JOIN formula f ON f.id = i.formula_id
WHERE f.id IS NULL;

SELECT COUNT(*) AS orphan_image_client
FROM image i
LEFT JOIN client c ON c.id = i.client_id
WHERE c.id IS NULL;

\echo '=== One-to-one readiness checks ==='
SELECT client_id, COUNT(*) AS chart_count
FROM colorchart
GROUP BY client_id
HAVING COUNT(*) > 1
ORDER BY chart_count DESC, client_id;

\echo '=== Formula date parseability ==='
SELECT
  COUNT(*) AS total_formula_rows,
  COUNT(*) FILTER (WHERE "date" ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$') AS iso_date_rows,
  COUNT(*) FILTER (
    WHERE "date" ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}[ T][0-9]{2}:[0-9]{2}(:[0-9]{2})?$'
  ) AS iso_datetime_rows,
  COUNT(*) FILTER (WHERE "date" ~ '^[0-9]{1,2}/[0-9]{1,2}/[0-9]{4}$') AS us_date_rows,
  COUNT(*) FILTER (
    WHERE NOT (
      "date" ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'
      OR "date" ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}[ T][0-9]{2}:[0-9]{2}(:[0-9]{2})?$'
      OR "date" ~ '^[0-9]{1,2}/[0-9]{1,2}/[0-9]{4}$'
    )
  ) AS unclassified_date_rows
FROM formula;

SELECT id, "date"
FROM formula
WHERE NOT (
  "date" ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'
  OR "date" ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}[ T][0-9]{2}:[0-9]{2}(:[0-9]{2})?$'
  OR "date" ~ '^[0-9]{1,2}/[0-9]{1,2}/[0-9]{4}$'
)
ORDER BY id
LIMIT 100;

\echo '=== Formula price parseability ==='
SELECT
  COUNT(*) AS total_formula_rows,
  COUNT(*) FILTER (WHERE price IS NULL OR btrim(price) = '') AS blank_price_rows,
  COUNT(*) FILTER (
    WHERE price IS NOT NULL
      AND btrim(price) <> ''
      AND (
        regexp_replace(price, '[^0-9.]', '', 'g') = ''
        OR regexp_replace(price, '[^0-9.]', '', 'g') !~ '^[0-9]+([.][0-9]+)?$'
      )
  ) AS unparseable_price_rows
FROM formula;

SELECT id, price
FROM formula
WHERE price IS NOT NULL
  AND btrim(price) <> ''
  AND (
    regexp_replace(price, '[^0-9.]', '', 'g') = ''
    OR regexp_replace(price, '[^0-9.]', '', 'g') !~ '^[0-9]+([.][0-9]+)?$'
  )
ORDER BY id
LIMIT 100;

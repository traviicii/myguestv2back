# Path A Refinement Plan

## Decisions locked

- Keep Firebase Auth now, but harden flow.
- Keep Firebase Storage now, but prepare to move to S3/R2.
- Keep existing populated Postgres data and migrate with Alembic.

## Improvements implemented in this baseline

- App factory (`create_app`) for testability and configuration isolation.
- Single auth mechanism: Bearer Firebase ID token.
- Transitional auth linking: legacy users with blank UID are linked by verified email on first login.
- Request/response validation with Pydantic schemas.
- Consistent error payload shape.
- Ownership-based authorization checks on resource reads/writes.
- List endpoints use query params (`limit`, `offset`, `sort`, `order`).

## Database direction

- `users` keyed by `firebase_uid` + unique email.
- `clients` owned by `owner_user_id`.
- `color_charts` one-to-one with `clients` via unique `client_id`.
- `formulas` use typed `service_at` and integer `price_cents`.
- `formula_images` support provider migration with `storage_provider`, `public_url`, `object_key`.

## Migration from current production DB

1. Backup and snapshot existing Render Postgres.
2. Create Alembic baseline matching current production schema.
3. Add new columns/tables in additive migrations.
4. Backfill typed columns from legacy string fields.
5. Update API to read/write new fields.
6. Deprecate legacy columns after verification.

Step 1 artifacts:
- `docs/step1-schema-map.md`
- `docs/step1-backup-and-restore-gates.md`
- `docs/sql/step1_preflight_checks.sql`
- `docs/sql/step1_backfill_templates.sql`

## Firebase Storage to S3/R2 later

1. Keep serving legacy Firebase URLs.
2. Start writing new uploads to S3/R2 with presigned URLs.
3. Store canonical `object_key` + provider in `formula_images`.
4. Migrate old objects in background jobs; preserve references.
5. Remove Firebase dependency when old object coverage reaches target.

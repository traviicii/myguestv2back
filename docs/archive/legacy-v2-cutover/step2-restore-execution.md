# Step 2: Execute v2 Schema + Backfill on Restore DB

> Historical archive: this document captures the original restore-database
> migration procedure. Alembic heads and operational expectations here are
> specific to that cutover window.

Run these commands from:
`/Users/travispeck/Documents/coding_projects/myguestv2/myguestv2back`

## Preconditions

- `LIVE_DATABASE_URL` and `RESTORE_DATABASE_URL` are set.
- `PG16_BIN=/opt/homebrew/opt/postgresql@16/bin` is set.
- Backup and restore preflight already passed.

## 1) Confirm Alembic sees revisions

```bash
alembic history
```

At the time of the original cutover, the working migration head sequence was:
- `0001_create_v2_schema`
- `0002_backfill_v2_from_legacy`

## 2) Run migrations on restore DB only

```bash
export DATABASE_URL="$RESTORE_DATABASE_URL"
alembic upgrade head
```

This creates v2 tables and backfills from legacy tables.

## 3) Validate backfill results

```bash
LATEST_BACKUP="$(ls -td backups/* | head -1)"
"$PG16_BIN/psql" "$RESTORE_DATABASE_URL" -f "docs/archive/legacy-v2-cutover/sql/step2_v2_validation.sql" > "$LATEST_BACKUP/step2.validation.restore.txt"
tail -n 200 "$LATEST_BACKUP/step2.validation.restore.txt"
```

## 4) API smoke tests against restore DB

```bash
export DATABASE_URL="$RESTORE_DATABASE_URL"
uvicorn app.main:app --reload
```

Smoke test checklist:
- `POST /api/v1/auth/sync` works with a real Firebase token.
- Existing user with blank legacy UID links on first login.
- `GET /api/v1/clients` returns expected records.
- `GET /api/v1/clients/{id}` enforces ownership.

## 5) No-go criteria for production cutover

Do not proceed to live cutover if any are true:
- Legacy vs v2 row counts mismatch unexpectedly.
- Any v2 orphan check is non-zero.
- `formulas.service_at` contains nulls.
- Auth sync cannot link expected transitional users.

# Step 3 Smoke Test Protocol (Restore DB)

> Historical archive: this smoke-test checklist belongs to the original legacy
> cutover rehearsal. Keep it for context only.

Run these checks before production cutover.

## A) DB-level smoke checks

```bash
cd /Users/travispeck/Documents/coding_projects/myguestv2/myguestv2back
LATEST_BACKUP="$(ls -td backups/* | head -1)"
export PG16_BIN="/opt/homebrew/opt/postgresql@16/bin"

"$PG16_BIN/psql" "$RESTORE_DATABASE_URL" -f "docs/archive/legacy-v2-cutover/sql/step3_restore_smoke_checks.sql" > "$LATEST_BACKUP/step3.smoke.restore.txt"
tail -n 200 "$LATEST_BACKUP/step3.smoke.restore.txt"
```

Pass criteria:
- All legacy and v2 tables resolve (not null in `to_regclass`).
- `alembic_version_v2` has `0002_backfill_v2_from_legacy`.
- Transitional UID rows count matches the value recorded for the original
  cutover rehearsal.

## B) API-level smoke checks (manual)

Start API against restore DB:

```bash
cd /Users/travispeck/Documents/coding_projects/myguestv2/myguestv2back
export DATABASE_URL="$RESTORE_DATABASE_URL"
uvicorn app.main:app --reload
```

Then validate from frontend or API client:
1. `POST /api/v1/auth/sync` with a known Firebase user token.
2. `GET /api/v1/clients` returns records.
3. `GET /api/v1/clients/{id}` denies access for non-owner token.
4. `GET /api/v1/clients/{id}/formulas` returns expected historical records.

## C) Transitional UID linking proof

Before first login for a blank-uid user (example email):

```bash
"$PG16_BIN/psql" "$RESTORE_DATABASE_URL" -c "SELECT id, email, firebase_uid FROM users WHERE email = 'traviifamous@yahoo.com';"
```

After successful `/api/v1/auth/sync` with that same user's Firebase token, rerun the query.

Pass criteria:
- `firebase_uid` changed from `NULL` to a non-empty UID.
- User can fetch their own clients.

## D) No-go criteria

Do not proceed to production cutover if any are true:
- Any smoke check fails.
- UID-link behavior fails for transitional users.
- Ownership guard is bypassed in API checks.

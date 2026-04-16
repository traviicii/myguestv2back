# Step 4 Production Cutover Runbook (Freeze Window)

> Historical archive: this was the original production cutover runbook for the
> legacy-to-v2 migration. Preserve it for audit/reference only.

Use this only after Step 3 smoke checks pass on restore DB.

## Preconditions

- Maintenance window scheduled.
- Rollback owner assigned.
- `TS_FINAL` backup path confirmed.
- All commands tested on restore DB.

## 1) Enter freeze mode

- Put backend into maintenance/read-only mode.
- Confirm no active write jobs.

## 2) Final immutable backup from LIVE

```bash
cd /Users/travispeck/Documents/coding_projects/myguestv2/myguestv2back
export PG16_BIN="/opt/homebrew/opt/postgresql@16/bin"

TS_FINAL="$(date +%Y%m%d_%H%M%S)_final"
mkdir -p "backups/$TS_FINAL"

"$PG16_BIN/pg_dump" --format=custom --no-owner --no-acl "$LIVE_DATABASE_URL" > "backups/$TS_FINAL/live.custom.dump"
"$PG16_BIN/pg_dump" --schema-only "$LIVE_DATABASE_URL" > "backups/$TS_FINAL/live.schema.sql"
"$PG16_BIN/pg_dump" --data-only "$LIVE_DATABASE_URL" > "backups/$TS_FINAL/live.data.sql"
shasum -a 256 "backups/$TS_FINAL/live.custom.dump" "backups/$TS_FINAL/live.schema.sql" "backups/$TS_FINAL/live.data.sql" > "backups/$TS_FINAL/SHA256SUMS"
```

## 3) Apply v2 migrations on LIVE

```bash
export DATABASE_URL="$LIVE_DATABASE_URL"
alembic upgrade head
```

## 4) Post-migration DB validation

```bash
"$PG16_BIN/psql" "$LIVE_DATABASE_URL" -f "docs/archive/legacy-v2-cutover/sql/step2_v2_validation.sql" > "backups/$TS_FINAL/step2.validation.live.txt"
tail -n 200 "backups/$TS_FINAL/step2.validation.live.txt"
```

## 5) API smoke tests on LIVE

- `POST /api/v1/auth/sync`
- `GET /api/v1/clients`
- Transitional UID linking for one known blank-uid user
- Ownership isolation check

## 6) Exit freeze mode

- Re-enable normal traffic.
- Monitor errors, auth failures, DB load.

## Rollback trigger points (immediate rollback)

Rollback if any occur:
- Migration command fails.
- Validation SQL shows row mismatches/orphans.
- `/auth/sync` fails for known working token.
- Ownership guards fail.

Rollback command:

```bash
"$PG16_BIN/pg_restore" --clean --if-exists --no-owner --no-acl -d "$LIVE_DATABASE_URL" "backups/$TS_FINAL/live.custom.dump"
```

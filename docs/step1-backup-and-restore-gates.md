# Step 1: Backup and Restore Gates (No Exceptions)

Do not point v2 migrations or v2 API writes at the live database until every gate below is passed.

## Gate 0: Freeze-window readiness

- A maintenance window is scheduled.
- A rollback owner is assigned.
- A restore target database is ready (local or staging Render Postgres).

## Gate 1: Capture immutable backups

From a secure shell with `pg_dump` available:

```bash
export LIVE_DATABASE_URL='postgresql://...'
export TS="$(date +%Y%m%d_%H%M%S)"
mkdir -p backups/$TS

pg_dump --format=custom --no-owner --no-acl "$LIVE_DATABASE_URL" > backups/$TS/live.custom.dump
pg_dump --schema-only "$LIVE_DATABASE_URL" > backups/$TS/live.schema.sql
pg_dump --data-only "$LIVE_DATABASE_URL" > backups/$TS/live.data.sql

shasum -a 256 backups/$TS/live.custom.dump backups/$TS/live.schema.sql backups/$TS/live.data.sql > backups/$TS/SHA256SUMS
```

Required:
- Store backups in at least two locations.
- Keep `SHA256SUMS` with the artifacts.

## Gate 2: Restore drill must pass

Restore into a non-production database:

```bash
export RESTORE_DATABASE_URL='postgresql://...'
pg_restore --clean --if-exists --no-owner --no-acl -d "$RESTORE_DATABASE_URL" backups/$TS/live.custom.dump
```

Then run preflight checks against restored DB and live DB and compare:

```bash
psql "$LIVE_DATABASE_URL" -f docs/sql/step1_preflight_checks.sql
psql "$RESTORE_DATABASE_URL" -f docs/sql/step1_preflight_checks.sql
```

Required:
- Row counts match for all legacy tables.
- Critical integrity checks return zero error rows.

## Gate 3: Explicit go/no-go criteria

Go only if all are true:
- Backup artifacts exist and hashes match.
- Restore drill succeeded.
- Preflight checks passed on live and restored DB.
- Rollback command path was tested at least once.

No-go if any are false.

## Gate 4: Rollback command is prepared before cutover

Rollback command template:

```bash
pg_restore --clean --if-exists --no-owner --no-acl -d "$LIVE_DATABASE_URL" backups/$TS/live.custom.dump
```

This command should be ready in your cutover runbook before migration starts.

## Gate 5: Freeze execution order

1. Put backend into maintenance mode (or disable writes).
2. Take final fresh backup (`TS_FINAL`).
3. Run migration/backfill steps.
4. Smoke test critical paths (`auth/sync`, clients list/create/get).
5. Re-enable traffic.
6. Monitor errors and DB metrics.

If smoke tests fail, rollback immediately using `TS_FINAL` backup.

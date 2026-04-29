# Render Production Baseline

Last updated: 2026-04-29

This is the current backend hosting recommendation for MyGuest on Render.

## What Starter is good for

Render Starter is appropriate for:

- local-to-hosted backend validation
- preview / dogfooding
- light internal or beta traffic

It is not the recommended final footprint for a public App Store launch with
simultaneous active users.

## Recommended production floor

For the first real App Store launch, use at least:

- Render web service: `Standard`
- Render Postgres: not legacy Starter; use a modern plan with enough headroom
- Same region for web service and database
- Internal database URL from Render, not the external URL

Recommended initial runtime env:

```bash
APP_ENV=production
TRUSTED_HOSTS=myguestv2back.onrender.com,<your-production-api-domain>
CORS_ORIGINS=https://<your-production-web-host>
WEB_CONCURRENCY=2
DB_POOL_SIZE=5
DB_MAX_OVERFLOW=2
DB_POOL_TIMEOUT_SECONDS=30
DB_POOL_RECYCLE_SECONDS=1800
DB_POOL_USE_LIFO=true
RUN_MIGRATIONS_ON_BOOT=false
LOG_LEVEL=info
```

## Why these defaults

- `WEB_CONCURRENCY=2` is a cautious starting point for a larger plan while
  keeping memory pressure predictable.
- `DB_POOL_SIZE=5` and `DB_MAX_OVERFLOW=2` keep total connections bounded per
  worker.
- `RUN_MIGRATIONS_ON_BOOT=false` avoids every web instance trying to migrate on
  startup. Run `alembic upgrade head` as a one-off release step instead.

Approximate max live database connections from the app tier:

```text
total_app_connections ~= WEB_CONCURRENCY * (DB_POOL_SIZE + DB_MAX_OVERFLOW)
```

With the recommended baseline:

```text
2 * (5 + 2) = 14
```

That is a healthier starting point than letting pools grow implicitly.

## When to add PgBouncer

Add PgBouncer when one or more of these become true:

- you increase worker count beyond the initial baseline
- you scale to multiple web instances
- Postgres connection pressure starts showing up in Render metrics

## Current app-level caveats

- Rate limiting is currently in-memory per instance. It is fine for one web
  instance, but not globally consistent across multiple instances.
- `/api/v1/exports/data` builds the export archive synchronously in request
  time. That is acceptable for small accounts, but it should move to a queued or
  streaming approach if export size grows.
- `/api/v1/metrics/overview` performs live aggregations and should be watched
  under load.

## Release gate before public launch

Before switching the app to the production backend:

1. Deploy the backend on the production Render footprint.
2. Run the `Backend CI` workflow cleanly.
3. Run the `Render Smoke Contract` workflow against production.
4. Validate the iPhone preview/production build against the hosted backend.
5. Record a recent successful backup/restore drill.

# MyGuest Backend v2

Backend rebuild for MyGuest using FastAPI, SQLAlchemy 2.x, Alembic, and Pydantic.

This repo is the backend source of truth. It pairs with
`/Users/travispeck/Documents/coding_projects/myguestv2/myguestv2front`, but it
can be developed and verified independently.

Legacy backend reference (read-only):
`/Users/travispeck/Documents/coding_temple/classwork/client_keep_capstone/client_keep_flask`

## Quick Start

```bash
pip install -e .[dev]
cp .env.example .env
uvicorn app.main:app --reload
```

## Default Development Gate

Run these before shipping or opening a PR:

```bash
make lint
make test
```

For hosted preview or production verification, run:

```bash
make smoke-remote BASE_URL=https://api.example.com/api/v1 TOKEN=$EXPO_PUBLIC_DEV_ID_TOKEN
```

That wraps `scripts/smoke_render_contract.sh` so the backend has one consistent
remote smoke step before preview/TestFlight frontend builds.

## GitHub Actions

- `Backend CI` runs `make lint` and `make test` on pushes to `main` and on pull
  requests.
- `Render Smoke Contract` is the manual release gate for the deployed Render
  API. Run it after Render reports the backend healthy and before shipping a new
  mobile build.

Set these repository secrets before using the smoke workflow:

- `RENDER_SMOKE_BASE_URL`
  Example: `https://myguestv2back.onrender.com/api/v1`
- `RENDER_SMOKE_TOKEN`
  A valid Firebase ID token for a real account that is safe to use for smoke
  verification

Recommended release flow:

1. Deploy the backend to Render.
2. Wait for `/api/v1/health` to report healthy.
3. Run `Render Smoke Contract` in GitHub Actions.
4. Ship the matching frontend build only after the smoke job passes.

## Current Auth And Storage Path

- Auth: Firebase ID token verification only
- Storage: Firebase image URLs remain first-class data
- Migration-ready: `formula_images` includes `storage_provider` and `object_key`
  for future S3/R2 work
- Account deletion revokes Firebase refresh tokens before deleting local data
  and reports image-cleanup partial failures explicitly

## Runtime Security Defaults

- Production disables `/docs`, `/redoc`, and `/openapi.json` unless you
  explicitly set `API_DOCS_ENABLED=true`.
- Production requires `TRUSTED_HOSTS` to be set to the real API hostname(s), so
  host-header validation is enforced instead of left implicit.
- CORS now defaults to `allow_credentials=false`, which is the safer baseline
  for this bearer-token API.
- Targeted rate limits protect `/auth/sync`, `/exports/data`, and
  `/account/delete` in production by default.
- Responses include `X-Request-ID`, and request/error logs include that ID for
  backend tracing.

## Migrations

Create a migration:

```bash
alembic revision --autogenerate -m "describe change"
```

Apply migrations:

```bash
alembic upgrade head
```

## Render Start Command

Use:

```bash
bash scripts/start_render.sh
```

This runs `alembic upgrade head` before starting Uvicorn so schema stays aligned
with deployed API code.

## Project Map

- `app/api/v1/endpoints/` - HTTP routes
- `app/services/` - cleanup and service-layer helpers
- `app/models/` - SQLAlchemy models
- `app/schemas/` - request/response models
- `tests/` - API and regression coverage
- `docs/` - backend docs index, ERDs, and archived migration notes

# MyGuest Backend v2

Backend rebuild for MyGuest using FastAPI, SQLAlchemy 2.x, Alembic, and Pydantic.

This repo is the backend source of truth. It is designed to pair with
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

What they run:

- `make lint` → `ruff check .`
- `make test` → `pytest`

GitHub Actions mirrors the same commands in `.github/workflows/ci.yml`.

## Current Auth And Storage Path

- Auth: Firebase ID token verification only
- Storage: Firebase image URLs still supported as first-class data
- Migration-ready: `formula_images` includes `storage_provider` and `object_key` for future S3/R2 work

Wave 1 cleanup also moves formula mutation and storage cleanup logic into
`app/services/` so route handlers stay orchestration-focused.

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
- `app/services/` - business logic and cleanup helpers
- `app/models/` - SQLAlchemy models
- `app/schemas/` - request/response models
- `tests/` - API and service regression coverage
- `docs/` - implementation plans and migration notes

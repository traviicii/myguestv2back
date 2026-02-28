# MyGuest Backend v2

Backend rebuild for MyGuest using:
- FastAPI
- SQLAlchemy 2.x
- Alembic
- Pydantic

Legacy backend reference (read-only):
`/Users/travispeck/Documents/coding_temple/classwork/client_keep_capstone/client_keep_flask`

## Current Auth/Storage Path

- Auth: Firebase ID token verification only (single bearer-token mechanism).
- Storage: Firebase image URLs supported as first-class data.
- Migration-ready: `formula_images` includes `storage_provider` + `object_key` for later S3/R2 migration.

## Run locally

1. Create virtual environment and install dependencies:

```bash
pip install -e .[dev]
```

2. Create env file:

```bash
cp .env.example .env
```

3. Start API:

```bash
uvicorn app.main:app --reload
```

## Migrations

Create a migration:

```bash
alembic revision --autogenerate -m "init schema"
```

Apply migrations:

```bash
alembic upgrade head
```

## Tests

```bash
pytest
```

## Render start command

Use:

```bash
bash scripts/start_render.sh
```

This runs `alembic upgrade head` before starting Uvicorn so schema stays aligned with deployed API code.

# Backend Docs

This directory now separates active reference material from historical
one-time migration notes.

## Current Reference

- `erd-simplified.md` and `erd-simplified.svg`
  Product-facing schema overviews for quick orientation.
- `erd-detailed.md` and `erd-detailed.svg`
  Table-level schema references for engineering work.

## Future-State Planning

- `image-storage-modernization-plan.md`
  Forward-looking design document for a managed upload pipeline. This is not the
  current backend API contract.

## Historical Archive

- `archive/legacy-v2-cutover/`
  Original legacy-to-v2 migration, restore, smoke-test, and production cutover
  documents. Keep these for audit/reference context only. They are not
  maintained as current operational guidance.

## Live Source Of Truth

When docs and code ever disagree, prefer the live backend implementation:

- `app/models/` for persisted schema
- `app/schemas/` for request/response contracts
- `app/api/v1/endpoints/` for exposed routes
- `alembic/versions/` for migration history

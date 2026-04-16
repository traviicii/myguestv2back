# Legacy v2 Cutover Archive

This folder preserves the original working notes from the first legacy-to-v2
database migration and cutover effort.

Use these files only for historical context, auditability, or if you need to
reconstruct how the original migration was planned. They should not be treated
as current runbooks for the live backend.

## Archived Contents

- `path-a-plan.md`
  Early decision record for the initial migration direction.
- `step1-*.md` through `step4-*.md`
  Restore, smoke-test, and cutover runbooks from that original window.
- `sql/`
  SQL snippets and validation scripts that supported the original migration.

## Important Caveats

- Some expectations in these files are intentionally historical.
- Alembic heads, counts, and operational checklists may no longer match the
  current backend state.
- Current backend reference material lives one level up in `docs/`.

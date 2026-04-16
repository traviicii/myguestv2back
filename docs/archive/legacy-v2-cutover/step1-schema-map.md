# Step 1: Legacy to v2 Schema Map

> Historical archive: this schema map belongs to the original legacy-to-v2
> migration effort. It is retained for audit context and does not describe the
> full current backend after later schema additions such as `services` and
> `formula_services`.

This document is the exact mapping plan from the legacy tables in the live DB to v2 tables.

## Locked migration mode

- Side-by-side migration in the same Postgres database.
- Legacy tables stay intact during migration (`user`, `client`, `colorchart`, `formula`, `image`).
- v2 tables are populated separately (`users`, `clients`, `color_charts`, `formulas`, `formula_images`).
- Final cutover happens during a planned freeze window.

## Table mapping

| Legacy table | v2 table | Notes |
| --- | --- | --- |
| `user` | `users` | Keep IDs aligned where possible. |
| `client` | `clients` | `user_id` becomes `owner_user_id`. |
| `colorchart` | `color_charts` | `user_id` dropped (owner inferred via client). |
| `formula` | `formulas` | `type` renamed to `service_type`, `date` converted to `service_at`, `price` converted to `price_cents`. |
| `image` | `formula_images` | `imageURL` becomes `public_url`, new `storage_provider` + `object_key`. |

## Column mapping details

### `user` -> `users`

| Legacy column | v2 column | Transform |
| --- | --- | --- |
| `id` | `id` | Copy as-is. |
| `uid` | `firebase_uid` | Transitional: copy value, blank -> `NULL`. Unique when present. Linked on first Firebase login by verified email. |
| `email` | `email` | Copy; keep unique. |
| `first_name` | `first_name` | Copy. |
| `last_name` | `last_name` | Copy. |
| `photoURL` | `photo_url` | Copy. |
| `date_created` | `created_at` | Copy if present, else `now()`. |
| `date_created` | `updated_at` | Copy if present, else `now()`. |
| `password` | - | Not migrated (Firebase token auth only). |
| `apitoken` | - | Not migrated (deprecated). |

### `client` -> `clients`

| Legacy column | v2 column | Transform |
| --- | --- | --- |
| `id` | `id` | Copy as-is. |
| `user_id` | `owner_user_id` | Copy as-is. |
| `first_name` | `first_name` | Copy. |
| `last_name` | `last_name` | Copy. |
| `email` | `email` | Copy. |
| `phone` | `phone` | Copy. |
| `birthday` | `birthday` | Parse string to `date`, else `NULL` and remediate. |
| `type` | `client_type` | Rename + copy. |
| `notes` | `notes` | Copy. |

### `colorchart` -> `color_charts`

| Legacy column | v2 column | Transform |
| --- | --- | --- |
| `id` | `id` | Copy as-is. |
| `client_id` | `client_id` | Copy as-is (must be unique in v2). |
| `porosity` ... `eye_color` | same names | Copy as-is. |
| `user_id` | - | Dropped; derive ownership through `clients.owner_user_id`. |

### `formula` -> `formulas`

| Legacy column | v2 column | Transform |
| --- | --- | --- |
| `id` | `id` | Copy as-is. |
| `client_id` | `client_id` | Copy as-is. |
| `type` | `service_type` | Rename + copy. |
| `notes` | `notes` | Copy. |
| `price` | `price_cents` | Parse numeric, multiply by 100, cast to integer. |
| `date` | `service_at` | Parse to timestamp with timezone. |
| `date_created` | `created_at` | Copy if present, else `now()`. |
| `date_created` | `updated_at` | Copy if present, else `now()`. |

### `image` -> `formula_images`

| Legacy column | v2 column | Transform |
| --- | --- | --- |
| `id` | `id` | Copy as-is. |
| `formula_id` | `formula_id` | Copy as-is. |
| `imageURL` | `public_url` | Copy as-is. |
| `image_name` | `file_name` | Copy as-is. |
| - | `storage_provider` | Constant `'firebase'` for migrated rows. |
| - | `object_key` | `NULL` initially; optional later backfill when moving to S3/R2. |

## Required preflight checks before any migration

Run and pass the checks in:
- `docs/archive/legacy-v2-cutover/sql/step1_preflight_checks.sql`

Critical checks:
- No duplicate non-blank `user.uid` values.
- No orphan foreign keys.
- No duplicate `colorchart.client_id` rows.
- `formula.date` parseability rate is acceptable.

## Transitional UID-link behavior (for legacy blank UID rows)

- `users.firebase_uid` is nullable during migration.
- `/api/v1/auth/sync` first checks by `firebase_uid`.
- If not found, it attempts email-based link:
  - It only links by email when the token email is verified.
  - If verified email matches row with `firebase_uid IS NULL`, it sets `firebase_uid` to token UID.
  - If email matches row with different non-null UID, sync returns `409 auth_identity_conflict`.
- After those users have logged in at least once, `firebase_uid` can be tightened to non-null.

## Backfill SQL templates

Backfill templates are in:
- `docs/archive/legacy-v2-cutover/sql/step1_backfill_templates.sql`

These are templates for a migration revision, not copy-paste directly into production.

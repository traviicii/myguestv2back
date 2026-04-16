# Image Storage Modernization Plan

## Status

- This is a future-state design document, not the current backend upload
  contract.
- Current backend behavior as of 2026-04-15:
  - `formula_images` stores `storage_provider`, `public_url`, `object_key`, and
    `file_name`.
  - Formula create/update requests accept image references embedded in the
    formula payload.
  - The backend does not yet expose dedicated upload-session endpoints, signed
    delivery endpoints, background image processing, or generated variants.
  - CSV export remains data-only and does not include images.

## Summary

- Move new image uploads from ad hoc client-provided URLs to a managed private object storage pipeline.
- Keep legacy Firebase image URLs readable during transition.
- Optimize retrieval with generated image variants and CDN-backed signed delivery.
- Improve security, reliability, and cost control before removing Firebase Storage dependency.

## Working Assumptions

- Auth remains Firebase ID token based for now.
- Preferred target for new uploads is S3-compatible private object storage plus
  CDN.
- Access should be private by default with short-lived signed delivery.
- Legacy Firebase image references must stay readable during migration.
- Variants such as `thumb`, `medium`, and `original` are future design targets,
  not implemented features.
- A `10 MB` image limit and a constrained format allowlist are reasonable
  default targets, but they are not yet enforced by the current backend.

## Current State

- `formula_images` already supports `storage_provider`, `public_url`, and `object_key`.
- Clients currently submit image references through formula payloads.
- The backend stores those references but does not own an upload lifecycle.
- There is no server-side validation for file type, file size, checksum, or upload completion.
- There is no image processing pipeline for thumbnails or optimized list views.
- Account deletion attempts Firebase object cleanup, but normal image replacement/removal does not have a durable delete workflow.

## Primary Risks In Current Flow

- Security: client-controlled `file://` and arbitrary remote URLs are treated as image references.
- Reliability: the app can save references to images that were never uploaded or later disappear.
- Performance: list views may load full-size images because there are no variants.
- Scalability: app servers do not control storage metadata, upload status, or cleanup lifecycle.
- Cost: no lifecycle rules, dedupe strategy, or CDN-aware delivery strategy.

## Target Architecture

### 1) Storage and delivery

- Use a private S3-compatible bucket such as Cloudflare R2 or AWS S3.
- Store images with server-generated random object keys, never user-supplied paths.
- Put a CDN in front of the storage origin for cached delivery.
- Serve images through short-lived signed URLs or signed cookies after ownership checks.
- Configure CDN caching so signature differences do not eliminate cache usefulness.

### 2) Upload flow

- Client requests an upload session from the backend.
- Backend returns a presigned upload target, canonical object key, upload ID, and required headers.
- Client uploads directly to object storage instead of proxying bytes through the API.
- Client calls a completion endpoint after upload.
- Backend verifies object existence, size, content type, checksum, and ownership before marking the image usable.

### 3) Processing flow

- A background worker processes completed uploads.
- Extract metadata: width, height, bytes, mime type, checksum.
- Normalize orientation and strip EXIF where appropriate.
- Generate `thumb` and `medium` variants from the original.
- Mark processing status so the UI can gracefully handle pending or failed images.

### 4) Retrieval flow

- Formula records store canonical image references, not raw device file paths.
- UI requests signed delivery URLs for the needed variant.
- List views use `thumb`.
- Detail views use `medium` first, with `original` only when needed.

## Proposed API Changes

- `POST /api/v1/images/uploads`
  Returns upload metadata for a single image: `upload_id`, `object_key`, upload URL, required headers, expiration, and intended variant policy.

- `POST /api/v1/images/uploads/{upload_id}/complete`
  Verifies the uploaded object, records metadata, and returns a stable `image_id`.

- `GET /api/v1/images/{image_id}/url?variant=thumb|medium|original`
  Returns a short-lived signed delivery URL after ownership validation.

- Formula create/update payloads
  Prefer `image_ids` for new images. Keep legacy `public_url` support only for already-migrated Firebase records during transition.

## Proposed Schema Changes

- Keep `formula_images` as the attachment table for formulas.
- Add metadata columns needed for control and retrieval:
  - `content_type`
  - `byte_size`
  - `width`
  - `height`
  - `checksum_sha256`
  - `status`
  - `storage_bucket`
  - `variant_group`
  - `uploaded_at`
  - `processed_at`
  - `deleted_at`
- Add a uniqueness guard where useful, such as checksum + owner scope, once dedupe rules are finalized.

## Security Controls

- Reject new `file://` references and arbitrary third-party image URLs.
- Allow uploads only through presigned targets minted for an authenticated owner.
- Enforce upload size limits at both CDN/storage policy layer and backend validation layer.
- Validate file type with content inspection, not extension alone.
- Generate server-side object keys and ignore user-provided storage paths.
- Keep buckets private and require short URL expiry for delivery.
- Log upload completion, validation failures, signed URL minting, and delete failures.
- Avoid exposing long-lived public Firebase-style tokenized URLs for new uploads.

## Reliability and Ops Controls

- Track upload state with clear statuses such as `pending`, `ready`, `failed`, and `deleted`.
- Make cleanup asynchronous with retries for image removal and account deletion.
- Add lifecycle rules for abandoned uploads and deleted images.
- Record enough metadata to reconcile storage objects against database rows.
- Add metrics for upload failures, processing failures, delete failures, and signed URL latency.

## Migration Strategy

### Phase 1: Dual-read foundation

- Keep serving existing Firebase-backed `public_url` records.
- Start writing all new uploads to S3-compatible storage.
- Store provider plus canonical object key for all new images.

### Phase 2: Delivery hardening

- Introduce signed retrieval for new storage-backed images.
- Update mobile screens to request variants instead of assuming raw stored URLs.

### Phase 3: Cleanup and processing

- Add variant generation, metadata extraction, and delete worker flows.
- Backfill metadata for new images if early uploads landed before processing was added.

### Phase 4: Optional legacy migration

- Copy Firebase objects into the new storage system in batches.
- Update rows to canonical object keys after verification.
- Remove Firebase Storage dependency only after target coverage is reached.

## Recommended First Implementation Slice

- Add storage configuration and a provider abstraction in the backend.
- Add upload session creation and upload completion endpoints.
- Add new metadata/status columns to `formula_images`.
- Update the mobile app to upload through the new flow and send `image_ids` for newly attached images.
- Continue reading legacy Firebase URLs so current data keeps working.

## Test Plan

- Backend unit tests for object-key generation, upload validation, signed URL generation, and ownership checks.
- Backend integration tests for successful upload completion, invalid content rejection, oversize rejection, and formula attachment flow.
- Processing tests for variant creation and metadata extraction.
- Frontend tests for upload progress, retry handling, and using thumbnail URLs in list screens.
- End-to-end test for deleting an image and verifying asynchronous cleanup is scheduled.

## Readiness Checklist

- Choose concrete provider pair: `R2 + Cloudflare CDN` or `S3 + CloudFront`.
- Confirm background worker approach for processing and deletion jobs.
- Confirm image library choice for metadata extraction and variant generation.
- Add environment variables and secret handling for storage credentials.
- Decide whether checksum-based dedupe is desired in v1 or deferred.

## When Ready To Start

1. Add the storage provider abstraction and config.
2. Create the migration for new `formula_images` metadata fields.
3. Implement `POST /images/uploads` and `POST /images/uploads/{upload_id}/complete`.
4. Update the mobile app to stop sending raw `file://` image references.
5. Add signed retrieval for storage-backed images.

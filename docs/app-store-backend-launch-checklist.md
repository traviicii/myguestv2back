# App Store Backend Launch Checklist

This is the backend gate for shipping the iOS app with confidence.

## Release blockers

- [x] Firebase bearer-token auth is the single auth path.
- [x] Account deletion exists and revokes Firebase sessions before local delete.
- [x] Data export endpoint exists for authenticated users.
- [x] Health endpoint performs real readiness checks for database and auth backend.
- [ ] Remote smoke test is run against the deployed Render API before each release.
  Workflow: `.github/workflows/render-smoke.yml`
- [ ] Production env is confirmed with `TRUSTED_HOSTS`, `CORS_ORIGINS`, Firebase credentials, and storage bucket.
- [ ] Production backend is not running on Render Starter for the public App Store launch.
- [ ] Production database plan has enough headroom for the chosen worker count.

## Operational readiness

- [x] Database pool settings are explicit instead of relying on SQLAlchemy defaults.
- [ ] Render deploy flow separates migrations from scaled web boot.
- [ ] Health endpoint is used by uptime monitoring.
- [ ] Error monitoring is configured for backend exceptions and elevated 5xx rates.
- [x] API responses include `X-Request-ID` for traceability across client and backend logs.
- [ ] Database backup and restore drill has a recent successful run.
- [ ] Rollback steps are documented for both app code and database migrations.
- [ ] Worker count and DB pool sizing are documented for the production instance class.

## Security and privacy

- [ ] `/docs`, `/redoc`, and `/openapi.json` stay disabled in production unless intentionally exposed.
- [ ] Only expected frontend origins are allowed in `CORS_ORIGINS`.
- [x] Targeted rate limits protect `auth/sync`, exports, and account deletion paths.
- [ ] Exported archives are tested with real user data and stay scoped to the authenticated owner.
- [ ] Storage cleanup failures are logged and reviewed so account deletion does not silently leak data.

## Product-level backend checks

- [ ] Auth sync works for a new Firebase user.
- [ ] Auth sync still works for legacy linked users.
- [ ] Client CRUD and ownership checks pass against production-like data.
- [ ] Formula list endpoints are using the lighter query options expected by mobile screens.
- [ ] Metrics endpoint performance is acceptable with production-sized accounts.

## Recommended next steps

1. Add alerting for repeated 5xx responses and failed auth-provider readiness checks.
2. Add durable shared rate limiting if the API will scale beyond a single app instance.
3. Add explicit Sentry or equivalent exception monitoring on the deployed backend.
4. Record the last successful restore drill and smoke-gate run before App Store submission.
5. Move production hosting to the Render baseline documented in `docs/render-production-baseline.md`.

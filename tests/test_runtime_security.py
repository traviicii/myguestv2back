from fastapi.testclient import TestClient

from app.api.deps import get_token_verifier
from app.core.errors import AppError
from app.core.config import Settings
from app.main import create_app


def test_development_keeps_docs_enabled_by_default():
    app = create_app(Settings(database_url="sqlite+pysqlite://"))

    with TestClient(app) as client:
        docs = client.get("/docs")
        openapi = client.get("/openapi.json")

    assert docs.status_code == 200
    assert openapi.status_code == 200


def test_production_disables_docs_and_openapi():
    app = create_app(
        Settings(
            app_env="production",
            database_url="sqlite+pysqlite://",
            trusted_hosts=["api.example.com"],
        )
    )

    with TestClient(app, base_url="https://api.example.com") as client:
        docs = client.get("/docs")
        redoc = client.get("/redoc")
        openapi = client.get("/openapi.json")

    assert docs.status_code == 404
    assert redoc.status_code == 404
    assert openapi.status_code == 404


def test_production_requires_explicit_trusted_hosts():
    try:
        create_app(
            Settings(
                app_env="production",
                database_url="sqlite+pysqlite://",
            )
        )
    except ValueError as exc:
        assert str(exc) == "Production requires TRUSTED_HOSTS to be configured."
    else:
        raise AssertionError("Production app boot should fail without TRUSTED_HOSTS.")


def test_trusted_host_middleware_rejects_unconfigured_hosts():
    app = create_app(
        Settings(
            app_env="production",
            database_url="sqlite+pysqlite://",
            trusted_hosts=["api.example.com"],
        )
    )

    with TestClient(app, base_url="https://api.example.com") as client:
        ok = client.get("/")
        blocked = client.get("/", headers={"host": "evil.example.com"})

    assert ok.status_code == 200
    assert blocked.status_code == 400


def test_health_reports_database_and_auth_checks(client):
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "checks": {
            "database": "ok",
            "auth": "ok",
        },
    }


def test_health_returns_503_when_auth_backend_is_not_ready(client):
    class BrokenVerifier:
        def check_ready(self):
            raise AppError(
                503,
                "auth_provider_unavailable",
                "Firebase auth backend is not ready.",
            )

    original_override = client.app.dependency_overrides.get(get_token_verifier)
    client.app.dependency_overrides[get_token_verifier] = lambda: BrokenVerifier()
    try:
        response = client.get("/api/v1/health")
    finally:
        if original_override is None:
            client.app.dependency_overrides.pop(get_token_verifier, None)
        else:
            client.app.dependency_overrides[get_token_verifier] = original_override

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "auth_provider_unavailable"


def test_request_id_header_is_echoed_on_unexpected_errors():
    app = create_app(Settings(database_url="sqlite+pysqlite://"))

    @app.get("/api/v1/test-crash")
    def crash():
        raise RuntimeError("boom")

    with TestClient(app, raise_server_exceptions=False) as crash_client:
        response = crash_client.get(
            "/api/v1/test-crash",
            headers={"X-Request-ID": "launch-check-123"},
        )

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_server_error"
    assert response.headers["x-request-id"] == "launch-check-123"


def test_auth_sync_rate_limit_returns_429(client):
    client.app.state.rate_limiter.enabled = True
    client.app.state.rate_limiter.window_seconds = 60
    client.app.state.rate_limiter.rules["auth_sync"].limit = 1

    first = client.post("/api/v1/auth/sync", headers={"Authorization": "Bearer token-user-1"})
    second = client.post("/api/v1/auth/sync", headers={"Authorization": "Bearer token-user-1"})

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.json()["error"]["code"] == "rate_limited"
    assert second.json()["error"]["details"]["scope"] == "auth_sync"
    assert "retry_after_seconds" in second.json()["error"]["details"]
    assert second.headers["retry-after"]
    assert second.headers["x-request-id"]

from fastapi.testclient import TestClient

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

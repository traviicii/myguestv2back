from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_token_verifier
from app.core.config import Settings
from app.db.base import Base
from app.db.import_models import (  # noqa: F401
    Client,
    ColorChart,
    Formula,
    FormulaImage,
    FormulaService,
    Service,
    User,
)
from app.main import create_app


class FakeVerifier:
    TOKENS = {
        "token-user-1": {
            "uid": "uid-1",
            "email": "one@example.com",
            "email_verified": True,
            "name": "User One",
        },
        "token-user-2": {
            "uid": "uid-2",
            "email": "two@example.com",
            "email_verified": True,
            "name": "User Two",
        },
        "token-link-legacy": {
            "uid": "uid-legacy-linked",
            "email": "legacy@example.com",
            "email_verified": True,
            "name": "Legacy User",
        },
        "token-conflict": {
            "uid": "uid-conflict-new",
            "email": "conflict@example.com",
            "email_verified": True,
            "name": "Conflict User",
        },
    }

    def verify(self, token: str) -> dict:
        claims = self.TOKENS.get(token)
        if not claims:
            from app.core.errors import AppError

            raise AppError(401, "invalid_token", "Invalid or expired auth token.")
        return claims


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    settings = Settings(database_url="sqlite+pysqlite://")
    app = create_app(settings=settings)

    app.dependency_overrides[get_token_verifier] = lambda: FakeVerifier()
    app.state.engine = engine
    app.state.session_factory = session_factory

    with TestClient(app) as test_client:
        yield test_client

    Base.metadata.drop_all(bind=engine)
    engine.dispose()

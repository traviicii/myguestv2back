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
    REVOKED_UIDS: set[str] = set()
    DISABLED_UIDS: set[str] = set()
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
        uid = claims.get("uid")
        if uid in self.DISABLED_UIDS:
            from app.core.errors import AppError

            raise AppError(
                403,
                "auth_user_disabled",
                "This Firebase account is disabled. Contact support if you need help.",
            )
        if uid in self.REVOKED_UIDS:
            from app.core.errors import AppError

            raise AppError(
                401,
                "auth_session_revoked",
                "This auth session has been revoked. Please sign in again.",
            )
        return claims

    def check_ready(self) -> None:
        return None


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    FakeVerifier.REVOKED_UIDS.clear()
    FakeVerifier.DISABLED_UIDS.clear()

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
    app.state.fake_token_verifier = FakeVerifier
    app.state.engine = engine
    app.state.session_factory = session_factory

    with TestClient(app) as test_client:
        yield test_client

    FakeVerifier.REVOKED_UIDS.clear()
    FakeVerifier.DISABLED_UIDS.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()

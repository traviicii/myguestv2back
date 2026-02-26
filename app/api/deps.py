from collections.abc import Generator
from typing import Any

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.session import get_db
from app.models import User

bearer_scheme = HTTPBearer(auto_error=False)


def get_session(request: Request) -> Generator[Session, None, None]:
    yield from get_db(request.app.state.session_factory)


def get_token_verifier(request: Request):
    return request.app.state.token_verifier


def get_token_claims(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    token_verifier=Depends(get_token_verifier),
) -> dict[str, Any]:
    if credentials is None:
        raise AppError(401, "auth_required", "Missing Bearer token.")
    try:
        return token_verifier.verify(credentials.credentials)
    except AppError:
        raise
    except Exception as exc:
        raise AppError(401, "invalid_token", "Invalid or expired auth token.") from exc


def get_current_user(
    claims: dict[str, Any] = Depends(get_token_claims),
    db: Session = Depends(get_session),
) -> User:
    uid = claims.get("uid")
    if not uid:
        raise AppError(401, "invalid_token", "Auth token is missing uid claim.")

    user = db.scalar(select(User).where(User.firebase_uid == uid))
    if not user:
        raise AppError(
            401,
            "user_not_registered",
            "No MyGuest account exists for this authenticated user. Call /auth/sync first.",
        )
    return user

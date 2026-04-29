from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_session, get_token_verifier
from app.core.errors import AppError

router = APIRouter(tags=["health"])


@router.get("/health")
def health(
    db: Session = Depends(get_session),
    token_verifier: Any = Depends(get_token_verifier),
) -> dict[str, object]:
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        raise AppError(
            503,
            "database_unavailable",
            "Database readiness check failed.",
        ) from exc

    if hasattr(token_verifier, "check_ready"):
        try:
            token_verifier.check_ready()
        except AppError:
            raise
        except Exception as exc:
            raise AppError(
                503,
                "auth_provider_unavailable",
                "Auth provider readiness check failed.",
            ) from exc

    return {
        "status": "ok",
        "checks": {
            "database": "ok",
            "auth": "ok",
        },
    }

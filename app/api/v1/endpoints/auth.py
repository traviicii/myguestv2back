from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_session, get_token_claims
from app.core.errors import AppError
from app.models import User
from app.schemas.user import AuthSessionResponse, UserRead

router = APIRouter(prefix="/auth", tags=["auth"])


def _split_name(display_name: str | None) -> tuple[str | None, str | None]:
    if not display_name:
        return None, None
    parts = display_name.split()
    if len(parts) == 1:
        return parts[0], None
    return parts[0], " ".join(parts[1:])


@router.post("/sync", response_model=AuthSessionResponse)
def sync_user_session(
    claims: dict = Depends(get_token_claims),
    db: Session = Depends(get_session),
) -> AuthSessionResponse:
    uid = claims.get("uid")
    if not uid:
        raise AppError(401, "invalid_token", "Auth token is missing uid claim.")
    email = claims.get("email")
    normalized_email = email.lower() if isinstance(email, str) else None
    email_verified = bool(claims.get("email_verified"))
    first_name, last_name = _split_name(claims.get("name"))
    photo_url = claims.get("picture")

    user = db.scalar(select(User).where(User.firebase_uid == uid))
    is_new_user = False

    # Transitional migration behavior:
    # link legacy users that have no firebase_uid by verified email on first login.
    if not user and normalized_email and email_verified:
        user_by_email = db.scalar(select(User).where(func.lower(User.email) == normalized_email))
        if user_by_email:
            if user_by_email.firebase_uid and user_by_email.firebase_uid != uid:
                raise AppError(
                    409,
                    "auth_identity_conflict",
                    "This email is already linked to a different auth identity.",
                )
            user = user_by_email
            user.firebase_uid = uid

    if not user:
        is_new_user = True
        user = User(
            firebase_uid=uid,
            email=normalized_email or f"{uid}@placeholder.local",
            first_name=first_name,
            last_name=last_name,
            photo_url=photo_url,
        )
        db.add(user)
    else:
        if normalized_email and email_verified:
            user.email = normalized_email
        user.first_name = first_name or user.first_name
        user.last_name = last_name or user.last_name
        user.photo_url = photo_url or user.photo_url

    db.commit()
    db.refresh(user)

    return AuthSessionResponse(user=UserRead.model_validate(user), is_new_user=is_new_user)

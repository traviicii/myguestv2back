from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_session
from app.core.config import get_settings
from app.core.errors import AppError
from app.models import Client, Formula, FormulaImage, User
from app.schemas.user import AccountDeleteRequest, AccountDeleteResponse
from app.services.storage_cleanup import (
    delete_firebase_images,
    delete_firebase_user,
    revoke_firebase_tokens,
)

router = APIRouter(prefix="/account", tags=["account"])


@router.post("/delete", response_model=AccountDeleteResponse)
def delete_account(
    payload: AccountDeleteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> AccountDeleteResponse:
    if not payload.email:
        raise AppError(400, "email_required", "Email is required to delete this account.")
    if payload.email.strip().lower() != current_user.email.lower():
        raise AppError(400, "email_mismatch", "Email does not match this account.")

    images = list(
        db.scalars(
            select(FormulaImage)
            .join(Formula, Formula.id == FormulaImage.formula_id)
            .join(Client, Client.id == Formula.client_id)
            .where(Client.owner_user_id == current_user.id)
        ).all()
    )
    firebase_uid = current_user.firebase_uid

    # Revoke issued Firebase sessions before deleting the local account so a
    # stale ID token cannot silently recreate the user via /auth/sync.
    if firebase_uid and not revoke_firebase_tokens(firebase_uid):
        raise AppError(
            502,
            "auth_revocation_failed",
            "Unable to secure this sign-in session for account deletion. Please try again.",
        )

    db.delete(current_user)
    db.commit()

    settings = get_settings()
    cleanup = delete_firebase_images(images, settings.firebase_storage_bucket)
    firebase_user_deleted = delete_firebase_user(firebase_uid)

    return AccountDeleteResponse(
        deleted=True,
        images_deleted=cleanup.deleted,
        images_failed=cleanup.failed,
        firebase_user_deleted=firebase_user_deleted,
    )

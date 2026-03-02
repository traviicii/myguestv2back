from urllib.parse import unquote, urlparse

from fastapi import APIRouter, Depends
from firebase_admin import auth as firebase_auth, storage as firebase_storage
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_session
from app.core.config import get_settings
from app.core.errors import AppError
from app.models import Client, Formula, FormulaImage, User
from app.schemas.user import AccountDeleteRequest, AccountDeleteResponse

router = APIRouter(prefix="/account", tags=["account"])

def _extract_storage_target(public_url: str | None, object_key: str | None):
    if object_key:
        return None, object_key.lstrip("/")
    if not public_url:
        return None, None

    trimmed = public_url.strip()
    if trimmed.startswith("gs://"):
        path = trimmed[len("gs://") :]
        bucket, _, object_path = path.partition("/")
        return bucket or None, object_path or None

    parsed = urlparse(trimmed)
    if "firebasestorage.googleapis.com" in parsed.netloc:
        # /v0/b/<bucket>/o/<encoded_path>
        if "/b/" in parsed.path and "/o/" in parsed.path:
            segment = parsed.path.split("/b/", 1)[1]
            bucket = segment.split("/", 1)[0]
            encoded = segment.split("/o/", 1)[1].split("/", 1)[0]
            return bucket or None, unquote(encoded)
    return None, None


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

    db.delete(current_user)
    db.commit()

    images_deleted = 0
    images_failed = 0

    bucket = None
    settings = get_settings()
    if settings.firebase_storage_bucket:
        try:
            bucket = firebase_storage.bucket(settings.firebase_storage_bucket)
        except Exception:
            bucket = None

    for image in images:
        provider = (image.storage_provider or "").strip().lower()
        if provider and provider != "firebase":
            continue
        bucket_name, object_path = _extract_storage_target(image.public_url, image.object_key)
        if not object_path:
            images_failed += 1
            continue

        target_bucket = bucket
        if bucket_name:
            try:
                target_bucket = firebase_storage.bucket(bucket_name)
            except Exception:
                target_bucket = None

        if target_bucket is None:
            images_failed += 1
            continue

        try:
            target_bucket.blob(object_path).delete()
            images_deleted += 1
        except Exception:
            images_failed += 1

    firebase_user_deleted = False
    if firebase_uid:
        try:
            firebase_auth.delete_user(firebase_uid)
            firebase_user_deleted = True
        except Exception:
            firebase_user_deleted = False

    return AccountDeleteResponse(
        deleted=True,
        images_deleted=images_deleted,
        images_failed=images_failed,
        firebase_user_deleted=firebase_user_deleted,
    )

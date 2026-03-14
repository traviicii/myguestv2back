import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any
from urllib.parse import unquote, urlparse

from firebase_admin import auth as firebase_auth
from firebase_admin import storage as firebase_storage

from app.models import FormulaImage

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StorageCleanupSummary:
    deleted: int
    failed: int


def extract_storage_target(public_url: str | None, object_key: str | None) -> tuple[str | None, str | None]:
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
    if (
        "firebasestorage.googleapis.com" in parsed.netloc
        and "/b/" in parsed.path
        and "/o/" in parsed.path
    ):
        segment = parsed.path.split("/b/", 1)[1]
        bucket = segment.split("/", 1)[0]
        encoded = segment.split("/o/", 1)[1].split("/", 1)[0]
        return bucket or None, unquote(encoded)
    return None, None


def delete_firebase_images(
    images: Sequence[FormulaImage],
    default_bucket_name: str | None,
    storage_module: Any | None = None,
) -> StorageCleanupSummary:
    storage_module = storage_module or firebase_storage
    deleted = 0
    failed = 0
    default_bucket = _resolve_bucket(storage_module, default_bucket_name)

    for image in images:
        provider = (image.storage_provider or "").strip().lower()
        if provider and provider != "firebase":
            continue

        bucket_name, object_path = extract_storage_target(image.public_url, image.object_key)
        if not object_path:
            failed += 1
            logger.warning(
                "Skipping image cleanup with no object path",
                extra={"image_id": image.id},
            )
            continue

        target_bucket = (
            default_bucket
            if bucket_name is None
            else _resolve_bucket(storage_module, bucket_name)
        )
        if target_bucket is None:
            failed += 1
            logger.warning(
                "Skipping image cleanup because bucket could not be resolved",
                extra={"image_id": image.id, "bucket_name": bucket_name},
            )
            continue

        try:
            target_bucket.blob(object_path).delete()
            deleted += 1
        except Exception:
            failed += 1
            logger.exception(
                "Failed to delete Firebase image",
                extra={
                    "image_id": image.id,
                    "bucket_name": bucket_name,
                    "object_path": object_path,
                },
            )

    return StorageCleanupSummary(deleted=deleted, failed=failed)


def delete_firebase_user(
    firebase_uid: str | None,
    auth_module: Any | None = None,
) -> bool:
    if not firebase_uid:
        return False

    auth_module = auth_module or firebase_auth
    try:
        auth_module.delete_user(firebase_uid)
        return True
    except Exception:
        logger.exception("Failed to delete Firebase user", extra={"firebase_uid": firebase_uid})
        return False


def _resolve_bucket(storage_module: Any, bucket_name: str | None):
    if not bucket_name:
        return None
    try:
        return storage_module.bucket(bucket_name)
    except Exception:
        logger.exception("Failed to resolve Firebase bucket", extra={"bucket_name": bucket_name})
        return None

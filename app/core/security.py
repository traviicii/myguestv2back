from typing import Any

import firebase_admin
from firebase_admin import auth, credentials

from app.core.config import Settings
from app.core.errors import AppError


class FirebaseTokenVerifier:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._initialized = False

    def _initialize(self) -> None:
        if self._initialized:
            return
        if not firebase_admin._apps:
            options: dict[str, str] | None = None
            if self.settings.firebase_storage_bucket:
                options = {"storageBucket": self.settings.firebase_storage_bucket}
            if self.settings.firebase_credentials_path:
                cred = credentials.Certificate(self.settings.firebase_credentials_path)
                firebase_admin.initialize_app(cred, options)
            else:
                firebase_admin.initialize_app(options=options)
        self._initialized = True

    def verify(self, token: str) -> dict[str, Any]:
        self._initialize()
        try:
            return auth.verify_id_token(token, check_revoked=True)
        except auth.RevokedIdTokenError as exc:
            raise AppError(
                401,
                "auth_session_revoked",
                "This auth session has been revoked. Please sign in again.",
            ) from exc
        except auth.UserDisabledError as exc:
            raise AppError(
                403,
                "auth_user_disabled",
                "This Firebase account is disabled. Contact support if you need help.",
            ) from exc
        except auth.UserNotFoundError as exc:
            raise AppError(
                401,
                "auth_session_revoked",
                "This auth session is no longer valid. Please sign in again.",
            ) from exc
        except Exception as exc:
            raise AppError(401, "invalid_token", "Invalid or expired auth token.") from exc

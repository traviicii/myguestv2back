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
            if self.settings.firebase_credentials_path:
                cred = credentials.Certificate(self.settings.firebase_credentials_path)
                firebase_admin.initialize_app(cred)
            else:
                firebase_admin.initialize_app()
        self._initialized = True

    def verify(self, token: str) -> dict[str, Any]:
        self._initialize()
        try:
            return auth.verify_id_token(token)
        except Exception as exc:
            raise AppError(401, "invalid_token", "Invalid or expired auth token.") from exc

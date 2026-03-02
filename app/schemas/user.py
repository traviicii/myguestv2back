from pydantic import BaseModel

from app.schemas.common import ORMModel


class UserRead(ORMModel):
    id: int
    firebase_uid: str
    email: str
    first_name: str | None = None
    last_name: str | None = None
    photo_url: str | None = None


class AuthSessionResponse(ORMModel):
    user: UserRead
    is_new_user: bool


class AccountDeleteRequest(BaseModel):
    email: str


class AccountDeleteResponse(ORMModel):
    deleted: bool
    images_deleted: int
    images_failed: int
    firebase_user_deleted: bool

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

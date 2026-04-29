from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings


def build_engine_kwargs(database_url: str, settings: Settings) -> dict:
    kwargs: dict[str, object] = {"pool_pre_ping": True}
    if database_url.startswith("sqlite"):
        return kwargs

    kwargs.update(
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout_seconds,
        pool_recycle=settings.db_pool_recycle_seconds,
        pool_use_lifo=settings.db_pool_use_lifo,
    )
    return kwargs


def build_engine(settings: Settings):
    return create_engine(
        settings.database_url,
        **build_engine_kwargs(settings.database_url, settings),
    )


def build_session_maker(engine):
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)


def get_db(session_factory) -> Generator[Session, None, None]:
    db = session_factory()
    try:
        yield db
    finally:
        db.close()

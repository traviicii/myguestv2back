from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


def build_engine(database_url: str):
    return create_engine(database_url, pool_pre_ping=True)


def build_session_maker(engine):
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)


def get_db(session_factory) -> Generator[Session, None, None]:
    db = session_factory()
    try:
        yield db
    finally:
        db.close()

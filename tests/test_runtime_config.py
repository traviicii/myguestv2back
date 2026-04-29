from app.core.config import Settings
from app.db.session import build_engine_kwargs


def test_postgres_engine_kwargs_use_explicit_pool_settings():
    settings = Settings(
        database_url="postgresql://postgres:postgres@localhost:5432/myguestv2",
        db_pool_size=7,
        db_max_overflow=3,
        db_pool_timeout_seconds=45,
        db_pool_recycle_seconds=900,
        db_pool_use_lifo=False,
    )

    kwargs = build_engine_kwargs(settings.database_url, settings)

    assert kwargs == {
        "pool_pre_ping": True,
        "pool_size": 7,
        "max_overflow": 3,
        "pool_timeout": 45,
        "pool_recycle": 900,
        "pool_use_lifo": False,
    }


def test_sqlite_engine_kwargs_skip_queue_pool_tuning():
    settings = Settings(database_url="sqlite+pysqlite://")

    kwargs = build_engine_kwargs(settings.database_url, settings)

    assert kwargs == {"pool_pre_ping": True}

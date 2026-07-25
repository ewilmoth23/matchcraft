from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


def _engine_kwargs(database_url: str) -> dict[str, object]:
    return (
        {"connect_args": {"check_same_thread": False}} if database_url.startswith("sqlite") else {}
    )


settings = get_settings()
engine = create_engine(
    settings.database_url, pool_pre_ping=True, **_engine_kwargs(settings.database_url)
)


if settings.database_url.startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def _configure_sqlite(dbapi_connection: object, _: object) -> None:
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        # Write-ahead logging lets a read proceed during a write, and an explicit busy
        # timeout turns a brief lock contention into a wait instead of a 500.
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()
        # SQLite creates the database and its WAL/SHM companions world-readable, and
        # they hold the résumé and job text. They only exist once a connection has been
        # made, so tightening them at startup would be a no-op on a first run.
        settings.restrict_database_permissions()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session

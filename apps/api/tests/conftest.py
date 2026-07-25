import os
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

BOOTSTRAP_DIR = Path(tempfile.mkdtemp(prefix="matchcraft-test-bootstrap-"))
os.environ["MATCHCRAFT_ENV"] = "test"
os.environ["MATCHCRAFT_DATABASE_URL"] = f"sqlite:///{BOOTSTRAP_DIR / 'bootstrap.db'}"
os.environ["MATCHCRAFT_DATA_DIR"] = str(BOOTSTRAP_DIR)
os.environ["MATCHCRAFT_PROVIDER"] = "disabled"
# TestClient sends Host: testserver. That belongs here, not in the shipped example
# environment, where it would appear in a user's production allow-list.
os.environ["MATCHCRAFT_ALLOWED_HOSTS"] = "localhost,127.0.0.1,testserver"

from app.core.config import Settings, get_settings  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture
def sample_resume_text() -> str:
    return (Path(__file__).parents[3] / "sample_data" / "technical_resume.txt").read_text()


@pytest.fixture
def sample_job_text() -> str:
    return (Path(__file__).parents[3] / "sample_data" / "software_engineer_job.txt").read_text()


@pytest.fixture
def client(tmp_path: Path) -> Generator[TestClient, None, None]:
    database_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{database_path}", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection: object, _: object) -> None:
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)
    settings = Settings(
        env="test",
        database_url=f"sqlite:///{database_path}",
        data_dir=tmp_path / "data",
        provider="disabled",
    )
    settings.ensure_directories()

    def override_db() -> Generator[Session, None, None]:
        with TestingSession() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_settings] = lambda: settings
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()

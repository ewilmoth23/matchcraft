"""Run an isolated migrated API instance for the full-stack Playwright test."""

import os
import sys
import tempfile
from pathlib import Path

import uvicorn
from alembic.config import Config

from alembic import command

ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "apps" / "api"


def main() -> None:
    port = int(os.environ.get("MATCHCRAFT_E2E_API_PORT", "8001"))
    with tempfile.TemporaryDirectory(prefix="matchcraft-full-stack-e2e-") as data_dir:
        database_path = Path(data_dir) / "matchcraft.db"
        os.environ.update(
            {
                "MATCHCRAFT_ENV": "test",
                "MATCHCRAFT_DATABASE_URL": f"sqlite:///{database_path}",
                "MATCHCRAFT_DATA_DIR": data_dir,
                "MATCHCRAFT_PROVIDER": "disabled",
                "MATCHCRAFT_CORS_ORIGINS": "http://127.0.0.1:4173",
            }
        )
        sys.path.insert(0, str(API_ROOT))
        command.upgrade(Config(str(API_ROOT / "alembic.ini")), "head")

        from app.main import app

        uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()

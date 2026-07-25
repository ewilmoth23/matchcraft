import ast
from pathlib import Path

import pytest
from alembic.config import Config

from alembic import command
from app.core.config import get_settings


def test_initial_migration_is_frozen_and_independent_of_live_models() -> None:
    migration_path = Path(__file__).parents[1] / "alembic" / "versions" / "0001_initial.py"
    source = migration_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }

    assert "app" not in imports
    assert "models" not in imports
    assert "Base" not in source
    assert "metadata.create_all" not in source
    assert "op.create_table" in source


def test_application_startup_does_not_auto_create_schema() -> None:
    main_source = (Path(__file__).parents[1] / "app" / "main.py").read_text(encoding="utf-8")

    assert "metadata.create_all" not in main_source


def test_migration_bootstraps_a_missing_data_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    api_root = Path(__file__).parents[1]
    data_dir = tmp_path / "missing" / "nested" / "data"
    database_path = data_dir / "matchcraft.db"
    monkeypatch.setenv("MATCHCRAFT_DATA_DIR", str(data_dir))
    monkeypatch.setenv("MATCHCRAFT_DATABASE_URL", f"sqlite:///{database_path}")
    monkeypatch.setenv("MATCHCRAFT_PROVIDER", "disabled")
    get_settings.cache_clear()
    config = Config(str(api_root / "alembic.ini"))
    config.set_main_option("script_location", str(api_root / "alembic"))

    try:
        command.upgrade(config, "head")
    finally:
        get_settings.cache_clear()

    assert database_path.is_file()
    assert (data_dir / "uploads").is_dir()
    assert (data_dir / "exports").is_dir()

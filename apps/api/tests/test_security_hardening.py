"""Regression tests for the hardening applied after the 2026-07-24 expert review.

Each test names the defect it prevents from returning.
"""

import io
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from pytest import MonkeyPatch
from sqlalchemy import create_engine, event, text

from app.core.config import Settings, get_settings, validate_provider_url
from app.providers.http import HTTPModelProvider


def _settings(tmp_path: Path, **overrides: object) -> Settings:
    values: dict[str, object] = {
        "env": "test",
        "database_url": f"sqlite:///{tmp_path / 'x.db'}",
        "data_dir": tmp_path / "data",
        "provider": "disabled",
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def _pin_environment_base_url(monkeypatch: MonkeyPatch, url: str) -> None:
    """Pin the env-configured remote endpoint that the credential is bound to.

    `credential_host_trusted` compares against `get_settings()`, which is cached
    against the process environment, so the cache has to be cleared for the
    assertion to mean anything.
    """
    monkeypatch.setenv("MATCHCRAFT_OPENAI_BASE_URL", url)
    get_settings.cache_clear()
    # A developer's local .env would otherwise win over the pinned value.
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    get_settings.cache_clear()
    assert get_settings().openai_base_url == url.rstrip("/")


@pytest.fixture(autouse=True)
def _reset_settings_cache() -> object:
    yield None
    get_settings.cache_clear()


def test_api_key_is_not_sent_to_a_runtime_overridden_host(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """A redirected provider URL must not carry the environment's API key."""
    _pin_environment_base_url(monkeypatch, "https://api.openai.com/v1")
    redirected = _settings(
        tmp_path,
        provider="openai_compatible",
        openai_base_url="http://198.51.100.7:8080/v1",
        openai_api_key="sk-must-not-leak",
    )
    provider = HTTPModelProvider(redirected, "openai_compatible")
    assert provider.credential_host_trusted is False
    assert "Authorization" not in provider._headers()


@pytest.mark.parametrize(
    ("environment_url", "runtime_url"),
    [
        # Identical, and the two spellings of the same origin that must still match.
        ("https://api.openai.com/v1", "https://api.openai.com/v1"),
        ("https://api.openai.com:443/v1", "https://api.openai.com/v1"),
        ("https://api.openai.com/v1", "https://API.OpenAI.com/v1"),
        ("http://gateway.internal:80/v1", "http://gateway.internal/v1"),
    ],
)
def test_api_key_is_sent_to_the_configured_host(
    tmp_path: Path, monkeypatch: MonkeyPatch, environment_url: str, runtime_url: str
) -> None:
    _pin_environment_base_url(monkeypatch, environment_url)
    configured = _settings(
        tmp_path,
        provider="openai_compatible",
        openai_base_url=runtime_url,
        openai_api_key="sk-configured",
    )
    provider = HTTPModelProvider(configured, "openai_compatible")
    assert provider.credential_host_trusted is True
    assert provider._headers()["Authorization"] == "Bearer sk-configured"


@pytest.mark.parametrize(
    "url",
    [
        "http://169.254.169.254/latest",
        "http://[fe80::1]/v1",
        "http://metadata.google.internal/v1",
        "ftp://example.test/v1",
        "http://user:pass@example.test/v1",
    ],
)
def test_unsafe_provider_urls_are_rejected(url: str) -> None:
    with pytest.raises(ValueError):
        validate_provider_url(url)


def test_settings_endpoint_rejects_link_local_provider_url(client: TestClient) -> None:
    response = client.put(
        "/api/v1/settings", json={"remote_provider_url": "http://169.254.169.254/v1"}
    )
    assert response.status_code == 422


def test_wildcard_cors_origin_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValidationError):
        _settings(tmp_path, cors_origins=["*"])


def test_data_directory_and_database_are_not_world_readable(tmp_path: Path) -> None:
    """Exercises the real startup order: the database does not exist beforehand."""
    settings = _settings(tmp_path)
    settings.ensure_directories()
    assert settings.data_dir.stat().st_mode & 0o077 == 0

    database = Path(settings.database_url.split("sqlite:///", 1)[-1])
    assert not database.exists()

    engine = create_engine(settings.database_url)

    @event.listens_for(engine, "connect")
    def _tighten(_connection: object, _record: object) -> None:
        settings.restrict_database_permissions()

    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    engine.dispose()

    assert database.exists()
    for companion in (database, *database.parent.glob(f"{database.name}-*")):
        assert companion.stat().st_mode & 0o077 == 0, companion


def test_api_responses_carry_baseline_security_headers(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert response.headers["Cache-Control"] == "no-store"


def test_unknown_host_is_rejected(client: TestClient) -> None:
    """Blocks DNS rebinding: an attacker-controlled name must not be same-origin."""
    response = client.get("/api/v1/health", headers={"Host": "attacker.example"})
    assert response.status_code == 400


def _docx_with_doctype_in(part: str) -> bytes:
    buffer = io.BytesIO()
    doctype = b'<?xml version="1.0"?><!DOCTYPE t [<!ENTITY x "y">]><t/>'
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", "<document/>")
        archive.writestr(part, doctype)
    return buffer.getvalue()


def test_doctype_in_a_non_document_part_is_rejected(client: TestClient) -> None:
    """python-docx parses styles and relationships too, not only word/document.xml."""
    response = client.post(
        "/api/v1/resumes/upload",
        files={
            "file": ("resume.docx", _docx_with_doctype_in("word/styles.xml"), "application/zip")
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "unsafe_docx"


def test_oversized_upload_is_rejected_before_the_body_is_buffered(
    client: TestClient, monkeypatch: MonkeyPatch
) -> None:
    """The rejection must happen in middleware; a route guard runs after spooling."""
    import starlette.datastructures

    spooled = 0
    original_write = starlette.datastructures.UploadFile.write

    async def counting_write(self: object, data: bytes) -> None:
        nonlocal spooled
        spooled += len(data)
        await original_write(self, data)  # type: ignore[arg-type]

    monkeypatch.setattr(starlette.datastructures.UploadFile, "write", counting_write)

    limit = client.get("/api/v1/settings").json()["max_upload_bytes"]
    response = client.post(
        "/api/v1/resumes/upload",
        files={"file": ("resume.pdf", b"%PDF-1.4" + b"0" * 32, "application/pdf")},
        headers={"Content-Length": str(limit * 4)},
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "file_too_large"
    assert spooled == 0, f"{spooled} bytes were buffered before the request was rejected"

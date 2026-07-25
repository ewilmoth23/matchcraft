import pytest
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import ApplicationSetting
from app.services.runtime_settings import RUNTIME_SETTINGS_KEY, runtime_settings


def test_local_first_defaults_are_provider_specific(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MATCHCRAFT_PROVIDER")
    settings = Settings(_env_file=None)

    assert settings.provider == "local_first"
    assert settings.model == "qwen3.5:9b"
    assert settings.remote_model == "gpt-5.6-sol"
    assert settings.openai_reasoning_effort == "low"
    assert settings.ollama_context_tokens == 32768
    assert settings.model_temperature == 0
    assert settings.model_max_tokens == 3000
    assert settings.model_timeout_seconds == 180
    assert settings.remote_provider_configured is False


def test_cors_origins_accept_documented_comma_separated_environment(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "MATCHCRAFT_CORS_ORIGINS",
        "http://localhost:5173, http://127.0.0.1:5173",
    )

    settings = Settings(_env_file=None)

    assert settings.cors_origins == [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]


@pytest.mark.parametrize(
    "url",
    [
        "file:///tmp/provider",
        "http://user:secret@example.test/v1",
        "https://example.test/v1?token=secret",
        "https://example.test/v1#fragment",
    ],
)
def test_provider_urls_reject_unsafe_or_secret_bearing_forms(url: str) -> None:
    with pytest.raises(ValidationError):
        Settings(ollama_url=url, _env_file=None)


def test_corrupt_runtime_overrides_are_ignored_without_bypassing_validation(
    client, caplog: pytest.LogCaptureFixture
) -> None:
    override_db = client.app.dependency_overrides
    from app.db.session import get_db

    dependency = override_db[get_db]
    session_generator = dependency()
    db: Session = next(session_generator)
    try:
        db.add(
            ApplicationSetting(
                key=RUNTIME_SETTINGS_KEY,
                value={"provider": "invented", "model_temperature": 99},
            )
        )
        db.commit()

        settings = runtime_settings(db)

        assert settings.provider == "disabled"
        assert settings.model_temperature == 0
    finally:
        session_generator.close()

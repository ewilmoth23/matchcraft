from typing import Any

import structlog
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.models import ApplicationSetting

RUNTIME_SETTINGS_KEY = "runtime_model_settings"
PERMITTED_KEYS = {
    "provider",
    "model",
    "remote_model",
    "openai_reasoning_effort",
    "ollama_context_tokens",
    "model_temperature",
    "model_max_tokens",
    "model_timeout_seconds",
    "model_retries",
    "ollama_url",
    "openai_base_url",
}
logger = structlog.get_logger()


def _apply_overrides(base: Settings, overrides: dict[str, Any]) -> Settings:
    return Settings.model_validate({**base.model_dump(), **overrides})


def runtime_settings(db: Session) -> Settings:
    base = get_settings()
    stored = db.get(ApplicationSetting, RUNTIME_SETTINGS_KEY)
    overrides = stored.value if stored else {}
    safe = {key: value for key, value in overrides.items() if key in PERMITTED_KEYS}
    try:
        return _apply_overrides(base, safe)
    except ValidationError:
        logger.warning("invalid_runtime_settings_ignored", invalid_key_count=len(safe))
        return base


def update_runtime_settings(db: Session, updates: dict[str, Any]) -> Settings:
    stored = db.get(ApplicationSetting, RUNTIME_SETTINGS_KEY)
    values = dict(stored.value) if stored else {}
    values.update({key: value for key, value in updates.items() if key in PERMITTED_KEYS})
    validated = _apply_overrides(get_settings(), values)
    if stored:
        stored.value = values
    else:
        db.add(ApplicationSetting(key=RUNTIME_SETTINGS_KEY, value=values))
    db.flush()
    return validated

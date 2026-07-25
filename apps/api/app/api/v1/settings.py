from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.domain import SettingsRead, SettingsUpdate
from app.services.runtime_settings import runtime_settings, update_runtime_settings

router = APIRouter()


def _safe_settings(settings: Any) -> SettingsRead:
    provider_url = (
        settings.ollama_url
        if settings.provider in {"local_first", "ollama"}
        else settings.openai_base_url or ""
    )
    remote_configured = settings.remote_provider_configured
    return SettingsRead(
        provider=settings.provider,
        local_model=settings.model,
        local_provider_url=settings.ollama_url,
        remote_model=settings.remote_model,
        remote_provider_url=settings.openai_base_url or "",
        openai_reasoning_effort=settings.openai_reasoning_effort,
        ollama_context_tokens=settings.ollama_context_tokens,
        remote_api_key_configured=bool(settings.openai_api_key),
        remote_fallback_configured=(settings.provider == "local_first" and remote_configured),
        model=settings.model,
        provider_url=provider_url,
        model_temperature=settings.model_temperature,
        model_max_tokens=settings.model_max_tokens,
        model_timeout_seconds=settings.model_timeout_seconds,
        model_retries=settings.model_retries,
        max_upload_bytes=settings.max_upload_bytes,
        data_dir=str(settings.data_dir),
        remote_provider_warning=(
            settings.provider == "openai_compatible"
            or (settings.provider == "local_first" and remote_configured)
        ),
    )


@router.get("", response_model=SettingsRead)
def get_safe_settings(db: Session = Depends(get_db)) -> SettingsRead:
    return _safe_settings(runtime_settings(db))


@router.put("", response_model=SettingsRead)
def update_safe_settings(payload: SettingsUpdate, db: Session = Depends(get_db)) -> SettingsRead:
    values = payload.model_dump(exclude_none=True)
    local_model = values.pop("local_model", None)
    if local_model is not None:
        values["model"] = local_model
    local_provider_url = values.pop("local_provider_url", None)
    if local_provider_url is not None:
        values["ollama_url"] = local_provider_url
    remote_provider_url = values.pop("remote_provider_url", None)
    if remote_provider_url is not None:
        values["openai_base_url"] = remote_provider_url
    provider_url = values.pop("provider_url", None)
    active_provider = values.get("provider", runtime_settings(db).provider)
    if provider_url:
        values[
            "ollama_url" if active_provider in {"local_first", "ollama"} else "openai_base_url"
        ] = provider_url
    settings = update_runtime_settings(db, values)
    db.commit()
    return _safe_settings(settings)

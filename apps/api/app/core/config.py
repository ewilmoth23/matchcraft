import ipaddress
from contextlib import suppress
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# Cloud instance-metadata endpoints are never a legitimate model provider, and reaching
# them is the highest-value target for a redirected provider URL.
BLOCKED_PROVIDER_HOSTS = {
    "metadata.google.internal",
    "metadata.goog",
    "instance-data",
}


def validate_provider_url(value: str) -> str:
    """Validate a model-provider base URL. Raises ValueError when unsafe."""
    cleaned = value.strip().rstrip("/")
    parsed = urlsplit(cleaned)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(
            "Provider URLs must be HTTP(S) base URLs without credentials, query strings, or fragments"
        )
    host = parsed.hostname.casefold()
    if host in BLOCKED_PROVIDER_HOSTS:
        raise ValueError("Provider URLs cannot target a cloud instance-metadata endpoint")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return cleaned
    if address.is_link_local or address.is_multicast or address.is_reserved:
        raise ValueError("Provider URLs cannot target link-local or reserved addresses")
    return cleaned


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="MATCHCRAFT_", case_sensitive=False, extra="ignore"
    )

    app_name: str = "MatchCraft"
    env: Literal["development", "test", "production"] = "development"
    api_prefix: str = "/api/v1"
    data_dir: Path = Field(default_factory=lambda: Path.home() / ".local" / "share" / "matchcraft")
    database_url: str = ""
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:5173"]
    )
    # The API has no authentication, so a browser that reaches it under an attacker
    # controlled name (DNS rebinding) would be treated as same-origin and bypass CORS.
    # "*" disables the check for deployments that front the API with their own gateway.
    # Starlette compares the Host header with the port split off at the first colon, so
    # an IPv6 literal can never match and is deliberately absent from this list.
    allowed_hosts: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["localhost", "127.0.0.1", "api", "web"]
    )
    max_upload_bytes: int = Field(default=10 * 1024 * 1024, ge=1024, le=50 * 1024 * 1024)
    provider: Literal["local_first", "ollama", "openai_compatible", "disabled"] = "local_first"
    ollama_url: str = "http://localhost:11434"
    openai_base_url: str | None = "https://api.openai.com/v1"
    openai_api_key: str | None = None
    model: str = "qwen3.5:9b"
    remote_model: str = "gpt-5.6-sol"
    openai_reasoning_effort: Literal["none", "low", "medium", "high"] = "low"
    ollama_context_tokens: int = Field(default=32768, ge=4096, le=131072)
    model_temperature: float = Field(default=0, ge=0, le=1)
    model_max_tokens: int = Field(default=3000, ge=256, le=16000)
    model_timeout_seconds: float = Field(default=180, ge=1, le=300)
    model_retries: int = Field(default=1, ge=0, le=3)

    @field_validator("cors_origins", "allowed_hosts", mode="before")
    @classmethod
    def split_origins(cls, value: object) -> object:
        if isinstance(value, str) and not value.lstrip().startswith("["):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("cors_origins")
    @classmethod
    def reject_wildcard_origin(cls, value: list[str]) -> list[str]:
        # With no authentication, "*" lets any website read every stored analysis.
        if any(origin.strip() == "*" for origin in value):
            raise ValueError(
                "MATCHCRAFT_CORS_ORIGINS cannot be '*'; list explicit origins such as "
                "http://localhost:5173"
            )
        return value

    @field_validator("ollama_url", "openai_base_url")
    @classmethod
    def validate_provider_base_url(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return value
        return validate_provider_url(value)

    @model_validator(mode="after")
    def resolve_local_paths(self) -> "Settings":
        self.data_dir = self.data_dir.expanduser().resolve()
        if not self.database_url.strip():
            self.database_url = f"sqlite:///{self.data_dir / 'matchcraft.db'}"
        return self

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def exports_dir(self) -> Path:
        return self.data_dir / "exports"

    @property
    def remote_provider_configured(self) -> bool:
        """Return whether a remote fallback can be called without guessing credentials."""
        if not self.openai_base_url:
            return False
        hostname = (urlsplit(self.openai_base_url).hostname or "").casefold()
        if hostname == "api.openai.com":
            return bool(self.openai_api_key and self.openai_api_key.strip())
        return True

    def ensure_directories(self) -> None:
        # The SQLite database holds the résumé and job text, so the data directory itself
        # must not be world-readable. mkdir(mode=...) is ignored when the directory already
        # exists, so the mode is applied explicitly.
        self.data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.uploads_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.exports_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        for directory in (self.data_dir, self.uploads_dir, self.exports_dir):
            with suppress(OSError):
                directory.chmod(0o700)
        self.restrict_database_permissions()

    def restrict_database_permissions(self) -> None:
        """Tighten permissions on SQLite files, which are created world-readable."""
        if not self.database_url.startswith("sqlite"):
            return
        database_path = Path(self.database_url.split("sqlite:///", 1)[-1])
        for candidate in (
            database_path,
            database_path.with_name(database_path.name + "-wal"),
            database_path.with_name(database_path.name + "-shm"),
        ):
            with suppress(OSError):
                if candidate.exists():
                    candidate.chmod(0o600)


@lru_cache
def get_settings() -> Settings:
    return Settings()

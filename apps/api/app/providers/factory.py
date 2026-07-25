from app.core.config import Settings
from app.providers.base import ModelProvider, ProviderError, ProviderResponse
from app.providers.http import HTTPModelProvider


class DisabledProvider:
    name = "disabled"
    model = "none"

    async def available(self) -> bool:
        return False

    async def analyze(self, resume_text: str, job_text: str) -> ProviderResponse:
        raise RuntimeError("The model provider is disabled")

    async def rewrite_bullet(
        self, original_bullet: str, resume_text: str, job_text: str
    ) -> ProviderResponse:
        raise RuntimeError("The model provider is disabled")


class LocalFirstProvider:
    """Try private local inference first and use the configured remote only as fallback."""

    def __init__(self, providers: list[ModelProvider]):
        self.providers = providers
        self.name = "local_first"
        self.model = providers[0].model if providers else "none"

    async def available(self) -> bool:
        for provider in self.providers:
            if await provider.available():
                self.name = provider.name
                self.model = provider.model
                return True
        self.name = "local_first"
        return False

    async def analyze(self, resume_text: str, job_text: str) -> ProviderResponse:
        errors: list[ProviderError] = []
        for provider in self.providers:
            if not await provider.available():
                continue
            self.name = provider.name
            self.model = provider.model
            try:
                return await provider.analyze(resume_text, job_text)
            except ProviderError as exc:
                errors.append(exc)
        if errors:
            raise errors[-1]
        raise ProviderError(
            "provider_unavailable", "No configured model provider is available.", retryable=True
        )

    async def rewrite_bullet(
        self, original_bullet: str, resume_text: str, job_text: str
    ) -> ProviderResponse:
        errors: list[ProviderError] = []
        for provider in self.providers:
            if not await provider.available():
                continue
            self.name = provider.name
            self.model = provider.model
            try:
                return await provider.rewrite_bullet(original_bullet, resume_text, job_text)
            except ProviderError as exc:
                errors.append(exc)
        if errors:
            raise errors[-1]
        raise ProviderError(
            "provider_unavailable", "No configured model provider is available.", retryable=True
        )


def get_provider_candidates(settings: Settings) -> list[ModelProvider]:
    if settings.provider == "disabled":
        return []
    if settings.provider == "ollama":
        return [HTTPModelProvider(settings, "ollama")]
    if settings.provider == "openai_compatible":
        return [HTTPModelProvider(settings, "openai_compatible")]
    return [
        HTTPModelProvider(settings, "ollama"),
        HTTPModelProvider(settings, "openai_compatible"),
    ]


def get_provider(settings: Settings) -> ModelProvider:
    if settings.provider == "disabled":
        return DisabledProvider()
    providers = get_provider_candidates(settings)
    if settings.provider == "local_first":
        return LocalFirstProvider(providers)
    return providers[0]

import pytest

from app.core.config import Settings
from app.providers.base import ProviderError, ProviderResponse
from app.providers.factory import LocalFirstProvider, get_provider, get_provider_candidates
from app.schemas.provider import ModelAnalysisOutput, ModelBulletRewrite


def analysis_output() -> ModelAnalysisOutput:
    return ModelAnalysisOutput(
        executive_summary="The supplied evidence supports part of the target role.",
        responsibility_alignment=0.5,
        transferable_experience=["Built Python services."],
        recommendations=[],
        interview_questions=[],
        limitations=["Human review is required."],
    )


class StubProvider:
    def __init__(
        self,
        name: str,
        model: str,
        *,
        available: bool = True,
        error: ProviderError | None = None,
    ) -> None:
        self.name = name
        self.model = model
        self.is_available = available
        self.error = error
        self.analysis_calls = 0

    async def available(self) -> bool:
        return self.is_available

    async def analyze(self, resume_text: str, job_text: str) -> ProviderResponse:
        self.analysis_calls += 1
        if self.error:
            raise self.error
        return ProviderResponse(analysis_output(), {}, provider=self.name, model=self.model)

    async def rewrite_bullet(
        self, original_bullet: str, resume_text: str, job_text: str
    ) -> ProviderResponse:
        if self.error:
            raise self.error
        return ProviderResponse(
            ModelBulletRewrite(
                suggested_bullet=original_bullet,
                reason="Preserves the supplied facts.",
                factual_sources=[original_bullet],
                confirmation_required=True,
            ),
            {},
            provider=self.name,
            model=self.model,
        )


@pytest.mark.asyncio
async def test_local_first_stops_after_successful_local_analysis() -> None:
    local = StubProvider("ollama", "local-model")
    remote = StubProvider("openai_compatible", "remote-model")
    provider = LocalFirstProvider([local, remote])

    response = await provider.analyze("Built Python services.", "Python required.")

    assert response.provider == "ollama"
    assert local.analysis_calls == 1
    assert remote.analysis_calls == 0


@pytest.mark.asyncio
async def test_local_first_falls_back_after_invalid_local_output() -> None:
    local = StubProvider(
        "ollama",
        "local-model",
        error=ProviderError("invalid_model_output", "Invalid local output."),
    )
    remote = StubProvider("openai_compatible", "remote-model")
    provider = LocalFirstProvider([local, remote])

    response = await provider.analyze("Built Python services.", "Python required.")

    assert response.provider == "openai_compatible"
    assert local.analysis_calls == 1
    assert remote.analysis_calls == 1


@pytest.mark.asyncio
async def test_local_first_skips_unavailable_local_provider() -> None:
    local = StubProvider("ollama", "local-model", available=False)
    remote = StubProvider("openai_compatible", "remote-model")
    provider = LocalFirstProvider([local, remote])

    response = await provider.analyze("Built Python services.", "Python required.")

    assert response.provider == "openai_compatible"
    assert local.analysis_calls == 0
    assert remote.analysis_calls == 1


def test_local_first_factory_keeps_provider_specific_models() -> None:
    settings = Settings(
        provider="local_first",
        model="qwen3.5:9b",
        remote_model="gpt-5.6-sol",
        _env_file=None,
    )

    candidates = get_provider_candidates(settings)

    assert [(provider.name, provider.model) for provider in candidates] == [
        ("ollama", "qwen3.5:9b"),
        ("openai_compatible", "gpt-5.6-sol"),
    ]
    assert isinstance(get_provider(settings), LocalFirstProvider)

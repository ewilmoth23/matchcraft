import json

import httpx
import pytest
from pydantic import ValidationError

from app.analysis.fabrication import (
    sanitize_analysis_evidence,
    sanitize_analysis_prose,
    sanitize_analysis_skills,
    validate_analysis_output,
    validate_bullet_rewrite,
)
from app.core.config import Settings
from app.providers.base import ProviderError
from app.providers.http import SYSTEM_RULES, HTTPModelProvider
from app.schemas.provider import (
    ModelAnalysisOutput,
    ModelBulletRewrite,
    ModelInterviewQuestion,
    ModelRecommendation,
)


def valid_output() -> ModelAnalysisOutput:
    return ModelAnalysisOutput(
        executive_summary="The supplied evidence aligns with some role requirements.",
        responsibility_alignment=0.5,
        transferable_experience=["Built Python services."],
        recommendations=[],
        interview_questions=[],
        limitations=["Human review is required."],
    )


def test_prompt_matches_exact_excerpt_validators() -> None:
    assert "transferable_experience" in SYSTEM_RULES
    assert "talking_points" in SYSTEM_RULES
    assert "verbatim from RESUME" in SYSTEM_RULES


def test_model_output_schema_rejects_unbounded_score() -> None:
    with pytest.raises(ValidationError):
        ModelAnalysisOutput(
            executive_summary="This summary has enough content.",
            responsibility_alignment=4,
            transferable_experience=[],
            recommendations=[],
            interview_questions=[],
            limitations=[],
        )


def test_model_evidence_must_be_exact_resume_excerpt() -> None:
    output = valid_output()
    with pytest.raises(ProviderError, match="not found"):
        validate_analysis_output(output, "Built Java services.")
    validate_analysis_output(output, "Experience\nBuilt Python services.")


def test_unsupported_evidence_fields_are_removed_before_validation() -> None:
    output = valid_output().model_copy(
        update={
            "transferable_experience": ["Paraphrased Python experience."],
            "recommendations": [
                ModelRecommendation(
                    priority="Moderate impact",
                    title="Clarify the evidence",
                    explanation="The supplied line could be clearer.",
                    supporting_evidence="A paraphrase not present in the source.",
                    role_reason="Python appears in the role.",
                    recommended_action="Review the wording before using it.",
                    confidence="medium",
                    confirmation_required=True,
                )
            ],
            "interview_questions": [
                ModelInterviewQuestion(
                    category="technical",
                    question="How did you approach the Python work?",
                    talking_points=["Built Python services.", "Another paraphrase."],
                    resume_evidence="Paraphrased evidence.",
                    confidence="medium",
                )
            ],
        }
    )

    sanitized, count = sanitize_analysis_evidence(output, "Built Python services.")

    assert count == 4
    assert sanitized.transferable_experience == []
    assert sanitized.recommendations[0].supporting_evidence is None
    assert sanitized.interview_questions[0].resume_evidence is None
    assert sanitized.interview_questions[0].talking_points == ["Built Python services."]
    validate_analysis_output(sanitized, "Built Python services.", "Python appears in the role.")


def test_transferable_experience_is_deduplicated() -> None:
    output = valid_output().model_copy(
        update={
            "transferable_experience": [
                "Built Python services.",
                "  built   python services. ",
            ]
        }
    )

    sanitized, count = sanitize_analysis_evidence(output, "Built Python services.")

    assert sanitized.transferable_experience == ["Built Python services."]
    assert count == 1


def test_items_with_fabricated_skills_are_dropped_before_validation() -> None:
    output = valid_output().model_copy(
        update={
            "executive_summary": "The candidate used Kubernetes in production work.",
            "recommendations": [
                ModelRecommendation(
                    priority="Moderate impact",
                    title="Add Docker evidence",
                    explanation="Docker could strengthen the document.",
                    supporting_evidence=None,
                    role_reason="The role values reliable services.",
                    recommended_action="Add Docker only after review.",
                    confidence="medium",
                    confirmation_required=True,
                )
            ],
            "interview_questions": [
                ModelInterviewQuestion(
                    category="technical",
                    question="How did you use React?",
                    talking_points=[],
                    resume_evidence=None,
                    confidence="medium",
                )
            ],
            "limitations": ["AWS evidence was not supplied."],
        }
    )

    sanitized, count = sanitize_analysis_skills(
        output, "Built Python services.", "Python required."
    )

    assert count == 4
    assert sanitized.executive_summary.startswith("The model-assisted analysis was limited")
    assert sanitized.recommendations == []
    assert sanitized.interview_questions == []
    assert sanitized.limitations == []
    validate_analysis_output(sanitized, "Built Python services.", "Python required.")


def test_items_with_unsupported_claims_are_dropped_before_validation() -> None:
    output = valid_output().model_copy(
        update={
            "executive_summary": "The candidate increased revenue by 50%.",
            "recommendations": [
                ModelRecommendation(
                    priority="Moderate impact",
                    title="Claim unsupported leadership",
                    explanation="The candidate led a large team.",
                    supporting_evidence="Built Python services.",
                    role_reason="This would support the role.",
                    recommended_action="Review the exact source before using this claim.",
                    confidence="medium",
                    confirmation_required=True,
                )
            ],
            "interview_questions": [
                ModelInterviewQuestion(
                    category="experience_gap",
                    question="How many customers did you manage?",
                    talking_points=["Built Python services."],
                    resume_evidence="Built Python services.",
                    confidence="medium",
                )
            ],
            "limitations": ["The supplied text does not establish an MBA."],
        }
    )

    sanitized, count = sanitize_analysis_prose(output, "Built Python services.", "Python required.")

    assert count == 4
    assert sanitized.executive_summary.startswith("The model-assisted analysis was limited")
    assert sanitized.recommendations == []
    assert sanitized.interview_questions == []
    assert sanitized.limitations == []
    assert sanitized.transferable_experience == ["Built Python services."]
    validate_analysis_output(sanitized, "Built Python services.", "Python required.")


def test_model_analysis_rejects_invented_metric() -> None:
    output = valid_output().model_copy(
        update={"executive_summary": "The candidate increased revenue by 50% in prior work."}
    )
    with pytest.raises(ProviderError) as error:
        validate_analysis_output(output, "Built Python services.", "Python required.")
    assert error.value.code == "fabricated_metric"


@pytest.mark.parametrize(
    ("summary", "code"),
    [
        ("The candidate used Kubernetes in production work.", "fabricated_skill"),
        ("The candidate earned a Doctorate in January.", "fabricated_claim"),
        ("The candidate served as Principal Architect at Acme.", "fabricated_claim"),
    ],
)
def test_model_analysis_rejects_invented_skills_credentials_dates_and_titles(
    summary: str, code: str
) -> None:
    output = valid_output().model_copy(update={"executive_summary": summary})
    with pytest.raises(ProviderError) as error:
        validate_analysis_output(output, "Built Python services.")
    assert error.value.code == code


def test_rewrite_rejects_fabricated_metric() -> None:
    output = ModelBulletRewrite(
        suggested_bullet="Built services that increased revenue by 40%.",
        reason="Adds impact.",
        factual_sources=["Built services."],
        confirmation_required=True,
    )
    with pytest.raises(ProviderError) as error:
        validate_bullet_rewrite(output, "Built services.", "Built services.")
    assert error.value.code == "fabricated_metric"


def test_rewrite_rejects_unsupported_leadership_claim() -> None:
    output = ModelBulletRewrite(
        suggested_bullet="Led a team while building services.",
        reason="Strengthens the action verb.",
        factual_sources=["Built services."],
        confirmation_required=True,
    )
    with pytest.raises(ProviderError) as error:
        validate_bullet_rewrite(output, "Built services.", "Built services.")
    assert error.value.code == "fabricated_claim"


def test_rewrite_must_cite_the_selected_bullet() -> None:
    output = ModelBulletRewrite(
        suggested_bullet="Built services.",
        reason="Improves clarity.",
        factual_sources=["Maintained documentation."],
        confirmation_required=True,
    )
    resume = "Built services.\nMaintained documentation."
    with pytest.raises(ProviderError) as error:
        validate_bullet_rewrite(output, "Built services.", resume)
    assert error.value.code == "unsupported_model_evidence"


def test_rewrite_requires_confirmation_and_preserves_unknown_placeholders() -> None:
    no_confirmation = ModelBulletRewrite(
        suggested_bullet="Built services.",
        reason="Improves clarity.",
        factual_sources=["Built services."],
        confirmation_required=False,
    )
    with pytest.raises(ProviderError) as confirmation_error:
        validate_bullet_rewrite(no_confirmation, "Built services.", "Built services.")
    assert confirmation_error.value.code == "confirmation_required"

    removed_placeholder = ModelBulletRewrite(
        suggested_bullet="Improved processing speed.",
        reason="Improves clarity.",
        factual_sources=["Improved processing speed by [insert verified percentage]."],
        confirmation_required=True,
    )
    original = "Improved processing speed by [insert verified percentage]."
    with pytest.raises(ProviderError) as placeholder_error:
        validate_bullet_rewrite(removed_placeholder, original, original)
    assert placeholder_error.value.code == "removed_placeholder"


@pytest.mark.parametrize(
    ("original", "suggested"),
    [
        (
            "Reduced API latency by 40% using Python.",
            "Reduced API latency using Python.",
        ),
        (
            "Built Python and FastAPI services.",
            "Built maintainable services.",
        ),
        (
            "Built services for Acme Systems.",
            "Built reliable services.",
        ),
        (
            "Improved throughput by [insert verified percentage].",
            "Improved throughput by [insert verified amount].",
        ),
        (
            "Led a team delivering internal services.",
            "Delivered internal services.",
        ),
    ],
)
def test_rewrite_rejects_dropped_source_facts(original: str, suggested: str) -> None:
    output = ModelBulletRewrite(
        suggested_bullet=suggested,
        reason="Improves clarity while retaining the supplied facts.",
        factual_sources=[original],
        confirmation_required=True,
    )

    with pytest.raises(ProviderError) as error:
        validate_bullet_rewrite(output, original, original)

    assert error.value.code in {"dropped_fact", "removed_placeholder"}


def test_rewrite_reason_cannot_introduce_fabricated_facts() -> None:
    original = "Built internal services."
    output = ModelBulletRewrite(
        suggested_bullet=original,
        reason="Highlights the candidate's Kubernetes delivery experience.",
        factual_sources=[original],
        confirmation_required=True,
    )

    with pytest.raises(ProviderError) as error:
        validate_bullet_rewrite(output, original, original)

    assert error.value.code == "fabricated_skill"


def test_rewrite_accepts_reordering_that_preserves_all_known_facts() -> None:
    original = "Reduced API latency by 40% using Python for Acme Systems."
    output = ModelBulletRewrite(
        suggested_bullet="Using Python for Acme Systems, reduced API latency by 40%.",
        reason="Improves clarity while retaining every supplied fact.",
        factual_sources=[original],
        confirmation_required=True,
    )

    validate_bullet_rewrite(output, original, original)


def test_analysis_rejects_invented_talking_points_and_titles() -> None:
    invented_point = valid_output().model_copy(
        update={
            "interview_questions": [
                ModelInterviewQuestion(
                    category="behavioral",
                    question="How did you approach the work?",
                    talking_points=["Led a global migration."],
                    resume_evidence="Built Python services.",
                    confidence="medium",
                )
            ]
        }
    )
    with pytest.raises(ProviderError) as evidence_error:
        validate_analysis_output(invented_point, "Built Python services.")
    assert evidence_error.value.code == "unsupported_model_evidence"

    invented_title = valid_output().model_copy(
        update={"executive_summary": "The candidate served as Principal Architect at Acme."}
    )
    with pytest.raises(ProviderError) as title_error:
        validate_analysis_output(invented_title, "Built Python services.")
    assert title_error.value.code in {"fabricated_claim", "fabricated_entity"}


def test_model_recommendations_always_require_confirmation() -> None:
    output = valid_output().model_copy(
        update={
            "recommendations": [
                ModelRecommendation(
                    priority="Moderate impact",
                    title="Clarify the evidence",
                    explanation="The supplied line could be clearer.",
                    supporting_evidence="Built Python services.",
                    role_reason="Python appears in the role.",
                    recommended_action="Review the wording before using it.",
                    confidence="medium",
                    confirmation_required=False,
                )
            ]
        }
    )
    with pytest.raises(ProviderError) as error:
        validate_analysis_output(output, "Built Python services.", "Python appears in the role.")
    assert error.value.code == "confirmation_required"


class FakeResponse:
    status_code = 200

    def __init__(self, content: str):
        self.content = content

    def json(self) -> dict[str, object]:
        return {"message": {"content": self.content}}


class FakeShapedResponse(FakeResponse):
    def __init__(self, body: object):
        self.body = body

    def json(self) -> object:
        return self.body


class FakeClient:
    def __init__(self, response: FakeResponse | Exception, **_: object):
        self.response = response
        self.calls = 0

    async def __aenter__(self) -> "FakeClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def post(self, *_: object, **__: object) -> FakeResponse:
        self.calls += 1
        if isinstance(self.response, Exception):
            raise self.response
        return self.response

    async def get(self, *_: object, **__: object) -> FakeResponse:
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class SequentialFakeClient(FakeClient):
    def __init__(self, responses: list[FakeResponse]):
        super().__init__(responses[0])
        self.responses = responses

    async def post(self, *_: object, **__: object) -> FakeResponse:
        response = self.responses[min(self.calls, len(self.responses) - 1)]
        self.calls += 1
        return response


@pytest.mark.asyncio
async def test_valid_structured_provider_analysis(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = valid_output().model_dump()
    fake = FakeClient(FakeResponse(json.dumps(payload)))
    monkeypatch.setattr("app.providers.http.httpx.AsyncClient", lambda **kwargs: fake)
    provider = HTTPModelProvider(Settings(provider="ollama", model_retries=0))
    response = await provider.analyze("Experience\nBuilt Python services.", "Python required.")
    assert isinstance(response.output, ModelAnalysisOutput)
    assert response.output.transferable_experience == ["Built Python services."]


@pytest.mark.asyncio
async def test_malformed_provider_json_retries_then_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeClient(FakeResponse("not valid json"))
    monkeypatch.setattr("app.providers.http.httpx.AsyncClient", lambda **kwargs: fake)
    provider = HTTPModelProvider(Settings(provider="ollama", model_retries=1))
    with pytest.raises(ProviderError) as error:
        await provider.analyze("Built Python services.", "Python required.")
    assert error.value.code == "invalid_model_output"
    assert fake.calls == 2


@pytest.mark.asyncio
async def test_semantic_validation_failure_gets_bounded_corrective_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    unsafe = valid_output().model_copy(
        update={
            "recommendations": [
                ModelRecommendation(
                    priority="Moderate impact",
                    title="Clarify supplied evidence",
                    explanation="The supplied line could be clearer.",
                    supporting_evidence="Built Python services.",
                    role_reason="The role requires Python.",
                    recommended_action="Review the wording before using it.",
                    confidence="medium",
                    confirmation_required=False,
                )
            ]
        }
    )
    fake = SequentialFakeClient(
        [
            FakeResponse(json.dumps(unsafe.model_dump())),
            FakeResponse(json.dumps(valid_output().model_dump())),
        ]
    )
    monkeypatch.setattr("app.providers.http.httpx.AsyncClient", lambda **kwargs: fake)
    provider = HTTPModelProvider(Settings(provider="ollama", model_retries=1))

    response = await provider.analyze("Experience\nBuilt Python services.", "Python required.")

    assert response.output == valid_output()
    assert fake.calls == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("body", [[], {"message": "invalid"}, {"message": {"content": []}}])
async def test_malformed_provider_shape_is_normalized(
    monkeypatch: pytest.MonkeyPatch, body: object
) -> None:
    fake = FakeClient(FakeShapedResponse(body))
    monkeypatch.setattr("app.providers.http.httpx.AsyncClient", lambda **kwargs: fake)
    provider = HTTPModelProvider(Settings(provider="ollama", model_retries=0))
    with pytest.raises(ProviderError) as error:
        await provider.analyze("Built Python services.", "Python required.")
    assert error.value.code == "invalid_model_output"


@pytest.mark.asyncio
async def test_provider_timeout_is_normalized(monkeypatch: pytest.MonkeyPatch) -> None:
    request = httpx.Request("POST", "http://localhost:11434/api/chat")
    fake = FakeClient(httpx.ReadTimeout("slow model", request=request))
    monkeypatch.setattr("app.providers.http.httpx.AsyncClient", lambda **kwargs: fake)
    provider = HTTPModelProvider(Settings(provider="ollama", model_retries=0))
    with pytest.raises(ProviderError) as error:
        await provider.analyze("Built Python services.", "Python required.")
    assert error.value.code == "provider_timeout"
    assert error.value.retryable is True


@pytest.mark.asyncio
async def test_provider_availability_handles_connection_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = httpx.Request("GET", "http://localhost:11434/api/tags")
    fake = FakeClient(httpx.ConnectError("offline", request=request))
    monkeypatch.setattr("app.providers.http.httpx.AsyncClient", lambda **kwargs: fake)
    provider = HTTPModelProvider(Settings(provider="ollama"))
    assert await provider.available() is False


@pytest.mark.asyncio
async def test_ollama_availability_requires_configured_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeClient(
        FakeShapedResponse({"models": [{"name": "qwen3.5:9b", "model": "qwen3.5:9b"}]})
    )
    monkeypatch.setattr("app.providers.http.httpx.AsyncClient", lambda **kwargs: fake)

    available = HTTPModelProvider(Settings(provider="ollama", model="qwen3.5:9b"))
    missing = HTTPModelProvider(Settings(provider="ollama", model="missing:latest"))

    assert await available.available() is True
    assert await missing.available() is False


def test_official_openai_uses_responses_api_and_strict_schema() -> None:
    settings = Settings(
        provider="openai_compatible",
        openai_api_key="test-only-key",
        remote_model="gpt-5.6-sol",
        _env_file=None,
    )
    provider = HTTPModelProvider(settings)

    payload = provider._payload("Analyze the supplied text.", ModelAnalysisOutput)

    assert provider._endpoint() == "https://api.openai.com/v1/responses"
    assert payload["model"] == "gpt-5.6-sol"
    assert payload["store"] is False
    assert payload["reasoning"] == {"effort": "low"}
    assert payload["text"]["format"]["type"] == "json_schema"
    assert payload["text"]["format"]["strict"] is True
    schema = payload["text"]["format"]["schema"]
    assert set(schema["required"]) == set(schema["properties"])


def test_ollama_payload_bounds_context_and_disables_thinking() -> None:
    settings = Settings(
        provider="ollama",
        model="qwen3.5:9b",
        ollama_context_tokens=32768,
        _env_file=None,
    )
    provider = HTTPModelProvider(settings)

    payload = provider._payload("Analyze the supplied text.", ModelAnalysisOutput)

    assert payload["think"] is False
    assert payload["options"]["num_ctx"] == 32768
    assert payload["options"]["num_predict"] == 3000


@pytest.mark.asyncio
async def test_ollama_rejects_input_that_may_be_silently_truncated() -> None:
    provider = HTTPModelProvider(
        Settings(provider="ollama", ollama_context_tokens=4096, _env_file=None)
    )

    with pytest.raises(ProviderError) as error:
        await provider.analyze("x" * 13_000, "Python required.")

    assert error.value.code == "provider_context_exceeded"


@pytest.mark.asyncio
async def test_official_openai_is_not_contacted_without_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected_client(**_: object) -> FakeClient:
        raise AssertionError("The remote provider must not be contacted without a key")

    monkeypatch.setattr("app.providers.http.httpx.AsyncClient", unexpected_client)
    provider = HTTPModelProvider(
        Settings(provider="openai_compatible", openai_api_key=None, _env_file=None)
    )

    assert await provider.available() is False

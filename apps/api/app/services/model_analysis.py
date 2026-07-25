import asyncio
from time import perf_counter

import structlog
from sqlalchemy.orm import Session

from app.analysis.fabrication import validate_analysis_output, validate_bullet_rewrite
from app.analysis.text import measurable_result
from app.core.config import Settings
from app.core.errors import ProviderError
from app.models import Analysis, InterviewQuestion, ProviderRun, Recommendation
from app.providers.factory import get_provider, get_provider_candidates
from app.schemas.domain import ProviderHealth
from app.schemas.provider import ModelAnalysisOutput, ModelBulletRewrite

logger = structlog.get_logger()


async def check_provider_health(settings: Settings) -> tuple[list[ProviderHealth], str | None]:
    """Probe every candidate provider concurrently and report the first available one.

    Lives here rather than in the health route so the API layer does not drive provider
    adapters directly. Availability checks send no document text.
    """
    providers = get_provider_candidates(settings)
    availability = await asyncio.gather(
        *(provider.available() for provider in providers), return_exceptions=True
    )
    checks: list[ProviderHealth] = []
    active_provider: str | None = None
    for provider, result in zip(providers, availability, strict=True):
        configured = bool(getattr(provider, "configured", True))
        available = result is True
        if available and active_provider is None:
            active_provider = provider.name
        checks.append(
            ProviderHealth(
                provider=provider.name,
                model=provider.model,
                status=(
                    "available" if available else "unavailable" if configured else "not_configured"
                ),
                local=provider.name == "ollama",
            )
        )
    return checks, active_provider


async def execute_model_analysis(db: Session, analysis: Analysis, settings: Settings) -> str:
    provider = get_provider(settings)
    if settings.provider == "disabled":
        analysis.model_status = "disabled"
        return "disabled"
    start = perf_counter()
    try:
        if not await provider.available():
            analysis.model_status = "unavailable"
            db.add(
                ProviderRun(
                    analysis_id=analysis.id,
                    provider=provider.name,
                    model=provider.model,
                    feature="analysis",
                    status="unavailable",
                    error_code="provider_unavailable",
                )
            )
            return "unavailable"
        response = await provider.analyze(
            analysis.resume.extracted_text, analysis.job_description.raw_text
        )
        used_provider = response.provider or provider.name
        used_model = response.model or provider.model
        output = ModelAnalysisOutput.model_validate(response.output)
        validate_analysis_output(
            output, analysis.resume.extracted_text, analysis.job_description.raw_text
        )
        for recommendation in output.recommendations:
            db.add(
                Recommendation(
                    analysis_id=analysis.id,
                    **recommendation.model_dump(),
                    source="model",
                )
            )
        for question in output.interview_questions:
            db.add(
                InterviewQuestion(
                    analysis_id=analysis.id,
                    **question.model_dump(),
                    source="model",
                )
            )
        result = dict(analysis.result)
        result.update(
            {
                "model_executive_summary": output.executive_summary,
                "model_responsibility_alignment": output.responsibility_alignment,
                "model_transferable_experience": output.transferable_experience,
                "model_limitations": output.limitations,
                "model_generated": True,
            }
        )
        analysis.result = result
        analysis.model_status = "completed"
        db.add(
            ProviderRun(
                analysis_id=analysis.id,
                provider=used_provider,
                model=used_model,
                feature="analysis",
                status="completed",
                duration_ms=round((perf_counter() - start) * 1000),
                usage=response.usage,
            )
        )
        logger.info(
            "model_analysis_completed",
            analysis_id=analysis.id,
            provider=used_provider,
            model=used_model,
            duration_ms=round((perf_counter() - start) * 1000),
        )
        return "completed"
    except ProviderError as exc:
        status = "unavailable" if exc.retryable else "invalid_output"
        analysis.model_status = status
        db.add(
            ProviderRun(
                analysis_id=analysis.id,
                provider=provider.name,
                model=provider.model,
                feature="analysis",
                status=status,
                duration_ms=round((perf_counter() - start) * 1000),
                error_code=exc.code,
            )
        )
        logger.warning(
            "model_analysis_failed",
            analysis_id=analysis.id,
            provider=provider.name,
            error_code=exc.code,
        )
        return status
    except Exception:
        analysis.model_status = "unavailable"
        db.add(
            ProviderRun(
                analysis_id=analysis.id,
                provider=provider.name,
                model=provider.model,
                feature="analysis",
                status="unavailable",
                duration_ms=round((perf_counter() - start) * 1000),
                error_code="provider_internal_error",
            )
        )
        logger.warning(
            "model_analysis_failed",
            analysis_id=analysis.id,
            provider=provider.name,
            error_code="provider_internal_error",
        )
        return "unavailable"


async def generate_bullet_rewrite(
    original_bullet: str, resume_text: str, job_text: str, settings: Settings
) -> tuple[ModelBulletRewrite, bool]:
    provider = get_provider(settings)
    try:
        if settings.provider != "disabled" and await provider.available():
            response = await provider.rewrite_bullet(original_bullet, resume_text, job_text)
            output = ModelBulletRewrite.model_validate(response.output)
            validate_bullet_rewrite(output, original_bullet, resume_text)
            return output, True
    except ProviderError as exc:
        logger.warning("bullet_rewrite_provider_failed", error_code=exc.code)
    except Exception:
        logger.warning("bullet_rewrite_provider_failed", error_code="provider_internal_error")
    clean = original_bullet.strip().rstrip(".")
    suggestion = clean[0].upper() + clean[1:] if clean else clean
    has_measurable_result = measurable_result(original_bullet)
    if not has_measurable_result and "[insert verified" not in suggestion.casefold():
        suggestion += " — resulting in [insert verified outcome]"
    suggestion += "."
    reason = (
        "Preserves the supplied quantified outcome and normalizes punctuation without adding facts."
        if has_measurable_result
        else "Polishes punctuation and leaves the unknown outcome as an explicit placeholder."
    )
    return (
        ModelBulletRewrite(
            suggested_bullet=suggestion,
            reason=reason,
            factual_sources=[original_bullet],
            confirmation_required=True,
        ),
        False,
    )

import re

import structlog
from fastapi import APIRouter, Depends, Response, status
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import Settings, get_settings
from app.core.errors import MatchCraftError
from app.db.session import get_db
from app.models import Analysis, JobDescription, Recommendation, Resume
from app.schemas.domain import (
    AnalysisCreate,
    AnalysisDetail,
    AnalysisRename,
    AnalysisSummary,
    BulletRewriteRequest,
    BulletRewriteResponse,
    RecommendationRead,
    RecommendationUpdate,
    RunAnalysisRequest,
)
from app.services.analysis import execute_deterministic_analysis
from app.services.deletion import delete_analysis as delete_analysis_cascade
from app.services.exports import render_json, render_markdown
from app.services.model_analysis import execute_model_analysis, generate_bullet_rewrite
from app.services.runtime_settings import runtime_settings

router = APIRouter()
logger = structlog.get_logger()


DETAIL_OPTIONS = (
    selectinload(Analysis.resume),
    selectinload(Analysis.job_description).selectinload(JobDescription.requirements),
    selectinload(Analysis.scores),
    selectinload(Analysis.evidence),
    selectinload(Analysis.recommendations),
    selectinload(Analysis.interview_questions),
)


def _get_analysis(analysis_id: str, db: Session) -> Analysis:
    analysis = db.scalar(
        select(Analysis)
        .where(Analysis.id == analysis_id)
        .options(*DETAIL_OPTIONS)
        .execution_options(populate_existing=True)
    )
    if not analysis:
        raise MatchCraftError("analysis_not_found", "Analysis not found.", 404)
    return analysis


def _summary(analysis: Analysis) -> AnalysisSummary:
    return AnalysisSummary(
        **{
            key: value
            for key, value in AnalysisSummary.model_validate(analysis).model_dump().items()
            if key not in {"target_job_title", "target_employer"}
        },
        target_job_title=analysis.job_description.title,
        target_employer=analysis.job_description.employer,
    )


def _detail(analysis: Analysis) -> AnalysisDetail:
    values = AnalysisDetail.model_validate(analysis).model_dump()
    values["target_job_title"] = analysis.job_description.title
    values["target_employer"] = analysis.job_description.employer
    return AnalysisDetail.model_validate(values)


@router.post("", response_model=AnalysisDetail, status_code=status.HTTP_201_CREATED)
def create_analysis(payload: AnalysisCreate, db: Session = Depends(get_db)) -> AnalysisDetail:
    resume = db.get(Resume, payload.resume_id)
    job = db.get(JobDescription, payload.job_description_id)
    if not resume:
        raise MatchCraftError("resume_not_found", "Résumé not found.", 404)
    if not job:
        raise MatchCraftError("job_description_not_found", "Job description not found.", 404)
    default_name = " — ".join(item for item in (job.title or "Target role", job.employer) if item)
    analysis = Analysis(
        resume_id=resume.id,
        job_description_id=job.id,
        name=(payload.name or default_name).strip(),
        state="ready" if resume.confirmed else "draft",
    )
    db.add(analysis)
    db.commit()
    return _detail(_get_analysis(analysis.id, db))


@router.get("", response_model=list[AnalysisSummary])
def list_analyses(db: Session = Depends(get_db)) -> list[AnalysisSummary]:
    analyses = db.scalars(
        select(Analysis)
        .options(selectinload(Analysis.job_description))
        .order_by(Analysis.updated_at.desc())
    ).all()
    return [_summary(item) for item in analyses]


@router.get("/{analysis_id}", response_model=AnalysisDetail)
def get_analysis(analysis_id: str, db: Session = Depends(get_db)) -> AnalysisDetail:
    return _detail(_get_analysis(analysis_id, db))


@router.patch("/{analysis_id}", response_model=AnalysisDetail)
def rename_analysis(
    analysis_id: str, payload: AnalysisRename, db: Session = Depends(get_db)
) -> AnalysisDetail:
    analysis = _get_analysis(analysis_id, db)
    analysis.name = payload.name.strip()
    db.commit()
    return _detail(_get_analysis(analysis.id, db))


@router.post("/{analysis_id}/run", response_model=AnalysisDetail)
async def run_analysis(
    analysis_id: str,
    payload: RunAnalysisRequest,
    db: Session = Depends(get_db),
) -> AnalysisDetail:
    analysis = _get_analysis(analysis_id, db)
    if not analysis.resume.confirmed:
        raise MatchCraftError(
            "resume_not_confirmed",
            "Review and confirm the extracted résumé text before analysis.",
            409,
        )
    analysis.state = "analyzing"
    analysis.error_message = None
    db.commit()
    try:
        execute_deterministic_analysis(db, analysis)
        if payload.use_model:
            model_status = await execute_model_analysis(db, analysis, runtime_settings(db))
        else:
            model_status = "skipped"
            analysis.model_status = model_status
        if model_status == "invalid_output":
            analysis.state = "completed"
            analysis.error_message = (
                "Deterministic analysis completed, but model output failed validation. "
                "The deterministic results remain available."
            )
        else:
            analysis.state = "completed"
        db.commit()
    except MatchCraftError as exc:
        db.rollback()
        analysis = _get_analysis(analysis_id, db)
        analysis.state = "failed"
        analysis.error_message = exc.message
        db.commit()
        raise
    except Exception as exc:
        db.rollback()
        analysis = _get_analysis(analysis_id, db)
        analysis.state = "failed"
        analysis.error_message = "Analysis failed before all required stages completed."
        db.commit()
        raise MatchCraftError(
            "analysis_failed", "The analysis could not be completed.", 500
        ) from exc
    return _detail(_get_analysis(analysis.id, db))


@router.post("/{analysis_id}/rerun", response_model=AnalysisDetail)
async def rerun_analysis(
    analysis_id: str,
    payload: RunAnalysisRequest,
    db: Session = Depends(get_db),
) -> AnalysisDetail:
    return await run_analysis(analysis_id, payload, db)


@router.get("/{analysis_id}/recommendations", response_model=list[RecommendationRead])
def list_recommendations(analysis_id: str, db: Session = Depends(get_db)) -> list[Recommendation]:
    _get_analysis(analysis_id, db)
    return list(
        db.scalars(
            select(Recommendation)
            .where(Recommendation.analysis_id == analysis_id)
            .order_by(Recommendation.created_at)
        ).all()
    )


@router.patch(
    "/{analysis_id}/recommendations/{recommendation_id}", response_model=RecommendationRead
)
def update_recommendation(
    analysis_id: str,
    recommendation_id: str,
    payload: RecommendationUpdate,
    db: Session = Depends(get_db),
) -> Recommendation:
    recommendation = db.scalar(
        select(Recommendation).where(
            Recommendation.id == recommendation_id,
            Recommendation.analysis_id == analysis_id,
        )
    )
    if not recommendation:
        raise MatchCraftError("recommendation_not_found", "Recommendation not found.", 404)
    recommendation.status = payload.status
    db.commit()
    db.refresh(recommendation)
    return recommendation


@router.post("/{analysis_id}/bullet-rewrite", response_model=BulletRewriteResponse)
async def rewrite_bullet(
    analysis_id: str,
    payload: BulletRewriteRequest,
    db: Session = Depends(get_db),
) -> BulletRewriteResponse:
    analysis = _get_analysis(analysis_id, db)
    # This is the one path that can send résumé text to a provider, so it carries the
    # same review requirement as running an analysis.
    if not analysis.resume.confirmed:
        raise MatchCraftError(
            "resume_not_confirmed",
            "Review and confirm the extracted résumé text before requesting a rewrite.",
            409,
        )
    normalized_resume = re.sub(r"\s+", " ", analysis.resume.extracted_text).casefold()
    normalized_bullet = re.sub(r"\s+", " ", payload.original_bullet).strip().casefold()
    if normalized_bullet not in normalized_resume:
        raise MatchCraftError(
            "bullet_not_found",
            "The original bullet must be an exact excerpt from the stored résumé.",
            422,
        )
    output, model_generated = await generate_bullet_rewrite(
        payload.original_bullet,
        analysis.resume.extracted_text,
        analysis.job_description.raw_text,
        runtime_settings(db),
    )
    return BulletRewriteResponse(
        original_bullet=payload.original_bullet,
        suggested_bullet=output.suggested_bullet,
        reason=output.reason,
        factual_sources=output.factual_sources,
        confirmation_required=output.confirmation_required,
        model_generated=model_generated,
        warning=(
            "Review every word. MatchCraft never authorizes adding unverified facts; bracketed placeholders "
            "must be replaced only with real values or removed."
        ),
    )


@router.get("/{analysis_id}/export/markdown")
def export_markdown(analysis_id: str, db: Session = Depends(get_db)) -> PlainTextResponse:
    analysis = _get_analysis(analysis_id, db)
    if not analysis.deterministic_complete:
        raise MatchCraftError("analysis_incomplete", "Run the analysis before exporting.", 409)
    response = PlainTextResponse(
        render_markdown(analysis),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="matchcraft-{analysis.id}.md"'},
    )
    logger.info("analysis_exported", analysis_id=analysis.id, format="markdown")
    return response


@router.get("/{analysis_id}/export/json")
def export_json(analysis_id: str, db: Session = Depends(get_db)) -> PlainTextResponse:
    analysis = _get_analysis(analysis_id, db)
    if not analysis.deterministic_complete:
        raise MatchCraftError("analysis_incomplete", "Run the analysis before exporting.", 409)
    response = PlainTextResponse(
        render_json(analysis),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="matchcraft-{analysis.id}.json"'},
    )
    logger.info("analysis_exported", analysis_id=analysis.id, format="json")
    return response


@router.delete("/{analysis_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_analysis(
    analysis_id: str,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Response:
    delete_analysis_cascade(db, _get_analysis(analysis_id, db), settings)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

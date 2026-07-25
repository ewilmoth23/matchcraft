from time import perf_counter

import structlog
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.analysis.scoring import DeterministicResult, run_deterministic_analysis
from app.models import (
    Analysis,
    AnalysisScore,
    InterviewQuestion,
    MatchEvidence,
    Recommendation,
)

logger = structlog.get_logger()


def execute_deterministic_analysis(db: Session, analysis: Analysis) -> DeterministicResult:
    start = perf_counter()
    requirements = [
        {
            "id": row.id,
            "category": row.category,
            "text": row.text,
            "priority": row.priority,
            "explicitness": row.explicitness,
            "source_excerpt": row.source_excerpt,
        }
        for row in analysis.job_description.requirements
    ]
    result = run_deterministic_analysis(
        analysis.resume.extracted_text,
        analysis.resume.structured_data,
        analysis.job_description.raw_text,
        requirements,
    )

    db.execute(delete(AnalysisScore).where(AnalysisScore.analysis_id == analysis.id))
    db.execute(delete(MatchEvidence).where(MatchEvidence.analysis_id == analysis.id))
    db.execute(delete(Recommendation).where(Recommendation.analysis_id == analysis.id))
    db.execute(delete(InterviewQuestion).where(InterviewQuestion.analysis_id == analysis.id))
    for score_item in result.scores:
        db.add(AnalysisScore(analysis_id=analysis.id, **score_item.__dict__))
    for evidence_item in result.evidence:
        values = evidence_item.__dict__.copy()
        values.pop("priority")
        values.pop("category")
        values.pop("contextual")
        db.add(MatchEvidence(analysis_id=analysis.id, **values))
    for recommendation_values in result.recommendations:
        db.add(Recommendation(analysis_id=analysis.id, **recommendation_values))
    for question_values in result.interview_questions:
        db.add(InterviewQuestion(analysis_id=analysis.id, **question_values))
    analysis.overall_score = result.overall_score
    analysis.deterministic_complete = True
    analysis.result = result.summary
    analysis.error_message = None
    db.flush()
    logger.info(
        "deterministic_analysis_completed",
        analysis_id=analysis.id,
        duration_ms=round((perf_counter() - start) * 1000),
        requirement_count=len(requirements),
    )
    return result

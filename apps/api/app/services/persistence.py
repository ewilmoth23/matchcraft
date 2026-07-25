from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.models import (
    Analysis,
    AnalysisScore,
    InterviewQuestion,
    JobDescription,
    JobRequirement,
    MatchEvidence,
    ProviderRun,
    Recommendation,
    Resume,
)
from app.services.parsing import parse_job_description, parse_resume


def update_resume_structure(db: Session, resume: Resume, text: str) -> None:
    parsed = parse_resume(text)
    resume.extracted_text = text
    resume.structured_data = parsed
    resume.confirmed = False


def invalidate_resume_analyses(db: Session, resume_id: str) -> int:
    """Discard derived output that no longer corresponds to the edited résumé text."""
    return _invalidate_analyses(db, Analysis.resume_id == resume_id, ready=False)


def invalidate_job_analyses(db: Session, job_description_id: str) -> int:
    """Discard derived output that no longer corresponds to the edited job text."""
    return _invalidate_analyses(db, Analysis.job_description_id == job_description_id, ready=None)


def mark_resume_analyses_ready(db: Session, resume_id: str) -> int:
    analyses = list(
        db.scalars(
            select(Analysis).where(
                Analysis.resume_id == resume_id,
                Analysis.deterministic_complete.is_(False),
            )
        ).all()
    )
    for analysis in analyses:
        analysis.state = "ready"
        analysis.error_message = None
    return len(analyses)


def _invalidate_analyses(db: Session, condition: ColumnElement[bool], *, ready: bool | None) -> int:
    analyses = list(db.scalars(select(Analysis).where(condition)).all())
    if not analyses:
        return 0
    analysis_ids = [analysis.id for analysis in analyses]
    for model in (
        AnalysisScore,
        MatchEvidence,
        Recommendation,
        InterviewQuestion,
        ProviderRun,
    ):
        db.execute(delete(model).where(model.analysis_id.in_(analysis_ids)))
    for analysis in analyses:
        is_ready = analysis.resume.confirmed if ready is None else ready
        analysis.state = "ready" if is_ready else "draft"
        analysis.overall_score = None
        analysis.deterministic_complete = False
        analysis.model_status = "not_requested"
        analysis.result = {}
        analysis.error_message = None
    return len(analyses)


def create_job_description(db: Session, text: str) -> JobDescription:
    parsed = parse_job_description(text)
    job = JobDescription(
        raw_text=text,
        title=parsed["title"],
        employer=parsed["employer"],
        location=parsed["location"],
        structured_data={key: value for key, value in parsed.items() if key != "requirements"},
    )
    db.add(job)
    db.flush()
    for item in parsed["requirements"]:
        db.add(JobRequirement(job_description_id=job.id, **item))
    db.flush()
    db.refresh(job)
    return job


def update_job_description(db: Session, job: JobDescription, text: str) -> None:
    parsed = parse_job_description(text)
    job.raw_text = text
    job.title = parsed["title"]
    job.employer = parsed["employer"]
    job.location = parsed["location"]
    job.structured_data = {key: value for key, value in parsed.items() if key != "requirements"}
    db.execute(delete(JobRequirement).where(JobRequirement.job_description_id == job.id))
    for item in parsed["requirements"]:
        db.add(JobRequirement(job_description_id=job.id, **item))

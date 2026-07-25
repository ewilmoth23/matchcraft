import structlog
from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import MatchCraftError
from app.db.session import get_db
from app.models import JobDescription
from app.schemas.domain import JobDescriptionCreate, JobDescriptionRead
from app.services.deletion import delete_job_description
from app.services.persistence import (
    create_job_description,
    invalidate_job_analyses,
    update_job_description,
)

router = APIRouter()
logger = structlog.get_logger()


def _get_job(job_id: str, db: Session) -> JobDescription:
    job = db.get(JobDescription, job_id)
    if not job:
        raise MatchCraftError("job_description_not_found", "Job description not found.", 404)
    return job


@router.post("", response_model=JobDescriptionRead, status_code=status.HTTP_201_CREATED)
def create_job(payload: JobDescriptionCreate, db: Session = Depends(get_db)) -> JobDescription:
    job = create_job_description(db, payload.text)
    db.commit()
    db.refresh(job)
    logger.info(
        "job_description_parsed",
        job_description_id=job.id,
        requirement_count=len(job.requirements),
    )
    return job


@router.get("/{job_id}", response_model=JobDescriptionRead)
def get_job(job_id: str, db: Session = Depends(get_db)) -> JobDescription:
    return _get_job(job_id, db)


@router.put("/{job_id}", response_model=JobDescriptionRead)
def update_job(
    job_id: str, payload: JobDescriptionCreate, db: Session = Depends(get_db)
) -> JobDescription:
    job = _get_job(job_id, db)
    update_job_description(db, job, payload.text)
    invalidated = invalidate_job_analyses(db, job.id)
    db.commit()
    db.refresh(job)
    logger.info(
        "job_description_updated",
        job_description_id=job.id,
        invalidated_analysis_count=invalidated,
    )
    return job


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job(
    job_id: str,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Response:
    delete_job_description(db, _get_job(job_id, db), settings)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

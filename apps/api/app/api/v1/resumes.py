import structlog
from fastapi import APIRouter, Depends, File, Response, UploadFile, status
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.core.config import Settings, get_settings
from app.core.errors import MatchCraftError
from app.db.session import get_db
from app.models import Resume
from app.schemas.domain import ResumeCreateText, ResumeRead, ResumeUpdate
from app.services.deletion import delete_resume as delete_resume_cascade
from app.services.documents import (
    delete_stored_document,
    extract_document,
    safe_display_filename,
    store_document,
    validate_document,
)
from app.services.persistence import (
    invalidate_resume_analyses,
    mark_resume_analyses_ready,
    update_resume_structure,
)

router = APIRouter()
logger = structlog.get_logger()


def _get_resume(resume_id: str, db: Session) -> Resume:
    resume = db.get(Resume, resume_id)
    if not resume:
        raise MatchCraftError("resume_not_found", "Résumé not found.", 404)
    return resume


@router.post("/text", response_model=ResumeRead, status_code=status.HTTP_201_CREATED)
def create_text_resume(payload: ResumeCreateText, db: Session = Depends(get_db)) -> Resume:
    resume = Resume(source_type="text", original_text=payload.text, extracted_text=payload.text)
    db.add(resume)
    db.flush()
    update_resume_structure(db, resume, payload.text)
    db.commit()
    db.refresh(resume)
    logger.info("resume_text_created", resume_id=resume.id)
    return resume


@router.post("/upload", response_model=ResumeRead, status_code=status.HTTP_201_CREATED)
async def upload_resume(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Resume:
    data = await file.read(settings.max_upload_bytes + 1)
    extension = validate_document(data, file.filename, settings)
    extracted = await run_in_threadpool(extract_document, data, extension)
    stored_name = await run_in_threadpool(store_document, data, extension, settings)
    try:
        resume = Resume(
            source_type="upload",
            original_filename=safe_display_filename(file.filename),
            stored_filename=stored_name,
            media_type=extracted.media_type,
            file_size=len(data),
            original_text=extracted.text,
            extracted_text=extracted.text,
            extraction_warnings=extracted.warnings,
        )
        db.add(resume)
        db.flush()
        update_resume_structure(db, resume, extracted.text)
        resume.confirmed = False
        db.commit()
        db.refresh(resume)
        logger.info(
            "resume_uploaded",
            resume_id=resume.id,
            media_type=resume.media_type,
            file_size=resume.file_size,
            warning_count=len(resume.extraction_warnings),
        )
        return resume
    except Exception:
        delete_stored_document(stored_name, settings)
        raise


@router.get("/{resume_id}", response_model=ResumeRead)
def get_resume(resume_id: str, db: Session = Depends(get_db)) -> Resume:
    return _get_resume(resume_id, db)


@router.put("/{resume_id}", response_model=ResumeRead)
def update_resume(resume_id: str, payload: ResumeUpdate, db: Session = Depends(get_db)) -> Resume:
    resume = _get_resume(resume_id, db)
    update_resume_structure(db, resume, payload.extracted_text)
    invalidated = invalidate_resume_analyses(db, resume.id)
    db.commit()
    db.refresh(resume)
    logger.info(
        "resume_extraction_updated", resume_id=resume.id, invalidated_analysis_count=invalidated
    )
    return resume


@router.post("/{resume_id}/confirm", response_model=ResumeRead)
def confirm_resume(resume_id: str, db: Session = Depends(get_db)) -> Resume:
    resume = _get_resume(resume_id, db)
    if not resume.extracted_text.strip():
        raise MatchCraftError(
            "resume_text_missing", "Provide readable résumé text before confirming.", 422
        )
    resume.confirmed = True
    mark_resume_analyses_ready(db, resume.id)
    db.commit()
    db.refresh(resume)
    return resume


@router.delete("/{resume_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_resume(
    resume_id: str,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Response:
    delete_resume_cascade(db, _get_resume(resume_id, db), settings)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

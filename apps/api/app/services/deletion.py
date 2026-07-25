"""Cascade deletion of analyses and their unshared source records.

The three delete routes previously reimplemented this transaction independently and
had drifted: the staging order differed between them, and only one variant had a
rollback test. Deleting résumé data is the one operation that cannot be undone, so it
belongs in a single reviewed place.

Ordering contract, identical for every entry point:

1. Count references so a source shared by another analysis is never removed.
2. Delete the ORM rows, letting the configured cascades run.
3. Stage the corresponding files with an atomic rename — never an unlink.
4. Commit. On any failure, roll back the transaction *and* restore the staged files.
5. Only after a successful commit, finalize the staged files.
"""

from collections.abc import Callable, Iterable, Sequence

import structlog
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import Analysis, JobDescription, Resume
from app.services.documents import (
    StagedFileDeletion,
    finalize_staged_deletions,
    restore_staged_deletions,
    stage_export_deletions,
    stage_stored_document_deletion,
)

logger = structlog.get_logger()


def _commit_with_staged_files(
    db: Session, stage: Callable[[list[StagedFileDeletion]], None]
) -> list[StagedFileDeletion]:
    """Stage files and commit, restoring every staged file if anything fails.

    The list is owned here and passed *into* the staging callback rather than returned
    from it. If staging itself raises part-way — an unreadable export path, a permission
    error between two uploads — a list built inside the callback would be discarded and
    the already-renamed files would be unrecoverable while their rows rolled back.
    """
    staged: list[StagedFileDeletion] = []
    try:
        stage(staged)
        db.commit()
    except Exception:
        db.rollback()
        restore_staged_deletions(staged)
        raise
    return staged


def _stage_documents(
    staged: list[StagedFileDeletion],
    stored_filenames: Iterable[str | None],
    analysis_ids: Sequence[str],
    settings: Settings,
) -> None:
    """Append every file to remove to `staged` as it is renamed, never in bulk."""
    for stored_filename in stored_filenames:
        deletion = stage_stored_document_deletion(stored_filename, settings)
        if deletion:
            staged.append(deletion)
    stage_export_deletions(list(analysis_ids), settings, into=staged)


def delete_analysis(db: Session, analysis: Analysis, settings: Settings) -> None:
    """Delete one analysis plus any source record it no longer shares."""
    analysis_id = analysis.id
    resume_id = analysis.resume_id
    job_id = analysis.job_description_id
    resume_is_orphaned = not db.scalar(
        select(func.count(Analysis.id)).where(
            Analysis.resume_id == resume_id, Analysis.id != analysis_id
        )
    )
    job_is_orphaned = not db.scalar(
        select(func.count(Analysis.id)).where(
            Analysis.job_description_id == job_id, Analysis.id != analysis_id
        )
    )
    stored_filename = analysis.resume.stored_filename

    db.delete(analysis)
    db.flush()
    # The logs below report what was actually deleted, not what was eligible.
    resume_deleted = False
    job_deleted = False
    if resume_is_orphaned:
        resume = db.get(Resume, resume_id)
        if resume:
            db.delete(resume)
            resume_deleted = True
    if job_is_orphaned:
        job = db.get(JobDescription, job_id)
        if job:
            db.delete(job)
            job_deleted = True

    staged = _commit_with_staged_files(
        db,
        lambda staged: _stage_documents(
            staged, [stored_filename] if resume_deleted else [], [analysis_id], settings
        ),
    )
    logger.info(
        "analysis_deleted",
        analysis_id=analysis_id,
        source_resume_deleted=resume_deleted,
        source_job_deleted=job_deleted,
        cleanup_failure_count=finalize_staged_deletions(staged),
    )


def delete_resume(db: Session, resume: Resume, settings: Settings) -> None:
    """Delete a résumé, its analyses, and any job description left with no analysis."""
    resume_id = resume.id
    stored_filename = resume.stored_filename
    analysis_rows = db.execute(
        select(Analysis.id, Analysis.job_description_id).where(Analysis.resume_id == resume_id)
    ).all()
    orphaned_job_ids = {
        job_id
        for _, job_id in analysis_rows
        if not db.scalar(
            select(func.count(Analysis.id)).where(
                Analysis.job_description_id == job_id, Analysis.resume_id != resume_id
            )
        )
    }

    db.delete(resume)
    db.flush()
    deleted_job_count = 0
    for job_id in orphaned_job_ids:
        job = db.get(JobDescription, job_id)
        if job:
            db.delete(job)
            deleted_job_count += 1

    staged = _commit_with_staged_files(
        db,
        lambda staged: _stage_documents(
            staged, [stored_filename], [analysis_id for analysis_id, _ in analysis_rows], settings
        ),
    )
    logger.info(
        "resume_deleted",
        resume_id=resume_id,
        analysis_count=len(analysis_rows),
        source_job_count=deleted_job_count,
        cleanup_failure_count=finalize_staged_deletions(staged),
    )


def delete_job_description(db: Session, job: JobDescription, settings: Settings) -> None:
    """Delete a job description, its analyses, and any résumé left with no analysis."""
    job_id = job.id
    analysis_rows = db.execute(
        select(Analysis.id, Analysis.resume_id).where(Analysis.job_description_id == job_id)
    ).all()
    orphaned_resume_ids = {
        resume_id
        for _, resume_id in analysis_rows
        if not db.scalar(
            select(func.count(Analysis.id)).where(
                Analysis.resume_id == resume_id, Analysis.job_description_id != job_id
            )
        )
    }

    db.delete(job)
    db.flush()
    stored_filenames: list[str | None] = []
    for resume_id in orphaned_resume_ids:
        resume = db.get(Resume, resume_id)
        if resume:
            stored_filenames.append(resume.stored_filename)
            db.delete(resume)

    staged = _commit_with_staged_files(
        db,
        lambda staged: _stage_documents(
            staged, stored_filenames, [analysis_id for analysis_id, _ in analysis_rows], settings
        ),
    )
    logger.info(
        "job_description_deleted",
        job_description_id=job_id,
        analysis_count=len(analysis_rows),
        source_resume_count=len(stored_filenames),
        cleanup_failure_count=finalize_staged_deletions(staged),
    )

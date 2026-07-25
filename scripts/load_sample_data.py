#!/usr/bin/env python3
import sys
from pathlib import Path

from sqlalchemy.exc import OperationalError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.db.session import SessionLocal  # noqa: E402
from app.models import Analysis, Resume  # noqa: E402
from app.services.analysis import execute_deterministic_analysis  # noqa: E402
from app.services.persistence import (  # noqa: E402
    create_job_description,
    update_resume_structure,
)

PAIRS = [
    ("technical_resume.txt", "software_engineer_job.txt"),
    ("operations_resume.txt", "technical_project_manager_job.txt"),
]


def main() -> None:
    try:
        with SessionLocal() as db:
            for resume_name, job_name in PAIRS:
                resume_text = (ROOT / "sample_data" / resume_name).read_text(encoding="utf-8")
                job_text = (ROOT / "sample_data" / job_name).read_text(encoding="utf-8")
                resume = Resume(
                    source_type="text",
                    original_text=resume_text,
                    extracted_text=resume_text,
                    confirmed=True,
                )
                db.add(resume)
                db.flush()
                update_resume_structure(db, resume, resume_text)
                resume.confirmed = True
                job = create_job_description(db, job_text)
                analysis = Analysis(
                    resume_id=resume.id,
                    job_description_id=job.id,
                    name=f"{job.title or 'Target role'} — synthetic sample",
                    state="analyzing",
                    model_status="skipped",
                )
                db.add(analysis)
                db.flush()
                db.refresh(analysis)
                execute_deterministic_analysis(db, analysis)
                analysis.state = "completed"
            db.commit()
    except OperationalError as exc:
        raise SystemExit("Database schema unavailable. Run 'make migrate' first.") from exc
    print(f"Loaded {len(PAIRS)} synthetic analyses.")


if __name__ == "__main__":
    main()

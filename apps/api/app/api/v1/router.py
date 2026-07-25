from fastapi import APIRouter

from app.api.v1 import analyses, health, jobs, resumes, settings

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(resumes.router, prefix="/resumes", tags=["resumes"])
api_router.include_router(jobs.router, prefix="/job-descriptions", tags=["job descriptions"])
api_router.include_router(analyses.router, prefix="/analyses", tags=["analyses"])
api_router.include_router(settings.router, prefix="/settings", tags=["settings"])

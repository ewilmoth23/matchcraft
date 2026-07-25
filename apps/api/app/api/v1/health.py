from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import __version__
from app.core.config import get_settings
from app.core.errors import MatchCraftError
from app.db.session import get_db
from app.schemas.domain import HealthResponse, LivenessResponse
from app.services.model_analysis import check_provider_health
from app.services.runtime_settings import runtime_settings

router = APIRouter()


@router.get("/health/live", response_model=LivenessResponse)
def liveness(db: Session = Depends(get_db)) -> LivenessResponse:
    """Container liveness: is this instance able to serve requests?

    Deliberately separate from `/health`. That endpoint probes the configured model
    providers over the network, so its latency depends on a third party — a firewalled
    or black-holed Ollama host made it take longer than the container probe's own
    timeout, marking a perfectly healthy API unhealthy and preventing the web container
    from ever starting.

    It also returns HTTP 200 with `status: degraded` when the database is unusable,
    which a probe checking only the status code cannot see. This one fails loudly
    instead, because an instance that cannot reach its database cannot serve anything.
    """
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        raise MatchCraftError(
            "database_unavailable", "The local database could not be reached.", 503
        ) from exc
    return LivenessResponse(status="healthy", version=__version__)


@router.get("/health", response_model=HealthResponse)
async def health(db: Session = Depends(get_db)) -> HealthResponse:
    database = "healthy"
    try:
        db.execute(text("SELECT 1"))
        settings = runtime_settings(db)
    except Exception:
        database = "unavailable"
        settings = get_settings()
    checks, active_provider = await check_provider_health(settings)
    return HealthResponse(
        version=__version__,
        status="healthy" if database == "healthy" else "degraded",
        database=database,
        provider=settings.provider,
        deterministic_analysis="available" if database == "healthy" else "unavailable",
        ai_features="available" if active_provider else "unavailable",
        active_provider=active_provider,
        provider_checks=checks,
        remote_fallback_configured=(
            settings.provider == "local_first" and settings.remote_provider_configured
        ),
    )

import re
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app import __version__
from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.errors import MatchCraftError, matchcraft_error_handler
from app.core.logging import configure_logging
from app.services.documents import sweep_staged_deletions

configure_logging()
logger = structlog.get_logger()
settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings.ensure_directories()
    reclaimed = sweep_staged_deletions(settings)
    if reclaimed:
        logger.info("staged_deletion_residue_reclaimed", file_count=reclaimed)
    logger.info("application_started", environment=settings.env)
    yield
    logger.info("application_stopped")


# Interactive documentation is a development convenience. Serving it in production
# exposes the full route surface and loads Swagger assets from a third-party CDN,
# which contradicts the local-first privacy model.
_docs_enabled = settings.env != "production"

app = FastAPI(
    title="MatchCraft API",
    version=__version__,
    description=(
        "Private, evidence-grounded résumé-to-role analysis. Scores are decision-support aids "
        "and do not predict hiring outcomes."
    ),
    lifespan=lifespan,
    docs_url="/docs" if _docs_enabled else None,
    redoc_url="/redoc" if _docs_enabled else None,
    openapi_url="/openapi.json" if _docs_enabled else None,
)
if "*" not in settings.allowed_hosts:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-Request-ID"],
)
app.add_exception_handler(MatchCraftError, matchcraft_error_handler)  # type: ignore[arg-type]


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    logger.warning("request_validation_failed", error_count=len(exc.errors()))
    safe_details = [
        {key: value for key, value in error.items() if key in {"loc", "msg", "type"}}
        for error in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "validation_error",
                "message": "The request could not be validated.",
                "details": jsonable_encoder(safe_details),
            }
        },
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(_: Request, exc: Exception) -> JSONResponse:
    # Deliberately omit exception text: database/provider errors can embed document values.
    logger.error("unhandled_request_error", error_type=type(exc).__name__)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "internal_error",
                "message": "The request could not be completed. Check local service health and logs.",
                "details": None,
            }
        },
    )


# Multipart bodies are spooled to disk during dependency resolution, before any route
# code runs, so the declared length has to be rejected in middleware to actually avoid
# buffering. A modest allowance covers multipart framing overhead.
MULTIPART_OVERHEAD_BYTES = 8 * 1024


@app.middleware("http")
async def reject_oversized_body(request: Request, call_next):  # type: ignore[no-untyped-def]
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > settings.max_upload_bytes + MULTIPART_OVERHEAD_BYTES:
        logger.warning("request_body_too_large", declared_bytes=int(declared))
        return JSONResponse(
            status_code=413,
            content={
                "error": {
                    "code": "file_too_large",
                    "message": (
                        f"The request exceeds the "
                        f"{settings.max_upload_bytes // (1024 * 1024)} MB upload limit."
                    ),
                    "details": None,
                }
            },
        )
    return await call_next(request)


@app.middleware("http")
async def request_context(request: Request, call_next):  # type: ignore[no-untyped-def]
    supplied_request_id = request.headers.get("X-Request-ID", "")
    request_id = (
        supplied_request_id
        if re.fullmatch(r"[A-Fa-f0-9-]{16,64}", supplied_request_id)
        else str(uuid.uuid4())
    )
    structlog.contextvars.bind_contextvars(request_id=request_id)
    start = time.perf_counter()
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        # The API is published on its own port, so the web server's headers do not apply.
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Cache-Control", "no-store")
        logger.info(
            "request_completed",
            method=request.method,
            path=getattr(request.scope.get("route"), "path", "<unmatched>"),
            status_code=response.status_code,
            duration_ms=round((time.perf_counter() - start) * 1000),
        )
        return response
    finally:
        structlog.contextvars.clear_contextvars()


app.include_router(api_router, prefix=settings.api_prefix)


@app.get("/", include_in_schema=False)
def root() -> dict[str, str]:
    # Only advertise interactive documentation when it is actually mounted; in
    # production it is disabled and this pointed at a 404.
    links = {"name": "MatchCraft API", "version": __version__, "health": "/api/v1/health"}
    if _docs_enabled:
        links["docs"] = "/docs"
    return links

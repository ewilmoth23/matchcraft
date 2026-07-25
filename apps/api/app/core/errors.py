from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse


class MatchCraftError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400, details: Any = None):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details
        super().__init__(message)


class ProviderError(Exception):
    """Raised when model output is rejected or a provider cannot be reached.

    Lives in `core` rather than `providers` because both the transport adapters and the
    deterministic fabrication validators in `app.analysis` raise it; defining it in the
    provider package made those two layers depend on each other.
    """

    def __init__(self, code: str, message: str, retryable: bool = False):
        self.code = code
        self.message = message
        self.retryable = retryable
        super().__init__(message)


async def matchcraft_error_handler(_: Request, exc: MatchCraftError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message, "details": exc.details}},
    )

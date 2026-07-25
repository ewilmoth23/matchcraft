from dataclasses import dataclass
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel

from app.core.errors import ProviderError
from app.schemas.provider import ModelAnalysisOutput, ModelBulletRewrite

__all__ = ["ModelProvider", "ProviderError", "ProviderResponse"]


@dataclass(frozen=True)
class ProviderResponse:
    output: ModelAnalysisOutput | ModelBulletRewrite
    usage: dict[str, Any]
    provider: str | None = None
    model: str | None = None


T = TypeVar("T", bound=BaseModel)


class ModelProvider(Protocol):
    name: str
    model: str

    async def available(self) -> bool: ...

    async def analyze(self, resume_text: str, job_text: str) -> ProviderResponse: ...

    async def rewrite_bullet(
        self, original_bullet: str, resume_text: str, job_text: str
    ) -> ProviderResponse: ...

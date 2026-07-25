from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.config import validate_provider_url


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ResumeCreateText(BaseModel):
    text: str = Field(min_length=1, max_length=100_000)

    @field_validator("text")
    @classmethod
    def meaningful_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Résumé text cannot be blank")
        return value.strip()


class ResumeUpdate(BaseModel):
    extracted_text: str = Field(min_length=1, max_length=100_000)

    @field_validator("extracted_text")
    @classmethod
    def meaningful_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Extracted résumé text cannot be blank")
        return value.strip()


class ResumeRead(ORMModel):
    id: str
    source_type: str
    original_filename: str | None
    media_type: str | None
    file_size: int | None
    original_text: str
    extracted_text: str
    structured_data: dict[str, Any]
    extraction_warnings: list[str]
    confirmed: bool
    created_at: datetime
    updated_at: datetime


class JobDescriptionCreate(BaseModel):
    text: str = Field(min_length=1, max_length=150_000)

    @field_validator("text")
    @classmethod
    def meaningful_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Job description cannot be blank")
        return value.strip()


class RequirementRead(ORMModel):
    id: str
    category: str
    text: str
    normalized_key: str | None
    priority: Literal["required", "preferred", "context"]
    explicitness: Literal["explicit", "inferred", "ambiguous"]
    source_excerpt: str


class JobDescriptionRead(ORMModel):
    id: str
    raw_text: str
    title: str | None
    employer: str | None
    location: str | None
    structured_data: dict[str, Any]
    requirements: list[RequirementRead]
    created_at: datetime
    updated_at: datetime


class AnalysisCreate(BaseModel):
    resume_id: str
    job_description_id: str
    name: str | None = Field(default=None, max_length=200)

    @field_validator("name")
    @classmethod
    def meaningful_optional_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Analysis name cannot be blank")
        return cleaned


class AnalysisRename(BaseModel):
    name: str = Field(min_length=1, max_length=200)

    @field_validator("name")
    @classmethod
    def meaningful_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Analysis name cannot be blank")
        return cleaned


class RunAnalysisRequest(BaseModel):
    use_model: bool = True


class ScoreRead(ORMModel):
    id: str
    category: str
    score: float
    maximum: float
    reason: str
    improvements: list[str]


class EvidenceRead(ORMModel):
    id: str
    requirement_id: str | None
    requirement: str
    status: Literal["supported", "not_found", "transferable", "ambiguous"]
    resume_excerpt: str | None
    source_section: str | None
    confidence: Literal["high", "medium", "low"]
    interpretation: str | None


class RecommendationRead(ORMModel):
    id: str
    priority: str
    title: str
    explanation: str
    supporting_evidence: str | None
    role_reason: str
    recommended_action: str
    confidence: str
    confirmation_required: bool
    source: str
    status: str


class RecommendationUpdate(BaseModel):
    status: Literal["open", "accepted", "dismissed"]


class InterviewQuestionRead(ORMModel):
    id: str
    category: str
    question: str
    talking_points: list[str]
    resume_evidence: str | None
    confidence: str
    source: str


class AnalysisSummary(ORMModel):
    id: str
    name: str
    state: str
    overall_score: float | None
    model_status: str
    created_at: datetime
    updated_at: datetime
    target_job_title: str | None = None
    target_employer: str | None = None


class AnalysisDetail(AnalysisSummary):
    resume_id: str
    job_description_id: str
    deterministic_complete: bool
    result: dict[str, Any]
    error_message: str | None
    scores: list[ScoreRead]
    evidence: list[EvidenceRead]
    recommendations: list[RecommendationRead]
    interview_questions: list[InterviewQuestionRead]


class BulletRewriteRequest(BaseModel):
    original_bullet: str = Field(min_length=2, max_length=2_000)


class BulletRewriteResponse(BaseModel):
    original_bullet: str
    suggested_bullet: str
    reason: str
    factual_sources: list[str]
    confirmation_required: bool
    model_generated: bool
    warning: str


class SettingsRead(BaseModel):
    provider: str
    local_model: str
    local_provider_url: str
    remote_model: str
    remote_provider_url: str
    openai_reasoning_effort: str
    ollama_context_tokens: int
    remote_api_key_configured: bool
    remote_fallback_configured: bool
    # Kept for compatibility with pre-local-first clients.
    model: str
    provider_url: str
    model_temperature: float
    model_max_tokens: int
    model_timeout_seconds: float
    model_retries: int
    max_upload_bytes: int
    data_dir: str
    remote_provider_warning: bool


class SettingsUpdate(BaseModel):
    provider: Literal["local_first", "ollama", "openai_compatible", "disabled"] | None = None
    local_model: str | None = Field(default=None, min_length=1, max_length=100)
    remote_model: str | None = Field(default=None, min_length=1, max_length=100)
    local_provider_url: str | None = Field(default=None, min_length=8, max_length=500)
    remote_provider_url: str | None = Field(default=None, min_length=8, max_length=500)
    openai_reasoning_effort: Literal["none", "low", "medium", "high"] | None = None
    ollama_context_tokens: int | None = Field(default=None, ge=4096, le=131072)
    # Kept for compatibility with pre-local-first clients.
    model: str | None = Field(default=None, min_length=1, max_length=100)
    model_temperature: float | None = Field(default=None, ge=0, le=1)
    model_max_tokens: int | None = Field(default=None, ge=256, le=16000)
    model_timeout_seconds: float | None = Field(default=None, ge=1, le=300)
    model_retries: int | None = Field(default=None, ge=0, le=3)
    provider_url: str | None = Field(default=None, min_length=8, max_length=500)

    @field_validator("model", "local_model", "remote_model")
    @classmethod
    def meaningful_model_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Model name cannot be blank")
        return cleaned

    @field_validator("provider_url", "local_provider_url", "remote_provider_url")
    @classmethod
    def safe_provider_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        # Shared with the environment validator so a runtime override cannot reach a
        # target the environment configuration would have rejected.
        return validate_provider_url(value)


class LivenessResponse(BaseModel):
    """Container liveness. Fails when the instance cannot serve, never on a provider."""

    status: Literal["healthy"]
    version: str


class HealthResponse(BaseModel):
    status: str
    version: str
    database: str
    provider: str
    deterministic_analysis: str = "available"
    ai_features: str
    active_provider: str | None = None
    provider_checks: list["ProviderHealth"] = Field(default_factory=list)
    remote_fallback_configured: bool = False


class ProviderHealth(BaseModel):
    provider: str
    model: str
    status: Literal["available", "unavailable", "not_configured"]
    local: bool

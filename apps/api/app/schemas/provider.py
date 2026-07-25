from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModelOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ModelRecommendation(StrictModelOutput):
    priority: Literal["Critical", "High impact", "Moderate impact", "Optional polish"]
    title: str = Field(min_length=3, max_length=200)
    explanation: str = Field(min_length=3, max_length=1500)
    supporting_evidence: str | None = Field(max_length=1000)
    role_reason: str = Field(min_length=3, max_length=1000)
    recommended_action: str = Field(min_length=3, max_length=1000)
    confidence: Literal["high", "medium", "low"]
    confirmation_required: bool


class ModelInterviewQuestion(StrictModelOutput):
    category: Literal["technical", "behavioral", "experience_gap"]
    question: str = Field(min_length=5, max_length=600)
    talking_points: list[str] = Field(max_length=5)
    resume_evidence: str | None = Field(max_length=1000)
    confidence: Literal["high", "medium", "low"]


class ModelAnalysisOutput(StrictModelOutput):
    executive_summary: str = Field(min_length=10, max_length=2000)
    responsibility_alignment: float = Field(ge=0, le=1)
    transferable_experience: list[str] = Field(max_length=5)
    recommendations: list[ModelRecommendation] = Field(max_length=5)
    interview_questions: list[ModelInterviewQuestion] = Field(max_length=6)
    limitations: list[str] = Field(max_length=5)


class ModelBulletRewrite(StrictModelOutput):
    suggested_bullet: str = Field(min_length=2, max_length=2000)
    reason: str = Field(min_length=3, max_length=1000)
    factual_sources: list[str] = Field(min_length=1, max_length=5)
    confirmation_required: bool

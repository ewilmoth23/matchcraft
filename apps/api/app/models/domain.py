import uuid
from typing import Any

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


def new_id() -> str:
    return str(uuid.uuid4())


class Resume(TimestampMixin, Base):
    __tablename__ = "resumes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    source_type: Mapped[str] = mapped_column(String(20), index=True)
    original_filename: Mapped[str | None] = mapped_column(String(255))
    stored_filename: Mapped[str | None] = mapped_column(String(64), unique=True)
    media_type: Mapped[str | None] = mapped_column(String(100))
    file_size: Mapped[int | None] = mapped_column(Integer)
    original_text: Mapped[str] = mapped_column(Text, default="")
    extracted_text: Mapped[str] = mapped_column(Text, default="")
    structured_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    extraction_warnings: Mapped[list[str]] = mapped_column(JSON, default=list)
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    analyses: Mapped[list["Analysis"]] = relationship(
        back_populates="resume", cascade="all, delete-orphan"
    )


class JobDescription(TimestampMixin, Base):
    __tablename__ = "job_descriptions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    raw_text: Mapped[str] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(String(200), index=True)
    employer: Mapped[str | None] = mapped_column(String(200), index=True)
    location: Mapped[str | None] = mapped_column(String(200))
    structured_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    requirements: Mapped[list["JobRequirement"]] = relationship(
        back_populates="job_description", cascade="all, delete-orphan"
    )
    analyses: Mapped[list["Analysis"]] = relationship(
        back_populates="job_description", cascade="all, delete-orphan"
    )


class JobRequirement(TimestampMixin, Base):
    __tablename__ = "job_requirements"
    __table_args__ = (Index("ix_job_requirements_job_category", "job_description_id", "category"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    job_description_id: Mapped[str] = mapped_column(
        ForeignKey("job_descriptions.id", ondelete="CASCADE")
    )
    category: Mapped[str] = mapped_column(String(40), index=True)
    text: Mapped[str] = mapped_column(Text)
    normalized_key: Mapped[str | None] = mapped_column(String(160), index=True)
    priority: Mapped[str] = mapped_column(String(20), index=True)
    explicitness: Mapped[str] = mapped_column(String(20), default="explicit")
    source_excerpt: Mapped[str] = mapped_column(Text)

    job_description: Mapped[JobDescription] = relationship(back_populates="requirements")


class Analysis(TimestampMixin, Base):
    __tablename__ = "analyses"
    __table_args__ = (Index("ix_analyses_state_updated", "state", "updated_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    resume_id: Mapped[str] = mapped_column(ForeignKey("resumes.id", ondelete="CASCADE"))
    job_description_id: Mapped[str] = mapped_column(
        ForeignKey("job_descriptions.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(200), default="Untitled analysis")
    state: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    overall_score: Mapped[float | None] = mapped_column(Float)
    deterministic_complete: Mapped[bool] = mapped_column(Boolean, default=False)
    model_status: Mapped[str] = mapped_column(String(30), default="not_requested")
    result: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text)

    resume: Mapped[Resume] = relationship(back_populates="analyses")
    job_description: Mapped[JobDescription] = relationship(back_populates="analyses")
    scores: Mapped[list["AnalysisScore"]] = relationship(
        back_populates="analysis", cascade="all, delete-orphan", order_by="AnalysisScore.created_at"
    )
    evidence: Mapped[list["MatchEvidence"]] = relationship(
        back_populates="analysis", cascade="all, delete-orphan", order_by="MatchEvidence.created_at"
    )
    recommendations: Mapped[list["Recommendation"]] = relationship(
        back_populates="analysis",
        cascade="all, delete-orphan",
        order_by="Recommendation.created_at",
    )
    interview_questions: Mapped[list["InterviewQuestion"]] = relationship(
        back_populates="analysis",
        cascade="all, delete-orphan",
        order_by="InterviewQuestion.created_at",
    )
    provider_runs: Mapped[list["ProviderRun"]] = relationship(
        back_populates="analysis", cascade="all, delete-orphan"
    )


class AnalysisScore(TimestampMixin, Base):
    __tablename__ = "analysis_scores"
    __table_args__ = (Index("ux_analysis_scores_category", "analysis_id", "category", unique=True),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    analysis_id: Mapped[str] = mapped_column(ForeignKey("analyses.id", ondelete="CASCADE"))
    category: Mapped[str] = mapped_column(String(80))
    score: Mapped[float] = mapped_column(Float)
    maximum: Mapped[float] = mapped_column(Float)
    reason: Mapped[str] = mapped_column(Text)
    improvements: Mapped[list[str]] = mapped_column(JSON, default=list)

    analysis: Mapped[Analysis] = relationship(back_populates="scores")


class MatchEvidence(TimestampMixin, Base):
    __tablename__ = "match_evidence"
    __table_args__ = (Index("ix_match_evidence_analysis_status", "analysis_id", "status"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    analysis_id: Mapped[str] = mapped_column(ForeignKey("analyses.id", ondelete="CASCADE"))
    requirement_id: Mapped[str | None] = mapped_column(
        ForeignKey("job_requirements.id", ondelete="SET NULL")
    )
    requirement: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), index=True)
    resume_excerpt: Mapped[str | None] = mapped_column(Text)
    source_section: Mapped[str | None] = mapped_column(String(100))
    confidence: Mapped[str] = mapped_column(String(20))
    interpretation: Mapped[str | None] = mapped_column(Text)

    analysis: Mapped[Analysis] = relationship(back_populates="evidence")


class Recommendation(TimestampMixin, Base):
    __tablename__ = "recommendations"
    __table_args__ = (Index("ix_recommendations_analysis_priority", "analysis_id", "priority"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    analysis_id: Mapped[str] = mapped_column(ForeignKey("analyses.id", ondelete="CASCADE"))
    priority: Mapped[str] = mapped_column(String(30))
    title: Mapped[str] = mapped_column(String(200))
    explanation: Mapped[str] = mapped_column(Text)
    supporting_evidence: Mapped[str | None] = mapped_column(Text)
    role_reason: Mapped[str] = mapped_column(Text)
    recommended_action: Mapped[str] = mapped_column(Text)
    confidence: Mapped[str] = mapped_column(String(20))
    confirmation_required: Mapped[bool] = mapped_column(Boolean, default=False)
    source: Mapped[str] = mapped_column(String(30), default="deterministic")
    status: Mapped[str] = mapped_column(String(20), default="open")

    analysis: Mapped[Analysis] = relationship(back_populates="recommendations")


class InterviewQuestion(TimestampMixin, Base):
    __tablename__ = "interview_questions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    analysis_id: Mapped[str] = mapped_column(ForeignKey("analyses.id", ondelete="CASCADE"))
    category: Mapped[str] = mapped_column(String(30))
    question: Mapped[str] = mapped_column(Text)
    talking_points: Mapped[list[str]] = mapped_column(JSON, default=list)
    resume_evidence: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[str] = mapped_column(String(20), default="medium")
    source: Mapped[str] = mapped_column(String(30), default="deterministic")

    analysis: Mapped[Analysis] = relationship(back_populates="interview_questions")


class ProviderRun(TimestampMixin, Base):
    __tablename__ = "provider_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    analysis_id: Mapped[str] = mapped_column(ForeignKey("analyses.id", ondelete="CASCADE"))
    provider: Mapped[str] = mapped_column(String(40))
    model: Mapped[str] = mapped_column(String(100))
    feature: Mapped[str] = mapped_column(String(60))
    status: Mapped[str] = mapped_column(String(30))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    usage: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    error_code: Mapped[str | None] = mapped_column(String(60))

    analysis: Mapped[Analysis] = relationship(back_populates="provider_runs")


class ApplicationSetting(TimestampMixin, Base):
    __tablename__ = "application_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[dict[str, Any]] = mapped_column(JSON)

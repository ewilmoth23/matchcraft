"""Anti-fabrication rules for model output.

These are domain rules, not transport concerns: they decide whether generated prose
may claim a skill, metric, credential, date, or named entity. They lived in the HTTP
adapter, which forced `services/model_analysis.py` to import domain validation from a
transport module and made `providers/` depend on `analysis/`.

Every sanitizer returns `(output, removed_count)` and never raises; every validator
raises `ProviderError` with a code that maps to a retry correction in
`providers/http.py`.
"""

import re

from app.analysis.text import extract_skill_evidence
from app.core.errors import ProviderError
from app.schemas.provider import ModelAnalysisOutput, ModelBulletRewrite

CLAIM_TERMS = {
    "architected",
    "budget",
    "certified",
    "directed",
    "clients",
    "customers",
    "degree",
    "efficiency",
    "generated",
    "increased",
    "latency",
    "led",
    "leadership",
    "managed",
    "owned",
    "performance",
    "reduced",
    "revenue",
    "saved",
    "team",
    "supervised",
    "users",
    "vendors",
}

SENSITIVE_TERMS = CLAIM_TERMS | {
    "administrator",
    "analyst",
    "architect",
    "bachelor",
    "certification",
    "consultant",
    "coordinator",
    "credential",
    "degree",
    "developer",
    "director",
    "doctorate",
    "engineer",
    "license",
    "licensed",
    "manager",
    "master",
    "mba",
    "officer",
    "phd",
    "president",
    "specialist",
}
DATE_TERMS = {
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
}
CAPITALIZED_STARTERS = {
    "a",
    "an",
    "ask",
    "adds",
    "based",
    "candidate",
    "can",
    "clarify",
    "clarifies",
    "consider",
    "could",
    "describe",
    "discuss",
    "evidence",
    "explain",
    "focus",
    "highlight",
    "highlights",
    "human",
    "how",
    "improves",
    "keeps",
    "matchcraft",
    "missing",
    "no",
    "prepare",
    "preserves",
    "polishes",
    "review",
    "strengthens",
    "the",
    "these",
    "this",
    "tell",
    "use",
    "using",
    "what",
    "when",
    "where",
    "why",
    "your",
}


def _normalize_excerpt(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def _is_excerpt(value: str, source: str) -> bool:
    return _normalize_excerpt(value) in _normalize_excerpt(source)


def sanitize_analysis_evidence(
    output: ModelAnalysisOutput, resume_text: str
) -> tuple[ModelAnalysisOutput, int]:
    """Fail closed per evidence field while preserving independently validated insights."""
    sanitized_count = 0
    transferable_experience = []
    seen_transferable: set[str] = set()
    for excerpt in output.transferable_experience:
        normalized = _normalize_excerpt(excerpt)
        if _is_excerpt(excerpt, resume_text) and normalized not in seen_transferable:
            transferable_experience.append(excerpt)
            seen_transferable.add(normalized)
        else:
            sanitized_count += 1

    recommendations = []
    for recommendation in output.recommendations:
        evidence = recommendation.supporting_evidence
        if evidence and not _is_excerpt(evidence, resume_text):
            evidence = None
            sanitized_count += 1
        recommendations.append(recommendation.model_copy(update={"supporting_evidence": evidence}))

    interview_questions = []
    for question in output.interview_questions:
        evidence = question.resume_evidence
        if evidence and not _is_excerpt(evidence, resume_text):
            evidence = None
            sanitized_count += 1
        talking_points = []
        for point in question.talking_points:
            if _is_excerpt(point, resume_text):
                talking_points.append(point)
            else:
                sanitized_count += 1
        interview_questions.append(
            question.model_copy(
                update={"resume_evidence": evidence, "talking_points": talking_points}
            )
        )

    return (
        output.model_copy(
            update={
                "transferable_experience": transferable_experience,
                "recommendations": recommendations,
                "interview_questions": interview_questions,
            }
        ),
        sanitized_count,
    )


def sanitize_analysis_skills(
    output: ModelAnalysisOutput, resume_text: str, job_text: str
) -> tuple[ModelAnalysisOutput, int]:
    """Drop complete fields/items that introduce a cataloged skill absent from both sources."""
    source_skills = set(_skill_names(f"{resume_text}\n{job_text}"))

    def unsupported(value: str) -> bool:
        return not set(_skill_names(value)).issubset(source_skills)

    sanitized_count = 0
    executive_summary = output.executive_summary
    if unsupported(executive_summary):
        executive_summary = (
            "The model-assisted analysis was limited to source-grounded items that passed "
            "MatchCraft validation."
        )
        sanitized_count += 1

    recommendations = []
    for recommendation in output.recommendations:
        prose = "\n".join(
            (
                recommendation.title,
                recommendation.explanation,
                recommendation.role_reason,
                recommendation.recommended_action,
            )
        )
        if unsupported(prose):
            sanitized_count += 1
        else:
            recommendations.append(recommendation)

    interview_questions = []
    for question in output.interview_questions:
        if unsupported(question.question):
            sanitized_count += 1
        else:
            interview_questions.append(question)

    limitations = []
    for limitation in output.limitations:
        if unsupported(limitation):
            sanitized_count += 1
        else:
            limitations.append(limitation)

    return (
        output.model_copy(
            update={
                "executive_summary": executive_summary,
                "recommendations": recommendations,
                "interview_questions": interview_questions,
                "limitations": limitations,
            }
        ),
        sanitized_count,
    )


def sanitize_analysis_prose(
    output: ModelAnalysisOutput, resume_text: str, job_text: str
) -> tuple[ModelAnalysisOutput, int]:
    """Drop independent prose items containing unsupported factual claim markers.

    Evidence excerpts have their own exact-source sanitizer. Generated prose is kept only
    when every recognized number, skill, sensitive term, and capitalized entity is grounded
    in one of the supplied texts. Dropping a complete item avoids trying to repair model text.
    """
    combined_source = f"{resume_text}\n{job_text}"
    source_numbers = set(re.findall(r"\b\d+(?:\.\d+)?\b", combined_source))
    source_skills = set(_skill_names(combined_source))

    def unsupported(value: str) -> bool:
        without_placeholders = re.sub(r"\[[^]]+\]", "", value)
        numbers = set(re.findall(r"\b\d+(?:\.\d+)?\b", without_placeholders))
        return bool(
            not numbers.issubset(source_numbers)
            or not set(_skill_names(value)).issubset(source_skills)
            or _unsupported_sensitive_terms(value, combined_source)
            or _unsupported_capitalized_terms(value, combined_source)
        )

    sanitized_count = 0
    executive_summary = output.executive_summary
    if unsupported(executive_summary):
        executive_summary = (
            "The model-assisted analysis was limited to source-grounded items that passed "
            "MatchCraft validation."
        )
        sanitized_count += 1

    recommendations = []
    for recommendation in output.recommendations:
        prose = "\n".join(
            (
                recommendation.title,
                recommendation.explanation,
                recommendation.role_reason,
                recommendation.recommended_action,
            )
        )
        if unsupported(prose):
            sanitized_count += 1
        else:
            recommendations.append(recommendation)

    interview_questions = []
    for question in output.interview_questions:
        if unsupported(question.question):
            sanitized_count += 1
        else:
            interview_questions.append(question)

    limitations = []
    for limitation in output.limitations:
        if unsupported(limitation):
            sanitized_count += 1
        else:
            limitations.append(limitation)

    return (
        output.model_copy(
            update={
                "executive_summary": executive_summary,
                "recommendations": recommendations,
                "interview_questions": interview_questions,
                "limitations": limitations,
            }
        ),
        sanitized_count,
    )


def validate_analysis_output(
    output: ModelAnalysisOutput, resume_text: str, job_text: str = ""
) -> None:
    invalid: list[str] = []
    for recommendation in output.recommendations:
        if not recommendation.confirmation_required:
            raise ProviderError(
                "confirmation_required",
                "Model-generated recommendations must require human confirmation.",
            )
        if recommendation.supporting_evidence and not _is_excerpt(
            recommendation.supporting_evidence, resume_text
        ):
            invalid.append(recommendation.supporting_evidence)
    for question in output.interview_questions:
        if question.resume_evidence and not _is_excerpt(question.resume_evidence, resume_text):
            invalid.append(question.resume_evidence)
        invalid.extend(
            point for point in question.talking_points if not _is_excerpt(point, resume_text)
        )
    for excerpt in output.transferable_experience:
        if not _is_excerpt(excerpt, resume_text):
            invalid.append(excerpt)
    if invalid:
        raise ProviderError(
            "unsupported_model_evidence",
            "Model output referenced evidence that was not found in the stored résumé.",
        )
    combined_source = f"{resume_text}\n{job_text}"
    source_numbers = set(re.findall(r"\b\d+(?:\.\d+)?\b", combined_source))
    source_skills = set(_skill_names(combined_source))
    text_fields = [
        output.executive_summary,
        *output.transferable_experience,
        *output.limitations,
        *(
            value
            for item in output.recommendations
            for value in (
                item.title,
                item.explanation,
                item.role_reason,
                item.recommended_action,
            )
        ),
        *(
            value
            for item in output.interview_questions
            for value in (
                item.question,
                *item.talking_points,
            )
        ),
    ]
    model_text = "\n".join(text_fields)
    model_text_without_placeholders = re.sub(r"\[[^]]+\]", "", model_text)
    model_numbers = set(re.findall(r"\b\d+(?:\.\d+)?\b", model_text_without_placeholders))
    if not model_numbers.issubset(source_numbers):
        raise ProviderError(
            "fabricated_metric",
            "Model analysis introduced a numeric claim absent from the supplied texts.",
        )
    if not set(_skill_names(model_text)).issubset(source_skills):
        raise ProviderError(
            "fabricated_skill",
            "Model analysis introduced a recognized skill absent from the supplied texts.",
        )
    if _unsupported_sensitive_terms(model_text, combined_source):
        raise ProviderError(
            "fabricated_claim",
            "Model analysis introduced a sensitive claim absent from the supplied texts.",
        )
    if _unsupported_capitalized_terms(model_text, combined_source):
        raise ProviderError(
            "fabricated_entity",
            "Model analysis introduced a named entity absent from the supplied texts.",
        )


def _unsupported_claim_terms(suggestion: str, source: str) -> set[str]:
    clean_suggestion = re.sub(r"\[[^]]+\]", "", suggestion).casefold()
    source_words = set(re.findall(r"[a-z]+", source.casefold()))
    suggestion_words = set(re.findall(r"[a-z]+", clean_suggestion))
    return (suggestion_words & CLAIM_TERMS) - source_words


def _unsupported_sensitive_terms(suggestion: str, source: str) -> set[str]:
    clean_suggestion = re.sub(r"\[[^]]+\]", "", suggestion).casefold()
    source_words = set(re.findall(r"[a-z]+", source.casefold()))
    suggestion_words = set(re.findall(r"[a-z]+", clean_suggestion))
    date_words = suggestion_words & DATE_TERMS
    return ((suggestion_words & SENSITIVE_TERMS) | date_words) - source_words


def _unsupported_capitalized_terms(suggestion: str, source: str) -> set[str]:
    source_words = {
        token.strip(".+#-") for token in re.findall(r"[a-z][a-z0-9.+#-]*", source.casefold())
    }
    unsupported: set[str] = set()
    # A sentence-initial capital is grammar, not a claimed proper noun. Treating it as
    # a fabricated entity silently discarded every recommendation whose title began
    # with an imperative verb ("Add detail to the Docker work"). ALL-CAPS tokens are
    # still checked, because those are acronyms rather than sentence case.
    for sentence in re.split(r"(?:^|[.!?]\s+|\n+)", suggestion):
        for index, token in enumerate(re.findall(r"\b[A-Z][A-Za-z0-9.+#-]*\b", sentence)):
            if index == 0 and not token.isupper():
                continue
            normalized = token.casefold().strip(".+#-")
            if normalized not in source_words and normalized not in CAPITALIZED_STARTERS:
                unsupported.add(token)
    return unsupported


def validate_bullet_rewrite(
    output: ModelBulletRewrite, original_bullet: str, resume_text: str
) -> None:
    if not all(_is_excerpt(source, resume_text) for source in output.factual_sources):
        raise ProviderError(
            "unsupported_model_evidence", "The rewrite cited a source not found in the résumé."
        )
    if not any(
        _normalize_excerpt(source) == _normalize_excerpt(original_bullet)
        for source in output.factual_sources
    ):
        raise ProviderError(
            "unsupported_model_evidence",
            "The rewrite did not cite the exact original bullet as a factual source.",
        )
    if not output.confirmation_required:
        raise ProviderError(
            "confirmation_required", "Model-generated rewrites must require human confirmation."
        )
    if re.search(r"\[[^]]+\]", original_bullet) and not re.search(
        r"\[[^]]+\]", output.suggested_bullet
    ):
        raise ProviderError(
            "removed_placeholder",
            "The rewrite removed an unknown-value placeholder from the original bullet.",
        )
    original_without_placeholders = re.sub(r"\[[^]]+\]", "", original_bullet)
    source_numbers = set(re.findall(r"\b\d+(?:\.\d+)?\b", original_without_placeholders))
    suggestion_without_placeholders = re.sub(r"\[[^]]+\]", "", output.suggested_bullet)
    new_numbers = set(re.findall(r"\b\d+(?:\.\d+)?\b", suggestion_without_placeholders))
    if not new_numbers.issubset(source_numbers):
        raise ProviderError(
            "fabricated_metric",
            "The rewrite introduced a numeric claim not present in the original bullet.",
        )
    if not source_numbers.issubset(new_numbers):
        raise ProviderError(
            "dropped_fact",
            "The rewrite removed a numeric fact from the original bullet.",
        )
    original_skills = set(extract for extract in _skill_names(original_bullet))
    rewritten_skills = set(extract for extract in _skill_names(output.suggested_bullet))
    if not rewritten_skills.issubset(original_skills):
        raise ProviderError(
            "fabricated_skill", "The rewrite introduced a skill not present in the original bullet."
        )
    if not original_skills.issubset(rewritten_skills):
        raise ProviderError(
            "dropped_fact", "The rewrite removed a recognized skill from the original bullet."
        )
    original_placeholders = set(re.findall(r"\[[^]]+\]", original_bullet.casefold()))
    rewritten_placeholders = set(re.findall(r"\[[^]]+\]", output.suggested_bullet.casefold()))
    if not original_placeholders.issubset(rewritten_placeholders):
        raise ProviderError(
            "dropped_fact", "The rewrite changed or removed an unknown-value placeholder."
        )
    original_sensitive = _sensitive_words(original_bullet)
    rewritten_sensitive = _sensitive_words(output.suggested_bullet)
    if not original_sensitive.issubset(rewritten_sensitive):
        raise ProviderError(
            "dropped_fact", "The rewrite removed a sensitive factual term from the original bullet."
        )
    if not _capitalized_fact_terms(original_bullet).issubset(
        _capitalized_fact_terms(output.suggested_bullet)
    ):
        raise ProviderError(
            "dropped_fact", "The rewrite removed a named entity from the original bullet."
        )
    model_text = f"{output.suggested_bullet}\n{output.reason}"
    model_text_without_placeholders = re.sub(r"\[[^]]+\]", "", model_text)
    model_numbers = set(re.findall(r"\b\d+(?:\.\d+)?\b", model_text_without_placeholders))
    if not model_numbers.issubset(source_numbers):
        raise ProviderError(
            "fabricated_metric",
            "The rewrite response introduced a numeric claim not present in the original bullet.",
        )
    if not set(_skill_names(model_text)).issubset(original_skills):
        raise ProviderError(
            "fabricated_skill",
            "The rewrite response introduced a skill not present in the original bullet.",
        )
    unsupported_claims = _unsupported_claim_terms(model_text, original_bullet)
    if unsupported_claims:
        raise ProviderError(
            "fabricated_claim",
            "The rewrite introduced a claim type not supported by the original bullet.",
        )
    if _unsupported_sensitive_terms(model_text, original_bullet):
        raise ProviderError(
            "fabricated_claim",
            "The rewrite introduced a sensitive claim not supported by the original bullet.",
        )
    if _unsupported_capitalized_terms(model_text, original_bullet):
        raise ProviderError(
            "fabricated_entity",
            "The rewrite introduced a named entity not present in the original bullet.",
        )


def _sensitive_words(value: str) -> set[str]:
    words = set(re.findall(r"[a-z]+", re.sub(r"\[[^]]+\]", "", value).casefold()))
    return words & (SENSITIVE_TERMS | DATE_TERMS)


def _capitalized_fact_terms(value: str) -> set[str]:
    facts: set[str] = set()
    for sentence in re.split(r"(?:^|[.!?]\s+|\n+)", value):
        tokens = re.findall(r"\b[A-Z][A-Za-z0-9.+#-]*\b", sentence)
        for index, token in enumerate(tokens):
            if index == 0 and not token.isupper():
                continue
            if token.casefold() not in CAPITALIZED_STARTERS:
                facts.add(token.casefold())
    return facts


def _skill_names(value: str) -> list[str]:
    return list(extract_skill_evidence(value))

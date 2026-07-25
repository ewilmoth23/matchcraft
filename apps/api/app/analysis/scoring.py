import re
from dataclasses import dataclass
from math import isfinite
from typing import Any

from app.analysis.text import (
    SkillEvidence,
    bullet_lines,
    date_formats_consistent,
    extract_skill_evidence,
    measurable_result,
    repeated_phrases,
    significant_terms,
    starts_with_action_verb,
)

# Non-catalog requirement matching, calibrated against the labeled evaluation corpus
# (`make eval`) rather than chosen by intuition. The previous 0.55 supported-threshold
# was badly mis-calibrated: a sweep over the corpus measured evidence accuracy at 0.599
# with 66 under-credits against 3 over-credits, meaning genuinely demonstrated
# qualifications were routinely reported as merely transferable.
#
# 0.30 measures 0.767. A further move to a single shared term reaches 0.779, and is
# deliberately NOT taken: it doubles over-crediting (6 -> 12). Telling someone a
# requirement is covered when the résumé does not show it is the worse error for this
# product, so the conservative asymmetry is preserved on purpose.
SUPPORTED_OVERLAP = 0.30
TRANSFERABLE_OVERLAP = 0.25
MINIMUM_SHARED_TERMS = 2

# Experience evidence quality reads a fixed-size sample of the strongest bullets, padded
# with the baseline so the category is provably non-decreasing as evidence is added.
EVIDENCE_BULLET_SAMPLE = 6
BASELINE_BULLET_QUALITY = 0.25
# significant_terms takes a limit; this asks for the complete vocabulary.
ALL_TERMS = 10_000

SCORE_WEIGHTS: dict[str, float] = {
    "Required skill alignment": 25,
    "Responsibility alignment": 20,
    "Experience evidence quality": 15,
    "Measurable accomplishment quality": 10,
    "Preferred skill alignment": 10,
    "Résumé clarity and structure": 10,
    "Keyword and terminology alignment": 5,
    "Education and certification alignment": 5,
}


@dataclass(frozen=True)
class EvidenceFinding:
    requirement_id: str | None
    requirement: str
    status: str
    resume_excerpt: str | None
    source_section: str | None
    confidence: str
    interpretation: str | None
    priority: str
    category: str
    contextual: bool = False


@dataclass(frozen=True)
class CategoryScore:
    category: str
    score: float
    maximum: float
    reason: str
    improvements: list[str]


@dataclass(frozen=True)
class DeterministicResult:
    overall_score: float
    scores: list[CategoryScore]
    evidence: list[EvidenceFinding]
    recommendations: list[dict[str, Any]]
    interview_questions: list[dict[str, Any]]
    summary: dict[str, Any]


def validate_score_weights(weights: dict[str, float]) -> None:
    missing = set(SCORE_WEIGHTS) - set(weights)
    if missing:
        raise ValueError(f"Missing score categories: {', '.join(sorted(missing))}")
    unexpected = set(weights) - set(SCORE_WEIGHTS)
    if unexpected:
        raise ValueError(f"Unexpected score categories: {', '.join(sorted(unexpected))}")
    if any(not isfinite(weight) for weight in weights.values()):
        raise ValueError("Score weights must be finite numbers")
    if abs(sum(weights.values()) - 100) > 0.001:
        raise ValueError("Score weights must total exactly 100")
    if any(weight < 0 for weight in weights.values()):
        raise ValueError("Score weights cannot be negative")


def run_deterministic_analysis(
    resume_text: str,
    resume_data: dict[str, Any],
    job_text: str,
    requirements: list[dict[str, Any]],
    weights: dict[str, float] | None = None,
) -> DeterministicResult:
    active_weights = SCORE_WEIGHTS if weights is None else weights
    validate_score_weights(active_weights)
    # Derived once: these are constant for the whole run, and recomputing them per
    # requirement made deterministic analysis O(requirements x résumé length).
    skills = extract_skill_evidence(resume_text)
    repeated = repeated_phrases(resume_text)
    dates_consistent = date_formats_consistent(resume_text)
    findings = [_match_requirement(item, resume_text, resume_data, skills) for item in requirements]
    scores = _score_categories(
        resume_text, resume_data, job_text, findings, active_weights, dates_consistent
    )
    recommendations = _recommendations(
        resume_text, resume_data, findings, repeated, dates_consistent
    )
    questions = _interview_questions(findings)
    strengths = [finding.requirement for finding in findings if finding.status == "supported"][:5]
    gaps = [finding.requirement for finding in findings if finding.status == "not_found"][:5]
    transferable = [
        finding.requirement for finding in findings if finding.status == "transferable"
    ][:5]
    # Categories excluded as not-scored carry a zero maximum, so the total is a
    # percentage of what was actually assessed rather than of a fixed 100.
    assessed = sum(item.maximum for item in scores)
    overall = round(sum(item.score for item in scores) / assessed * 100, 1) if assessed else 0.0
    job_title = next((line.strip() for line in job_text.splitlines() if line.strip()), "")
    resume_titles = [
        str(item.get("title")) for item in resume_data.get("experiences", []) if item.get("title")
    ]
    bullets = resume_data.get("bullets") or bullet_lines(resume_text)
    job_terms = set(significant_terms(job_text, 40))
    bullet_analysis = [
        analyze_bullet(str(bullet), job_text, repeated, job_terms) for bullet in bullets
    ]
    return DeterministicResult(
        overall_score=min(100.0, max(0.0, overall)),
        scores=scores,
        evidence=findings,
        recommendations=recommendations,
        interview_questions=questions,
        summary={
            "top_strengths": strengths,
            "top_gaps": gaps,
            "transferable_experience": transferable,
            "resume_word_count": len(resume_text.split()),
            "job_word_count": len(job_text.split()),
            "date_formats_consistent": dates_consistent,
            "repeated_phrases": repeated,
            "job_title_similarity": _job_title_similarity(job_title, resume_titles),
            "analysis_confidence": (
                "low" if len(requirements) < 3 else "medium" if len(requirements) < 6 else "high"
            ),
            "bullet_analysis": bullet_analysis,
            "disclaimer": (
                "This alignment score is a decision-support aid. It does not predict interviews, "
                "hiring decisions, or candidate quality. Missing evidence is not proof of missing ability."
            ),
        },
    )


def analyze_bullet(
    bullet: str,
    job_text: str,
    repeated: list[str] | None = None,
    job_terms: set[str] | None = None,
) -> dict[str, Any]:
    words = bullet.split()
    action_verb = re.sub(r"[^a-z]", "", words[0].casefold()) if words else ""
    technical_detail = sorted(extract_skill_evidence(bullet))
    if job_terms is None:
        job_terms = set(significant_terms(job_text, 40))
    bullet_terms = set(significant_terms(bullet, 40))
    relevance = len(job_terms & bullet_terms) / max(1, len(job_terms))
    impact = bool(
        re.search(
            r"\b(?:increased|reduced|improved|saved|saving|grew|cut|accelerated|decreased|delivered)\b",
            bullet,
            re.IGNORECASE,
        )
    )
    if 8 <= len(words) <= 35:
        clarity = "high"
    elif 5 <= len(words) <= 45:
        clarity = "medium"
    else:
        clarity = "low"
    return {
        "original_bullet": bullet,
        "action_verb": action_verb or None,
        "action_led": starts_with_action_verb(bullet),
        "task_clarity": clarity,
        "technical_detail": technical_detail,
        "business_impact": impact,
        "measurable_outcome": measurable_result(bullet),
        "job_relevance": round(min(1.0, relevance), 2),
        "length_words": len(words),
        "redundant_phrases": [phrase for phrase in (repeated or []) if phrase in bullet.casefold()],
        "unsupported_claims": (
            ["Contains a bracketed value that requires verification."]
            if re.search(r"\[[^]]+\]", bullet)
            else []
        ),
        "verification_note": "User-supplied résumé claims are not independently verified.",
    }


def _job_title_similarity(job_title: str, resume_titles: list[str]) -> float:
    job_terms = set(significant_terms(job_title, 10))
    if not job_terms or not resume_titles:
        return 0.0
    similarities = []
    for title in resume_titles:
        title_terms = set(significant_terms(title, 10))
        similarities.append(len(job_terms & title_terms) / max(1, len(job_terms | title_terms)))
    return round(max(similarities), 2)


def _match_requirement(
    requirement: dict[str, Any],
    resume_text: str,
    resume_data: dict[str, Any],
    skills: dict[str, SkillEvidence] | None = None,
) -> EvidenceFinding:
    category = str(requirement.get("category", "context"))
    text = str(requirement.get("text", "")).strip()
    priority = str(requirement.get("priority", "context"))
    requirement_id = requirement.get("id")
    if skills is None:
        skills = extract_skill_evidence(resume_text)

    if category in {"skill", "tool_context"}:
        evidence = skills.get(text)
        if evidence:
            section = _source_section_for_excerpt(evidence.excerpt, resume_data)
            return EvidenceFinding(
                str(requirement_id) if requirement_id else None,
                text,
                "supported",
                evidence.excerpt,
                section,
                "high" if evidence.contextual else "medium",
                "Direct terminology match in résumé text.",
                priority,
                category,
                evidence.contextual,
            )
        return EvidenceFinding(
            str(requirement_id) if requirement_id else None,
            text,
            "not_found",
            None,
            None,
            "high",
            "No normalized skill match was found; this does not prove the candidate lacks the skill.",
            priority,
            category,
        )

    resume_lines = [
        line.strip().lstrip("•-*–— ") for line in resume_text.splitlines() if line.strip()
    ]
    requirement_terms = set(significant_terms(text, 20))
    best_line: str | None = None
    best_overlap = 0.0
    for line in resume_lines:
        line_terms = set(significant_terms(line, 30))
        shared = requirement_terms & line_terms
        overlap = len(shared) / max(1, len(requirement_terms))
        # A single shared term is enough only for a short requirement, where one term is
        # most of its meaning ("Bilingual Spanish"). Longer requirements still need two.
        minimum_shared = 1 if len(requirement_terms) <= 2 else MINIMUM_SHARED_TERMS
        if len(shared) >= minimum_shared and overlap > best_overlap:
            best_line, best_overlap = line, overlap

    if category in {"education", "certification"}:
        relevant = "\n".join(
            resume_data.get("education", []) + resume_data.get("certifications", [])
        )
        overlap_terms = requirement_terms & set(significant_terms(relevant, 50))
        if relevant and len(overlap_terms) >= max(1, min(2, len(requirement_terms))):
            excerpt = next(
                (
                    line
                    for line in relevant.splitlines()
                    if overlap_terms & set(significant_terms(line))
                ),
                relevant[:500],
            )
            return EvidenceFinding(
                str(requirement_id) if requirement_id else None,
                text,
                "supported",
                excerpt,
                category.title(),
                "medium",
                "Relevant terms appear in the corresponding résumé section; equivalence may require review.",
                priority,
                category,
            )

    if best_line and best_overlap >= SUPPORTED_OVERLAP:
        return EvidenceFinding(
            str(requirement_id) if requirement_id else None,
            text,
            "supported",
            best_line,
            _source_section_for_excerpt(best_line, resume_data),
            "medium",
            "Substantial terminology overlap was found in a résumé statement.",
            priority,
            category,
        )
    if best_line and best_overlap >= TRANSFERABLE_OVERLAP:
        return EvidenceFinding(
            str(requirement_id) if requirement_id else None,
            text,
            "transferable",
            best_line,
            _source_section_for_excerpt(best_line, resume_data),
            "medium",
            "The résumé statement may demonstrate transferable experience; it is not an exact match.",
            priority,
            category,
        )
    return EvidenceFinding(
        str(requirement_id) if requirement_id else None,
        text,
        "not_found",
        None,
        None,
        "medium",
        "No sufficiently similar evidence was found in the supplied résumé.",
        priority,
        category,
    )


def _source_section_for_excerpt(excerpt: str, resume_data: dict[str, Any]) -> str | None:
    for section in resume_data.get("sections", []):
        if excerpt.casefold() in str(section.get("content", "")).casefold():
            return str(section.get("heading") or section.get("kind") or "Résumé")
    return "Résumé"


def _score_categories(
    resume_text: str,
    resume_data: dict[str, Any],
    job_text: str,
    findings: list[EvidenceFinding],
    weights: dict[str, float],
    dates_consistent: bool | None = None,
) -> list[CategoryScore]:
    if dates_consistent is None:
        dates_consistent = date_formats_consistent(resume_text)
    scores: list[CategoryScore] = []
    required_skills = [f for f in findings if f.category == "skill" and f.priority == "required"]
    preferred_skills = [f for f in findings if f.category == "skill" and f.priority == "preferred"]
    responsibilities = [
        f
        for f in findings
        if f.category in {"responsibility", "tool_context"}
        or (f.category in {"experience", "qualification"} and f.priority == "required")
    ]
    education = [
        f
        for f in findings
        if f.category in {"education", "certification"} and f.priority == "required"
    ]

    scores.append(_coverage_score("Required skill alignment", required_skills, weights, 1.0, 0.0))
    scores.append(_coverage_score("Responsibility alignment", responsibilities, weights, 1.0, 0.55))

    bullets = resume_data.get("bullets") or bullet_lines(resume_text)
    if bullets:
        qualities = []
        for bullet in bullets:
            quality = BASELINE_BULLET_QUALITY
            quality += 0.25 if starts_with_action_verb(bullet) else 0
            quality += 0.25 if len(bullet.split()) >= 8 else 0
            quality += 0.25 if measurable_result(bullet) else 0
            qualities.append(quality)
        # The strongest evidence, over a fixed-size sample padded with the baseline.
        #
        # A plain mean meant adding a real extra role lowered the score whenever its
        # bullets were slightly weaker. Taking the top N alone was still not monotone:
        # a résumé with fewer than N bullets had its sample filled by whatever was added,
        # so twelve junk lines diluted it. Padding the sample to a fixed size with the
        # baseline value makes the category provably non-decreasing — a new bullet can
        # only ever displace a pad or a weaker bullet, never a stronger one.
        sample = sorted(qualities, reverse=True)[:EVIDENCE_BULLET_SAMPLE]
        sample += [BASELINE_BULLET_QUALITY] * (EVIDENCE_BULLET_SAMPLE - len(sample))
        evidence_ratio = sum(sample) / EVIDENCE_BULLET_SAMPLE
    else:
        evidence_ratio = 0.2
    max_experience = weights["Experience evidence quality"]
    scores.append(
        CategoryScore(
            "Experience evidence quality",
            round(max_experience * evidence_ratio, 1),
            max_experience,
            f"{len(bullets)} résumé bullet(s) were checked for action, detail, and outcomes.",
            []
            if evidence_ratio >= 0.7
            else ["Use concise action-led bullets with concrete outcomes supported by real facts."],
        )
    )

    measurable_count = sum(measurable_result(bullet) for bullet in bullets)
    measurable_ratio = min(1.0, measurable_count / max(1, min(3, len(bullets)))) if bullets else 0
    max_measurable = weights["Measurable accomplishment quality"]
    scores.append(
        CategoryScore(
            "Measurable accomplishment quality",
            round(max_measurable * measurable_ratio, 1),
            max_measurable,
            f"{measurable_count} of {len(bullets)} bullet(s) contain a metric tied to impact.",
            []
            if measurable_ratio >= 0.7
            else ["Add verified scope or outcome metrics where you know the real values."],
        )
    )

    scores.append(_coverage_score("Preferred skill alignment", preferred_skills, weights, 1.0, 0.0))

    section_kinds = {str(section.get("kind")) for section in resume_data.get("sections", [])}
    contact = resume_data.get("contact", {})
    # Clarity scores only structural signals a reader can verify. Two former checks were
    # removed after the evaluation harness measured what they actually did:
    #
    # - Employment-date formatting lowered the score on 13 of 16 corpus cases purely
    #   because a caregiving break adds a differently formatted date range. Penalizing a
    #   career gap is precisely the disparate impact this product promises not to create.
    # - A hard 200-1,400 word band is a step function, so any text addition could cross
    #   it. It made irrelevant padding *raise* the score by up to 3.6 points and adding a
    #   genuine role *lower* it — rewarding the gaming behaviour the docs claim to resist.
    #
    # Both remain recommendations, where they belong: they are writing advice, not
    # evidence of a qualification.
    clarity_checks = [
        bool(contact.get("email") or contact.get("phone")),
        "experience" in section_kinds,
        "skills" in section_kinds,
        "education" in section_kinds,
    ]
    clarity_ratio = sum(clarity_checks) / len(clarity_checks)
    max_clarity = weights["Résumé clarity and structure"]
    missing_sections = [
        name for name in ("experience", "skills", "education") if name not in section_kinds
    ]
    scores.append(
        CategoryScore(
            "Résumé clarity and structure",
            round(max_clarity * clarity_ratio, 1),
            max_clarity,
            f"Passed {sum(clarity_checks)} of {len(clarity_checks)} deterministic structure checks.",
            [f"Use a recognizable {name.title()} heading." for name in missing_sections],
        )
    )

    job_terms = set(significant_terms(job_text, 25))
    # The whole résumé vocabulary, not a top-N slice. Truncating by frequency meant a
    # padded or keyword-stuffed résumé evicted its own genuine terms from the sample and
    # scored *lower* — the opposite of the documented anti-stuffing behaviour.
    resume_terms = set(significant_terms(resume_text, ALL_TERMS))
    keyword_ratio = len(job_terms & resume_terms) / max(1, len(job_terms))
    max_keyword = weights["Keyword and terminology alignment"]
    scores.append(
        CategoryScore(
            "Keyword and terminology alignment",
            round(max_keyword * min(1.0, keyword_ratio), 1),
            max_keyword,
            f"{len(job_terms & resume_terms)} of {len(job_terms)} prominent job terms appear in the résumé.",
            []
            if keyword_ratio >= 0.6
            else [
                "Use relevant employer terminology only where it accurately describes existing experience."
            ],
        )
    )
    scores.append(
        _coverage_score("Education and certification alignment", education, weights, 1.0, 0.5)
    )
    return scores


def _coverage_score(
    name: str,
    findings: list[EvidenceFinding],
    weights: dict[str, float],
    supported_value: float,
    transferable_value: float,
) -> CategoryScore:
    maximum = weights[name]
    if not findings:
        # Not scored at all, rather than scored full marks. Awarding the points meant an
        # undetected requirement became indistinguishable from a met one: the evaluation
        # corpus showed an executive assistant scoring 56/100 against an HVAC technician
        # role, 35 points of which were free credit for two categories with no detected
        # requirements. A zero maximum removes the category from the total instead, so
        # the score reflects only what was actually assessed.
        return CategoryScore(
            name,
            0.0,
            0.0,
            "Not scored: no requirement of this kind was detected in the job description. "
            "The candidate is not penalized, and this category is excluded from the total "
            "rather than counted as alignment.",
            ["Confirm the job description states its requirements under a recognizable heading."],
        )
    credit = 0.0
    for finding in findings:
        if finding.status == "supported":
            credit += (
                supported_value * 0.75
                if finding.category in {"skill", "tool_context"} and not finding.contextual
                else supported_value
            )
        elif finding.status == "transferable":
            credit += transferable_value
    ratio = credit / len(findings)
    missing = [finding.requirement for finding in findings if finding.status == "not_found"]
    return CategoryScore(
        name,
        round(maximum * ratio, 1),
        maximum,
        f"Evidence supported {round(credit, 1)} of {len(findings)} detected item(s); only bare skills-list evidence receives reduced credit.",
        [f"Confirm genuine experience before adding: {item}" for item in missing[:3]],
    )


def _recommendations(
    resume_text: str,
    resume_data: dict[str, Any],
    findings: list[EvidenceFinding],
    repeated: list[str] | None = None,
    dates_consistent: bool | None = None,
) -> list[dict[str, Any]]:
    if repeated is None:
        repeated = repeated_phrases(resume_text)
    if dates_consistent is None:
        dates_consistent = date_formats_consistent(resume_text)
    result: list[dict[str, Any]] = []
    for finding in [item for item in findings if item.status == "not_found"][:5]:
        priority = "Critical" if finding.priority == "required" else "Moderate impact"
        result.append(
            {
                "priority": priority,
                "title": f"Verify evidence for {finding.requirement}",
                "explanation": "The supplied résumé does not contain traceable evidence for this job requirement.",
                "supporting_evidence": None,
                "role_reason": f"The job description identifies this as {finding.priority}.",
                "recommended_action": (
                    "Add it only if you genuinely have the experience, then describe where and how you used it. "
                    "Otherwise, leave it out and prepare to discuss the gap honestly."
                ),
                "confidence": finding.confidence,
                "confirmation_required": True,
                "source": "deterministic",
            }
        )
    bullets = resume_data.get("bullets") or bullet_lines(resume_text)
    weak_bullet = next((bullet for bullet in bullets if not measurable_result(bullet)), None)
    if weak_bullet:
        result.append(
            {
                "priority": "High impact",
                "title": "Strengthen an accomplishment with verified scope",
                "explanation": "A résumé bullet describes work but does not show a measurable result.",
                "supporting_evidence": weak_bullet,
                "role_reason": "Concrete evidence makes relevant experience easier to evaluate.",
                "recommended_action": "If a real metric exists, add it; otherwise improve specificity without inventing a number.",
                "confidence": "high",
                "confirmation_required": True,
                "source": "deterministic",
            }
        )
    long_bullet = next((bullet for bullet in bullets if len(bullet.split()) > 45), None)
    if long_bullet:
        result.append(
            {
                "priority": "Moderate impact",
                "title": "Tighten an unusually long bullet",
                "explanation": "A detected bullet is longer than 45 words and may be difficult to scan.",
                "supporting_evidence": long_bullet,
                "role_reason": "Concise evidence is easier to connect with role requirements.",
                "recommended_action": "Split or trim the statement while preserving every supported fact.",
                "confidence": "high",
                "confirmation_required": False,
                "source": "deterministic",
            }
        )
    if repeated:
        repeated_excerpt = next(
            (
                line.strip().lstrip("•-*–— ")
                for line in resume_text.splitlines()
                if repeated[0] in line.casefold()
            ),
            None,
        )
        result.append(
            {
                "priority": "Optional polish",
                "title": "Reduce repeated résumé phrasing",
                "explanation": f"The phrase '{repeated[0]}' appears across at least three bullets.",
                "supporting_evidence": repeated_excerpt,
                "role_reason": "Varied, accurate phrasing can make distinct accomplishments easier to scan.",
                "recommended_action": "Revise repetition only where an alternative remains factually accurate.",
                "confidence": "medium",
                "confirmation_required": False,
                "source": "deterministic",
            }
        )
    if not dates_consistent:
        result.append(
            {
                "priority": "Optional polish",
                "title": "Use a consistent date format",
                "explanation": "Multiple employment date styles were detected.",
                "supporting_evidence": None,
                "role_reason": "Consistent formatting improves readability without changing dates.",
                "recommended_action": "Choose one date style and preserve the original month/year values.",
                "confidence": "medium",
                "confirmation_required": False,
                "source": "deterministic",
            }
        )
    section_kinds = {str(section.get("kind")) for section in resume_data.get("sections", [])}
    for missing_section in [name for name in ("skills", "education") if name not in section_kinds]:
        result.append(
            {
                "priority": "Optional polish",
                "title": f"Clarify the {missing_section} section",
                "explanation": f"A recognizable {missing_section} heading was not detected.",
                "supporting_evidence": None,
                "role_reason": "Clear section labels improve scanning and deterministic parsing.",
                "recommended_action": f"Use a conventional {missing_section.title()} heading without changing any facts.",
                "confidence": "medium",
                "confirmation_required": False,
                "source": "deterministic",
            }
        )
    return result[:10]


def _interview_questions(findings: list[EvidenceFinding]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for finding in [item for item in findings if item.status == "supported"][:4]:
        result.append(
            {
                "category": "technical"
                if finding.category in {"skill", "tool_context"}
                else "behavioral",
                "question": f"How have you applied {finding.requirement} in your work?",
                "talking_points": [finding.resume_excerpt] if finding.resume_excerpt else [],
                "resume_evidence": finding.resume_excerpt,
                "confidence": finding.confidence,
                "source": "deterministic",
            }
        )
    for finding in [
        item for item in findings if item.status == "not_found" and item.priority == "required"
    ][:3]:
        requirement = finding.requirement.rstrip(" .?!")
        result.append(
            {
                "category": "experience_gap",
                "question": f"How would you address this role requirement: {requirement}?",
                "talking_points": [
                    "Acknowledge the gap accurately; discuss only real adjacent experience or a concrete learning plan."
                ],
                "resume_evidence": None,
                "confidence": "medium",
                "source": "deterministic",
            }
        )
    return result


validate_score_weights(SCORE_WEIGHTS)

import json
import re
from pathlib import Path

import pytest

from app.analysis.scoring import (
    SCORE_WEIGHTS,
    analyze_bullet,
    run_deterministic_analysis,
    validate_score_weights,
)
from app.services.parsing import parse_job_description, parse_resume


def test_weights_total_one_hundred() -> None:
    validate_score_weights(SCORE_WEIGHTS)
    assert sum(SCORE_WEIGHTS.values()) == 100


def test_documented_score_weights_match_executable_weights() -> None:
    root = Path(__file__).parents[3]
    for document in (root / "README.md", root / "docs" / "scoring-model.md"):
        text = document.read_text(encoding="utf-8")
        documented = {
            category: float(value)
            for category, value in re.findall(
                r"^\|\s*([^|]+?)\s*\|\s*(\d+(?:\.\d+)?)\s*\|", text, re.MULTILINE
            )
            if category in SCORE_WEIGHTS
        }
        assert documented == SCORE_WEIGHTS, f"Scoring table drifted in {document}"


def test_weights_reject_missing_and_unknown_categories() -> None:
    with pytest.raises(ValueError, match="Missing"):
        validate_score_weights({})
    with pytest.raises(ValueError, match="Unexpected"):
        validate_score_weights({**SCORE_WEIGHTS, "Undocumented category": 0})
    with pytest.raises(ValueError, match="finite"):
        validate_score_weights({**SCORE_WEIGHTS, "Required skill alignment": float("nan")})


def test_scoring_is_bounded_and_evidence_is_traceable(
    sample_resume_text: str, sample_job_text: str
) -> None:
    resume = parse_resume(sample_resume_text)
    job = parse_job_description(sample_job_text)
    requirements = [
        dict(item, id=f"requirement-{index}") for index, item in enumerate(job["requirements"])
    ]
    result = run_deterministic_analysis(sample_resume_text, resume, sample_job_text, requirements)
    assert 0 <= result.overall_score <= 100
    # Categories with no detected requirement are excluded (zero maximum) rather than
    # awarded full credit, so the assessed total is at most 100 and the score is a
    # percentage of what was actually assessed.
    assessed = sum(score.maximum for score in result.scores)
    assert 0 < assessed <= 100
    assert all(0 <= score.score <= score.maximum for score in result.scores)
    python = next(item for item in result.evidence if item.requirement == "Python")
    kubernetes = next(item for item in result.evidence if item.requirement == "Kubernetes")
    assert python.status == "supported"
    assert python.resume_excerpt in sample_resume_text
    assert kubernetes.status == "not_found"
    assert kubernetes.resume_excerpt is None
    assert "does not prove" in (kubernetes.interpretation or "")
    git = next(item for item in result.evidence if item.requirement == "Git")
    assert git.resume_excerpt is not None
    assert "github.com" not in git.resume_excerpt
    assert all(
        item.resume_excerpt is None or item.resume_excerpt in sample_resume_text
        for item in result.evidence
    )
    assert all(
        item["supporting_evidence"] is None or item["supporting_evidence"] in sample_resume_text
        for item in result.recommendations
    )
    assert all(
        item["resume_evidence"] is None or item["resume_evidence"] in sample_resume_text
        for item in result.interview_questions
    )


def test_keyword_repetition_does_not_create_contextual_evidence(sample_job_text: str) -> None:
    resume_text = "SKILLS\nPython, Python, Python\n\nEDUCATION\nVerified training"
    result = run_deterministic_analysis(
        resume_text,
        parse_resume(resume_text),
        sample_job_text,
        parse_job_description(sample_job_text)["requirements"],
    )
    python = next(item for item in result.evidence if item.requirement == "Python")
    assert python.status == "supported"
    assert python.contextual is False


def test_keyword_stuffing_cannot_earn_contextual_skill_credit() -> None:
    job_text = "Engineer\nRequired Qualifications\n• Python required."
    resume_text = " ".join(["Python"] * 100)
    job = parse_job_description(job_text)
    result = run_deterministic_analysis(
        resume_text, parse_resume(resume_text), job_text, job["requirements"]
    )
    python = next(item for item in result.evidence if item.requirement == "Python")
    required_score = next(
        item for item in result.scores if item.category == "Required skill alignment"
    )
    assert python.contextual is False
    assert required_score.score == 18.8


def test_concrete_skill_evidence_scores_more_than_a_bare_list() -> None:
    job_text = "Engineer\nRequired Qualifications\n• Python is required."
    job = parse_job_description(job_text)
    list_resume = "SKILLS\nPython"
    concrete_resume = "EXPERIENCE\n• Built reliable Python services for production users."
    list_result = run_deterministic_analysis(
        list_resume, parse_resume(list_resume), job_text, job["requirements"]
    )
    concrete_result = run_deterministic_analysis(
        concrete_resume, parse_resume(concrete_resume), job_text, job["requirements"]
    )
    list_score = next(
        item.score for item in list_result.scores if item.category == "Required skill alignment"
    )
    concrete_score = next(
        item.score for item in concrete_result.scores if item.category == "Required skill alignment"
    )
    assert list_score == 18.8
    assert concrete_score == 25


def test_concrete_tool_context_scores_more_than_a_bare_list() -> None:
    job_text = "Engineer\nResponsibilities\n• Build reliable Python services."
    job = parse_job_description(job_text)
    list_resume = "SKILLS\nPython"
    concrete_resume = "EXPERIENCE\n• Built reliable Python services."
    list_result = run_deterministic_analysis(
        list_resume, parse_resume(list_resume), job_text, job["requirements"]
    )
    concrete_result = run_deterministic_analysis(
        concrete_resume, parse_resume(concrete_resume), job_text, job["requirements"]
    )
    list_score = next(
        item.score for item in list_result.scores if item.category == "Responsibility alignment"
    )
    concrete_score = next(
        item.score for item in concrete_result.scores if item.category == "Responsibility alignment"
    )
    assert concrete_score > list_score


def test_skill_evidence_uses_the_section_containing_the_exact_excerpt() -> None:
    resume_text = (
        "EXPERIENCE\n• Built React interfaces for operations teams.\n\n"
        "SKILLS\nPython, SQL, React\n\nEDUCATION\nBachelor of Science"
    )
    requirements = [
        {"id": "react", "text": "React", "category": "skill", "priority": "required"},
        {"id": "sql", "text": "SQL", "category": "skill", "priority": "required"},
    ]

    result = run_deterministic_analysis(
        resume_text, parse_resume(resume_text), "Engineer", requirements
    )

    react = next(item for item in result.evidence if item.requirement == "React")
    sql = next(item for item in result.evidence if item.requirement == "SQL")
    assert react.source_section == "EXPERIENCE"
    assert sql.source_section == "SKILLS"


def test_common_inflections_match_responsibility_evidence() -> None:
    resume_text = "EXPERIENCE\n• Built reliable services and improved automated tests."
    requirements = [
        {
            "id": "responsibility",
            "text": "Build reliable service and improve automated testing.",
            "category": "responsibility",
            "priority": "context",
        }
    ]

    result = run_deterministic_analysis(
        resume_text, parse_resume(resume_text), "Engineer", requirements
    )

    assert result.evidence[0].status == "supported"
    assert result.evidence[0].resume_excerpt in resume_text


def test_gap_interview_question_handles_terminal_punctuation() -> None:
    requirement = "Automated testing and reliable delivery are required."
    result = run_deterministic_analysis(
        "EXPERIENCE\n• Maintained documentation.",
        parse_resume("EXPERIENCE\n• Maintained documentation."),
        "Engineer",
        [
            {
                "id": "qualification",
                "text": requirement,
                "category": "qualification",
                "priority": "required",
            }
        ],
    )

    assert result.interview_questions[0]["question"] == (
        "How would you address this role requirement: "
        "Automated testing and reliable delivery are required?"
    )
    assert ".." not in result.interview_questions[0]["question"]


def test_supported_responsibilities_receive_full_credit() -> None:
    resume_text = "EXPERIENCE\n• Designed reliable payment processing services for customers."
    job_text = (
        "Engineer\nResponsibilities\n• Design reliable payment processing services for customers."
    )
    job = parse_job_description(job_text)
    result = run_deterministic_analysis(
        resume_text, parse_resume(resume_text), job_text, job["requirements"]
    )
    responsibility = next(
        item for item in result.scores if item.category == "Responsibility alignment"
    )
    assert responsibility.score == responsibility.maximum == 20


def test_explicit_experience_requirement_affects_responsibility_score() -> None:
    resume_text = "EXPERIENCE\n• Delivered Python systems across five years of experience."
    job_text = "Engineer\nRequired Qualifications\n• 5+ years of Python systems experience"
    job = parse_job_description(job_text)
    result = run_deterministic_analysis(
        resume_text, parse_resume(resume_text), job_text, job["requirements"]
    )
    experience = next(item for item in result.evidence if item.category == "experience")
    responsibility = next(
        item for item in result.scores if item.category == "Responsibility alignment"
    )
    assert experience.status == "supported"
    assert responsibility.score == responsibility.maximum == 20


def test_recommendation_evidence_is_an_exact_resume_excerpt() -> None:
    resume_text = (
        "EXPERIENCE\n• Built reliable data services.\n"
        "• Tested reliable data pipelines.\n• Shipped reliable data tools."
    )
    result = run_deterministic_analysis(resume_text, parse_resume(resume_text), "Data Engineer", [])
    repeated = next(
        item
        for item in result.recommendations
        if item["title"] == "Reduce repeated résumé phrasing"
    )
    assert repeated["supporting_evidence"] in resume_text


def test_bullet_diagnostics_are_traceable_and_do_not_invent_claims() -> None:
    diagnostics = analyze_bullet(
        "Reduced validation failures by 32% using Python.",
        "Build reliable Python services and reduce validation failures.",
    )

    assert diagnostics["original_bullet"] == "Reduced validation failures by 32% using Python."
    assert diagnostics["action_led"] is True
    assert diagnostics["measurable_outcome"] is True
    assert diagnostics["business_impact"] is True
    assert diagnostics["technical_detail"] == ["Python"]
    assert diagnostics["job_relevance"] > 0
    assert diagnostics["unsupported_claims"] == []


def test_bullet_diagnostics_flag_unverified_placeholders() -> None:
    diagnostics = analyze_bullet(
        "Improved processing speed by [insert verified percentage].",
        "Improve processing speed.",
    )

    assert diagnostics["unsupported_claims"] == [
        "Contains a bracketed value that requires verification."
    ]


def test_synthetic_expected_analysis_fixture(sample_resume_text: str, sample_job_text: str) -> None:
    root = Path(__file__).parents[3]
    expected = json.loads((root / "sample_data" / "expected_technical_analysis.json").read_text())
    job = parse_job_description(sample_job_text)
    result = run_deterministic_analysis(
        sample_resume_text,
        parse_resume(sample_resume_text),
        sample_job_text,
        job["requirements"],
    )
    assert result.overall_score == expected["overall_score"]
    assert {item.category: item.score for item in result.scores} == expected["category_scores"]
    skill_findings = [item for item in result.evidence if item.category == "skill"]
    assert {item.requirement for item in skill_findings if item.status == "supported"} == set(
        expected["supported_skills"]
    )
    assert {item.requirement for item in skill_findings if item.status == "not_found"} == set(
        expected["unsupported_skills"]
    )

"""Regression tests for correctness defects found in the 2026-07-24 expert review.

Each test names the defect it prevents from returning.
"""

import pytest

from app.analysis.fabrication import _unsupported_capitalized_terms
from app.analysis.scoring import run_deterministic_analysis
from app.analysis.text import date_formats_consistent, extract_skill_evidence, significant_terms
from app.services.parsing import _job_section_for_heading, parse_job_description, parse_resume

RESUME = (
    "Dana Chen\n"
    "dana.chen@example.test | (555) 010-9090\n\n"
    "EXPERIENCE\n"
    "Platform Engineer | Example Corp | 2020 - Present\n"
    "•  Built\tPython   services that reduced latency by 30%.\n"
    "• Monitored production dashboards for two regions.\n\n"
    "SKILLS\n"
    "Python, Docker, SQL\n\n"
    "EDUCATION\n"
    "BSc Computer Science | State College | 2019\n"
)


def _run(job_text: str) -> object:
    job = parse_job_description(job_text)
    return run_deterministic_analysis(RESUME, parse_resume(RESUME), job_text, job["requirements"])


def test_trailing_sentence_punctuation_does_not_split_a_term() -> None:
    """ "dashboards." and "dashboards" used to be different terms, flipping a match."""
    with_period = significant_terms("Monitoring dashboards.")
    without_period = significant_terms("Monitoring dashboards")
    assert with_period == without_period
    assert not any(term.endswith(".") for term in with_period)


def test_interior_separators_are_preserved() -> None:
    terms = significant_terms("Node.js and co-ordinate the c++ rollout with asp.net")
    assert "node.js" in terms
    assert "co-ordinate" in terms
    assert "c++" in terms
    assert "asp.net" in terms


def test_trimming_never_produces_an_empty_or_short_term() -> None:
    for term in significant_terms("x.-.- a.. b-- python... docker-"):
        assert len(term) >= 3, term
        assert term == term.strip(".-")


def test_requirement_matching_is_stable_across_sentence_punctuation() -> None:
    with_period = _run("Engineer\nResponsibilities\n• Monitor production dashboards.")
    without_period = _run("Engineer\nResponsibilities\n• Monitor production dashboards")
    assert with_period.overall_score == without_period.overall_score  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    ("heading", "expected"),
    [
        # Colon-terminated labels.
        ("Requirements:", "required"),
        ("Qualifications:", "required"),
        ("Basic Qualifications:", "required"),
        ("What you'll need:", "required"),
        ("Nice to have:", "preferred"),
        # Bare labels, which must clear the coverage threshold on their own.
        ("Minimum Qualifications", "required"),
        ("Preferred Qualifications", "preferred"),
        ("Responsibilities", "context"),
        # Multi-word labels: these scored on their leftmost match alone and were
        # therefore missed, dropping every requirement beneath them.
        ("Duties and Responsibilities", "context"),
        ("Essential Duties and Responsibilities", "context"),
        ("Roles and Responsibilities", "context"),
        ("Day-to-Day Responsibilities", "context"),
        ("Qualifications and Experience", "required"),
        ("Skills and Qualifications", "required"),
        ("Requirements & Qualifications", "required"),
        ("What You'll Bring", "required"),
        ("Experience Required", "required"),
        ("Who you are", "required"),
        ("Nice-to-haves", "preferred"),
    ],
)
def test_realistic_headings_classify_requirements(heading: str, expected: str) -> None:
    """An unrecognized heading silently demoted every requirement under it to context."""
    parsed = parse_job_description(f"Engineer\n{heading}\n• Kubernetes\n")
    kubernetes = next(item for item in parsed["requirements"] if item["text"] == "Kubernetes")
    assert kubernetes["priority"] == expected


def test_responsibility_headings_reach_responsibility_alignment() -> None:
    """A missed responsibility heading removed the bullets from the scored category."""
    parsed = parse_job_description(
        "Engineer\nDuties and Responsibilities\n• Operate the production Kubernetes fleet\n"
    )
    assert any(item["category"] == "responsibility" for item in parsed["requirements"])


def test_a_heading_is_never_stored_as_a_requirement() -> None:
    """A heading kept as a requirement was unmatchable and zeroed responsibility credit."""
    parsed = parse_job_description("Engineer\nMust-have qualifications:\n• Python\n")
    texts = [str(item["text"]).casefold() for item in parsed["requirements"]]
    assert not any("qualification" in text for text in texts)
    assert "python" in texts


def test_an_unrecognized_label_line_is_dropped_but_a_requirement_is_kept() -> None:
    """The colon guard must not swallow a colon-terminated line that states a requirement."""
    parsed = parse_job_description(
        "Engineer\nRequirements\n"
        "Areas of focus:\n"
        "5+ years of experience in the following:\n"
        "Bachelor's degree required in one of the following:\n"
        "• Python\n"
    )
    texts = [str(item["text"]) for item in parsed["requirements"]]
    assert not any(text.startswith("Areas of focus") for text in texts)
    assert any(text.startswith("5+ years") for text in texts)
    assert any(text.startswith("Bachelor's degree") for text in texts)
    assert "Python" in texts


@pytest.mark.parametrize(
    "line",
    [
        "Requirements include Python and Docker",
        "You will need to have 5 years of Python",
        "The role requires strong Python",
        "Salary: $120k",
        "Location: Remote",
        "Experience with Kubernetes is a plus",
    ],
)
def test_a_content_line_is_never_treated_as_a_heading(line: str) -> None:
    """A line wrongly read as a heading loses its content and re-sections everything after it."""
    assert _job_section_for_heading(line) is None


def test_a_sentence_mentioning_requirements_is_not_treated_as_a_heading() -> None:
    parsed = parse_job_description(
        "Engineer\nRequirements include Python and Docker\n"
        "Preferred qualifications include Kubernetes"
    )
    by_text = {item["text"]: item for item in parsed["requirements"]}
    assert by_text["Python"]["priority"] == "required"
    assert by_text["Kubernetes"]["priority"] == "preferred"


def test_a_repeated_heading_does_not_demote_the_lines_after_it() -> None:
    parsed = parse_job_description(
        "Engineer\nRequirements:\n• Python\nBenefits\n• Health cover\nRequirements:\n• Kubernetes\n"
    )
    kubernetes = next(item for item in parsed["requirements"] if item["text"] == "Kubernetes")
    assert kubernetes["priority"] == "required"


def test_skill_evidence_excerpts_are_exact_substrings_of_the_resume() -> None:
    """The UI presents excerpts as verbatim quotations; collapsing spaces broke that."""
    evidence = extract_skill_evidence(RESUME)
    for item in evidence.values():
        assert item.excerpt in RESUME, item.excerpt


def test_analysis_evidence_excerpts_are_exact_substrings_of_the_resume() -> None:
    result = _run("Engineer\nRequirements:\n• Python\n• Docker\n• Kubernetes\n")
    for finding in result.evidence:  # type: ignore[attr-defined]
        if finding.resume_excerpt:
            assert finding.resume_excerpt in RESUME, finding.resume_excerpt


@pytest.mark.parametrize("marker", ["Present", "present", "Current", "Now"])
def test_open_ended_date_markers_do_not_look_like_month_names(marker: str) -> None:
    assert date_formats_consistent(f"Engineer | 2019 - {marker}\nAnalyst | 2018 - 2019") is True


def test_a_not_applicable_category_says_so_in_its_reason() -> None:
    """Silent full credit for an undetected requirement reads as demonstrated alignment."""
    result = _run("Engineer\nAbout us\nWe build things.\n")
    required = next(
        item
        for item in result.scores  # type: ignore[attr-defined]
        if item.category == "Required skill alignment"
    )
    assert required.maximum == 0.0
    assert "Not scored" in required.reason
    assert "excluded from the total" in required.reason


def test_sentence_initial_capitals_are_not_treated_as_fabricated_entities() -> None:
    """This discarded every model recommendation whose title began with a verb."""
    source = "Built python services with docker."
    assert _unsupported_capitalized_terms("Add detail to the Docker work.", source) == set()
    assert _unsupported_capitalized_terms("Strengthen the python bullet.", source) == set()
    # A genuine unsupported proper noun is still caught.
    assert _unsupported_capitalized_terms("Add the Kubernetes rollout.", source) == {"Kubernetes"}
    # An all-caps acronym is still checked even in first position.
    assert _unsupported_capitalized_terms("AWS was used here.", source) == {"AWS"}


def test_scores_stay_bounded_for_degenerate_input() -> None:
    for job_text in ("", "   ", "Engineer\nRequirements:\n" + "• Python\n" * 200):
        job = parse_job_description(job_text)
        result = run_deterministic_analysis(
            RESUME, parse_resume(RESUME), job_text, job["requirements"]
        )
        assert 0.0 <= result.overall_score <= 100.0
        for score in result.scores:
            assert 0.0 <= score.score <= score.maximum

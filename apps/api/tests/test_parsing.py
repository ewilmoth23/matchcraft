from app.analysis.text import date_formats_consistent, measurable_result, repeated_phrases
from app.services.parsing import parse_job_description, parse_resume


def test_resume_sections_skills_and_bullets(sample_resume_text: str) -> None:
    parsed = parse_resume(sample_resume_text)
    kinds = {section["kind"] for section in parsed["sections"]}
    assert {"summary", "skills", "experience", "education"}.issubset(kinds)
    assert {"Python", "FastAPI", "React", "Docker"}.issubset(parsed["skills"])
    assert any("2 million records" in bullet for bullet in parsed["bullets"])
    assert parsed["contact"]["email"] == "jordan.rivera@example.test"


def test_job_required_preferred_and_duplicates(sample_job_text: str) -> None:
    parsed = parse_job_description(sample_job_text + "\n• AWS experience preferred.\n")
    python = next(item for item in parsed["requirements"] if item["text"] == "Python")
    kubernetes = next(item for item in parsed["requirements"] if item["text"] == "Kubernetes")
    assert python["priority"] == "required"
    assert kubernetes["priority"] == "preferred"
    assert parsed["duplicate_lines_removed"] == 1


def test_measurable_result_requires_metric_and_impact() -> None:
    assert measurable_result("Reduced validation failures by 32% through typed contracts.")
    assert not measurable_result("Worked with 12 engineers on the platform.")
    assert not measurable_result("Improved the validation process.")


def test_formatting_and_repetition_heuristics() -> None:
    assert (
        date_formats_consistent("Engineer | January 2020 - March 2022\nAnalyst | 2018 - 2019")
        is False
    )
    assert date_formats_consistent("Engineer | 2020 - 2022\nAnalyst | 2018 - 2019") is True
    repeated = repeated_phrases(
        "• Built reliable data services.\n• Tested reliable data pipelines.\n• Shipped reliable data tools."
    )
    assert "reliable data" in repeated


def test_vague_job_description_reports_low_signal() -> None:
    parsed = parse_job_description("Join our growing team and help us do meaningful work.")
    assert parsed["title"] is None
    assert parsed["requirements"] == []
    assert "No explicit qualifications" in parsed["warnings"][0]


def test_inline_requirement_sentences_are_not_discarded_as_headings() -> None:
    parsed = parse_job_description(
        "Senior Engineer\nRequirements include Python and Docker\n"
        "Preferred qualifications include Kubernetes"
    )
    by_text = {item["text"]: item for item in parsed["requirements"]}
    assert by_text["Python"]["priority"] == "required"
    assert by_text["Docker"]["priority"] == "required"
    assert by_text["Kubernetes"]["priority"] == "preferred"


def test_generic_explicit_qualifications_are_preserved() -> None:
    parsed = parse_job_description(
        "Program Manager\nRequired Qualifications\n"
        "• Strong written communication and stakeholder facilitation\n"
        "Preferred Qualifications\n• Public-sector procurement experience"
    )
    qualifications = [
        item for item in parsed["requirements"] if item["category"] == "qualification"
    ]
    assert [item["priority"] for item in qualifications] == ["required", "preferred"]
    assert all(item["explicitness"] == "explicit" for item in qualifications)


def test_non_requirement_sections_reset_classification() -> None:
    parsed = parse_job_description(
        "Engineer\nRequired Qualifications\n• Python\nBenefits\n• Health insurance"
    )
    assert not any("Health insurance" in item["text"] for item in parsed["requirements"])

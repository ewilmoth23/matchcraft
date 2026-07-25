import re
from dataclasses import asdict
from typing import Any

from app.analysis.text import (
    bullet_lines,
    extract_skill_evidence,
    looks_like_heading,
    normalize_space,
    section_kind,
    significant_terms,
)

EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE_RE = re.compile(r"(?:\+?\d[\d ().-]{7,}\d)")
LINK_RE = re.compile(r"https?://\S+|(?:linkedin\.com|github\.com)/\S+", re.IGNORECASE)
DATE_RE = re.compile(
    r"\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|"
    r"Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?|\d{1,2}/\d{4}|\d{4})"
    r"\s*(?:-|–|—|to)\s*(?:Present|Current|Now|"
    r"Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|"
    r"Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?|\d{1,2}/\d{4}|\d{4})\b",
    re.IGNORECASE,
)


def parse_resume(text: str) -> dict[str, Any]:
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    nonempty = [normalize_space(line) for line in lines if line.strip()]
    sections: list[dict[str, Any]] = []
    current_kind = "header"
    current_heading: str | None = None
    current_lines: list[str] = []

    def flush() -> None:
        if current_lines:
            sections.append(
                {
                    "kind": current_kind,
                    "heading": current_heading,
                    "content": "\n".join(current_lines).strip(),
                    "position": len(sections),
                }
            )

    for line in lines:
        stripped = normalize_space(line)
        if stripped and looks_like_heading(stripped.rstrip(":")):
            kind = section_kind(stripped.rstrip(":"))
            if kind:
                flush()
                current_kind = kind
                current_heading = stripped.rstrip(":")
                current_lines = []
                continue
        current_lines.append(line)
    flush()

    evidence = extract_skill_evidence(text)
    contact_zone = "\n".join(nonempty[:8])
    email_match = EMAIL_RE.search(contact_zone)
    phone_match = PHONE_RE.search(contact_zone)
    education = [section["content"] for section in sections if section["kind"] == "education"]
    certifications = [
        section["content"] for section in sections if section["kind"] == "certifications"
    ]
    projects = [section["content"] for section in sections if section["kind"] == "projects"]
    name = (
        nonempty[0]
        if nonempty and len(nonempty[0]) <= 80 and not EMAIL_RE.search(nonempty[0])
        else None
    )

    experiences = _parse_experiences(sections)
    return {
        "name": name,
        "contact": {
            "email": email_match.group(0) if email_match else None,
            "phone": phone_match.group(0) if phone_match else None,
            "links": LINK_RE.findall(text),
        },
        "sections": sections,
        "experiences": experiences,
        "bullets": bullet_lines(text),
        "skills": sorted(evidence),
        "skill_evidence": {key: asdict(value) for key, value in evidence.items()},
        "education": education,
        "certifications": certifications,
        "projects": projects,
    }


def _parse_experiences(sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    experience_text = "\n".join(
        section["content"] for section in sections if section["kind"] == "experience"
    )
    if not experience_text:
        return []
    lines = [line.strip() for line in experience_text.splitlines() if line.strip()]
    experiences: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line in lines:
        cleaned = re.sub(r"^[•●▪◦*\-–—]\s+", "", line)
        if DATE_RE.search(cleaned) and not line.startswith(("•", "-", "*")):
            if current:
                experiences.append(current)
            parts = [part.strip() for part in re.split(r"\s*[|,]\s*", cleaned) if part.strip()]
            date_match = DATE_RE.search(cleaned)
            current = {
                "title": parts[0] if parts else None,
                "employer": parts[1] if len(parts) > 1 else None,
                "date_text": date_match.group(0) if date_match else None,
                "location": parts[2] if len(parts) > 2 else None,
                "bullets": [],
                "position": len(experiences),
            }
        elif re.match(r"^[•●▪◦*\-–—]\s+", line) and current is not None:
            current["bullets"].append(cleaned)
    if current:
        experiences.append(current)
    if not experiences and bullet_lines(experience_text):
        experiences.append(
            {
                "title": None,
                "employer": None,
                "date_text": None,
                "location": None,
                "bullets": bullet_lines(experience_text),
                "position": 0,
            }
        )
    return experiences


def parse_job_description(text: str) -> dict[str, Any]:
    raw_lines = [normalize_space(line) for line in text.splitlines() if line.strip()]
    lines: list[str] = []
    seen: set[str] = set()
    duplicates = 0
    for line in raw_lines:
        key = line.casefold()
        # Section headings legitimately repeat in a posting. Removing a repeated heading
        # silently demoted every requirement after it to unclassified context.
        if _job_section_for_heading(line) is not None:
            lines.append(line)
            continue
        if key in seen:
            duplicates += 1
            continue
        seen.add(key)
        lines.append(line)

    title = _first_labeled_value(lines, ("job title", "title", "position"))
    employer = _first_labeled_value(lines, ("company", "employer", "organization"))
    location = _first_labeled_value(lines, ("location",))
    if title is None and lines and _looks_like_job_title(lines[0]):
        title = lines[0].rstrip(":")

    current_section = "context"
    requirement_rows: list[dict[str, str | None]] = []
    for line in lines:
        detected_section = _job_section_for_heading(line)
        if detected_section is not None:
            current_section = detected_section
            continue
        if len(line.split()) > 60:
            continue
        # An unrecognized label line ("Technical skills:", "Areas of focus:")
        # introduces content; storing it as a requirement produced an unmatchable
        # row that permanently zeroed responsibility alignment.
        if _looks_like_section_heading(line, current_section):
            continue

        priority = _priority(line, current_section)
        category = _requirement_category(line, current_section)
        skill_evidence = extract_skill_evidence(line)
        if skill_evidence:
            for skill in skill_evidence:
                requirement_rows.append(
                    {
                        "category": "skill"
                        if current_section != "responsibility"
                        else "tool_context",
                        "text": skill,
                        "normalized_key": skill.casefold(),
                        "priority": priority,
                        "explicitness": "explicit"
                        if priority in {"required", "preferred"}
                        else "inferred",
                        "source_excerpt": line,
                    }
                )
        if category and (not skill_evidence or category != "skill"):
            requirement_rows.append(
                {
                    "category": category,
                    "text": line.lstrip("•-*–— "),
                    "normalized_key": None,
                    "priority": priority,
                    "explicitness": "explicit"
                    if priority in {"required", "preferred"}
                    else "ambiguous",
                    "source_excerpt": line,
                }
            )
        elif (
            not category
            and priority in {"required", "preferred"}
            and (
                not skill_evidence or _has_unmodeled_qualification_terms(line, set(skill_evidence))
            )
        ):
            requirement_rows.append(
                {
                    "category": "qualification",
                    "text": line.lstrip("•-*–— "),
                    "normalized_key": None,
                    "priority": priority,
                    "explicitness": "explicit",
                    "source_excerpt": line,
                }
            )

    requirement_rows = _deduplicate_requirements(requirement_rows)
    compensation = next(
        (line for line in lines if re.search(r"\$\s?\d|compensation|salary range", line, re.I)),
        None,
    )
    work_mode = next(
        (
            mode
            for mode in ("remote", "hybrid", "on-site", "onsite")
            if re.search(rf"\b{mode}\b", text, re.I)
        ),
        None,
    )
    warnings = ["Repeated job-description lines were ignored."] if duplicates else []
    if not requirement_rows:
        warnings.append(
            "No explicit qualifications or responsibilities were detected; review the complete text."
        )
    return {
        "title": title,
        "employer": employer,
        "location": location,
        "requirements": requirement_rows,
        "compensation": compensation,
        "work_mode": work_mode,
        "duplicate_lines_removed": duplicates,
        "warnings": warnings,
    }


def _first_labeled_value(lines: list[str], labels: tuple[str, ...]) -> str | None:
    for line in lines[:12]:
        for label in labels:
            match = re.match(rf"{re.escape(label)}\s*:\s*(.+)", line, re.I)
            if match:
                return match.group(1).strip()
    return None


def _looks_like_job_title(line: str) -> bool:
    words = re.findall(r"[A-Za-z][A-Za-z&/+-]*", line.rstrip(":"))
    role_nouns = {
        "administrator",
        "analyst",
        "architect",
        "consultant",
        "coordinator",
        "developer",
        "director",
        "engineer",
        "lead",
        "manager",
        "officer",
        "president",
        "scientist",
        "specialist",
    }
    return (
        1 <= len(words) <= 8
        and any(word.casefold() in role_nouns for word in words)
        and all(word[0].isupper() or word.isupper() for word in words)
    )


# Ordered because a heading such as "Preferred qualifications" also contains
# "qualifications"; the more specific pattern must win.
_HEADING_MODIFIER = r"(?:additional |basic |core |essential |general |key |minimum |required )?"
JOB_HEADING_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "preferred",
        re.compile(
            rf"\b(?:(?:preferred|desirable|nice[- ]to[- ]have|good[- ]to[- ]have|bonus)"
            rf"(?: {_HEADING_MODIFIER}(?:qualifications?|requirements?|skills?|experience))?"
            rf"|nice to haves?|a plus)\b"
        ),
    ),
    (
        "context",
        re.compile(
            r"\b(?:about (?:us|the (?:company|team|role))|benefits|perks|compensation|salary|"
            r"equal opportunity|what we offer|why join|our (?:mission|values)|location)\b"
        ),
    ),
    (
        "required",
        re.compile(
            rf"\b(?:{_HEADING_MODIFIER}(?:requirements?|qualifications?)|must[- ]haves?"
            rf"|what you.?ll need|what you.?ll bring|what we.?re looking for|who you are"
            rf"|experience required|skills?|experience)\b"
        ),
    ),
    (
        "responsibility",
        re.compile(
            rf"\b(?:{_HEADING_MODIFIER}(?:responsibilities|duties)|what you.?ll do"
            rf"|what you will do|the role|role overview|day[- ]to[- ]day|in this role)\b"
        ),
    ),
)

# A heading labels the section that follows. A sentence that merely mentions the word
# ("Requirements include Python and Docker") states a requirement and must be kept.
_HEADING_COVERAGE_THRESHOLD = 0.6


def _job_section_for_heading(line: str) -> str | None:
    """Return the section a line introduces, or None when it is not a heading."""
    if re.match(r"^[•●▪◦*\-–—]", line):
        return None
    if len(line.split()) > 8:
        return None
    # A section label never carries a figure. "Salary: $120k" and "5+ years of
    # experience in the following:" contain heading vocabulary but state content.
    if re.search(r"[\d$€£]", line):
        return None
    label = normalize_space(re.sub(r"[^a-z' ]", " ", line.rstrip(":").casefold()))
    if not label:
        return None
    ends_with_colon = line.rstrip().endswith(":")
    best_section: str | None = None
    best_coverage = 0.0
    for section, pattern in JOB_HEADING_PATTERNS:
        # finditer, not search: search returns the leftmost match only, so
        # "Duties and Responsibilities" scored on "duties" alone and fell below
        # the threshold. Every pattern is scored and the strongest one wins.
        matched = sum(len(match.group(0)) for match in pattern.finditer(label))
        coverage = matched / len(label)
        if coverage > best_coverage:
            best_section, best_coverage = section, coverage
    if best_section is None:
        return None
    if ends_with_colon or best_coverage >= _HEADING_COVERAGE_THRESHOLD:
        return best_section
    return None


def _looks_like_section_heading(line: str, section: str) -> bool:
    """A short label line that introduces content rather than stating a requirement.

    A colon-terminated line can still carry a requirement ("5+ years in the
    following:"), so anything with a requirement signal is kept.
    """
    stripped = line.strip()
    if not stripped.endswith(":") or len(stripped.split()) > 8:
        return False
    if re.match(r"^[•●▪◦*\-–—]", stripped):
        return False
    if _requirement_category(stripped, section) is not None:
        return False
    return not extract_skill_evidence(stripped)


def _has_unmodeled_qualification_terms(line: str, skills: set[str]) -> bool:
    terms = set(significant_terms(line, 50))
    for skill in skills:
        terms.difference_update(significant_terms(skill, 10))
    terms.difference_update(
        {
            "building",
            "experience",
            "framework",
            "must",
            "nice",
            "similar",
            "strong",
        }
    )
    return len(terms) >= 3


def _priority(line: str, section: str) -> str:
    lower = line.casefold()
    if section == "preferred" or re.search(r"\b(preferred|nice to have|bonus|a plus)\b", lower):
        return "preferred"
    if section == "required" or re.search(
        r"\b(required|must|minimum|need to|at least|requirements?\s+(?:include|are))\b",
        lower,
    ):
        return "required"
    return "context"


def _requirement_category(line: str, section: str) -> str | None:
    lower = line.casefold()
    if re.search(r"\b\d+\+?\s+years?\b", lower):
        return "experience"
    if re.search(r"\b(bachelor|master|phd|degree|diploma)\b", lower):
        return "education"
    if re.search(r"\b(certification|certified|license)\b", lower):
        return "certification"
    if section == "responsibility":
        return "responsibility"
    return None


def _deduplicate_requirements(rows: list[dict[str, str | None]]) -> list[dict[str, str | None]]:
    result: list[dict[str, str | None]] = []
    seen: set[tuple[str | None, str | None, str | None]] = set()
    for row in rows:
        key = (row["category"], row["text"].casefold() if row["text"] else None, row["priority"])
        if key not in seen:
            seen.add(key)
            result.append(row)
    return result

"""Metamorphic properties: relations that must hold between two analyses.

A résumé-to-role score has no ground truth, so it cannot be validated by comparing it to
a "correct" number. It *can* be validated by asserting how it must respond to a change.
This is metamorphic testing, and it is the strongest tool available here.

Two families:

**Fairness (invariance).** Changing only a signal the system must never use — a name, a
university, pronouns, a graduation year, an employment gap, non-native phrasing — must
leave the score and every evidence classification untouched. These are the only automated
defense against a scoring system quietly rewarding identity signals. A failure here is a
defect regardless of how small the delta is: `docs/responsible-ai.md` promises the score
reflects evidence coverage, and any movement falsifies that promise.

**Soundness (directional).** Adding genuine evidence must not lower the score; removing
it must not raise it; reordering sections must not matter; padding with irrelevant text
must not meaningfully help. These catch scoring bugs that labeled cases miss because they
are about *response to change*, not about any single output.

Every mutation below is applied to synthetic text only.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

Relation = Literal["invariant", "non_decreasing", "non_increasing", "bounded_change"]


@dataclass(frozen=True)
class Property:
    """One mutation plus the relation its result must satisfy."""

    name: str
    family: Literal["fairness", "soundness"]
    relation: Relation
    mutate: Callable[[str], str]
    rationale: str
    # Only meaningful for bounded_change: the largest defensible movement in points.
    tolerance: float = 0.0
    # Fairness properties additionally require identical evidence classifications.
    require_identical_evidence: bool = False


def _replace_name(resume: str) -> str:
    """Swap an Anglo-coded name for a non-Anglo-coded one, changing nothing else."""
    return resume.replace("Jordan Rivera", "Oluwaseun Adeyemi").replace(
        "jordan.rivera", "oluwaseun.adeyemi"
    )


def _replace_name_gendered(resume: str) -> str:
    return resume.replace("Jordan Rivera", "Mary O'Sullivan").replace(
        "jordan.rivera", "mary.osullivan"
    )


def _replace_university(resume: str) -> str:
    """An institution's prestige must not move an evidence-coverage score."""
    return resume.replace("State College", "Howard University")


def _add_pronouns(resume: str) -> str:
    lines = resume.split("\n")
    for index, line in enumerate(lines):
        if "@" in line:
            lines.insert(index + 1, "Pronouns: she/her")
            break
    return "\n".join(lines)


def _shift_graduation_year(resume: str) -> str:
    """A 1998 graduate and a 2019 graduate with identical evidence must score alike."""
    return re.sub(r"\b(2019|2018)\b(?=[^\n]*(?:Bachelor|College|University))", "1998", resume)


def _add_employment_gap(resume: str) -> str:
    """A career break is not evidence about skills.

    The wording is deliberately neutral. An earlier version said "family caregiving",
    which is topically relevant to healthcare roles and legitimately added a keyword
    match on one case — the probe was measuring its own vocabulary rather than the gap.
    """
    return resume.replace(
        "PROFESSIONAL EXPERIENCE",
        "PROFESSIONAL EXPERIENCE\nCareer break | 2021 - 2022",
    )


def _add_disability_disclosure(resume: str) -> str:
    lines = resume.split("\n")
    for index, line in enumerate(lines):
        if "@" in line:
            lines.insert(index + 1, "Member, National Association of the Deaf")
            break
    return "\n".join(lines)


def _add_veteran_status(resume: str) -> str:
    lines = resume.split("\n")
    for index, line in enumerate(lines):
        if "@" in line:
            lines.insert(index + 1, "U.S. Army veteran")
            break
    return "\n".join(lines)


def _add_international_address(resume: str) -> str:
    """Add a non-US location without removing anything.

    An earlier version replaced "| Remote" with a city, which conflated two changes: it
    removed a term the job description also used. The score moved for a defensible
    reason (lost keyword overlap) and the probe reported a fairness violation that was
    not one. A probe that cannot distinguish its own signal is worse than no probe.
    """
    lines = resume.split("\n")
    for index, line in enumerate(lines):
        if "@" in line:
            lines.insert(index + 1, "Lagos, Nigeria")
            break
    return "\n".join(lines)


def _reorder_sections(resume: str) -> str:
    """Section order is presentation, not evidence."""
    blocks = resume.split("\n\n")
    if len(blocks) < 4:
        return resume
    header, *rest = blocks
    return "\n\n".join([header, *reversed(rest)])


def _pad_with_irrelevant_text(resume: str) -> str:
    """Volume is not evidence. Padding must not meaningfully raise the score."""
    filler = "\n".join(
        f"• Attended the {name} community meetup and took notes."
        for name in ("spring", "summer", "autumn", "winter", "annual")
    )
    return f"{resume}\n\nCOMMUNITY\n{filler}\n"


def _repeat_a_skill(resume: str) -> str:
    """Keyword stuffing must not multiply credit — the docs promise this explicitly."""
    return f"{resume}\n\nADDITIONAL\n" + "\n".join("• Python. Python. Python." for _ in range(12))


def _remove_a_supported_skill(resume: str) -> str:
    """Deleting real evidence must not raise the score."""
    without_skill = re.sub(r"(?i)\bdocker\b", "an internal tool", resume)
    return without_skill


def _add_genuine_evidence(resume: str) -> str:
    """Adding contextual evidence for an unmet requirement must not lower the score."""
    return resume.replace(
        "PROFESSIONAL EXPERIENCE",
        "PROFESSIONAL EXPERIENCE\n"
        "Platform Engineer | Rivermark Systems | 2018 - 2019 | Remote\n"
        "• Operated Kubernetes clusters running production data services.",
        1,
    )


PROPERTIES: tuple[Property, ...] = (
    Property(
        "candidate_name_is_ignored",
        "fairness",
        "invariant",
        _replace_name,
        "An evidence-coverage score that moves when a name changes is measuring the name.",
        require_identical_evidence=True,
    ),
    Property(
        "gendered_name_is_ignored",
        "fairness",
        "invariant",
        _replace_name_gendered,
        "Perceived gender is never evidence of a qualification.",
        require_identical_evidence=True,
    ),
    Property(
        "institution_is_ignored",
        "fairness",
        "invariant",
        _replace_university,
        "Institutional prestige is a proxy for background, not for demonstrated skill.",
        require_identical_evidence=True,
    ),
    Property(
        "pronoun_disclosure_is_ignored",
        "fairness",
        "invariant",
        _add_pronouns,
        "Voluntary disclosure must never carry a scoring cost.",
        require_identical_evidence=True,
    ),
    Property(
        "graduation_year_is_ignored",
        "fairness",
        "invariant",
        _shift_graduation_year,
        "Graduation year is the most common age proxy on a résumé.",
        require_identical_evidence=True,
    ),
    Property(
        "employment_gap_is_ignored",
        "fairness",
        "invariant",
        _add_employment_gap,
        "Caregiving breaks disproportionately affect women; a gap is not skill evidence.",
        require_identical_evidence=True,
    ),
    Property(
        "disability_affiliation_is_ignored",
        "fairness",
        "invariant",
        _add_disability_disclosure,
        "Membership of a disability organization must not alter an evidence score.",
        require_identical_evidence=True,
    ),
    Property(
        "veteran_status_is_ignored",
        "fairness",
        "invariant",
        _add_veteran_status,
        "Protected status must not alter an evidence score in either direction.",
        require_identical_evidence=True,
    ),
    Property(
        "location_is_ignored",
        "fairness",
        "invariant",
        _add_international_address,
        "National origin proxies must not alter an evidence score.",
        require_identical_evidence=True,
    ),
    Property(
        "section_order_is_ignored",
        "soundness",
        "bounded_change",
        _reorder_sections,
        "Section order is presentation. Some movement is defensible if section detection "
        "legitimately changes, but a large swing means the score tracks layout.",
        tolerance=5.0,
    ),
    Property(
        "irrelevant_padding_does_not_help",
        "soundness",
        "bounded_change",
        _pad_with_irrelevant_text,
        "Volume is not evidence; padding must not buy a materially better score.",
        tolerance=3.0,
    ),
    Property(
        "keyword_stuffing_does_not_help",
        "soundness",
        "bounded_change",
        _repeat_a_skill,
        "docs/scoring-model.md states repetition does not multiply credit.",
        tolerance=1.0,
    ),
    Property(
        "removing_evidence_does_not_help",
        "soundness",
        "non_increasing",
        _remove_a_supported_skill,
        "Deleting a demonstrated skill cannot make a candidate look better aligned.",
    ),
    Property(
        "adding_evidence_does_not_hurt",
        "soundness",
        "non_decreasing",
        _add_genuine_evidence,
        "Adding real, relevant experience cannot lower an evidence-coverage score.",
    ),
)

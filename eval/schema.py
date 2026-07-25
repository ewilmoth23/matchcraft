"""Schema for labeled evaluation cases and metamorphic properties.

Why this exists: before this harness, the only empirical check on MatchCraft's analysis
was a single expected-output fixture. That proves the pipeline is *consistent*, not that
it is *correct* — every scoring change was unfalsifiable, and a regression that made the
analysis worse in a realistic way would still show green.

Two complementary techniques, because a résumé-to-role judgment has no single truth:

1. **Labeled cases** — a human states what a job description requires and what a résumé
   genuinely evidences. Requirement extraction and evidence classification *do* have a
   defensible ground truth, and they are measured with precision/recall/F1.
2. **Metamorphic properties** — relations that must hold between two runs, regardless of
   what the "right" score is. Adding real evidence must not lower the score; swapping a
   candidate's name must not change it at all. These catch what labels cannot, and the
   fairness properties are the only automated defense against a scoring system that
   quietly rewards signals it must never use.

The overall score is deliberately labeled as a *band*, not a number. Asserting an exact
score encodes today's arithmetic as truth and blocks every future improvement.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

Priority = Literal["required", "preferred", "context"]
EvidenceStatus = Literal["supported", "transferable", "not_found"]
ScoreBand = Literal["weak", "partial", "strong"]

# Bands rather than points. A band is a claim a reviewer can defend ("this résumé only
# partially covers this role"); a point value is an artifact of the current weights.
SCORE_BANDS: dict[ScoreBand, tuple[float, float]] = {
    "weak": (0.0, 45.0),
    "partial": (45.0, 75.0),
    "strong": (75.0, 100.0),
}


@dataclass(frozen=True)
class ExpectedRequirement:
    """A requirement a competent reviewer would say the job description states."""

    text: str
    priority: Priority
    # How the résumé actually evidences it. None means "not labeled" — used when a case
    # is only exercising extraction.
    evidence: EvidenceStatus | None = None
    # Set when the parser is known to legitimately express this differently, e.g. a
    # catalog skill surfaced as "Python" rather than the full sentence.
    matches_any_of: tuple[str, ...] = ()

    def surfaces(self) -> tuple[str, ...]:
        return (self.text, *self.matches_any_of)


@dataclass(frozen=True)
class EvaluationCase:
    """One labeled résumé/job-description pair."""

    case_id: str
    role_family: str
    resume: str
    job: str
    expected_requirements: tuple[ExpectedRequirement, ...]
    expected_band: ScoreBand
    # Requirements the parser must NOT invent — headings, boilerplate, benefits copy.
    forbidden_requirements: tuple[str, ...] = ()
    notes: str = ""

    @classmethod
    def from_dict(cls, payload: dict[str, Any], root: Path) -> EvaluationCase:
        return cls(
            case_id=str(payload["case_id"]),
            role_family=str(payload["role_family"]),
            resume=(root / payload["resume"]).read_text(encoding="utf-8"),
            job=(root / payload["job"]).read_text(encoding="utf-8"),
            expected_requirements=tuple(
                ExpectedRequirement(
                    text=str(item["text"]),
                    priority=item["priority"],
                    evidence=item.get("evidence"),
                    matches_any_of=tuple(item.get("matches_any_of", ())),
                )
                for item in payload["expected_requirements"]
            ),
            expected_band=payload["expected_band"],
            forbidden_requirements=tuple(payload.get("forbidden_requirements", ())),
            notes=str(payload.get("notes", "")),
        )


def load_cases(corpus_dir: Path) -> list[EvaluationCase]:
    """Load every labeled case, sorted by id so reports are stable."""
    manifest = json.loads((corpus_dir / "cases.json").read_text(encoding="utf-8"))
    cases = [EvaluationCase.from_dict(item, corpus_dir) for item in manifest["cases"]]
    return sorted(cases, key=lambda case: case.case_id)


@dataclass
class MetricResult:
    """Precision/recall/F1 with the raw counts kept, so a report can show its working."""

    true_positive: int = 0
    false_positive: int = 0
    false_negative: int = 0
    examples: list[str] = field(default_factory=list)

    @property
    def precision(self) -> float:
        predicted = self.true_positive + self.false_positive
        return self.true_positive / predicted if predicted else 1.0

    @property
    def recall(self) -> float:
        actual = self.true_positive + self.false_negative
        return self.true_positive / actual if actual else 1.0

    @property
    def f1(self) -> float:
        total = self.precision + self.recall
        return 2 * self.precision * self.recall / total if total else 0.0

    def merge(self, other: MetricResult) -> None:
        self.true_positive += other.true_positive
        self.false_positive += other.false_positive
        self.false_negative += other.false_negative
        self.examples.extend(other.examples)


def band_for(score: float) -> ScoreBand:
    for band, (low, high) in SCORE_BANDS.items():
        if low <= score < high:
            return band
    return "strong"

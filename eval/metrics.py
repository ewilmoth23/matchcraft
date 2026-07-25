"""Scoring the analysis against labeled cases.

Matching a predicted requirement to a labeled one is itself a judgment call. The rule
here is deliberately generous on *surface form* and strict on *semantics*: a label is
matched when the parser produced a requirement whose normalized text contains, or is
contained by, one of the label's accepted surfaces. That tolerates "Python" vs "Strong
Python and SQL skills are required" without tolerating a wrong classification.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from eval.schema import EvaluationCase, ExpectedRequirement, MetricResult, band_for


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9+#./ -]", " ", value.casefold()).strip()


def _surface_matches(predicted: str, expected: ExpectedRequirement) -> bool:
    predicted_normalized = _normalize(predicted)
    if not predicted_normalized:
        return False
    for surface in expected.surfaces():
        surface_normalized = _normalize(surface)
        if not surface_normalized:
            continue
        if surface_normalized in predicted_normalized or predicted_normalized in surface_normalized:
            return True
    return False


@dataclass
class CaseReport:
    case_id: str
    role_family: str
    extraction: MetricResult = field(default_factory=MetricResult)
    priority: MetricResult = field(default_factory=MetricResult)
    evidence: MetricResult = field(default_factory=MetricResult)
    fabricated_requirements: list[str] = field(default_factory=list)
    overall_score: float = 0.0
    expected_band: str = ""
    actual_band: str = ""

    @property
    def band_correct(self) -> bool:
        return self.expected_band == self.actual_band


def evaluate_case(
    case: EvaluationCase,
    parsed_job: dict[str, Any],
    findings: list[Any],
    overall_score: float,
) -> CaseReport:
    """Compare one analysis against its labels."""
    report = CaseReport(
        case_id=case.case_id,
        role_family=case.role_family,
        overall_score=overall_score,
        expected_band=case.expected_band,
        actual_band=band_for(overall_score),
    )
    predicted = list(parsed_job["requirements"])
    predicted_texts = [str(item["text"]) for item in predicted]
    finding_by_text = {finding.requirement: finding for finding in findings}

    matched_predictions: set[int] = set()
    for expected in case.expected_requirements:
        hits = [
            index for index, text in enumerate(predicted_texts) if _surface_matches(text, expected)
        ]
        if not hits:
            report.extraction.false_negative += 1
            report.extraction.examples.append(f"missed: {expected.text}")
            continue
        report.extraction.true_positive += 1
        matched_predictions.update(hits)

        # Priority: correct when any matching prediction carries the labeled priority.
        actual_priorities = {str(predicted[index]["priority"]) for index in hits}
        if expected.priority in actual_priorities:
            report.priority.true_positive += 1
        else:
            report.priority.false_positive += 1
            report.priority.false_negative += 1
            report.priority.examples.append(
                f"{expected.text}: expected {expected.priority}, got {sorted(actual_priorities)}"
            )

        if expected.evidence is None:
            continue
        actual_statuses = {
            finding_by_text[predicted_texts[index]].status
            for index in hits
            if predicted_texts[index] in finding_by_text
        }
        if expected.evidence in actual_statuses:
            report.evidence.true_positive += 1
        else:
            report.evidence.false_positive += 1
            report.evidence.false_negative += 1
            report.evidence.examples.append(
                f"{expected.text}: expected {expected.evidence}, got {sorted(actual_statuses)}"
            )

    # Anything predicted that no label accounts for is a false positive only when it is
    # explicitly forbidden. Job descriptions carry real detail a label set may omit, so
    # unlabeled extras are not penalized — but boilerplate never should be extracted.
    for index, text in enumerate(predicted_texts):
        if index in matched_predictions:
            continue
        if any(
            _surface_matches(text, ExpectedRequirement(f, "context"))
            for f in case.forbidden_requirements
        ):
            report.extraction.false_positive += 1
            report.fabricated_requirements.append(text)
    return report


@dataclass
class SuiteReport:
    cases: list[CaseReport] = field(default_factory=list)

    @property
    def extraction(self) -> MetricResult:
        return self._aggregate("extraction")

    @property
    def priority(self) -> MetricResult:
        return self._aggregate("priority")

    @property
    def evidence(self) -> MetricResult:
        return self._aggregate("evidence")

    @property
    def band_accuracy(self) -> float:
        if not self.cases:
            return 1.0
        return sum(case.band_correct for case in self.cases) / len(self.cases)

    def _aggregate(self, attribute: str) -> MetricResult:
        total = MetricResult()
        for case in self.cases:
            total.merge(getattr(case, attribute))
        return total

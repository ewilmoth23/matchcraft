#!/usr/bin/env python3
"""Run the MatchCraft evaluation suite.

    python eval/run.py                 # human-readable report
    python eval/run.py --json          # machine-readable, for CI
    python eval/run.py --gate          # exit non-zero when a threshold regresses

Thresholds live in eval/thresholds.json so a deliberate change is a reviewable diff
rather than an edit buried in code.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))
sys.path.insert(0, str(ROOT))

from app.analysis.scoring import run_deterministic_analysis  # noqa: E402
from app.services.parsing import parse_job_description, parse_resume  # noqa: E402
from eval.metrics import SuiteReport, evaluate_case  # noqa: E402
from eval.properties import PROPERTIES, Property  # noqa: E402
from eval.schema import EvaluationCase, load_cases  # noqa: E402

CORPUS = Path(__file__).resolve().parent / "corpus"
THRESHOLDS = Path(__file__).resolve().parent / "thresholds.json"


def analyze(resume_text: str, job_text: str) -> tuple[dict[str, Any], Any]:
    parsed_job = parse_job_description(job_text)
    result = run_deterministic_analysis(
        resume_text, parse_resume(resume_text), job_text, parsed_job["requirements"]
    )
    return parsed_job, result


@dataclass
class PropertyOutcome:
    case_id: str
    property_name: str
    family: str
    relation: str
    baseline: float
    mutated: float
    evidence_changed: int
    passed: bool
    rationale: str

    @property
    def delta(self) -> float:
        return round(self.mutated - self.baseline, 2)


def _evidence_signature(findings: list[Any]) -> dict[str, str]:
    return {finding.requirement: finding.status for finding in findings}


def check_property(case: EvaluationCase, prop: Property) -> PropertyOutcome | None:
    mutated_resume = prop.mutate(case.resume)
    if mutated_resume == case.resume:
        # The mutation did not apply to this case's text; skip rather than claim a pass.
        return None
    _, baseline = analyze(case.resume, case.job)
    _, mutated = analyze(mutated_resume, case.job)

    before = _evidence_signature(baseline.evidence)
    after = _evidence_signature(mutated.evidence)
    changed = sum(1 for key, value in before.items() if after.get(key, value) != value)

    # The overall score is a percentage of the categories that could actually be
    # assessed. When a mutation makes a previously unassessable category assessable —
    # adding a Kubernetes role where the job listed no other detectable preferred skill
    # — the denominator changes and a directional comparison is meaningless. That is
    # correct behaviour for a renormalized score, not a violation, so the comparison is
    # skipped rather than silently passed or wrongly failed.
    scored_before = {item.category for item in baseline.scores if item.maximum > 0}
    scored_after = {item.category for item in mutated.scores if item.maximum > 0}
    if prop.relation in {"non_decreasing", "non_increasing"} and scored_before != scored_after:
        return None

    delta = mutated.overall_score - baseline.overall_score
    if prop.relation == "invariant":
        passed = abs(delta) < 0.05
    elif prop.relation == "non_decreasing":
        passed = delta >= -0.05
    elif prop.relation == "non_increasing":
        passed = delta <= 0.05
    else:
        passed = abs(delta) <= prop.tolerance
    if prop.require_identical_evidence and changed:
        passed = False

    return PropertyOutcome(
        case_id=case.case_id,
        property_name=prop.name,
        family=prop.family,
        relation=prop.relation,
        baseline=baseline.overall_score,
        mutated=mutated.overall_score,
        evidence_changed=changed,
        passed=passed,
        rationale=prop.rationale,
    )


def run() -> tuple[SuiteReport, list[PropertyOutcome]]:
    cases = load_cases(CORPUS)
    suite = SuiteReport()
    outcomes: list[PropertyOutcome] = []
    for case in cases:
        parsed_job, result = analyze(case.resume, case.job)
        suite.cases.append(
            evaluate_case(case, parsed_job, list(result.evidence), result.overall_score)
        )
        for prop in PROPERTIES:
            outcome = check_property(case, prop)
            if outcome is not None:
                outcomes.append(outcome)
    return suite, outcomes


def summarize(suite: SuiteReport, outcomes: list[PropertyOutcome]) -> dict[str, Any]:
    fairness = [item for item in outcomes if item.family == "fairness"]
    soundness = [item for item in outcomes if item.family == "soundness"]
    return {
        "cases": len(suite.cases),
        "requirement_extraction_f1": round(suite.extraction.f1, 4),
        "requirement_extraction_recall": round(suite.extraction.recall, 4),
        "requirement_extraction_precision": round(suite.extraction.precision, 4),
        "priority_accuracy": round(suite.priority.recall, 4),
        "evidence_accuracy": round(suite.evidence.recall, 4),
        "score_band_accuracy": round(suite.band_accuracy, 4),
        "fairness_checks": len(fairness),
        "fairness_violations": sum(not item.passed for item in fairness),
        "soundness_checks": len(soundness),
        "soundness_violations": sum(not item.passed for item in soundness),
    }


def render(suite: SuiteReport, outcomes: list[PropertyOutcome]) -> str:
    summary = summarize(suite, outcomes)
    lines = [
        "MatchCraft evaluation",
        "=" * 60,
        f"Labeled cases: {summary['cases']}",
        "",
        "Requirement extraction",
        f"  precision {summary['requirement_extraction_precision']:.3f}"
        f"  recall {summary['requirement_extraction_recall']:.3f}"
        f"  F1 {summary['requirement_extraction_f1']:.3f}",
        f"Priority classification accuracy  {summary['priority_accuracy']:.3f}",
        f"Evidence classification accuracy  {summary['evidence_accuracy']:.3f}",
        f"Score band accuracy               {summary['score_band_accuracy']:.3f}",
        "",
    ]
    misses = [
        example
        for case in suite.cases
        for example in (*case.extraction.examples, *case.priority.examples, *case.evidence.examples)
    ]
    if misses:
        lines.append(f"Labeled misses ({len(misses)}):")
        lines.extend(f"  - {item}" for item in misses[:25])
        if len(misses) > 25:
            lines.append(f"  ... and {len(misses) - 25} more")
        lines.append("")

    for family, title in (
        ("fairness", "Fairness properties"),
        ("soundness", "Soundness properties"),
    ):
        group = [item for item in outcomes if item.family == family]
        failures = [item for item in group if not item.passed]
        lines.append(f"{title}: {len(group) - len(failures)}/{len(group)} held")
        for item in failures:
            lines.append(
                f"  VIOLATION {item.property_name} [{item.case_id}] "
                f"{item.baseline} -> {item.mutated} (delta {item.delta:+}), "
                f"{item.evidence_changed} evidence change(s)"
            )
            lines.append(f"            {item.rationale}")
        lines.append("")
    return "\n".join(lines)


def gate(summary: dict[str, Any]) -> list[str]:
    thresholds = json.loads(THRESHOLDS.read_text(encoding="utf-8"))
    failures: list[str] = []
    for key, minimum in thresholds.get("minimums", {}).items():
        actual = summary.get(key)
        if actual is None:
            failures.append(f"{key}: not measured")
        elif actual < minimum:
            failures.append(f"{key}: {actual} below required {minimum}")
    for key, maximum in thresholds.get("maximums", {}).items():
        actual = summary.get(key)
        if actual is None:
            failures.append(f"{key}: not measured")
        elif actual > maximum:
            failures.append(f"{key}: {actual} above allowed {maximum}")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the MatchCraft evaluation suite.")
    parser.add_argument("--json", action="store_true", help="emit machine-readable summary")
    parser.add_argument("--gate", action="store_true", help="fail when a threshold regresses")
    args = parser.parse_args()

    suite, outcomes = run()
    summary = summarize(suite, outcomes)
    print(json.dumps(summary, indent=2) if args.json else render(suite, outcomes))

    if not args.gate:
        return 0
    failures = gate(summary)
    if failures:
        print("\nEvaluation gate failed:", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        return 1
    print("\nEvaluation gate passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

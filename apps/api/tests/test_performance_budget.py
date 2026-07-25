"""Executable latency budgets at the documented input ceilings.

Deterministic analysis was once O(requirements x résumé length) because skill evidence
was re-derived inside the per-requirement loop. A 300-requirement job against a large
résumé did not finish in 45 seconds, and `run_analysis` is `async def`, so it blocked the
event loop for the whole application. Nothing failed — the suite was green throughout.

These budgets are deliberately loose. They exist to catch a return to quadratic
behaviour, not to police small changes, so they are set well above the measured time on
modest hardware. A failure here means an algorithmic regression, not a slow machine.
"""

import time

import pytest

from app.analysis.scoring import run_deterministic_analysis
from app.services.parsing import parse_job_description, parse_resume

# The schema ceilings are 100,000 résumé characters and 150,000 job characters. These
# inputs are large but realistic; the ceilings themselves are covered by the ratio test.
LARGE_RESUME = "Dana Chen\ndana@example.test\n\nEXPERIENCE\n" + "\n".join(
    f"• Built Python services that processed {index} million records each week."
    for index in range(300)
)
LARGE_JOB = "Senior Engineer\nRequirements\n" + "\n".join(
    f"• Experience with distributed service pattern number {index}." for index in range(120)
)


def _elapsed(resume_text: str, job_text: str) -> float:
    parsed_job = parse_job_description(job_text)
    parsed_resume = parse_resume(resume_text)
    start = time.perf_counter()
    run_deterministic_analysis(resume_text, parsed_resume, job_text, parsed_job["requirements"])
    return time.perf_counter() - start


@pytest.mark.parametrize("budget_seconds", [10.0])
def test_large_analysis_completes_within_budget(budget_seconds: float) -> None:
    elapsed = _elapsed(LARGE_RESUME, LARGE_JOB)
    assert elapsed < budget_seconds, (
        f"deterministic analysis took {elapsed:.2f}s for 300 bullets x 120 requirements; "
        "this is the shape of an algorithmic regression, not a slow machine"
    )


def test_cost_grows_sub_quadratically_with_requirement_count() -> None:
    """Quadratic growth is the specific failure this guards against.

    Quadrupling the requirement count against a fixed résumé must not quadruple the
    cost beyond a linear allowance. The threshold is generous — a genuine O(n^2) return
    produced a ~7x ratio when this was written, and linear work produces roughly 4x.
    """
    small_job = "Engineer\nRequirements\n" + "\n".join(
        f"• Experience with service pattern number {index}." for index in range(20)
    )
    large_job = "Engineer\nRequirements\n" + "\n".join(
        f"• Experience with service pattern number {index}." for index in range(80)
    )
    small = max(_elapsed(LARGE_RESUME, small_job), 1e-3)
    large = _elapsed(LARGE_RESUME, large_job)
    ratio = large / small
    assert ratio < 6.0, (
        f"cost grew {ratio:.1f}x for a 4x increase in requirements; "
        "per-requirement work is being recomputed instead of hoisted"
    )

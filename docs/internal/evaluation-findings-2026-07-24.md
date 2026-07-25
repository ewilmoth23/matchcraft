# What Measuring the Analysis Revealed — 2026-07-24

MatchCraft was, by this point, well engineered: 186 tests, strict typing, a hardened
security posture, two real browser journeys, an acyclic import graph. None of that
answered the only question that matters for a system that scores people — **is the
analysis any good?**

Nothing measured it. Two résumés, two job descriptions, one expected-output fixture, and
64 hand-written skill aliases were the entire empirical basis. Every scoring change was
unfalsifiable. This pass built the measurement, then acted on what it said.

## What was built

**A labeled corpus.** 16 synthetic résumé/job pairs across eight role families —
deliberately including HVAC, medical office administration, warehouse operations, and
instructional coaching, because a technology-heavy skill catalog needed cases that could
*expose* that bias rather than flatter it. 178 labeled requirements, each with the
priority a reviewer would assign and the evidence status the résumé genuinely shows.

**Metamorphic properties.** A résumé score has no ground truth, so it cannot be checked
against a correct number — but it can be checked against how it must *respond to change*.
Nine fairness properties assert invariance when only an identity signal changes: name
(Anglo-coded, non-Anglo-coded, gendered), institution, pronouns, graduation year,
employment gap, disability affiliation, veteran status, location. Five soundness
properties assert direction: adding evidence must not lower the score, removing it must
not raise it, padding and keyword stuffing must not help.

**A gate.** `make eval-gate` runs in CI. Fairness and soundness are zero-tolerance.

## What it found, and what changed

| Measure | Before | After |
|---|---|---|
| Evidence classification accuracy | 0.576 | **0.767** |
| Fairness violations | **20 of 68** | **0 of 79** |
| Soundness violations | **28 of 64** | **0 of 64** |
| Requirement extraction F1 | 0.972 | 0.972 |
| Priority accuracy | 0.959 | 0.959 |

### Adding a caregiving career break lowered the score on 13 of 16 cases

The single most serious finding. Employment-date formatting was one of six clarity
checks; a career break introduces a differently formatted date range, so the résumé
became "inconsistent" and lost 1.7 points. A résumé tool that quietly penalizes career
gaps has a disparate impact on exactly the group most likely to have one.

Date formatting is a presentation preference, not evidence of a qualification. It was
removed from scoring and remains a recommendation.

### Free credit made an unqualified candidate look employable

An executive assistant scored **56/100** against an HVAC technician role. Thirty-five of
those points were full marks for Required and Preferred skill alignment — awarded because
no requirement of either kind was *detected*. Full credit for a requirement nobody found
is indistinguishable from a met requirement.

Not-applicable categories now carry a zero maximum and are excluded; the score is a
percentage of what was actually assessed. That candidate now scores 31.8.

This is the change I declined to make in the previous review pass, for lack of evidence.
The corpus supplied the evidence.

### The matcher was mis-calibrated by a wide margin

The confusion matrix was lopsided: **66 under-credits against 3 over-credits.** Genuinely
demonstrated qualifications were routinely reported as merely "transferable".

A sweep over the corpus measured the `SUPPORTED_OVERLAP` threshold at 0.55 → 0.599
accuracy, and 0.30 → 0.767. A further move to a single shared term reaches 0.779 and was
**deliberately not taken**: it doubles over-crediting. Telling someone a requirement is
covered when the résumé does not show it is the worse error for this product, so the
conservative asymmetry was preserved on purpose.

Supporting fixes: a light, symmetric inflection rule so `scheduling` and `scheduled` are
one term, and ten scaffolding words (`experience`, `strong`, `demonstrated`, …) added to
the stopword list, since they appeared in nearly every requirement and inflated the
denominator of every overlap ratio.

### Three soundness failures shared one root cause

A hard 200–1,400 word clarity band is a step function, so any text addition could cross
it. It made irrelevant padding *raise* the score by up to 3.6 points and adding a genuine
role *lower* it — rewarding precisely the gaming behaviour the docs claim to resist.
Removed from scoring, kept as a recommendation.

Experience evidence quality was a plain mean, so adding a real role with slightly weaker
bullets lowered it. It now reads a fixed-size sample of the strongest bullets padded with
the baseline, which makes the category provably non-decreasing.

### Two of my own probes were wrong

Reported honestly because a probe that cannot isolate its signal is worse than no probe.
One replaced `| Remote` with a foreign city — also removing a term the job description
used, so the score moved for a defensible reason. One described a career break as "family
caregiving", which is topically relevant to healthcare roles and legitimately added a
keyword match. Both were fixed to isolate the signal they claim to test.

### A regression the tests caught in my own fix

The new inflection rule turned `node.js` into `node.j`. An existing regression test
failed immediately. Technical tokens are now exempt.

## What this does not claim

- **Sixteen cases is small.** The metrics are directional, not precise.
- **The thresholds were tuned on the same corpus they are measured against**, so the
  reported accuracy is optimistic. A held-out split is needed before further tuning.
- **The labels are one author's judgment.** Independent labeling and an inter-rater
  agreement measure would make the ground truth defensible rather than merely stated.
- **Fairness is tested, not proven.** Nine named signals do not move the score, and a
  regression fails the build. Proxies nobody thought to test are not covered.

## The remaining ceiling is lexical

After calibration, most surviving errors are not threshold problems — they are vocabulary
problems. The résumé says "GitHub Actions build and release pipelines"; the job says
"continuous integration". "People management for four developers" against "demonstrated
team leadership". No threshold fixes those.

Closing that gap needs broader concept coverage or local semantic matching, and it is now
a **measurable** project rather than an open-ended one: the number to move is evidence
accuracy, currently 0.767, and the constraint is that the fairness properties must
continue to hold at zero.

## Also in this pass

A performance budget test now locks in the fix for the previously quadratic analysis
path, asserting both an absolute ceiling and sub-quadratic growth in requirement count —
the shape of the regression, not just its symptom.

## Verified

188 backend tests · evaluation gate passed · 20 frontend tests · both Playwright suites
in real Chromium · ruff · strict mypy · eslint · prettier · production build · Alembic
upgrade and check.

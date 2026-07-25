# Evaluation harness

`make eval` measures whether MatchCraft's analysis is any good. `make eval-gate` fails
the build when it regresses. CI runs the gate on every pull request.

Before this existed, the only empirical check on the analysis was one expected-output
fixture. That proved the pipeline was *consistent*, not *correct* — every scoring change
was unfalsifiable, and a change that made the analysis meaningfully worse would still
show a green build.

## What it measures

| Metric | Question it answers |
|---|---|
| Requirement extraction P/R/F1 | Did the parser find the requirements a human reviewer says the job states? |
| Priority accuracy | Did it correctly separate required from preferred from context? |
| Evidence accuracy | Did it correctly judge whether the résumé supports each requirement? |
| Score band accuracy | Does the overall score land in the band a reviewer would assign? |
| Fairness violations | Did the score move when only an identity signal changed? |
| Soundness violations | Did the score respond to evidence in the direction it must? |

Evidence accuracy and the property checks are the honest signals. Extraction F1 reads
high partly because unlabeled predictions are not penalized unless explicitly forbidden,
and because surface matching is generous in both directions — treat it as an upper bound.

## Two techniques, and why both are needed

**Labeled cases** (`corpus/`) work because requirement extraction and evidence
classification genuinely have a defensible ground truth: a competent reviewer can say
what a job requires and what a résumé shows.

**Metamorphic properties** (`properties.py`) work where labels cannot. There is no
"correct" score for a résumé, but there are relations that must hold between two runs:

- *Fairness (invariance).* Swapping a name, a university, pronouns, a graduation year, a
  career break, or a location must change nothing. These are the only automated defense
  against a scoring system quietly rewarding signals it must never use. Zero tolerance.
- *Soundness (directional).* Adding real evidence must not lower the score; removing it
  must not raise it; padding and keyword stuffing must not help.

A property failure is a defect even when the delta is small, because
`docs/responsible-ai.md` promises the score reflects evidence coverage. Any movement
falsifies that promise.

## Adding a case

1. Write synthetic résumé and job-description `.txt` files in `corpus/`. No real person,
   employer, or contact detail — use `example.test` addresses and invented organizations.
2. Add an entry to `corpus/cases.json`. The schema is `EvaluationCase` in `schema.py`.
3. Label what is **true**, not what you predict the parser will output. The gap between
   the two is the entire point. If you find yourself softening a label to make a metric
   look better, stop and write the honest label — then either fix the parser or record
   the miss.
4. Run `make eval` and read the misses.

`expected_band` is a band, not a number, on purpose. Asserting an exact score would
encode today's arithmetic as truth and block every future improvement.

## Adding a property

Add a `Property` to `PROPERTIES` in `properties.py` with a mutation and the relation it
must satisfy. Write the `rationale` as the sentence you would say to someone defending
the current behaviour.

A probe must isolate one signal. Two probes in this suite were wrong when first written:
one replaced `| Remote` with a foreign city, which also removed a term the job used, and
one described a career break as "family caregiving", which is topically relevant to
healthcare roles. Both reported fairness violations that were not violations. A probe
that cannot distinguish its own signal is worse than no probe.

## Thresholds

`thresholds.json` holds the gate. Fairness and soundness are zero-tolerance. The accuracy
floors sit slightly below current measurements so corpus growth does not fail the build
while a real regression does. Raise them as the corpus grows; never lower one without
recording why in the changelog.

## Known limitations

- **Sixteen cases is small.** Metrics are directional, not precise.
- **The thresholds were calibrated on this corpus.** `SUPPORTED_OVERLAP` was tuned by
  sweeping against these same labels, so the reported evidence accuracy is optimistic.
  The corpus should grow, and a held-out split should be introduced before any further
  threshold tuning.
- **The labels are one author's judgment.** Multiple independent labelings and an
  inter-rater agreement measure would make the ground truth defensible rather than
  merely stated.
- **The remaining errors are lexical, not calibration.** After tuning, most misses are
  cases where the résumé and the job describe the same thing in different words —
  "GitHub Actions build pipelines" against "continuous integration". No threshold fixes
  those; they need broader concept coverage or semantic matching. The harness now makes
  that work measurable, which is the point.

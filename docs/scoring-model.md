# Scoring model

MatchCraft reports a **résumé-to-role alignment score**, not an ATS score and not a hiring prediction. The score measures evidence coverage in the supplied text at one point in time. Missing evidence is not proof that a candidate lacks a skill.

Weights are defined in `apps/api/app/analysis/scoring.py`, validated to total exactly 100, and applied only by the backend.

| Category | Maximum | Deterministic rule |
|---|---:|---|
| Required skill alignment | 25 | Coverage of skills explicitly classified as required |
| Responsibility alignment | 20 | Term overlap for job responsibilities, tool context, and explicitly required experience thresholds/non-catalog qualifications; partial credit for transferable overlap |
| Experience evidence quality | 15 | Bullet-level action, useful detail, length, and supported outcome indicators |
| Measurable accomplishment quality | 10 | Metrics tied to impact language, capped after three qualifying bullets |
| Preferred skill alignment | 10 | Coverage of explicitly preferred skills |
| Résumé clarity and structure | 10 | Contact signal, experience/skills/education headings, and practical word-count range |
| Keyword and terminology alignment | 5 | Unique prominent job terms appearing in the résumé |
| Education and certification alignment | 5 | Evidence for explicit education/certification requirements |

Term comparison ignores trailing sentence punctuation, so `dashboards` and `dashboards.` are the
same term, while interior separators that carry meaning (`node.js`, `asp.net`, `co-ordinate`,
`c++`) are preserved. Terms containing a slash, such as `ci/cd`, are not tokenized at all and
contribute no overlap; they are matched through the skill alias catalog instead.

## Skill evidence quality

Skills use canonical aliases and word-boundary matching. One normalized skill creates at most one finding, so repetition does not multiply credit.

- A skill in a concrete sentence or accomplishment receives full supported credit.
- A skill appearing only in a compact skills/tools list receives 75% of supported credit. Contact links are not treated as contextual skill evidence.
- Repeating the word without new context remains one skills-list finding.
- Semantic equivalence may be described by an optional model, but it does not silently create deterministic skill credit.

For a category with `n` findings:

```text
category points = category maximum × (sum of evidence credit / n)
```

Required and preferred skills are scored separately. An unsupported preferred skill can affect at most 10 points; an unsupported required skill can affect up to 25.

## Responsibility alignment

The engine compares significant, non-stopword terms from a job responsibility, tool context, or
explicitly required experience threshold/non-catalog qualification with résumé lines. Preferred
non-skill qualifications remain visible as evidence but do not consume required-responsibility
points. A deliberately small normalization table treats common inflections such as
`build`/`built`, `service`/`services`, and `test`/`testing` as the same term; it does not perform
broad semantic inference:

- at least two overlapping terms and 55%+ requirement-term coverage: supported, medium confidence;
- at least two overlapping terms and 25%+ coverage: potentially transferable, medium confidence;
- otherwise: not found.

Transferable findings receive 55% credit in this category. Supported findings receive full
credit, except that bare-list evidence for a responsibility's tool context receives the same 75%
skill-evidence discount. The UI labels the
interpretation rather than presenting it as an exact employer requirement match. Date arithmetic
and complex equivalence are not inferred, so users should review years-of-experience findings.

## Experience evidence quality

Each detected bullet starts with 25% baseline credit and can earn another 25% each for:

- beginning with a recognized action verb;
- containing at least eight words of useful detail;
- containing a measurable result.

The category uses the average bullet quality. If no bullets are detected, conservative baseline credit acknowledges that unconventional formatting may have hidden experience while still showing a structure problem.

## Measurable accomplishments

A measurable result requires both a metric (for example percentage, currency, time, records, users, or multiplier) and impact language such as reduced, improved, saved, grew, or delivered. A number alone—for example a team size—does not automatically count as an outcome.

Full credit is reached when up to three bullets (or all bullets if fewer than three exist) contain supported metric/impact pairs. MatchCraft never invents a metric to improve this score.

## Clarity and terminology

Clarity checks six equally weighted signals: a contact signal, recognizable experience, skills, and education sections, a practical 200–1,400 word range, and internally consistent employment-date formatting. These are readability heuristics, not quality judgments about nontraditional backgrounds.

Terminology uses unique prominent terms rather than raw frequency. Keyword stuffing therefore has limited effect and cannot create contextual evidence.

## Not-scored coverage categories

Four categories are pure coverage measures: **Required skill alignment (25)**, **Responsibility
alignment (20)**, **Preferred skill alignment (10)**, and **Education and certification alignment
(5)**. When the parser detects no requirement of that kind, the category is **not scored**: it
carries a zero maximum and is excluded from the total. The overall score is therefore a percentage
of what was actually assessed.

This replaced an earlier rule that awarded full credit for an undetected requirement. The
evaluation corpus showed what that rule actually did: an executive assistant scored 56/100 against
an HVAC technician role, 35 points of it free credit for two categories with no detected
requirements. Full credit for a requirement nobody found is indistinguishable from a met
requirement, which is the opposite of an evidence-based score.

The candidate is still never penalized for an employer requirement that was not stated — the
category simply does not participate. If a report shows several not-scored categories, the job
description is probably missing recognizable headings; confirm the complete posting was pasted
before trusting the overall number.

## What is deliberately not scored

Two heuristics were removed from scoring after the evaluation harness measured their real effect:

- **Employment-date formatting.** It lowered the score on 13 of 16 corpus cases purely because a
  career break introduces a differently formatted date range. Penalizing a caregiving gap is
  exactly the disparate impact this product promises not to create.
- **Résumé word count.** A hard 200–1,400 word band is a step function, so any addition could
  cross it. It made irrelevant padding *raise* the score by up to 3.6 points and adding a genuine
  role *lower* it.

Both remain recommendations. They are writing advice, not evidence of a qualification.

## Measurement

The scoring model is measured, not asserted. `make eval` runs a labeled synthetic corpus and a set
of metamorphic properties; `make eval-gate` runs in CI. The non-catalog matching thresholds in
`analysis/scoring.py` were calibrated by sweeping against that corpus — the previous
`SUPPORTED_OVERLAP` of 0.55 measured 0.599 evidence accuracy with 66 under-credits against 3
over-credits, and 0.30 measures 0.767. See the [evaluation harness](../eval/README.md), including
its stated limitations.

Headings are matched by pattern rather than exact string, so `Requirements:`, `Qualifications:`,
`Basic Qualifications:`, `What you'll need:`, `Must-have qualifications:`, `Nice to have:`, and
`Preferred Qualifications` are all recognized. A line that merely mentions one of those words
("Requirements include Python and Docker") is treated as a requirement, not a heading.

## Education and certification

Preferred education and certification findings remain visible without consuming required-alignment
points. When a required item exists, relevant term overlap in the corresponding résumé section
receives conservative medium-confidence support. Users should review equivalence.

## Example

Suppose the category results are 20/25, 12/20, 11/15, 6/10, 7.5/10, 8/10, 3.5/5, and 5/5:

```text
20 + 12 + 11 + 6 + 7.5 + 8 + 3.5 + 5 = 73/100
```

The report must be read with its evidence and explanations. A 73 does not mean a 73% chance of an interview, a candidate percentile, or an ATS result.

## Changing weights safely

Update `SCORE_WEIGHTS`, keep the total at 100, add or update unit fixtures, document the rationale here, and verify that offline/model-online runs retain deterministic parity. A scoring change requires review because it affects every saved interpretation after rerun.

## Limitations

Heuristics may miss unconventional section headings, semantic equivalents, indirect accomplishments, and complex education equivalence. Job descriptions can be vague or internally inconsistent. Human review remains authoritative.

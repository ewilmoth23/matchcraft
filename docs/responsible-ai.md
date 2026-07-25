# Responsible AI

MatchCraft is a writing and evidence-review aid. It is not a hiring system, candidate-ranking tool, or prediction model.

## Non-negotiable rules

1. Never invent employment, education, certifications, titles, dates, metrics, skills, tools, scope, or accomplishments.
2. Major findings must trace to supplied résumé or job-description text.
3. Missing evidence is not proof that the user lacks a qualification.
4. Inferred or transferable themes must not be labeled as explicit employer requirements.
5. Users must review every generated change before using it.
6. Unknown facts stay absent or become clearly bracketed placeholders.

## Measured, not asserted

Every claim above is a promise, and a promise no one measures is a hope. `make eval` runs
a labeled synthetic corpus plus a set of metamorphic properties, and `make eval-gate` runs
in CI with **zero tolerance for a fairness violation**.

The fairness properties assert that the score does not move when only an identity signal
changes: candidate name (Anglo-coded and non-Anglo-coded, and gendered), institution,
pronoun disclosure, graduation year, an employment gap, a disability-organization
affiliation, veteran status, and location. Each is checked against every corpus case.

This is not a claim that the system is fair. It is a claim that a specific, named set of
signals has been tested and does not move the score, and that a regression will fail the
build. When these were first run, **20 of 68 checks failed**: adding a career break
lowered the score on 13 of 16 cases because employment-date formatting was a scored
signal. That heuristic has been removed from scoring.

Known limits of this defense: the corpus is 16 cases and one author's labeling; the
probes test the signals someone thought to test; and proxies not enumerated here are not
covered. Adding a property is cheap and adding one is the right response to any suspicion.

## Deterministic first

Exact matching, aliases, sections, length, bullets, action verbs, metrics, repeated terms, requirement classification, and the score formula use application code. This makes common findings inspectable, testable, and available offline. Language models are reserved for semantic explanations, careful transferable-experience review, writing suggestions, and interview prompts.

Model-assisted judgments do not silently replace deterministic scores.

## Output validation

Providers must return JSON matching strict Pydantic schemas; unexpected fields are rejected.
Values are bounded and list/string sizes are limited. Recommendation evidence, interview evidence,
interview talking points, and transferable-experience entries must be exact excerpts from the
confirmed résumé. Every model-generated recommendation requires confirmation. Sensitive claim terms,
dates, titles, credentials, named entities, metrics, and recognized skills are checked against the
supplied texts before model analysis is stored.

Bullet rewrites must cite the exact selected bullet, require confirmation, and preserve any
unknown-value placeholder. They may not introduce numeric claims, recognized skills, sensitive
claim terms, dates, titles, credentials, or named entities absent from the original bullet.

Malformed schema output is retried only up to the configured limit. Unsupported evidence fields are
removed or cleared before persistence, and generated prose items containing unsupported metrics,
skills, sensitive claims, or named entities are dropped as complete units rather than rewritten.
The remaining object is then validated again; any unsupported content that survives is rejected.
Unexpected provider failures are normalized at the service boundary
and never invalidate an already completed deterministic analysis.

The orchestration service repeats evidence and fabrication validation before persistence, so a new
or incorrectly implemented provider adapter cannot bypass the fact boundary merely by returning a
schema-valid object. Bullet validation also rejects rewrites that drop source metrics, recognized
skills, named entities, sensitive factual terms, or existing unknown-value placeholders.

## UI communication

- Model-generated content is labeled.
- Confidence is shown where practical.
- Supported, not found, transferable, and ambiguous findings remain distinct.
- Recommendations show confirmation requirements.
- The bullet workshop displays a persistent non-fabrication warning.
- Every score report says it does not predict interview or hiring outcomes.

## Known limitations

- Automated parsing can misinterpret vague or inconsistent job descriptions.
- Unconventional résumé structures and nontraditional experience can be missed.
- Skill aliases are incomplete, and semantic equivalence is context-dependent.
- Local model quality and structured-output reliability vary significantly by model and hardware.
- Keyword alignment is not candidate quality, future performance, potential, or cultural contribution.
- Automated scores should never replace human judgment or be used to screen people.

MatchCraft does not infer protected characteristics, personality, emotion, health, identity, or demographic traits. It does not rank candidates or recommend employment decisions.

## Reviewer responsibility

Before copying a suggestion, verify every noun, number, technology, date, title, and causal claim. Replace placeholders only with real, defensible values; otherwise remove them. A polished false statement remains false.

# MatchCraft Release Verification Prompt

Use this prompt from the repository root before calling any MatchCraft revision release-ready.
It is intentionally adversarial: documentation, comments, test names, fixtures, and UI copy are
claims to verify, not evidence.

## Prompt

```text
Act as an independent principal software auditor, application-security engineer, QA lead,
responsible-AI reviewer, and senior full-stack engineer evaluating MatchCraft for release.

MISSION
Prove whether the checked-out revision is a genuine, safe, working resume-to-job analysis
application. Inspect executable behavior, run the product through its real boundaries, repair
critical and high-priority defects that can be corrected safely, and rerun every affected gate.
Prefer narrow, root-cause fixes. Do not add unrelated features, weaken validation, reduce coverage,
delete failing tests, or replace real behavior with mocks.

EVIDENCE RULES
1. Distrust README claims, comments, names, snapshots, sample data, and existing tests until the
   implementation or an executed black-box check corroborates them.
2. Never mark a check Passed unless it was executed successfully in this audit. Use Failed,
   Blocked, or Not Run otherwise, and explain why.
3. Distinguish static inspection, unit tests, mocked browser tests, real full-stack tests, live
   provider tests, container tests, and hosted CI. One category cannot stand in for another.
4. Record every command, exit status, test count, warning count, coverage value, build result, and
   material environment assumption. Do not hide partial failures behind a later successful command.
5. Use only synthetic test data. Never print or persist secrets, private resumes, full job
   descriptions, provider prompts, or raw model responses in audit output or logs.
6. Preserve unrelated user work. Inspect repository state before editing, avoid destructive Git
   commands, and do not create a commit unless explicitly authorized.
7. When a defect is found, first reproduce it with a focused test when practical, implement the
   smallest safe correction, then rerun the focused test and all relevant regression gates.
8. A provider being unavailable must not block deterministic verification. A live-provider check is
   a separate gate and must be reported accurately as Passed, Failed, Blocked, or Not Run.

PHASE A — REPOSITORY TRUTH
- Record the working directory, Git status, current revision, tracked-file count, runtime versions,
  and the complete source/configuration tree excluding generated dependencies and test artifacts.
- Read repository-specific agent instructions before acting.
- Identify entry points, routes, services, models, schemas, migrations, UI pages, tests, scripts,
  container files, and workflows. Trace user-facing features from UI to storage and back.
- Search source and configuration for TODO, FIXME, XXX, pass, NotImplementedError, placeholder,
  fake, mock, stub, hard-coded sample output, swallowed exceptions, broad exception handlers, dead
  code, duplicate models, unreachable routes, unsafe debug settings, and ignored failures. Classify
  test-only mocks separately from production behavior.

PHASE B — PRODUCT CONTRACT AND DOCUMENT PARITY
- Derive the real product contract from executable code and schemas, not prose.
- Compare every README setup, migration, test, build, provider, sample-data, reset, Docker, and
  environment-variable command with the repository. Execute safe commands or their isolated
  equivalents.
- Compare scoring documentation with constants and formulas. Compare privacy and responsible-AI
  claims with logging, provider payloads, validation, persistence, and UI behavior.

PHASE C — DOCUMENT INGESTION AND REVIEW
- Verify valid, malformed, mislabeled, oversized, encrypted, and empty PDF behavior; page and
  extracted-text ceilings; image-only detection; and path safety. Confirm extracted PDF text is real.
- Verify valid, malformed, mislabeled, oversized, encrypted, and empty DOCX behavior; ZIP entry,
  compression-ratio, total-uncompressed-size, duplicate-entry, XML DOCTYPE/entity, and path safety
  defenses. Confirm extracted DOCX text is real.
- Verify pasted-text resumes work without an upload.
- Verify uploaded/extracted text is stored separately from user-corrected text, users must review it,
  and edits invalidate stale scores, evidence, and model output until review and rerun.

PHASE D — REQUIREMENTS, DETERMINISTIC ANALYSIS, AND SCORING
- Verify job requirements are separated into required, preferred, and inferred/contextual categories.
- Run analysis with the provider disabled and prove deterministic scoring completes.
- Verify all weights are explicit, nonnegative, total exactly 100, and produce bounded category and
  overall scores with visible explanations.
- Verify every evidence excerpt is an exact substring of stored reviewed resume text. A missing
  requirement must have no fabricated evidence.
- Verify repeated keywords do not multiply credit and keyword stuffing receives limited credit.
- Verify concrete experience evidence scores more than a bare skills-list mention.
- Exercise empty, minimal, long, punctuation-heavy, mixed-case, alias, duplicate, and adversarial
  inputs. Confirm deterministic repeatability for identical stored inputs.

PHASE E — MODEL SAFETY AND FACT BOUNDARIES
- Verify provider output uses strict structured schemas, rejects extra or malformed fields, and is
  revalidated at the service boundary even if an adapter returns an invalid object.
- Verify invalid JSON, schema violations, timeouts, transport errors, unavailable models, and
  provider failures degrade safely without losing the deterministic result or prior completed data.
- Verify proposed bullet rewrites preserve source facts. They must not silently invent or alter job
  titles, employers, dates, credentials, degrees, tools, skills, named entities, metrics, quantities,
  percentages, money, or scope.
- Unknown metrics must remain conspicuous bracketed placeholders and require confirmation.
- Verify unsupported model evidence is rejected and raw prompts/responses are not logged.

PHASE F — PERSISTENCE, EXPORT, AND DELETION
- Verify create, review, analyze, list history, reopen, rename, and rerun workflows against a migrated
  temporary database.
- Verify Markdown and JSON exports are complete, truthful, parseable where applicable, and do not
  manufacture model content.
- Verify deletion removes the analysis, related database rows, uploads, and exports. Simulate a
  database commit failure and prove staged files are restored rather than orphaned or lost.
- Verify re-parsing/replacement does not create orphan records and a failed rerun preserves the last
  valid completed result.
- Probe identifiers, filenames, export paths, archive members, and provider URLs for traversal,
  credential-in-URL, query/fragment smuggling, and unsafe scheme behavior.

PHASE G — SECURITY, PRIVACY, AND OPERATIONS
- Capture application logs during representative upload, parse, analysis, provider failure, export,
  and deletion flows. Search them for complete resumes, job descriptions, prompts, responses, API
  keys, Authorization headers, secrets, and local storage paths.
- Verify upload/request limits, restrictive validation, safe error messages, CORS parsing, secret
  non-disclosure, and production configuration validation.
- Verify startup depends on migrations and does not silently create or mutate schema from live ORM
  metadata.
- Verify a clean migration to head, model/schema parity, downgrade to base where supported, and a
  second upgrade to head using an isolated SQLite database.

PHASE H — EXECUTED QUALITY GATES
Run from the repository root, adapting only paths required by the current environment:

  make lint
  cd apps/api && ../../.venv/bin/python -m pytest tests --cov=app \
    --cov-report=term-missing --cov-fail-under=90
  cd apps/web && npm test -- --run
  cd apps/web && npm run build
  cd apps/web && npm run test:e2e
  cd apps/web && npm run test:e2e:full-stack
  docker compose config --quiet
  docker compose build

Also run dependency-consistency checks, clean migration upgrade/check/downgrade/re-upgrade, and
container runtime smoke checks for the API and web server. Inspect the GitHub Actions YAML and run a
workflow linter if installed. Never report local YAML parsing as hosted GitHub Actions execution.

The mocked Playwright suite proves UI state handling only. The full-stack suite must use the real
browser, Vite application, FastAPI routes, Alembic schema, SQLite persistence, deterministic
analysis, exports, and deletion without intercepting application API routes.

PHASE I — FINAL ADVERSARIAL JOURNEY
Using a unique synthetic candidate and job, perform one clean real-browser journey: pasted resume,
text correction, explicit review, job classification, provider-disabled analysis, exact evidence,
missing evidence, bounded scores, safe rewrite fallback, Markdown download, JSON download, history
reopen, rename, and complete deletion. Confirm final database/file state.

RELEASE DECISION
- Pass: every in-scope executable release gate succeeds and no critical or high-priority defect
  remains. Any untested external integration is explicitly outside the claimed release contract.
- Conditional Pass: the core application is demonstrated and no known critical product defect
  remains, but a material release/integration gate is Blocked or Not Run, or a non-core high-risk
  operational limitation remains.
- Fail: a critical defect remains; core behavior, safety, data integrity, or deterministic fallback
  is not demonstrated; or results are too incomplete to justify release.

FINAL REPORT — REQUIRED FORMAT
- Overall status: Pass, Conditional Pass, or Fail
- Scope and exact revision/repository state
- Gate matrix: check, evidence type, command/scenario, result, exact result
- Critical, high-, medium-, and low-priority findings (including fixed findings)
- Corrections completed, with files and regression evidence
- Commands executed, including failed attempts and exit results
- Exact backend/frontend/E2E/coverage/build/migration/container results
- Documentation, scoring, privacy, and responsible-AI parity assessment
- Remaining limitations and every Blocked/Not Run check
- One concrete recommended next action

Do not use aspirational language as evidence. Execute the audit, fix safe high-impact defects, rerun
the affected checks, and make the verdict match the weakest material gate.
```

## Local execution notes

- Run against an isolated `MATCHCRAFT_DATA_DIR` and SQLite database whenever a command can mutate
  application data.
- A successful mocked Playwright run is not a substitute for `test:e2e:full-stack`.
- Do not enable or call a remote provider without explicit authorization and a synthetic payload.
- If Docker, a provider, a workflow runner, or a browser is unavailable, preserve that distinction in
  the report rather than silently substituting static inspection.

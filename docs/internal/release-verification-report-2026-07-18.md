# MatchCraft Release Verification Report — 2026-07-18

> Historical baseline. The live-provider limitation and test totals in this report were superseded by
> the [2026-07-23 local-first AI verification](local-first-ai-verification-2026-07-23.md).

## Overall status: Conditional Pass

The executable application is genuine and its local deterministic workflow is working. Backend,
frontend, real browser, migration, export, deletion, privacy, scoring, model-boundary, and container
checks passed after the corrections described below. It is not release-ready as a repository because
the `.git` directory has no `HEAD` and Git tracks zero files. A live model provider and hosted GitHub
Actions were also not executed.

This audit executed the reusable [release verification prompt](release-verification-prompt.md) from
the repository root on macOS using Python 3.12.13, Node 25.7.0, npm 11.12.1, Docker 29.6.1, and
Docker Compose 5.3.0. CI and containers target Python 3.12 and Node 22.

## Repository truth and map

- Git revision: unavailable (`git rev-parse --verify HEAD` failed).
- Tracked files: 0.
- Source/configuration files before this report: 117, excluding installed dependencies and generated
  Playwright artifacts.
- Git status: every top-level project path is untracked.
- No `AGENTS.md` was present.

```text
apps/api/app/api/v1       FastAPI routes
apps/api/app/analysis     deterministic text analysis and scoring
apps/api/app/models       SQLAlchemy persistence model
apps/api/app/providers    optional structured model-provider adapter and fact validation
apps/api/app/schemas      request, response, and model-output contracts
apps/api/app/services     documents, parsing, orchestration, exports, persistence
apps/api/alembic          frozen schema migrations 0001 and 0002
apps/api/tests            backend behavior, safety, migrations, docs, scoring
apps/web/src              React workflow and presentation client
apps/web/tests            Vitest/Testing Library regressions
apps/web/e2e              mocked and real full-stack Playwright journeys
scripts                   isolated E2E server, samples, reset, provider check
docs                      architecture, development, scoring, security, responsible AI
.github/workflows         four-job CI workflow
```

## Gate matrix

| Area | Evidence | Result | Exact result |
|---|---|---:|---|
| Repository revision | Git commands | **Failed** | No `HEAD`; 0 tracked files |
| Production placeholders/dead stubs | Static scan and route/service tracing | Passed | No production TODO, FIXME, XXX, `pass`, `NotImplementedError`, fake/stub result, or `metadata.create_all`; only the mocked E2E intercepts API routes |
| Backend lint/format/types | `make lint` | Passed | Ruff passed; 53 files formatted; strict mypy passed 37 source files |
| Backend behavior/coverage | pytest with coverage floor | Passed | **95 passed, 6 warnings, 92.01% coverage** |
| Frontend lint | ESLint | Passed | 0 errors, 0 warnings |
| Frontend unit/component | Vitest | Passed | **4 files, 13 tests passed** |
| Frontend production build | TypeScript + Vite | Passed | **2,290 modules transformed**, build succeeded |
| Mocked browser workflow | Playwright Chromium | Passed | **1 passed in 2.8s** |
| Real full-stack workflow | Playwright Chromium + Vite + FastAPI + Alembic + SQLite | Passed | **1 passed in 3.9s**; no application API interception |
| PDF/DOCX/pasted text | Focused and full backend tests | Passed | Real extraction, malformed/empty/image-only/limit/archive defenses, encrypted PDF and encrypted DOCX rejection, paste/review/edit |
| Requirement categories | Parser tests and real browser | Passed | Required, preferred, and context/inferred groups populated and visible |
| Offline deterministic analysis | API and real browser | Passed | Provider disabled; 8 categories; result completed; model status skipped |
| Scoring/evidence | Deterministic tests and parsed JSON download | Passed | Weights total 100; bounded totals; exact stored-text excerpts; missing Kubernetes evidence is `null`; stuffing limited; contextual evidence outranks bare list |
| Model safety | Schema, adapter-bypass, malformed JSON, timeout, and fact-boundary tests | Passed | Invalid output is rejected; deterministic result remains; titles, dates, metrics, skills, credentials, entities, and placeholders guarded |
| History/export/deletion | API tests and real browser | Passed | Reopen/rename; Markdown content; parseable JSON; related rows/files deleted; commit-failure restore; final history API returned `[]` |
| Privacy/path safety | Log-capture and document/provider URL tests | Passed | Synthetic document/path markers absent from logs; traversal and secret-bearing provider URLs rejected |
| Migrations | Clean isolated database | Passed | Upgrade 0001→0002; `alembic check` clean; downgrade to base; re-upgrade; head is 0002; fresh missing data directory bootstraps |
| README command parity | Tests plus isolated CLI replay | Passed | Make targets/env names exist; migrate, sample (2 analyses), disabled provider check, and interactive reset succeeded |
| Dependencies | `pip check`, `npm ls --all --omit=optional` | Passed | No broken Python requirements; npm dependency tree exited 0 |
| Compose and images | Compose validation/build/runtime | Passed | Config valid; API/web images built; API migrated and imported; Nginx syntax successful |
| Workflow definition | PyYAML inspection | Passed locally | 4 jobs: backend, frontend, integration, compose |
| Workflow lint | `actionlint` availability | **Not Run** | `actionlint` is not installed |
| Hosted GitHub Actions | External runner | **Not Run** | Local checks cannot establish hosted execution |
| Live Ollama/OpenAI-compatible provider | External integration | **Not Run** | Disabled provider check behaved correctly; controlled provider tests passed |

## Corrections completed

### High priority

1. **Corrected résumé text could become stale in the Bullet Workshop.** The backend stored and scored
   the edit, but the frontend retained pre-edit résumé structure for the 15-second query stale window.
   Selecting that stale bullet caused the fact-boundary API to reject it. The confirmation response now
   replaces the cached résumé, with a component regression assertion and real-browser correction flow.

2. **Reopening a renamed analysis could show its former name.** History updated but the cached detail
   record did not. The rename response now replaces the detail cache, with unit and full-stack
   rename/reopen coverage.

3. **The documented first migration could fail on a fresh machine.** Alembic attempted to open SQLite
   before creating the configured data directory. Migration bootstrap now creates restricted upload and
   export directories first. A test starts with a missing nested directory, and the isolated README CLI
   sequence now succeeds.

### Medium priority

4. **Encrypted PDF behavior was safe but ambiguous.** Password-protected PDFs were reported as merely
   corrupt. They now receive an explicit `encrypted_pdf` rejection. An adversarial DOCX central-directory
   encryption flag fixture also proves encrypted archive entries are rejected before extraction.

5. **The real browser test under-verified its downloads and postconditions.** It now corrects résumé
   text, checks all three job classifications, parses JSON, reads Markdown, validates exact/missing
   evidence, verifies eight maxima total 100, exercises safe rewrite fallback, renames/reopens, deletes,
   and confirms the final analysis collection is empty.

## Findings by severity

### Critical

- **Unresolved — repository integrity:** no Git `HEAD`, no commit identity, and zero tracked files. The
  program cannot be reproduced, reviewed as a revision, diffed reliably, or released safely in this
  state. No commit was created because authorization was not given.

### High

- No known high-priority application defect remains after the three corrections above.

### Medium

- No live Ollama or OpenAI-compatible endpoint was exercised. Provider transport and malformed output
  were verified with controlled HTTP/provider tests only.
- Hosted GitHub Actions was not executed, and `actionlint` is unavailable locally.
- E2E coverage is Chromium-only.
- The application intentionally has no OCR, malware scanner, authentication, or public-deployment
  hardening; it remains a trusted, single-user local tool.
- An abandoned pre-analysis draft may remain if a browser closes mid-workflow; direct API deletion is
  available, but drafts do not have a separate cleanup UI.
- Fact guards are conservative lexical controls and cannot prove arbitrary semantic equivalence.

### Low

- Six third-party deprecation warnings remain: one Starlette TestClient/httpx warning and five PyMuPDF
  SWIG warnings. They do not change the passing result.
- Optional `ollama/ollama:latest` is not digest-pinned. Release API/web base images are digest-pinned.
- Python constraints pin versions but do not contain package hashes.
- A final staged-file unlink failure is logged but can leave a hidden staged file; there is no janitor.
- The Nginx unprivileged entrypoint reports that its read-only copied configuration cannot be modified;
  `nginx -t` still succeeds.

## Commands executed and exact outcomes

Primary successful commands:

```text
make lint
  Ruff: pass; format: 53 files; mypy: 37 files; ESLint: pass

cd apps/api && ../../.venv/bin/python -m pytest tests --cov=app \
  --cov-report=term-missing --cov-fail-under=90
  95 passed, 6 warnings, 92.01%

cd apps/web && npm test -- --run
  4 files, 13 tests passed

cd apps/web && npm run build
  2,290 modules transformed; success

cd apps/web && npm run test:e2e
  1 Chromium test passed in 2.8s

cd apps/web && npm run test:e2e:full-stack
  migrations 0001 and 0002 applied; 1 Chromium full-stack test passed in 3.9s

docker compose config --quiet
  exit 0

docker compose build
  matchcraft-api and matchcraft-web built successfully

docker run --rm ... matchcraft-api ...
  fresh nested SQLite directory created; migrations applied; alembic check clean; MatchCraft API imported

docker run --rm --add-host api:127.0.0.1 matchcraft-web nginx -t
  syntax and configuration test successful

isolated make migrate / make sample / make provider-check / make reset-data
  migrations applied; 2 synthetic analyses loaded; disabled provider unavailable as expected; reset confirmed
```

Other executed checks included `pip check`, `npm ls --all --omit=optional`, runtime version capture,
workflow YAML parsing, static placeholder/exception/log/path scans, focused document and migration tests,
clean Alembic upgrade/check/downgrade/re-upgrade, and Git state/file counts.

Material failed attempts retained in the audit record:

- Initial Playwright and Docker commands were denied loopback/daemon metadata access by the workspace
  sandbox; the identical commands passed with explicit local permission.
- The strengthened browser journey reproduced the stale corrected-résumé cache and later the stale
  renamed-detail cache; both passed after fixes.
- An isolated `make migrate` against a nonexistent configured data directory failed with
  `sqlite3.OperationalError`; the exact scenario passed after the migration-bootstrap fix.
- Intermediate lint runs caught two unnecessary TypeScript assertions, one floating navigation
  promise, and one Python import-order issue; all were corrected and final lint passed.

## Documentation, scoring, privacy, and responsible-AI parity

- README Make targets and documented environment keys have executable parity tests.
- Documented score names and weights are compared directly with executable constants; totals are 100.
- Model-provided explanation does not modify deterministic category scores.
- Exact evidence is derived from reviewed stored text. Unsupported requirements carry no excerpt.
- Missing evidence is described as absence from the supplied résumé, not absence of candidate ability.
- Model output uses strict Pydantic contracts and a second service-level evidence/fact validation layer.
- Deterministic results survive provider unavailability, timeout, malformed JSON, malformed schema, and
  an unsafe adapter return.
- Routine structured logs use identifiers/counts and passed synthetic leakage-marker tests.

## Recommended next action

Create and review the initial Git commit on a protected `main` branch, then push it and require all four
GitHub Actions jobs to pass. After repository integrity is established, run one authorized synthetic
live-provider smoke test and record the endpoint/model version without committing credentials.

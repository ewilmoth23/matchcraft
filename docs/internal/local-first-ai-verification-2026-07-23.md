# MatchCraft Local-First AI Verification — 2026-07-23

## Overall status: Conditional Pass

MatchCraft is a genuine working local résumé-to-role analysis application. Its deterministic analysis,
document workflow, exports, history, deletion, and Docker deployment remain operational. The AI path
now runs Ollama first and completed live analysis and bullet-rewrite requests with structured,
source-grounded output.

The application has no known remaining critical or high-priority runtime defect from this review.
Release status remains conditional because the repository has no Git `HEAD` and tracks zero files,
hosted GitHub Actions was not executed, and no live remote-provider request was authorized.

## Critical findings

- **Unresolved repository integrity:** `git rev-parse --verify HEAD` fails and every project path is
  untracked. There is no reproducible revision to review, tag, protect, or release. Creating the
  initial commit was not inferred from the audit request.

## High-priority findings

All high-priority AI defects found in this review were corrected:

- Docker had been configured with AI disabled and a nonexistent local-model default.
- There was no local-first provider chain or safe configured-only remote fallback.
- A 60-second Nginx proxy timeout terminated legitimate local inference before the API completed.
- Ollama could allocate its maximum context and excessive memory instead of a bounded context.
- One unsafe model-written field caused an otherwise useful response to be discarded in full.
- Model evidence could be paraphrased, repeated, or exceed the documented result limits.
- Settings did not clearly distinguish local and remote models, health, or key configuration.

## Medium-priority findings

- No live OpenAI request was executed because `MATCHCRAFT_OPENAI_API_KEY` is not configured. Official
  OpenAI request construction, strict Structured Outputs, refusal/error handling, and fallback
  selection passed controlled transport tests.
- Hosted GitHub Actions was not executed. The workflow definition and all equivalent local commands
  passed, but `actionlint` is not installed.
- End-to-end browser coverage is Chromium-only.
- Local 9B-model analysis is materially slower and less instruction-reliable than a frontier remote
  model. The final synthetic analysis took 84,656 ms and required 13 field/item removals by the
  fail-closed sanitizer. Three exact transferable excerpts and three grounded model questions
  remained useful.
- MatchCraft is intentionally a trusted, single-user local application. It has no authentication,
  OCR, malware scanner, rate limiting, TLS termination, or public-deployment threat model.

## Low-priority findings

- Six dependency deprecation warnings remain: one Starlette TestClient/httpx warning and five
  PyMuPDF SWIG warnings.
- The optional `ollama/ollama:latest` image is not digest-pinned.
- Python constraints pin versions but do not contain package hashes.
- The temporary Compose override used on this machine is necessary because host port 8000 belongs to
  another application; MatchCraft itself is exposed through Nginx on port 5173.

## Corrections completed

- Added `local_first` as the default provider strategy.
- Selected `qwen3.5:9b` as the balanced local default and verified the exact model is installed.
- Added configured-only fallback to the separate remote model and endpoint.
- Set the remote default to `gpt-5.6-sol`, low reasoning effort, the Responses API, `store: false`,
  and strict JSON-schema Structured Outputs for official OpenAI.
- Kept generic OpenAI-compatible endpoints on strict JSON-schema Chat Completions.
- Added a 32,768-token Ollama context, zero temperature, 3,000 output tokens, a 180-second provider
  timeout, one bounded retry, `think: false`, and safe context-overrun rejection.
- Added actual successful provider/model attribution to provider-run records.
- Added exact résumé-evidence validation for recommendation evidence, interview evidence, talking
  points, and transferable excerpts.
- Added fail-closed removal of unsupported evidence fields and complete generated-prose items that
  introduce metrics, skills, sensitive claims, titles, dates, credentials, or named entities.
- Deduplicated transferable excerpts and enforced output-list bounds in the model schema.
- Preserved the final authoritative validator after sanitization and before persistence.
- Kept deterministic results available when either model provider is unavailable, malformed, unsafe,
  or times out.
- Increased Nginx upstream timeouts so the browser can wait for bounded local-model retries.
- Reworked Settings to show the provider chain, local/remote models, context, reasoning effort,
  API-key configured state, fallback state, and provider-specific health without returning a key.
- Updated Docker, environment examples, architecture, security, troubleshooting, responsible-AI,
  README, and changelog documentation.
- Verified the dark-mode Settings, results, and bullet-workshop UI, including a narrow viewport.

## Commands executed and exact results

```text
cd apps/api
../../.venv/bin/python -m pytest tests --cov=app --cov-report=term-missing
  116 passed, 6 warnings, 91% total coverage

../../.venv/bin/ruff check app tests ../../scripts
  All checks passed

../../.venv/bin/ruff format --check app tests ../../scripts
  51 files already formatted

../../.venv/bin/mypy app
  Success: no issues found in 37 source files

cd apps/web
npm run lint
  0 errors, 0 warnings

npm test -- --run
  4 test files passed; 13 tests passed

npm run build
  2,290 modules transformed; production build succeeded

npm run test:e2e
  1 Chromium test passed in 3.3s

npm run test:e2e:full-stack
  migrations 0001 and 0002 applied; 1 Chromium full-stack test passed in 4.3s

docker compose config --quiet
  exit 0

docker compose -f docker-compose.yml \
  -f /private/tmp/matchcraft-browser-compose.override.yml up -d --build --wait
  API and web images built; both containers healthy
```

Live Docker verification:

- `/api/v1/health`: `healthy`; deterministic analysis `available`; AI `available`.
- Active provider: `ollama`; local model: `qwen3.5:9b`; status: `available`.
- Remote model: `gpt-5.6-sol`; status: `not_configured`; no fallback transmission is possible.
- Synthetic analysis: state `completed`, model status `completed`, deterministic score `62.6`.
- Latest persisted provider run: `ollama/qwen3.5:9b`, `completed`, 84,656 ms, 1,258 prompt tokens,
  1,806 completion tokens, 13 fail-closed field/item removals, no error code.
- Final model output retained three unique exact résumé excerpts, three source-grounded questions,
  three limitations, and no fabricated missing-requirement evidence.
- UI-triggered bullet rewrite: HTTP 200 in 19,965 ms after a cold restart; `model-generated`;
  `confirmation required`; exact original `2 million` fact, Python, and FastAPI preserved; exact stored
  bullet cited as the factual source.
- Browser console: zero warnings or errors after the successful rewrite.
- Current structured-log leakage scan: zero matches for synthetic résumé/job markers, prompt section
  labels, bearer headers, or secret-like tokens.
- Settings response exposes only `remote_api_key_configured: false`; no key field or key value is
  returned.

## Remaining limitations

- Local model quality varies with hardware, model version, and document length. Sanitization can
  intentionally reduce the AI portion to a neutral summary and independently safe items.
- The 32K local context is a resource/safety default, not a guarantee that unusually long documents
  fit. Oversized input fails safely and can fall back only when a remote provider is explicitly
  configured.
- Remote fallback sends confirmed résumé and job text to the configured endpoint. It remains inactive
  by default and must be enabled with an environment-only key.
- Lexical and catalog-based fabrication checks are conservative safeguards, not a proof of semantic
  truth. Human review remains required.
- Hosted CI, a live remote provider, non-Chromium E2E, and public-deployment hardening remain unverified.

## Recommended next action

Create and review the initial Git commit on a protected `main` branch, push it, and require the
backend, frontend, integration, and Compose GitHub Actions jobs. Then run one authorized synthetic
remote-provider smoke test without committing credentials. For local testing now, open
`http://localhost:5173`; both Docker services are healthy and the verified synthetic bullet workshop
is left open.

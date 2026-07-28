# MatchCraft

[![CI](https://github.com/ewilmoth23/matchcraft/actions/workflows/ci.yml/badge.svg)](https://github.com/ewilmoth23/matchcraft/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)


## Project status

> **Actively developed, pre-1.0.** This is a personal project built in the open, published so the
> work can be read and run. It is not a supported product.

Known gaps and caveats, stated up front:

- Not yet exercised end-to-end outside development; expect rough edges on first run.
- Scores are a transparent heuristic, not a prediction of interview or hiring outcomes.
- Local, single-user, no authentication.

Issues and pull requests are welcome. If something breaks on first run, that is
useful information — please open an issue rather than assuming it works for
everyone else.

**Private, evidence-first résumé-to-role analysis.**

MatchCraft is an open-source, single-user local application for comparing a résumé with a job description. It combines deterministic document analysis with optional local AI, shows exactly how its 0–100 alignment score is composed, and traces important findings to the supplied text.

MatchCraft does **not** predict interview or hiring outcomes. Missing résumé evidence is not proof that a candidate lacks a qualification.

## What it does

- Accepts pasted text, PDF, and DOCX résumés.
- Preserves uploaded/extracted text separately and requires review before analysis.
- Separates explicit required qualifications, preferred qualifications, and contextual themes.
- Scores eight visible categories using documented backend weights.
- Shows matched skills with exact résumé excerpts and unsupported requirements with no invented evidence.
- Detects action verbs, outcome metrics, section structure, prominent terminology, and contextual skill usage.
- Produces prioritized, confirmation-aware recommendations.
- Offers evidence-cited, fact-constrained bullet suggestions that require review; unknown outcomes remain bracketed placeholders.
- Builds technical, behavioral, and gap-focused interview prompts from supplied evidence.
- Saves, renames, reopens, exports, and completely deletes local analyses. Editing a saved source
  invalidates prior derived scores and evidence until it is reviewed and rerun.
- Continues deterministic analysis when Ollama or another configured model endpoint is offline.

## Privacy model

SQLite data, uploads, and export storage live in `MATCHCRAFT_DATA_DIR` (default `~/.local/share/matchcraft`, outside the source tree). Routine logs contain identifiers, durations, status, and error codes—not résumé text, job-description text, prompts, API keys, or local file paths.

The default strategy is local-first: MatchCraft tries Ollama, validates the output, and only then tries a configured remote endpoint if local inference is unavailable or invalid. The OpenAI fallback is inactive until `MATCHCRAFT_OPENAI_API_KEY` is set. When a remote fallback is active, the résumé and job description are sent to that endpoint for the requested AI-assisted feature. Deterministic features never require that transmission. See [security](docs/security.md) and [responsible AI](docs/responsible-ai.md).

## Architecture

```text
React / TypeScript / Vite
           │ /api/v1
           ▼
FastAPI ─ services ─ deterministic analysis
   │          │                 │
SQLite     PDF/DOCX       traceable scores
   │
local uploads/exports       provider chain ─ Ollama first ─ optional remote fallback
```

The backend owns parsing, matching, scoring, evidence, and model validation. The frontend is a typed presentation/workflow client and does not duplicate scoring formulas. More detail: [architecture](docs/architecture.md).

## Technology

- Python 3.12, FastAPI, Pydantic, SQLAlchemy, Alembic, SQLite
- PyMuPDF and python-docx
- Ollama plus optional OpenAI-compatible endpoints
- React 19, TypeScript, Vite, Tailwind CSS, TanStack Query, React Router
- React Hook Form, Zod, Recharts
- pytest, Ruff, mypy, Vitest, Testing Library, Playwright
- Docker Compose and GitHub Actions

## Quick start

Prerequisites: Python 3.12+, Node.js 22+, npm, and optionally [Ollama](https://ollama.com/) for AI-assisted features. Docker is optional for local development but required for `make compose` and for the contributor checklist in [CONTRIBUTING.md](CONTRIBUTING.md).

```bash
cp .env.example .env
make install
make migrate
```

In terminal one:

```bash
make api
```

In terminal two:

```bash
make web
```

Open [http://localhost:5173](http://localhost:5173). Interactive API documentation is at [http://localhost:8000/docs](http://localhost:8000/docs) in development; it is disabled when `MATCHCRAFT_ENV=production`, which is what the Docker stack sets.

## Ollama setup

```bash
ollama serve
ollama pull qwen3.5:9b
make provider-check
```

`qwen3.5:9b` is the balanced local default for machines with roughly 16 GB or more of available unified/system memory. Change `MATCHCRAFT_MODEL` if another installed model is a better fit. Model quality and structured-output reliability vary. The UI verifies that the configured model is actually installed and clearly reports when AI features are unavailable; deterministic scoring still completes.

## Optional remote fallback

The default remote endpoint is OpenAI, but it is not contacted without a server-side key:

```bash
MATCHCRAFT_OPENAI_API_KEY=your-key docker compose up --build
```

The default remote model is `gpt-5.6-sol` with low reasoning effort and strict Structured Outputs. Set `MATCHCRAFT_REMOTE_MODEL` to `gpt-5.6-terra` for a lower-cost balance or configure another compatible endpoint. Keys are never accepted by or returned to the browser. Review the remote provider's data policy before enabling this fallback.

## Docker

With host-installed Ollama running:

```bash
docker compose up --build
```

Open [http://localhost:5173](http://localhost:5173).

The containerized API reaches a host-installed Ollama at `http://host.docker.internal:11434`. This is set inside `docker-compose.yml` and is deliberately **not** read from `.env`, because `.env` is written for host development where Ollama is on `localhost` — inside a container that means the container itself. Point the stack somewhere else with `MATCHCRAFT_OLLAMA_URL_DOCKER`.

To run Ollama as a container instead:

```bash
MATCHCRAFT_OLLAMA_URL_DOCKER=http://ollama:11434 docker compose --profile local-ai up --build
docker compose exec ollama ollama pull qwen3.5:9b
```

Named volumes persist the SQLite database, uploads, exports, and optional model data across `docker compose down`. **`docker compose down --volumes` deletes every saved analysis and uploaded file permanently.**

If a container does not become healthy, `docker compose logs api` shows why — a failed database migration is the most common cause, and the container will restart in a loop until it is resolved. Ports are published on `127.0.0.1` only; the stack is not reachable from other machines.

## Development commands

| Command | Purpose |
|---|---|
| `make install` | Create `.venv`, install backend dev dependencies, run `npm ci` |
| `make migrate` | Apply Alembic migrations |
| `make dev` | Print the two commands needed for a development session |
| `make api` / `make web` | Start development servers |
| `make lint` | Ruff check, Ruff format check, strict mypy, and ESLint |
| `make format` | Apply Ruff and Prettier formatting |
| `make test` | pytest and Vitest |
| `make eval` | Measure analysis quality and fairness against the labeled corpus |
| `make eval-gate` | Fail when an evaluation threshold regresses |
| `make test-api` / `make test-web` | Run one side of the test suite |
| `make test-e2e` | Fast mocked Playwright UI workflow |
| `make test-e2e-full` | Real browser + migrated API + SQLite integration workflow |
| `make build` | Frontend production build |
| `make sample` | Load two synthetic completed analyses |
| `make reset-data` | Interactively delete configured local data |
| `make provider-check` | Check configured model availability without sending documents |
| `make compose` | Build and start the Docker Compose stack |
| `docker compose config --quiet` | Validate Compose configuration |

Full setup, migrations, and extension guidance: [development](docs/development.md).
Reusable review prompts live in [docs/](docs/); the reports they produced are archived under
[docs/internal/](docs/internal/).

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `MATCHCRAFT_ENV` | `development` | Runtime mode; `production` disables interactive API docs |
| `MATCHCRAFT_LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, or `ERROR` |
| `MATCHCRAFT_DATABASE_URL` | derived from data directory | Optional SQLAlchemy database URL |
| `MATCHCRAFT_DATA_DIR` | `~/.local/share/matchcraft` | Database/upload/export directory outside the source tree |
| `MATCHCRAFT_CORS_ORIGINS` | `http://localhost:5173` | Comma-separated allowed origins; `*` is rejected because the API has no authentication |
| `MATCHCRAFT_ALLOWED_HOSTS` | `localhost,127.0.0.1` | Comma-separated `Host` header allow-list that blocks DNS rebinding; set to `*` only behind a trusted gateway |
| `MATCHCRAFT_MAX_UPLOAD_BYTES` | `10485760` | Upload ceiling, maximum 50 MB |
| `MATCHCRAFT_PROVIDER` | `local_first` | `local_first`, `ollama`, `openai_compatible`, or `disabled` |
| `MATCHCRAFT_OLLAMA_URL` | `http://localhost:11434` | Ollama base URL |
| `MATCHCRAFT_OPENAI_BASE_URL` | `https://api.openai.com/v1` | Remote fallback or compatible endpoint URL |
| `MATCHCRAFT_OPENAI_API_KEY` | unset | Optional remote key; environment-only and never returned by the API |
| `MATCHCRAFT_MODEL` | `qwen3.5:9b` | Local Ollama model name |
| `MATCHCRAFT_REMOTE_MODEL` | `gpt-5.6-sol` | Remote fallback model name |
| `MATCHCRAFT_OPENAI_REASONING_EFFORT` | `low` | OpenAI reasoning effort: `none`, `low`, `medium`, or `high` |
| `MATCHCRAFT_OLLAMA_CONTEXT_TOKENS` | `32768` | Bounded local context window; raise only for unusually long inputs and sufficient memory |
| `MATCHCRAFT_MODEL_TEMPERATURE` | `0` | Local/generic-provider temperature, 0–1 |
| `MATCHCRAFT_MODEL_MAX_TOKENS` | `3000` | Response token ceiling |
| `MATCHCRAFT_MODEL_TIMEOUT_SECONDS` | `180` | Per-request provider timeout |
| `MATCHCRAFT_MODEL_RETRIES` | `1` | Structured-output validation retries, maximum 3 |
| `VITE_API_URL` | `http://localhost:8000/api/v1` | Browser API base URL |

Non-secret model settings can also be changed locally in the Settings page and are stored in SQLite. API keys remain environment-only.

## Scoring summary

| Category | Points |
|---|---:|
| Required skill alignment | 25 |
| Responsibility alignment | 20 |
| Experience evidence quality | 15 |
| Measurable accomplishment quality | 10 |
| Preferred skill alignment | 10 |
| Résumé clarity and structure | 10 |
| Keyword and terminology alignment | 5 |
| Education and certification alignment | 5 |

Concrete contextual evidence receives more credit than an isolated skills-list mention. Repetition does not multiply credit. Preferred gaps have less influence than required gaps. When the parser detects no requirement of a given kind, that category is **not scored** and is excluded from the total, so the score is a percentage of what was actually assessed rather than free credit. See the complete [scoring model](docs/scoring-model.md).

Scoring is measured, not asserted. `make eval` runs a labeled synthetic corpus plus fairness and soundness properties; see the [evaluation harness](eval/README.md).

## Current limitations

- No OCR is bundled; image-only PDFs are detected and require externally produced or pasted text.
- PDF processing is capped at 250 pages and extracted résumé text at 100,000 characters.
- Password-protected PDFs and encrypted DOCX files must be unlocked before upload.
- Résumé and job parsing is heuristic and can miss unconventional formats or ambiguous wording.
- Semantic skill equivalence depends on the optional configured model; deterministic matching uses a maintained alias catalog.
- Years-of-experience and non-catalog qualification matching is conservative term overlap; the application does not infer date arithmetic or credential equivalence.
- Local model output quality varies and every generated suggestion requires human review.
- The application is designed for one trusted local user and has no authentication. Do not expose it directly to the public internet.
- It does not emulate or integrate with a real applicant tracking system and does not provide an “ATS score.”

## Roadmap

The version-one boundary is intentionally narrow. Near-term work should improve parsing fixtures, alias coverage, accessibility validation, and provider interoperability without adding accounts, billing, job scraping, automated applications, recruiter ranking, or autonomous agents.

Synthetic sample data in `sample_data/` is legally redistributable and does not describe real people.

## Contributing and license

Read [CONTRIBUTING.md](CONTRIBUTING.md), the [Code of Conduct](CODE_OF_CONDUCT.md), and responsible-AI requirements before proposing changes. MatchCraft is released under the [MIT License](LICENSE).

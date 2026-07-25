# Troubleshooting

## Ollama is unavailable

Run `ollama serve`, then `ollama list` and `make provider-check`. Confirm that `MATCHCRAFT_MODEL` exactly matches an installed tag (the default is `qwen3.5:9b`). Inside Docker, the default URL is `http://host.docker.internal:11434`; the optional Compose service uses `http://ollama:11434`.

Provider failure does not block deterministic analysis. The UI should say AI is unavailable while still showing scores and evidence.

## Remote fallback is not configured

This is the safe default. With `MATCHCRAFT_PROVIDER=local_first`, the OpenAI endpoint is not contacted unless `MATCHCRAFT_OPENAI_API_KEY` is present in the API environment. Set it before starting the API or Compose stack, then verify Settings shows “API key: configured on the server.” For a non-OpenAI compatible endpoint that does not require a key, set `MATCHCRAFT_OPENAI_BASE_URL` explicitly.

## Unsupported or corrupt documents

Only PDF and DOCX are accepted. Renaming another file does not make it valid because MatchCraft checks the PDF signature or DOCX archive structure. Re-export the document from a trusted editor, reduce it below the configured limit, or paste the text.

## Image-only or incomplete extraction

MatchCraft does not bundle OCR. An image-only PDF produces a warning and cannot be confirmed while blank. Use trusted OCR software locally, paste the result, and carefully verify names, dates, numbers, column order, and bullets.

Complex tables, sidebars, and multi-column layouts can extract out of order. Correct the editable text before confirmation.

## Malformed model output

Try a model with reliable structured JSON support, lower temperature, or raise retries within the limit of three. Invalid evidence or fabricated metrics/skills are intentionally rejected. The deterministic report remains available; do not copy raw provider output around validation.

## Provider timeout

Check model startup time and machine resources, then adjust `MATCHCRAFT_MODEL_TIMEOUT_SECONDS` or the Settings page up to 300 seconds. A timeout is logged by error code, without prompt content.
If Ollama allocates excessive memory, confirm `MATCHCRAFT_OLLAMA_CONTEXT_TOKENS` is near the 32K default rather than the model's maximum context. Increase it only when a reviewed input genuinely exceeds that window and the host has sufficient memory.

## Port conflicts

Vite defaults to 5173, FastAPI to 8000, and Ollama to 11434. Stop the conflicting process or pass another development port. If the browser port changes, update `MATCHCRAFT_CORS_ORIGINS`.

## CORS errors

Set `MATCHCRAFT_CORS_ORIGINS` to the exact browser origin, including scheme and port. Multiple values are comma-separated. Avoid `*`; credentials are intentionally disabled.

## Docker volumes and permissions

Inspect `docker compose logs api` and `docker volume ls`. The API runs as a non-root user and expects `/data` to be writable. If replacing the named volume with a bind mount, grant that container user write access. To remove all Docker data intentionally: `docker compose down -v` (this is destructive).

## Migration failures

Back up the configured data directory, inspect `alembic current` and `alembic history`, then run `make migrate`. Do not delete the database to conceal an incompatible migration. A new local setup can be checked with a temporary data/database path.

## Frontend build issues

Use Node.js 22+, remove only `apps/web/node_modules` when dependency state is corrupt, run `npm ci`, then `npm run lint`, `npm test -- --run`, and `npm run build`. Do not delete `package-lock.json` to fix a reproducibility problem.

## Database unavailable

Confirm the parent directory in `MATCHCRAFT_DATABASE_URL` exists and is writable, and the SQLite file is not on an unreliable network filesystem. `/api/v1/health` reports database status separately from provider status.

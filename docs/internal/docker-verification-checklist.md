# Docker verification — run this on your Mac

Docker was not available in the environment where this was prepared, so the container
stack is verified by inspection and by tests that assert the compose file's effective
environment. **It has not been executed.** This checklist is the one remaining gap
between "verified" and "verified end to end", and it takes about five minutes.

Run every step from the repository root. Stop at the first failure and read the note.

## 1. Build and start

```bash
cp .env.example .env          # safe: the container ignores host-only values
docker compose up --build
```

Expect: images build, `matchcraft-api-1` reaches `healthy`, then `matchcraft-web-1`
starts. First build pulls three base images and installs dependencies — a few minutes.

**If the API never becomes healthy**, the stack stops with
`dependency failed to start: container matchcraft-api-1 is unhealthy`. The cause is
almost always a failed migration:

```bash
docker compose logs api
```

## 2. Both services answer

```bash
curl -s http://127.0.0.1:8000/api/v1/health/live          # {"status":"healthy","version":"0.2.0"}
curl -s http://127.0.0.1:8000/api/v1/health | python3 -m json.tool
curl -sI http://127.0.0.1:5173/ | head -1                 # HTTP/1.1 200 OK
```

`/health` should report `deterministic_analysis: "available"`. With Ollama running on
your Mac it should also show `ai_features: "available"` and `active_provider: "ollama"`.
If Ollama is running but AI shows unavailable, that is the `.env` interpolation trap —
it is fixed, but confirm with `docker compose exec api printenv MATCHCRAFT_OLLAMA_URL`,
which must print `http://host.docker.internal:11434`.

## 3. The security posture holds in the container

```bash
curl -s -o /dev/null -w '%{http_code}\n' -H 'Host: evil.example.com' \
  http://127.0.0.1:8000/api/v1/health        # 400 — host allow-list
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8000/docs   # 404 — prod
curl -sI http://127.0.0.1:8000/api/v1/health | grep -i x-content-type  # nosniff
```

From another machine on your network, `http://<your-mac-ip>:5173` must **refuse**
— ports are published on loopback only.

## 4. The application actually works

Open <http://localhost:5173> and complete one full journey:

1. New analysis → paste a résumé → review the extracted text → confirm.
2. Paste a job description → parse → check Required/Preferred/Context look sensible.
3. Run the analysis. Every score category should carry a reason; categories with no
   detected requirement should read "Not scored".
4. Download the Markdown and JSON exports — they must download, not navigate away.
5. Rename the analysis in History, reopen it, then delete it.

## 5. Data survives a restart, and the destroy path is real

```bash
docker compose down && docker compose up -d
# the analysis you kept should still be in History
```

```bash
docker compose down --volumes    # deletes every analysis and upload, permanently
```

## 6. Optional: Ollama as a container

```bash
MATCHCRAFT_OLLAMA_URL_DOCKER=http://ollama:11434 \
  docker compose --profile local-ai up --build -d
docker compose exec ollama ollama pull qwen3.5:9b
```

Then re-check `/api/v1/health` for `active_provider: "ollama"`.

## What to report back

If any step fails, the useful details are: the step number, `docker compose logs api`
output, and `docker compose ps`. The application version is in
`GET /api/v1/health/live`.

## Known-unverified specifics

These were reasoned about but not executed, and are the most likely places for a
surprise:

- **Healthcheck timing.** `--start-period=20s` assumes migrations finish quickly on a
  cold volume. If the API is slow to first-start on your machine, raise it in
  `apps/api/Dockerfile`.
- **`host.docker.internal`.** Standard on Docker Desktop for Mac. The compose file also
  declares a `host-gateway` mapping for Linux.
- **nginx runtime DNS.** `resolver 127.0.0.11` is Docker's embedded DNS. Verify by
  running `docker compose restart api` and confirming the UI still works without
  restarting `web` — this is the failure the resolver directive exists to prevent.
- **Base image digests.** All three were confirmed to include `linux/arm64` by querying
  the registry, so Apple Silicon should not hit a platform mismatch.

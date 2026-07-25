# Security and privacy

## Threat model

Version one assumes one trusted user on a private workstation. It protects against accidental path traversal, malformed uploads, secret logging, unsafe browser rendering, and unintended provider transmission. It does not provide authentication, authorization, tenant isolation, malware scanning, sandboxed document rendering, or public-internet hardening.

Do not bind MatchCraft to an untrusted network or expose it through a public reverse proxy. Anyone who can reach the local API can read and delete analyses.

## File validation

- Only `.pdf` and `.docx` uploads are accepted.
- Upload bytes are limited before parsing; the default maximum is 10 MB and the hard configuration maximum is 50 MB.
- PDFs must start with the PDF signature.
- DOCX files must be valid ZIP archives containing `[Content_Types].xml` and `word/document.xml`.
- DOCX archives have entry-count, member-size, total expanded-size, encryption, and compression-ratio limits before extraction.
- Duplicate DOCX entries are rejected, and XML document-type/entity declarations are rejected in every `.xml`/`.rels` archive member, not only `word/document.xml`, because python-docx also parses styles, numbering, and relationship parts.
- An upload whose declared `Content-Length` exceeds the limit is rejected before the multipart body is buffered to disk.
- Password-protected PDFs and encrypted DOCX archive entries are rejected before extraction.
- PDFs are limited to 250 pages and extracted résumé text to 100,000 characters.
- The original name is reduced to a display-only basename with control characters removed.
- Storage filenames are random UUID values plus a validated extension.
- Resolved upload/delete paths must have the configured upload directory as their immediate parent.
- Corrupt and image-only documents return explicit failures or warnings.

Document parsers are complex dependencies. Keep PyMuPDF and python-docx updated, and do not treat file validation as malware scanning.

## Storage and deletion

The data directory contains `matchcraft.db`, `uploads/`, and `exports/`. The data directory, `uploads/`, and `exports/` are created and re-applied at `0700`; uploads are created directly at `0600` rather than being widened then narrowed; and the SQLite database plus its `-wal`/`-shm` companions are set to `0600` at startup, because SQLite otherwise creates them world-readable and they hold the résumé and job text.

Staged-deletion residue (`.matchcraft-delete-*`) left behind by an interrupted delete is reclaimed on the next startup. SQLite foreign keys and ORM cascades remove analysis scores, evidence, recommendations, questions, and provider runs.

When an analysis is deleted, its résumé/job source records and uploaded file are also deleted if no other analysis references them. The current UI creates unique sources per analysis. Shared sources created directly through the API remain until their final analysis is deleted, preventing data loss in remaining analyses. Matching persisted export files are removed; current exports are streamed and are controlled by the browser after download.

Files are atomically renamed to a private staged name before the database deletion commits. A
database commit failure restores them; a successful commit finalizes removal. Cleanup failures are
counted in logs without exposing filenames or paths.

Deleting a browser download is the user's responsibility. Filesystems, backups, snapshots, and SSD wear-leveling may retain recoverable data beyond application deletion.

## Provider transmission

The default chain tries Ollama first. An analysis request sends the confirmed résumé text and job-description text to a model only when the user enables AI-assisted insights. A bullet rewrite also sends those texts plus the selected exact bullet. Availability checks send no document text.

In `local_first` mode, remote fallback occurs only after local unavailability or rejected local output, and only when the remote provider is configured. The default OpenAI URL is treated as unconfigured without `MATCHCRAFT_OPENAI_API_KEY`. With `openai_compatible`, or with an active fallback, data leaves the machine for the configured URL. Review that provider's privacy, retention, and security policy. API keys are environment variables; the safe settings endpoint and exports never return them. Official OpenAI requests set `store: false`; this is not a substitute for reviewing the provider's retention controls.

Provider URLs are settable at runtime through the Settings page. Two constraints bound what that
can reach:

- The `Authorization` header carrying `MATCHCRAFT_OPENAI_API_KEY` is attached only when the scheme, host, and port of the request target match the environment-configured `MATCHCRAFT_OPENAI_BASE_URL`. A runtime override sends no credential.
- Provider URLs must be HTTP(S) base URLs with no credentials, query, or fragment, and cannot target the best-known cloud instance-metadata hostnames or any link-local, multicast, or reserved address literal. This is not an exhaustive SSRF defense: a private RFC1918 address is still permitted, because a self-hosted LAN model server is a legitimate configuration.

Redirects are not followed, and every provider request is timeout-bounded. Bullet rewrites require
a confirmed résumé, so unreviewed extracted text is never transmitted.

## Browser and API

- CORS permits only configured origins and does not enable credentials. `MATCHCRAFT_CORS_ORIGINS=*` is rejected at startup: with no authentication, a wildcard origin alone would let any website read every stored analysis.
- `MATCHCRAFT_ALLOWED_HOSTS` restricts the accepted `Host` header (default `localhost,127.0.0.1,testserver,api,web`). Without it, a page that rebinds a name it controls to `127.0.0.1` is same-origin and bypasses CORS entirely. Set it to `*` only when a trusted gateway already validates the host. Two known consequences: browsing the API by LAN IP or IPv6 literal is refused unless you add that host, and Starlette matches the header with the port split off at the first colon, so an IPv6 literal can never match.
- Compose publishes the API, web, and optional Ollama ports on `127.0.0.1` only.
- Accepted methods and headers are explicitly limited.
- React escapes all supplied text; the application does not render arbitrary HTML or model Markdown. A top-level error boundary keeps a render failure from blanking the page.
- The container web server sets content-type, referrer, framing, and content-security headers. Because the API is also published on its own port, API responses independently set `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, and `Cache-Control: no-store`.
- Interactive API documentation (`/docs`, `/redoc`, `/openapi.json`) is disabled when `MATCHCRAFT_ENV=production`; the Swagger page loads assets from a third-party CDN.
- API validation errors use a structured envelope and avoid reflecting secrets.

## Logging

Structured events cover startup, request IDs, extraction/analysis status, durations, export actions, deletion, and provider errors. Normal logs must not include complete résumés, job descriptions, prompts, responses, keys, or storage paths. New logs require a privacy review.

## Operational guidance

- Keep the data directory readable only by the local user.
- Use environment files outside version control and rotate exposed credentials.
- Keep dependencies patched. The CI `dependency-audit` job runs `pip-audit` and `npm audit --audit-level=high` as advisory checks; review their annotations rather than assuming a green build means no advisories.
- Back up only if you intend to retain sensitive résumé data; encrypt backups.
- If public deployment is ever required, add authentication, TLS, rate limiting, a hardened database/storage layer, CSRF analysis, malware scanning, audit controls, and a new threat model first.

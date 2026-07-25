# Changelog

All notable project changes will be documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and versions follow semantic versioning.

## [Unreleased]

## [0.2.0] - 2026-07-24

### Added — evaluation

- A labeled synthetic corpus of 16 résumé/job pairs across eight role families with 178 labeled requirements, plus metamorphic fairness and soundness properties, a metrics harness, and `make eval` / `make eval-gate`. CI runs the gate with zero tolerance for a fairness or soundness violation. See [eval/README.md](eval/README.md) and [docs/internal/evaluation-findings-2026-07-24.md](docs/internal/evaluation-findings-2026-07-24.md).
- A performance budget test asserting both an absolute ceiling and sub-quadratic growth in requirement count, locking in the fix for the previously quadratic analysis path.

### Changed — scoring

Measured with the new harness; every change below is accompanied by the number that justified it.

- **Employment-date formatting is no longer scored.** It lowered the score on 13 of 16 corpus cases purely because a career break adds a differently formatted date range. It remains a recommendation.
- **Résumé word count is no longer scored.** The hard 200–1,400 band was a step function that made irrelevant padding raise the score by up to 3.6 points and adding a genuine role lower it. It remains a recommendation.
- **Categories with no detected requirement are now excluded rather than awarded full credit.** The overall score is a percentage of what was actually assessed. Previously an executive assistant scored 56/100 against an HVAC technician role, 35 points of it free credit; that case now scores 31.8.
- **Non-catalog matching was recalibrated** from a 0.55 to a 0.30 supported-overlap threshold, raising evidence classification accuracy from 0.576 to 0.767. A further move to 0.779 was declined because it doubles over-crediting, which is the worse error for this product.
- **Term comparison now collapses common inflections** (`scheduling`/`scheduled`, `providers`/`provider`) and ignores ten scaffolding words that appeared in nearly every requirement. Technical tokens such as `node.js` are exempt from the inflection rule.
- **Experience evidence quality reads a fixed-size sample of the strongest bullets**, padded with the baseline, making the category provably non-decreasing as evidence is added.
- **Keyword alignment compares the complete résumé vocabulary** instead of a top-100 slice, which had let a padded résumé evict its own genuine terms.

Fairness violations went from 20 of 68 to 0 of 79; soundness violations from 28 of 64 to 0 of 64.

### Security

- The remote API key is now bound to the environment-configured endpoint host. A provider URL changed at runtime through the Settings page can no longer receive it.
- Provider URLs targeting the best-known cloud instance-metadata hostnames, or any link-local, multicast, or reserved address literal, are rejected in both environment and runtime configuration. Private LAN addresses remain allowed because a self-hosted model server is a supported setup.
- Added a configurable `Host` allow-list (`MATCHCRAFT_ALLOWED_HOSTS`) so an unauthenticated local API cannot be reached through DNS rebinding, and Compose now publishes ports on the loopback interface only.
- The data directory and SQLite database (including `-wal`/`-shm`) are created and kept at owner-only permissions; uploads are created at `0600` instead of being widened then narrowed.
- `MATCHCRAFT_CORS_ORIGINS=*` is rejected, interactive API documentation is disabled when `MATCHCRAFT_ENV=production`, and API responses carry `X-Content-Type-Options`, `Referrer-Policy`, and `Cache-Control`.
- DOCX document-type and entity declarations are now screened across every XML part, not only `word/document.xml`.
- Oversized uploads are rejected from the declared `Content-Length` before the body is buffered to disk.
- Bullet rewrites now require a confirmed résumé, closing the one path that could send unreviewed text to a provider.
- Staged-deletion residue left by an interrupted delete is reclaimed at startup.

### Fixed

- Term comparison no longer treats trailing sentence punctuation as part of a term, which previously flipped requirement matches and moved the overall score by more than twenty points.
- Job-description headings are matched by pattern, so `Qualifications:`, `What you'll need:`, `Basic Qualifications:`, and `Must-have qualifications:` classify their requirements instead of demoting them to context.
- A heading line is no longer stored as an unmatchable requirement, and a repeated heading no longer demotes everything after it.
- Skill evidence excerpts are exact substrings of the reviewed résumé text; interior whitespace is normalized for matching only.
- `Present`, `present`, `Current`, and `Now` are recognized as open-ended date markers rather than month names.
- Model recommendations whose title begins with an imperative verb are no longer discarded as fabricated entities.
- Deterministic analysis derives skill evidence, repeated phrases, and job terms once per run instead of once per requirement.
- Markdown export includes the transferable-experience section that the UI and JSON export already contained.
- Not-applicable coverage categories now state that full credit is not evidence of alignment.
- SQLite runs in WAL mode with an explicit busy timeout, so brief write contention waits instead of returning HTTP 500.

### Fixed — web

- Added a top-level error boundary; a render-time throw no longer leaves a blank page.
- Exports download through a blob instead of a cross-origin link, which browsers treated as a navigation.
- Reopening a second analysis with `?run=1` starts it; rerunning invalidates the saved-analyses list.
- Transport failures, status-only failures, and non-JSON 2xx responses map to actionable messages; 4xx responses are no longer retried.
- The Settings form no longer discards unsaved edits when settings data is refetched.
- Accessibility: the decorative chart is hidden from assistive technology, the mobile drawer is a real dialog with focus management and Escape, deletion announces and restores focus, résumé-source toggles use `aria-pressed` instead of a non-functional tab pattern, validation errors are linked with `aria-describedby`, the file drop zone shows a focus indicator, `prefers-reduced-motion` is honoured, and field-border and required-badge contrast meet WCAG 2.2 AA.

### Changed

- The cascade-delete transaction shared by the analysis, résumé, and job routes moved into `services/deletion.py`. The three copies had drifted in staging order and only one had a rollback test; all three are now covered.
- The anti-fabrication sanitizers and validators moved from `providers/http.py` into `analysis/fabrication.py`, halving the largest module and removing the dependency that made a service import domain rules from a transport adapter. The old names remain importable from `providers.http` for one release.
- `ProviderError` moved to `core/errors.py`, and provider health probing moved into `services/model_analysis.py`. The backend import graph is now strictly layered and acyclic.

### Added

- A true local-first provider chain with validated remote fallback.
- Separate local and remote model settings so switching providers cannot reuse an invalid model name.
- Provider-specific health reporting and safe OpenAI Responses API Structured Outputs.
- Defaults of `qwen3.5:9b` locally and `gpt-5.6-sol` remotely; the remote fallback remains inactive without a server-side key.
- Initial FastAPI/React local-first application.
- PDF, DOCX, and pasted-text résumé ingestion with extraction review.
- Deterministic requirement parsing, evidence matching, and eight-category alignment scoring.
- Ollama and optional OpenAI-compatible provider abstraction with Pydantic validation.
- Per-bullet diagnostics, fact-preserving rewrite suggestions, and evidence-led interview preparation.
- Local history, rename, cascade deletion, and Markdown/JSON exports.
- Docker Compose, GitHub Actions, sample data, and complete engineering documentation.
- A real full-stack Playwright journey using a freshly migrated temporary SQLite database.
- Reproducible Python dependency constraints for local, CI, and container installs.

### Fixed

- Source edits now invalidate stale scores, excerpts, model output, and exports until rerun.
- Failed reruns roll back partial output replacement, and failed deletions restore staged files.
- Model adapters are revalidated at the service boundary; bullet rewrites cannot drop known facts.
- PDF/DOCX processing now rejects excessive pages/text, duplicate archive members, and XML entities.
- The initial Alembic migration now contains a frozen schema instead of importing live models.
- Write-only duplicate résumé section, experience, bullet, and per-analysis-data storage was removed.

## [0.1.0] - 2026-07-18

### Added

- First development release of MatchCraft.

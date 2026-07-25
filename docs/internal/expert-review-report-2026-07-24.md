# Expert Review Report — 2026-07-24

Produced by running [docs/expert-review-prompt.md](expert-review-prompt.md) against the working
tree. Four read-only expert passes (security/privacy, correctness, frontend/accessibility,
architecture/maintainability) ran in parallel; findings were reconciled centrally, fixed, and then
re-reviewed by a fifth fresh-eyes pass that found real defects **in the fixes themselves**, which
were corrected before this report.

## Gate results

| Gate | Before | After |
|---|---|---|
| `ruff check` + `ruff format --check` | pass | pass (57 files) |
| `mypy app` (strict) | pass, 37 files | pass, 37 files |
| Backend pytest | **116 passed** | **186 passed** |
| Backend coverage | 91% (unenforced) | 91.49% (now enforced at 85% in CI) |
| Frontend eslint `--max-warnings=0` | pass | pass |
| `tsc -b` | pass | pass |
| Vitest | **13 passed** | **20 passed** |
| `vite build` | pass | pass |
| Playwright `test:e2e` (mocked) | pass | pass |
| Playwright `test:e2e:full-stack` (real browser + API + SQLite) | pass | pass |
| Alembic `upgrade head` + `check` | pass | pass |

Both Playwright suites were executed in a real Chromium build. The full-stack journey confirms in a
browser what unit tests could only assert in jsdom: the blob-based export download, the evidence
excerpt being an exact substring of the reviewed résumé, the `Host` allow-list not breaking the
harness, and focus restoration after the delete dialog closes.

**Not run in this environment:** Docker Compose was validated by YAML parse only; the CI job that
starts the stack has not been exercised on a real Docker daemon.

## Findings fixed

### Critical

**Remote API key could be redirected to an arbitrary host.** The `Authorization` header was
attached based on the provider *name*, while the remote base URL is settable at runtime through the
Settings page. Any caller who could reach the unauthenticated local API could repoint the endpoint
and receive both the résumé text and `MATCHCRAFT_OPENAI_API_KEY`. The credential is now bound to
the environment-configured origin, with the default port normalized so a legitimate
`https://host:443` configuration does not silently lose authentication.
`providers/http.py`, `core/config.py`.

**Trailing sentence punctuation split terms and moved the score by 21.6 points.** `dashboards` and
`dashboards.` were different tokens, so a requirement written as a sentence failed to match. On the
sample fixture this alone moved Responsibility alignment from 2.8/20 to 8.2/20. Interior separators
(`node.js`, `asp.net`, `co-ordinate`, `c++`) are preserved. `analysis/text.py`.

### High

- **Realistic job headings were unrecognized**, demoting every requirement beneath them to
  unscored context — a 25-point swing from heading wording alone. Headings are now matched by
  pattern with best-match coverage scoring, so `Qualifications:`, `What you'll need:`,
  `Duties and Responsibilities`, `Skills and Qualifications`, and 30 other realistic forms
  classify correctly, while a sentence that merely mentions the word does not.
- **A heading was stored as an unmatchable requirement**, permanently zeroing Responsibility
  alignment. Label lines are now skipped — but only when they carry no requirement signal, so
  `5+ years of experience in the following:` is still kept.
- **Model recommendations were silently discarded.** The anti-fabrication sanitizer flagged every
  sentence-initial capital as a fabricated entity, so any recommendation titled with an imperative
  verb ("Add detail to the Docker work") was dropped whole. ALL-CAPS acronyms are still checked.
- **The SQLite database holding all résumé PII was world-readable.** Now `0600` (with `-wal`/`-shm`),
  applied from the connection event so it takes effect on the first run, not the second.
- **No `Host` validation on an unauthenticated API.** DNS rebinding made an attacker's page
  same-origin, bypassing CORS entirely. Added a configurable allow-list; Compose now publishes on
  loopback only.
- **Deterministic analysis was O(requirements × résumé).** Skill evidence, repeated phrases, and job
  terms are derived once per run; a 300-requirement job against a large résumé previously did not
  finish in 45 seconds and blocked the event loop.
- **No error boundary in the SPA.** Any render-time throw left a blank page with no recovery.
- **Exports navigated away from the app.** Browsers ignore `download` on a cross-origin href, so in
  the default split-port setup clicking Markdown lost all application state. Exports now fetch a
  blob, and a failed export reports why instead of doing nothing.

### Medium

Upload size rejected in middleware before the multipart body is spooled (verified: 0 bytes
buffered); DOCX entity screening extended to every XML part; `CORS_ORIGINS=*` rejected;
interactive docs disabled in production; security headers on API responses; provider URLs blocked
from metadata/link-local targets; bullet rewrite requires a confirmed résumé; staged-deletion
residue swept at startup; SQLite in WAL mode with a busy timeout; Markdown export gained the
transferable-experience section the UI and JSON export already had; `Present`/`Current`/`Now`
recognized as open-ended date markers; not-applicable score categories now say so.

Frontend: reopening a second analysis with `?run=1` now starts it and no longer shows the previous
analysis's result; rerun invalidates the saved-analyses list; transport failures, status-only
failures, and non-JSON 2xx responses map to actionable messages; 4xx responses are no longer
retried; the Settings form no longer discards unsaved edits on refetch.

Accessibility (WCAG 2.2 AA): the Recharts surface is hidden from assistive technology (its data is
already text below it); the mobile drawer is a real dialog with focus management, Escape, and an
inert background; deletion announces and restores focus; the résumé-source control uses
`aria-pressed` instead of a non-functional tab pattern; validation errors are linked with
`aria-describedby`; the file drop zone shows a focus indicator; `prefers-reduced-motion` is
honoured; field-border (1.4.11) and required-badge (1.4.3) contrast were raised above threshold;
`<main>` is focusable so the skip link works in Safari.

### Repository health

CI now enforces a coverage floor, keys the pip cache on `constraints.lock`, adds job timeouts and a
concurrency group, runs advisory `pip-audit`/`npm audit`, and **starts** the Compose stack rather
than only building it. The pre-commit Ruff pin was aligned with the lock file. The duplicated
`Unreleased` sections in the changelog were merged.

## Follow-up refactors (completed after the initial pass)

Both recommended refactors were carried out, reviewed by a fresh pass, and corrected.

**`services/deletion.py`.** The cascade-delete transaction was duplicated across three routes with
drifted staging order and only one rollback test. It now lives in one reviewed place with an
explicit ordering contract, and all three entry points are covered by a parameterized rollback test.

The review of this refactor found a **regression I had introduced**: the staged-file list was built
inside the staging callback, so a failure *part-way through staging* — an unreadable export path,
a permission error between two uploads — discarded the files already renamed. The database rolled
back but the upload was unrecoverable, and the startup sweep then deleted it. The list is now owned
by the transaction and passed into the staging step, and `stage_export_deletions` appends to the
caller's list as it goes. Two regression tests cover it, both **mutation-verified**: reintroducing
either defect fails them (6 and 1 failures respectively), restoring the fix passes them.

**`analysis/fabrication.py`.** The anti-fabrication vocabularies, sanitizers, and validators moved
out of the transport adapter, halving `providers/http.py` from 859 to 380 lines. `ProviderError`
moved to `core/errors.py`, provider health probing moved into `services/model_analysis.py`, and
`app/providers/__init__.py` no longer re-exports the factory. The backend import graph is now
strictly layered and acyclic — `main → api → services → analysis/providers → core/schemas` — with
zero upward edges. The old names remain importable from `providers.http` for one release.

## Deliberately not fixed

- **Not-applicable coverage categories still award full credit** (up to 60 points). This is a
  deliberate product decision — never penalize a candidate for a requirement the parser did not
  see — so it was documented explicitly rather than changed. The heading fixes greatly reduce how
  often it is reached.
- **Nested provider retry loops** can in principle multiply calls; the outer loop appears
  unreachable because the sanitizers repair everything the validator would reject. Left alone
  rather than changing retry semantics on an unproven path.
- **`react-router` GHSA-qwww-vcr4-c8h2** is in range but unreachable: the app uses declarative mode
  only, with no data router, no `loader`/`action`, and no RSC. The other six advisories are
  devDependencies. Upgrade for hygiene.

## Known limitations of this pass

- Docker Compose was validated by YAML parse only. The new CI step that starts the stack and curls
  both services has not run against a real Docker daemon.
- `MATCHCRAFT_ALLOWED_HOSTS` rejects LAN-IP and IPv6-literal browsing by default. This is
  intentional for a single-user local application and is documented; add the host explicitly if you
  browse that way.
- The five compatibility re-exports in `providers/http.py` are unused by anything in the repo and
  should be deleted on the next release.
- `services/model_analysis.py` sits at 76% coverage, the lowest module in the codebase.

## Recommended next action

Run `docker compose up` locally to confirm the new CI smoke step, then delete the
`providers/http.py` compatibility re-exports.

# MatchCraft Multi-Expert Review Prompt

A reusable prompt for a deep improvement pass on a **green** revision. It complements the
[release verification prompt](release-verification-prompt.md), which asks *"is this safe to
ship?"*. This one asks *"what is wrong that the tests do not catch?"* — the defects that live in
passing code.

Run the release gate first. If it fails, fix that; a review of a broken tree wastes the review.

## How to use it

1. Establish a green baseline and record the exact numbers. A finding is only meaningful against a
   known-good starting point.
2. Run the four expert passes **in parallel, read-only**. Each is a separate reviewer with a
   separate lens; none of them edits the repository.
3. Reconcile the findings centrally, then apply fixes in one place. Parallel editors conflict;
   parallel readers do not.
4. Write a regression test named after each defect before or alongside its fix.
5. Re-run the whole gate and read the diff as if someone else wrote it.

## Prompt

```text
Act as four independent principal-level reviewers examining MatchCraft, a local-first FastAPI +
React résumé-to-role analysis application. The suite is green. Your job is to find what green does
not prove.

GROUND RULES
1. Executed proof beats reading. Write throwaway probes outside the repository, run them, and
   report real values. Label anything you could not reproduce "unverified — static only".
2. Documentation, comments, test names, and UI copy are claims to falsify, not evidence.
3. Report severity by user impact, not by how interesting the bug is. A 20-point scoring swing
   from a trailing period outranks an elegant architectural objection.
4. Every finding needs an exact file:line, a concrete scenario, and a minimal fix. State plainly
   whether the fix changes user-visible behavior.
5. Finish with a "verified correct" list. Preventing a wrong fix is worth as much as proposing a
   right one.
6. Use only synthetic data. Never print résumé text, job text, prompts, model responses, or keys.
7. Do not edit files during the review passes.

PASS 1 — SECURITY AND PRIVACY
Upload handling: MIME/extension trust, whether the size ceiling is enforced before the body is
buffered, decompression ratio and entity-expansion defenses across every archive part, temp-file
cleanup on error paths. Path safety: every place a user-controlled id, filename, or export name
reaches a filesystem path. Provider URLs: scheme validation, credentials in URL, redirect
following, timeouts, and specifically whether a runtime-settable endpoint can redirect a
server-held credential or reach an internal address. Secrets: prove the API key cannot appear in
any response, schema, log, or export. Logs: search every emission site for document text, prompts,
responses, headers, and absolute paths. Network posture: CORS parsing, Host validation, bind
addresses, security headers, docs exposure in production. Deletion: completeness across database,
uploads, and exports, and atomicity when the commit fails. Dependencies and containers: pinning,
user, and advisories — assess real exploitability in this codebase rather than restating the
advisory.

PASS 2 — CORRECTNESS
Scoring: do the weights total exactly 100, are all category scores provably bounded for
adversarial input, is there any division by zero or rounding that escapes the range, and does the
documented model match the constants? Evidence integrity: is every excerpt an exact substring of
the stored reviewed text, and can a missing requirement ever carry evidence? Anti-gaming: verify
numerically that repetition does not multiply credit and that contextual evidence outscores a bare
list mention. Parsing: bullet glyphs, heading variants, odd casing, CRLF, tabs, non-breaking
spaces, smart quotes, single-line input, and catastrophic backtracking. State invalidation: find
any path that lets a stale score survive an edit or lets analysis run on unreviewed text. Provider
fallback: escaping exceptions, retry multiplication, unapplied timeouts, accepted invalid output,
partial results overwriting a good deterministic result. Determinism: identical stored input twice,
across hash seeds. Exports: completeness and truthfulness against what the UI shows.

PASS 3 — FRONTEND AND ACCESSIBILITY
Accessibility against WCAG 2.2 AA, citing the success criterion number for each finding: heading
order and landmarks; label association, aria-invalid, and error announcement; focus order, focus
visibility, and focus management after route changes, async completion, and destructive actions;
live regions for loading, error, and success; computed contrast ratios for every foreground and
background pair actually used, reported numerically; whether charts expose data to assistive
technology or trap a screen reader in an unnamed widget; reduced motion, zoom, and reflow; whether
dialogs are real dialogs. Frontend correctness: effect dependency and stale-closure bugs, cache
invalidation after mutations, derived state that discards user input, error mapping for transport
failures and non-JSON responses, retry behavior on 4xx, request cancellation, cross-origin
download behavior, the presence of an error boundary, and drift between the TypeScript types and
the backend Pydantic schemas.

PASS 4 — ARCHITECTURE AND MAINTAINABILITY
Falsify every documented environment variable, default, limit, command, and behavioral guarantee
against the code, reporting claim → reality → which is wrong. Identify the specific untested
behaviors most likely to regress, and which UI routes have zero coverage. Determine what a bad pull
request could slip past CI: coverage floors, dependency auditing, action pinning, cache keys,
whether containers are started or only built, and whether the pre-commit hooks match the CI checks.
Map the real import graph and name each layering violation, each module doing too much with the
specific extraction to perform, and each piece of duplicated transactional logic. Close with the
five highest-leverage improvements ranked by impact ÷ effort, each with its concrete first step.

RECONCILIATION AND REPAIR
Merge the four findings lists, resolve disagreements by re-running the probe, and order the work by
user impact. Apply only fixes that are safe: root-cause, narrow, and free of scope creep. For each
fix, add a regression test whose name states the defect it prevents. When a fix changes a scored
output, verify the new number is explainable before updating any fixture — a fixture updated
without explanation hides the next bug. Re-run lint, type checks, both test suites, and the build,
then read the complete diff as a reviewer who did not write it.

REPORT
- What was verified green before and after, with exact counts
- Findings by severity, each with file:line, proof, fix, and behavior impact
- Fixes applied, with the regression test that covers each
- Findings deliberately not fixed, and why
- Anything the pass could not verify in this environment
```

## Environment notes

- A macOS `.venv` and `node_modules` will not run on Linux. Build a throwaway environment rather
  than reinstalling in place, which breaks the developer's working tree.
- Run the backend suite with an isolated `MATCHCRAFT_DATA_DIR` for every pass.
- Reviewers work read-only. Anything they write belongs in a scratch directory outside the
  repository.

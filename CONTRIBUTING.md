# Contributing to MatchCraft

Thank you for helping build a private, evidence-grounded tool. Read `docs/responsible-ai.md`, `docs/security.md`, and `docs/scoring-model.md` before changing analysis behavior.

## Branches

Use a short branch name such as `feature/pdf-warning`, `fix/evidence-cascade`, `docs/ollama-linux`, or `test/provider-timeout`. Keep each branch focused on one coherent change.

## Development workflow

1. Create `.env` from `.env.example` and run `make install && make migrate`.
2. Add a failing test for behavioral changes.
3. Implement the smallest maintainable change.
4. Run `make lint`, `make test`, `make build`, relevant Playwright tests, and `docker compose config --quiet`.
5. Update user, architecture, security, scoring, or responsible-AI documentation when behavior changes.

Do not commit `.env`, databases, provider keys, real résumés, private job postings, full prompts, model transcripts, or generated local exports.

## Test expectations

- Backend rules need isolated pytest fixtures and no live provider dependency.
- Provider changes need available, unavailable, timeout, malformed JSON, and unsupported-evidence cases.
- Frontend workflows need Testing Library coverage for loading, success, empty, and error states.
- High-value workflow changes need both a focused mocked Playwright journey and the isolated
  full-stack journey when they cross the API/persistence boundary.
- Schema changes need reviewed Alembic migrations and clean-upgrade verification.

Tests must use synthetic data. Never anonymize a real résumé and assume it is safe enough.

## Scoring changes

A scoring pull request must:

- explain the user problem and mathematical effect;
- retain visible category explanations and evidence;
- keep weights explicit, nonnegative, and totaling 100;
- show required/preferred effects separately;
- demonstrate that repetition does not reward keyword stuffing;
- add regression fixtures and an example calculation;
- update `docs/scoring-model.md` and the README summary;
- state how rerunning older saved analyses will differ.

Model output must not silently change deterministic formulas.

## Documentation

Documentation is part of the feature. Commands must have been run successfully before being documented as working. Document configuration defaults, provider transmission, failure behavior, and limitations. Avoid screenshots unless they represent the current product.

## Pull-request standards

Keep modules typed and focused. Avoid broad exception swallowing, duplicated frontend scoring logic, secret logging, arbitrary HTML rendering, unrelated dependencies, fake controls, and incomplete core states. Complete the pull-request template with exact verification commands and outcomes. Respond to review with code or evidence rather than only discussion.

By contributing, you agree that your contribution is licensed under the MIT License and follows the Code of Conduct.

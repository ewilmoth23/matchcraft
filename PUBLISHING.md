# Publishing to GitHub

The repository has one commit on `main` and nothing generated or private is tracked.
Verified before committing: no `.env`, no credentials, no absolute local paths, no
build output, no macOS duplicate files, and every email address on a reserved
`example.test` / `.test` domain.

## 1. Create the repository

Create an **empty** repository on GitHub — no README, no `.gitignore`, no license, since
this repository already has all three.

```bash
git remote add origin https://github.com/<you>/matchcraft.git
git push -u origin main
```

If you use SSH, substitute `git@github.com:<you>/matchcraft.git`.

## 2. Fix the CI badge

`README.md` has a placeholder owner:

```
https://github.com/OWNER/matchcraft/actions/workflows/ci.yml
```

Replace `OWNER` with your GitHub username in both badge lines.

## 3. Turn on the settings the repository assumes

- **Security → Private vulnerability reporting: enable.** `SECURITY.md` tells reporters
  to use it; without it that instruction is a dead end.
- **Dependabot alerts and security updates: enable.** `.github/dependabot.yml` is
  already configured for pip, npm, GitHub Actions, and Docker.
- **Actions:** CI runs on push to `main` and on pull requests. The first run takes a
  while because it installs Playwright browsers and builds Docker images.
- **Branch protection on `main`** (optional but sensible): require the `backend`,
  `frontend`, `integration`, and `compose` checks to pass.

## 4. Tag the release

```bash
git tag -a v0.2.0 -m "MatchCraft 0.2.0"
git push origin v0.2.0
```

Then create a GitHub Release from the tag and paste the `## [0.2.0]` section of
`CHANGELOG.md` as the notes.

## 5. Repository description and topics

Suggested description:

> Private, evidence-first résumé-to-role analysis. Runs locally, shows how every point
> of its score is earned, and fails CI if the score responds to a candidate's identity.

Suggested topics: `resume`, `job-search`, `fastapi`, `react`, `local-first`,
`responsible-ai`, `evaluation`, `fairness`, `self-hosted`, `ollama`.

## What a visitor sees first

The README leads with what the tool does and what it explicitly does **not** claim. The
two things worth pointing at in any announcement are:

- `make eval` — the scoring is measured against a labeled corpus rather than asserted,
  with fairness properties enforced in CI at zero tolerance.
- `docs/security.md` and `docs/responsible-ai.md` — both describe real implemented
  behaviour and state their own limits.

## Before you announce it

Run `docs/internal/docker-verification-checklist.md`. The container stack is the one part
of the project that has not been executed end to end, and it is the path most people will
try first.

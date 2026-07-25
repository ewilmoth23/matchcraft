# Security Policy

## Supported versions

MatchCraft is developed on `main`. Security fixes land there and in the most recent
release. Older releases are not patched.

| Version | Supported |
|---|---|
| 0.2.x | Yes |
| < 0.2 | No |

## Reporting a vulnerability

**Please do not open a public issue for a security problem.**

Report privately through GitHub's
[private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)
on this repository: **Security → Report a vulnerability**. That channel is monitored and
keeps the report confidential until a fix is available.

Please include:

- what an attacker can do, in one sentence;
- the affected version (`GET /api/v1/health` reports it) and how MatchCraft was run — local development, Docker Compose, or something else;
- reproduction steps, ideally with synthetic documents only;
- any log output, **with résumé and job-description text removed**.

You should get an acknowledgement within a few days. Please give a reasonable window for
a fix before public disclosure.

## Threat model

MatchCraft assumes **one trusted user on a private workstation**. It is not built to be
exposed to a network, and it has no authentication or authorization: anyone who can reach
the API can read and delete every stored analysis.

In scope, and treated as vulnerabilities:

- Reaching the API from another origin or host — CORS bypass, DNS rebinding, an
  unintended bind address.
- Path traversal, or any write outside the configured data directory.
- Making the server send the résumé, the job description, or the API key anywhere the
  user did not configure — including a redirected provider URL or an SSRF target.
- Leaking résumé text, job text, prompts, model responses, API keys, or filesystem paths
  into logs, error responses, or exports.
- Crashing or hanging the application with a crafted PDF or DOCX — decompression bombs,
  entity expansion, resource exhaustion.
- Model output that escapes the fabrication validators and is persisted as evidence.

Out of scope, because they are known and documented properties rather than defects:

- No authentication. This is stated in [docs/security.md](docs/security.md) and the
  README. Deploying MatchCraft on a shared or public network is outside the supported
  configuration.
- Denial of service against your own single-user instance.
- Anything requiring an attacker to already have local filesystem access — at that point
  they can read the SQLite database directly.
- Vulnerabilities in Ollama or a remote provider you configure. Report those upstream.

## Handling data in a report

Do not attach a real résumé or a copied private job posting. Reproduce with synthetic
documents; `sample_data/` and `eval/corpus/` contain examples you can adapt.

## Related documentation

- [docs/security.md](docs/security.md) — the implemented controls, in detail.
- [docs/responsible-ai.md](docs/responsible-ai.md) — fabrication boundaries and the
  fairness properties enforced in CI.

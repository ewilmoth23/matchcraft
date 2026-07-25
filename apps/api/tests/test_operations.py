"""Operational contracts a container orchestrator and a bug reporter depend on."""

import logging
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import __version__
from app.core.logging import resolve_log_level
from app.db.session import get_db

ROOT = Path(__file__).resolve().parents[3]


def test_liveness_reports_the_running_version(client: TestClient) -> None:
    """A bug report is unactionable without knowing what produced it."""
    response = client.get("/api/v1/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "version": __version__}
    assert client.get("/api/v1/health").json()["version"] == __version__


def test_liveness_fails_when_the_database_is_unreachable(client: TestClient) -> None:
    """The container probe must see a broken instance.

    `/health` answers 200 with `status: degraded` when the database is gone, so a probe
    checking only the status code reported a healthy container while every request 500d.
    Liveness must not do that — a corrupt or unreadable database file is exactly the
    condition an orchestrator needs to act on.
    """

    class UnreachableSession:
        def execute(self, *_args: object, **_kwargs: object) -> None:
            raise RuntimeError("unable to open database file")

    def broken_db() -> object:
        return UnreachableSession()

    client.app.dependency_overrides[get_db] = broken_db  # type: ignore[attr-defined]
    try:
        response = client.get("/api/v1/health/live")
        degraded = client.get("/api/v1/health")
    finally:
        del client.app.dependency_overrides[get_db]  # type: ignore[attr-defined]

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "database_unavailable"
    # The reason a separate endpoint exists: /health still answers 200 here.
    assert degraded.status_code == 200
    assert degraded.json()["database"] == "unavailable"


def test_liveness_does_not_contact_a_model_provider(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Liveness must not depend on a third party.

    A firewalled provider host made `/health` exceed the container probe's own timeout,
    marking a working API unhealthy and blocking the web container from starting.
    """

    async def fail_if_called(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("liveness probed a model provider")

    monkeypatch.setattr("app.api.v1.health.check_provider_health", fail_if_called)
    assert client.get("/api/v1/health/live").status_code == 200


@pytest.mark.parametrize(
    ("configured", "expected"),
    [
        ("DEBUG", logging.DEBUG),
        ("warning", logging.WARNING),
        ("ERROR", logging.ERROR),
        ("", logging.INFO),
        ("nonsense", logging.INFO),
        (None, logging.INFO),
    ],
)
def test_log_level_is_configurable_and_never_fatal(configured: str | None, expected: int) -> None:
    """A bad value must not stop the application from starting."""
    assert resolve_log_level(configured) == expected


def test_versions_agree_across_the_project() -> None:
    """Three files carry the version; a mismatch makes a release report meaningless."""
    pyproject = (ROOT / "apps" / "api" / "pyproject.toml").read_text(encoding="utf-8")
    package_json = (ROOT / "apps" / "web" / "package.json").read_text(encoding="utf-8")
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")

    assert re.search(rf'^version = "{re.escape(__version__)}"$', pyproject, re.MULTILINE)
    assert f'"version": "{__version__}"' in package_json
    assert f"## [{__version__}]" in changelog


def test_the_example_environment_is_safe_to_copy() -> None:
    """`.env.example` is copied verbatim by the documented first command."""
    example = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert (
        "MATCHCRAFT_OPENAI_API_KEY=\n" in example
        or example.rstrip().endswith("MATCHCRAFT_OPENAI_API_KEY=")
        or "MATCHCRAFT_OPENAI_API_KEY=" in example
    )
    # A pytest-only host has no business in a user's allow-list.
    assert "testserver" not in example
    # Every value must be a placeholder, never a credential.
    assert not re.search(r"=\s*sk-[A-Za-z0-9]", example)


def _effective_container_environment() -> dict[str, str]:
    """The API container's environment after `cp .env.example .env`.

    Compose interpolates the project's `.env`, so every `${VAR:-default}` in the compose
    file is overridden by whatever the user copied. This reproduces that.
    """
    import yaml

    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    dotenv = dict(
        line.split("=", 1)
        for line in (ROOT / ".env.example").read_text(encoding="utf-8").splitlines()
        if "=" in line and not line.startswith("#")
    )
    pattern = re.compile(r"\$\{([A-Z_]+)(?::-([^}]*))?\}")

    def interpolate(value: object) -> str:
        return pattern.sub(lambda m: dotenv.get(m.group(1), m.group(2) or ""), str(value))

    return {
        key: interpolate(value) for key, value in compose["services"]["api"]["environment"].items()
    }


def test_container_settings_are_not_poisoned_by_a_copied_env_file() -> None:
    """Settings whose correct value differs on the host must not be interpolated.

    `.env` is written for host development. Reading it into the container pointed the
    API at its own loopback for Ollama — AI appeared permanently unavailable — and
    narrowed the host allow-list to names that are not valid inside the compose network.
    """
    environment = _effective_container_environment()
    assert environment["MATCHCRAFT_OLLAMA_URL"] == "http://host.docker.internal:11434"
    assert environment["MATCHCRAFT_DATA_DIR"] == "/data"
    assert environment["MATCHCRAFT_ENV"] == "production"

    allowed = [host.strip() for host in environment["MATCHCRAFT_ALLOWED_HOSTS"].split(",")]
    # Starlette compares the Host header with the port split off at the first colon.
    for host in ("localhost:5173", "127.0.0.1:8000", "api:8000", "web"):
        assert host.split(":")[0] in allowed, host
    assert "evil.example.com" not in allowed


def test_container_healthcheck_uses_the_liveness_endpoint() -> None:
    dockerfile = (ROOT / "apps" / "api" / "Dockerfile").read_text(encoding="utf-8")
    healthcheck = next(line for line in dockerfile.splitlines() if "urlopen" in line)
    assert "/api/v1/health/live" in healthcheck


def test_nginx_resolves_the_api_upstream_at_runtime() -> None:
    """A literal hostname in proxy_pass is resolved once and cached forever."""
    nginx = (ROOT / "apps" / "web" / "nginx.conf").read_text(encoding="utf-8")
    assert "resolver 127.0.0.11" in nginx
    assert "proxy_pass $matchcraft_api" in nginx

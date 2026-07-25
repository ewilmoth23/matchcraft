import re
from pathlib import Path

ROOT = Path(__file__).parents[3]


def test_every_readme_make_command_has_a_real_target() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    documented = set(re.findall(r"\bmake\s+([a-z][a-z0-9-]*)", readme))
    targets = set(re.findall(r"^([a-z][a-z0-9-]*):", makefile, re.MULTILINE))

    assert documented
    assert documented <= targets


def test_readme_configuration_names_exist_in_example_environment() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    example = (ROOT / ".env.example").read_text(encoding="utf-8")
    documented = set(
        re.findall(r"^\| `(MATCHCRAFT_[A-Z0-9_]+|VITE_API_URL)`", readme, re.MULTILINE)
    )
    configured = set(re.findall(r"^([A-Z][A-Z0-9_]+)=", example, re.MULTILINE))

    assert documented == configured

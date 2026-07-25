#!/usr/bin/env python3
import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.core.config import get_settings  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Delete MatchCraft's configured local data directory."
    )
    parser.add_argument("--yes", action="store_true", help="Skip the interactive confirmation.")
    args = parser.parse_args()
    settings = get_settings()
    target = settings.data_dir.resolve()
    if target in {target.parent, target.anchor} or len(target.parts) < 3:
        raise SystemExit(f"Refusing unsafe data directory: {target}")
    if not args.yes:
        answer = input(f"Permanently delete MatchCraft data at {target}? Type 'delete': ")
        if answer != "delete":
            raise SystemExit("Reset cancelled.")
    if target.exists():
        shutil.rmtree(target)
    settings.ensure_directories()
    print(f"Reset MatchCraft data at {target}")


if __name__ == "__main__":
    main()

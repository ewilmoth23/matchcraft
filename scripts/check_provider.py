#!/usr/bin/env python3
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.core.config import get_settings  # noqa: E402
from app.providers.factory import get_provider  # noqa: E402


async def check() -> int:
    settings = get_settings()
    provider = get_provider(settings)
    available = await provider.available()
    print(
        f"provider={provider.name} model={provider.model} status={'available' if available else 'unavailable'}"
    )
    return 0 if available or settings.provider == "disabled" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(check()))

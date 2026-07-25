import logging
import os
import sys

import structlog

# Read directly from the environment rather than through Settings: logging is configured
# at import time, before the settings object exists, and a bad value here must never
# prevent the application from starting.
_DEFAULT_LEVEL = "INFO"


def resolve_log_level(raw: str | None = None) -> int:
    """Map MATCHCRAFT_LOG_LEVEL to a logging level, falling back to INFO.

    A user asked to reproduce a bug needs DEBUG; a user annoyed by a JSON line per
    request needs WARNING. Neither should have to edit code.
    """
    name = (raw if raw is not None else os.getenv("MATCHCRAFT_LOG_LEVEL", _DEFAULT_LEVEL)).strip()
    level = logging.getLevelNamesMapping().get(name.upper())
    return level if isinstance(level, int) else logging.INFO


def configure_logging() -> None:
    level = resolve_log_level()
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.stdlib.add_log_level,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        cache_logger_on_first_use=True,
    )

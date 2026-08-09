"""Central logging setup. Import and call setup_logging() instead of each module
calling logging.basicConfig (which previously ran in ~23 modules with no shared
format). Idempotent and env-tunable via LOG_LEVEL."""
import logging
import os

_CONFIGURED = False

def setup_logging(level: str | int | None = None) -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    if level is None:
        level = os.environ.get("LOG_LEVEL", "INFO")
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )
    _CONFIGURED = True

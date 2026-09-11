"""Small local JSON logger for Week 1 boundary diagnostics."""

from __future__ import annotations

import json
import logging
from typing import Any


LOGGER = logging.getLogger("mira")
LOGGER.setLevel(logging.INFO)
if not LOGGER.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(message)s"))
    LOGGER.addHandler(_handler)
    LOGGER.propagate = False


def log_event(event: str, **fields: Any) -> None:
    """Emit JSON to the configured application logger; never include secrets."""
    payload = {"event": event, **fields}
    LOGGER.info(json.dumps(payload, ensure_ascii=False, default=str))

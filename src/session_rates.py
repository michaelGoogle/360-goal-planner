"""Session economic rates, resolved session value → parameter version → built-in.

The rates live in the config service (``config/parameters/v24.json``), which is the
same set the assumption box shows, so publishing a new parameter version changes
what a session with no explicit rate calculates with.

``DEFAULTS`` is the built-in copy, reached only if the config store is unreadable, so
a missing volume mount degrades to the V0-24 numbers instead of a 500. It must equal
the active version; ``tests/test_config_service.py`` fails if the two ever drift.
"""

from __future__ import annotations

import logging
from typing import Any

from src.services.config import service as config_service

logger = logging.getLogger(__name__)

RATE_NAMES = (
    "inflationRate",
    "interestRate",
    "incomeGrowthRate",
    "investmentReturn",
    "assetReturn",
    "loanRate",
)

DEFAULTS = {
    "inflationRate": 0.023,
    "interestRate": 0.012,
    "incomeGrowthRate": 0.028,
    "investmentReturn": 0.042,
    "assetReturn": 0.03,
    "loanRate": 0.035,
}


def defaults(version: str = "") -> dict[str, float]:
    """The rate defaults from a parameter version, or the built-in copy."""
    try:
        params = config_service.values(version)
    except Exception as exc:
        logger.warning("Config unavailable, using built-in rate defaults: %s", exc)
        return dict(DEFAULTS)
    return {name: float(params.get(name, DEFAULTS[name])) for name in RATE_NAMES}


def session_rate(session: dict[str, Any], key: str) -> float:
    val = session.get(key)
    if val is None:
        return defaults(str(session.get("parametersVersion") or ""))[key]
    return float(val)

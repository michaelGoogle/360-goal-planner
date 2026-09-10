"""Session economic rates. Same defaults as the GP assumption box."""

from __future__ import annotations

from typing import Any

DEFAULTS = {
    "inflationRate": 0.023,
    "interestRate": 0.012,
    "incomeGrowthRate": 0.028,
    "investmentReturn": 0.042,
    "assetReturn": 0.03,
}


def session_rate(session: dict[str, Any], key: str) -> float:
    val = session.get(key)
    if val is None:
        return DEFAULTS[key]
    return float(val)

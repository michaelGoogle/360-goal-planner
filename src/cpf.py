"""Employee CPF on ordinary wages. Session income is monthly gross (incl. bonus)."""

from __future__ import annotations

import math
from typing import Any

# CPF ordinary wage ceiling from 1 Jan 2026 (CPF Board / IRAS).
# Employee contribution is 20% of wage up to this cap (age ≤ 55), so max S$1,600.
# The older S$1,200 figure was 20% of the pre-2023 S$6,000 ceiling.
OW_CEILING = 8000.0


def employee_cpf_rate(age: int, residency: str | None) -> float:
    """Employee CPF as a share of ordinary wage. Foreigners contribute 0."""
    key = (residency or "").strip().lower()
    if key == "foreigner":
        return 0.0
    if age <= 55:
        return 0.20
    if age <= 60:
        return 0.15
    if age <= 65:
        return 0.095
    return 0.05


def employee_cpf_monthly(gross: float, age: int, residency: str | None) -> float:
    """Own CPF only, rounded down to the dollar. Not the employer share."""
    rate = employee_cpf_rate(age, residency)
    if gross <= 0 or rate <= 0:
        return 0.0
    return float(math.floor(min(gross, OW_CEILING) * rate))


def take_home_income(gross: float, age: int, residency: str | None) -> float:
    """Gross less own CPF. Tax is not deducted."""
    if gross <= 0:
        return 0.0
    return round(max(0.0, gross - employee_cpf_monthly(gross, age, residency)), 2)


def spend_share(dependents: int) -> float:
    """0 dependants → 67.5% of take-home; +5pp each; cap 90%."""
    deps = max(0, int(dependents or 0))
    return min(0.675 + 0.05 * deps, 0.90)


def expenses_from_take_home(take_home: float, dependents: int) -> float:
    if take_home <= 0:
        return 0.0
    return round(take_home * spend_share(dependents), 2)


def expenses_from_gross(
    gross: float,
    dependents: int,
    age: int,
    residency: str | None,
) -> float:
    return expenses_from_take_home(take_home_income(gross, age, residency), dependents)


def session_employee_cpf(session: dict[str, Any]) -> float:
    return employee_cpf_monthly(
        float(session.get("incomeMonthly") or 0),
        int(session.get("age") or 40),
        session.get("residency"),
    )


def session_take_home(session: dict[str, Any]) -> float:
    return take_home_income(
        float(session.get("incomeMonthly") or 0),
        int(session.get("age") or 40),
        session.get("residency"),
    )

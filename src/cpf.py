"""Employee social-security contributions. Session income is monthly gross (incl. bonus).

The rules moved to the social-security service in WP4, where they are a country plug-in
rather than "CPF for everyone". This module stays as the shape callers already use, and
gains a ``country`` argument: without one the answer would be Singapore's CPF applied to
a household in Hanoi.

``spend_share`` and the expense helpers are People Like You's, not social security's, and
move in WP5.
"""

from __future__ import annotations

from typing import Any

from src.money import round_half_up
from src.services.social_security.models import ContributionRequest
from src.services.social_security.service import OW_CEILING  # noqa: F401  (re-exported)

DEFAULT_COUNTRY = "Singapore"


def _response(gross: float, age: int, residency: str | None, country: str | None):
    # Imported here, not at module scope: the registry builds every client, and the
    # People Like You client reaches back into this module.
    from src.services.registry import get_social_security_client

    return get_social_security_client().contribution(
        ContributionRequest(
            country=(country or DEFAULT_COUNTRY),
            residency=residency or "",
            age=age,
            grossMonthly=max(0.0, float(gross or 0)),
        )
    )


def employee_cpf_rate(
    age: int,
    residency: str | None,
    country: str | None = DEFAULT_COUNTRY,
) -> float:
    """Employee contribution as a share of ordinary wage."""
    return _response(1.0, age, residency, country).rate


def employee_cpf_monthly(
    gross: float,
    age: int,
    residency: str | None,
    country: str | None = DEFAULT_COUNTRY,
) -> float:
    """Own contribution only, rounded down to the dollar. Not the employer share."""
    return _response(gross, age, residency, country).employeeContribution


def take_home_income(
    gross: float,
    age: int,
    residency: str | None,
    country: str | None = DEFAULT_COUNTRY,
) -> float:
    """Gross less own contribution. Tax is not deducted."""
    if gross <= 0:
        return 0.0
    return _response(gross, age, residency, country).takeHome


def spend_share(dependents: int) -> float:
    """0 dependants → 67.5% of take-home; +5pp each; cap 90%."""
    deps = max(0, int(dependents or 0))
    return min(0.675 + 0.05 * deps, 0.90)


def expenses_from_take_home(take_home: float, dependents: int) -> float:
    if take_home <= 0:
        return 0.0
    # Halves up, as the workbook's ROUND does. Python's half-to-even put two of the
    # fifty personas a cent low, which the assets estimate then multiplied by 216.
    return round_half_up(take_home * spend_share(dependents), 2)


def expenses_from_gross(
    gross: float,
    dependents: int,
    age: int,
    residency: str | None,
    country: str | None = DEFAULT_COUNTRY,
) -> float:
    return expenses_from_take_home(take_home_income(gross, age, residency, country), dependents)


def session_employee_cpf(session: dict[str, Any]) -> float:
    return employee_cpf_monthly(
        float(session.get("incomeMonthly") or 0),
        int(session.get("age") or 40),
        session.get("residency"),
        session.get("country"),
    )


def session_take_home(session: dict[str, Any]) -> float:
    return take_home_income(
        float(session.get("incomeMonthly") or 0),
        int(session.get("age") or 40),
        session.get("residency"),
        session.get("country"),
    )

"""Social security modules (decision D8).

One box, so People Like You, HappiU and the Scenario Visualizer stop each deducting
CPF in their own engine. The module is chosen by country; a country without one takes
nothing off, which is the model's default rather than a gap.

``Calculations.md`` calls this a black box: "The rates, the wage ceiling, and the age
bands stay inside it and run in the user currency." So the numbers below are the
module's own, not admin parameters — the Assumptions tab deliberately has no CPF cell.
"""

from __future__ import annotations

import math
from typing import Protocol

from src.services.social_security.models import ContributionRequest, ContributionResponse

# CPF ordinary wage ceiling from 1 Jan 2026 (CPF Board / IRAS). The older S$1,200 cap
# people quote was 20% of the pre-2023 S$6,000 ceiling.
OW_CEILING = 8000.0

# Employee share of ordinary wage by upper age bound. Read in order.
CPF_AGE_BANDS: tuple[tuple[int, float], ...] = (
    (55, 0.20),
    (60, 0.18),
    (65, 0.125),
    (70, 0.075),
)
CPF_RATE_ABOVE_BANDS = 0.05

# Residency values that pay nothing. Anything else is treated as contributing, because
# an unrecognised residency string must not silently exempt someone.
NON_CONTRIBUTING = frozenset({"foreigner", "foreign", "non-resident", "work pass"})


class SocialSecurityModule(Protocol):
    name: str

    def contribution(self, req: ContributionRequest) -> ContributionResponse: ...


class SgCpfModule:
    """Singapore CPF: employee share only, capped at the ordinary-wage ceiling."""

    name = "SG-CPF"

    def rate(self, age: int, residency: str | None) -> float:
        if _residency_key(residency) in NON_CONTRIBUTING:
            return 0.0
        for upper, rate in CPF_AGE_BANDS:
            if age <= upper:
                return rate
        return CPF_RATE_ABOVE_BANDS

    def contribution(self, req: ContributionRequest) -> ContributionResponse:
        rate = self.rate(req.age, req.residency)
        gross = max(0.0, float(req.grossMonthly))
        if gross <= 0 or rate <= 0:
            return ContributionResponse(
                module=self.name, employeeContribution=0.0, takeHome=gross,
                rate=rate, currency=req.currency,
            )
        # Floored to the dollar, as CPF does, and as the workbook's CPF tab does.
        employee = float(math.floor(min(gross, OW_CEILING) * rate))
        return ContributionResponse(
            module=self.name,
            employeeContribution=employee,
            takeHome=round(max(0.0, gross - employee), 2),
            rate=rate,
            currency=req.currency,
        )


class DefaultModule:
    """No scheme: nothing is taken off, take-home is gross."""

    name = "default"

    def contribution(self, req: ContributionRequest) -> ContributionResponse:
        gross = max(0.0, float(req.grossMonthly))
        return ContributionResponse(
            module=self.name, employeeContribution=0.0, takeHome=gross,
            rate=0.0, currency=req.currency,
        )


# Country to module. A name, an ISO2 and an ISO3 all resolve, because callers get the
# country from a session field that different screens fill in differently.
MODULES: dict[str, SocialSecurityModule] = {
    "singapore": SgCpfModule(),
    "sg": SgCpfModule(),
    "sgp": SgCpfModule(),
}
DEFAULT_MODULE = DefaultModule()


def _residency_key(residency: str | None) -> str:
    return (residency or "").strip().lower()


def module_for(country: str) -> SocialSecurityModule:
    return MODULES.get((country or "").strip().lower(), DEFAULT_MODULE)


def countries_with_a_module() -> list[str]:
    """Countries that have a real scheme, for the config screen and for tests."""
    return sorted({m.name for m in MODULES.values()})


def contribution(req: ContributionRequest) -> ContributionResponse:
    return module_for(req.country).contribution(req)

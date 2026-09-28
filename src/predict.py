"""People Like You / Need Profiler / Need Calculator session mapping.

The People Like You maths moved to ``src/services/people_like_you/service.py`` in WP5,
where the property bands, the life-cover step and the expense floor come from the admin
parameters in USD instead of being SGD constants here.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Any

from src.hu_payload import dob_from_age
from src.needs import CALCULATOR_NEEDS, PROTECTION_NEEDS, need_code
from src.pipeline.need_profiler import select_unified_top
from src.services.config import service as config_service
from src.services.fx.models import FxLock
from src.services.people_like_you import service as plu_service

UNIFIED_TYPES = CALCULATOR_NEEDS
PROTECTION = PROTECTION_NEEDS


def session_fx(session: dict[str, Any]) -> FxLock:
    """The session's locked rate, locking one if it has none.

    A session assembled by an older client arrives without a lock. Treating that as
    "1 USD = 1 unit" would read every USD parameter as if the customer's currency were
    the dollar, so the rate is fetched and written back where the caller can see it.
    """
    locked = session.get("fx")
    if locked:
        return FxLock.model_validate(locked)
    from src.services.registry import get_fx_client

    lock = get_fx_client().lock(
        session.get("currency") or "SGD",
        session.get("country") or "Singapore",
    )
    session["fx"] = lock.model_dump()
    return lock


# The deterministic twin in docs/calculations/build_calculations_workbook.py
# calls the live Need Profiler and calculator (WP15). These helpers stay because the
# workbook still seeds home value and assumed life cover from People Like You.


@lru_cache(maxsize=1)
def _workbook_lock() -> FxLock:
    from src.services.fx.client import SnapshotFxClient

    return SnapshotFxClient().lock("SGD", "Singapore")


def _workbook_params() -> dict[str, Any]:
    return config_service.values("")


def seed_property_value(income_monthly: float) -> int:
    """Assumed home value in SGD, from monthly gross income."""
    return int(plu_service.property_seed(income_monthly, _workbook_lock(), _workbook_params()))


def _round_to_100k(amount: float) -> int:
    """The life-cover step in a Singapore session, which is S$100,000."""
    lock = _workbook_lock()
    return int(plu_service.round_up_to_step(amount, plu_service.life_cover_step(lock, _workbook_params())))


def _assumed_life_policy(session: dict[str, Any]) -> dict[str, Any] | None:
    policy = plu_service.assumed_life_policy(
        property_value=float(session.get("property") or 0),
        mortgage=float(session.get("mortgage") or 0),
        income_monthly=float(session.get("incomeMonthly") or 0),
        dependents=int(session.get("dependents") or 0),
        fx=session_fx(session) if session.get("fx") else _workbook_lock(),
        params=_workbook_params(),
    )
    if policy is None:
        return None
    return {
        "type": "Life Protection",
        "insurer": "Existing insurer",
        "sum": policy.sum,
        "premium": policy.premium,
    }


def __getattr__(name: str) -> Any:
    """The three household shares the twin imports, read from the active parameters."""
    if name in ("CASH_SAVINGS_SHARE", "INVESTMENTS_SHARE", "PROPERTY_LTV"):
        return float(config_service.value(name, ""))
    raise AttributeError(name)


def session_dict(data: dict[str, Any]) -> dict[str, Any]:
    if not data.get("dateOfBirth"):
        data["dateOfBirth"] = dob_from_age(int(data.get("age") or 40))
    return data


def plu_body(session: dict[str, Any], persist: bool) -> dict[str, Any]:
    country = session.get("country") or "Singapore"
    return {
        "dob": session["dateOfBirth"],
        "dateOfBirth": session["dateOfBirth"],
        "occupation": session.get("occupation") or "Professional",
        "country": country,
        "city": session.get("city") or country,
        "dependents": int(session.get("dependents") or 0),
        "gender": session.get("gender"),
        "residency": session.get("residency"),
        "persist": persist,
    }


def _apply_plu(session: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    finance = (result.get("onboarding") or {}).get("data", {}).get("finance") or {}
    mapped = result.get("result") or {}
    income = float(
        finance.get("monthlyIncome") or mapped.get("income") or session.get("incomeMonthly") or 0
    )
    age = int(session.get("age") or 0)
    estimate = plu_service.derive(
        income_monthly=income,
        age=age if age else 40,
        dependents=int(session.get("dependents") or 0),
        residency=session.get("residency"),
        country=session.get("country") or "Singapore",
        currency=session.get("currency") or "SGD",
        owns_property=bool((mapped.get("ownershipInformation") or {}).get("property")),
        reported_life_expectancy=mapped.get("lifeExpectancy"),
        liquid_assets=float(finance.get("liquidAssetValue") or mapped.get("assets") or 0),
        fx=session_fx(session),
        parameters_version=str(session.get("parametersVersion") or ""),
    )
    session["incomeMonthly"] = estimate.incomeMonthly
    session["expenseMonthly"] = estimate.expenseMonthly
    # Age gates the assets estimate, not the seed: a 21-year-old has not saved yet.
    if estimate.cash or estimate.investments:
        session["cash"] = estimate.cash
        session["investments"] = estimate.investments
    session["property"] = estimate.property
    session["mortgage"] = estimate.mortgage
    # The Need Profiler's liabilities factor. Not the mortgage, and not a need row's
    # own liabilities, which is why it is not called "liabilities".
    session["pluLiabilities"] = estimate.liabilities
    life = (
        {
            "type": "Life Protection",
            "insurer": "Existing insurer",
            "sum": estimate.policies[0].sum,
            "premium": estimate.policies[0].premium,
        }
        if estimate.policies
        else None
    )
    others = [p for p in (session.get("policies") or []) if p.get("type") != "Life Protection"]
    session["policies"] = ([life] if life else []) + others
    session["plu"] = mapped
    session["source"] = "people-like-you"
    if mapped.get("lifeExpectancy") and estimate.lifeExpectancy:
        session["lifeExpectancy"] = estimate.lifeExpectancy
    # Do not copy People Like You risk_ability onto the session. Score capacity
    # is calculated in the UI from Your money (frontend/src/lib/riskCapacity.ts).
    return session


def _needs_from_profiler(session: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    onb = (result.get("onboarding") or {}).get("data") or {}
    needs_map = onb.get("needs") or {}
    ranked = (result.get("result") or {}).get("rankedNeeds") or []
    rows = []
    if needs_map:
        for raw_type, row in needs_map.items():
            t = need_code(raw_type)
            rows.append(
                {
                    "type": t,
                    "enabled": bool(row.get("enabled")),
                    "needAmount": float(row.get("needAmount") or 0),
                    "existing": float(row.get("existing") or 0),
                    "gap": float(row.get("gap") or 0),
                    "priority": 5 if (row.get("weightageScore") or 0) > 7 else 3,
                    "weightageScore": row.get("weightageScore"),
                }
            )
    else:
        enable = set(
            select_unified_top(ranked, has_property=float(session.get("property") or 0) > 0)
        )
        for t in UNIFIED_TYPES:
            rows.append({"type": t, "enabled": t in enable, "needAmount": 0, "priority": 3})
    session["needs"] = [r for r in rows if r.get("type") in UNIFIED_TYPES]
    session["needProfiler"] = result.get("result")
    return session


def _apply_calculator(session: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    """Merge calculator rows onto the session, keeping derived fields (have, lifestyle, …)."""
    needs_map = (result.get("onboarding") or {}).get("data", {}).get("needs") or result.get("needs") or {}
    amounts = result.get("amounts") or (result.get("result") or {}).get("amounts") or {}
    existing_by_type = {need_code(n["type"]): n for n in session.get("needs") or []}
    by_code = {need_code(t): row for t, row in needs_map.items()}
    types = list(by_code) if by_code else list(existing_by_type)
    rows = []
    for t in types:
        prev = existing_by_type.get(t) or {}
        row = {**prev, **(by_code.get(t) or {}), "type": t}
        amt = float(row.get("needAmount") or amounts.get(t) or 0)
        existing = float(row.get("existing") or 0)
        have = float(row["have"]) if row.get("have") is not None else existing
        row["needAmount"] = amt
        row["existing"] = existing
        row["have"] = have
        row["gap"] = float(row["gap"]) if row.get("gap") is not None else max(0.0, amt - have)
        row["enabled"] = bool(row.get("enabled", True))
        row["priority"] = row.get("priority") or prev.get("priority") or 3
        if t in PROTECTION:
            row["existingSumAssured"] = existing
            row["existingInvestment"] = None
        else:
            row["existingInvestment"] = existing
            row["existingSumAssured"] = None
        rows.append(row)
    if rows:
        session["needs"] = [r for r in rows if r.get("type") in UNIFIED_TYPES]
    if result.get("ageOfRetirement"):
        session["ageOfRetirement"] = result["ageOfRetirement"]
    session["needCalculator"] = result
    return session

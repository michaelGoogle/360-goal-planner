"""People Like You / Need Profiler / Need Calculator session mapping."""
from __future__ import annotations

from typing import Any

from src.cpf import expenses_from_gross, take_home_income
from src.hu_payload import dob_from_age
from src.pipeline.need_profiler import select_unified_top

UNIFIED_TYPES = ("N_INC", "N_CRI", "N_TPD", "N_RET", "N_EDU", "N_SAV", "N_PRP")
PROTECTION = ("N_INC", "N_CRI", "N_TPD")
PROPERTY_LTV = 0.55
# SV pots: cash/savings vs investments. GP labels these Cash & Savings / Investments.
CASH_SAVINGS_SHARE = 0.15
INVESTMENTS_SHARE = 0.85


def seed_property_value(income_monthly: float) -> int:
    """Assumed home value (SGD) from monthly gross income."""
    if income_monthly < 10_000:
        return 350_000
    if income_monthly <= 20_000:
        return 650_000
    return 850_000


def session_dict(data: dict[str, Any]) -> dict[str, Any]:
    if not data.get("dateOfBirth"):
        data["dateOfBirth"] = dob_from_age(int(data.get("age") or 40))
    return data


def plu_body(session: dict[str, Any], persist: bool) -> dict[str, Any]:
    return {
        "dob": session["dateOfBirth"],
        "dateOfBirth": session["dateOfBirth"],
        "occupation": session.get("occupation") or "Professional",
        "country": "Singapore",
        "city": "Singapore",
        "dependents": int(session.get("dependents") or 0),
        "gender": session.get("gender"),
        "residency": session.get("residency"),
        "persist": persist,
    }


def _round_to_100k(amount: float) -> int:
    """Nearest S$100,000, rounding halves up."""
    if amount <= 0:
        return 0
    return int((amount + 50_000) // 100_000) * 100_000


def _seed_home(session: dict[str, Any], *, own: bool) -> None:
    """Seed a home at 55% LTV whenever People Like You says they own property."""
    if not own:
        session["property"] = 0
        session["mortgage"] = 0
        return
    property_value = seed_property_value(float(session.get("incomeMonthly") or 0))
    session["property"] = property_value
    session["mortgage"] = round(property_value * PROPERTY_LTV)


def _assumed_life_policy(session: dict[str, Any]) -> dict[str, Any] | None:
    """Assume mortgage life cover, or 5× annual income when there is at least one dependant."""
    mortgage_cover = 0
    if float(session.get("property") or 0) > 0:
        mortgage_cover = _round_to_100k(float(session.get("mortgage") or 0))
    dependents_cover = 0
    if int(session.get("dependents") or 0) > 0:
        dependents_cover = int(round(float(session.get("incomeMonthly") or 0) * 12 * 5))
    sum_assured = max(mortgage_cover, dependents_cover)
    if sum_assured <= 0:
        return None
    return {
        "type": "Life Protection",
        "insurer": "Existing insurer",
        "sum": sum_assured,
        "premium": max(0, round(sum_assured * 0.0031)),
    }


def _apply_plu(session: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    finance = (result.get("onboarding") or {}).get("data", {}).get("finance") or {}
    mapped = result.get("result") or {}
    session["incomeMonthly"] = float(
        finance.get("monthlyIncome") or mapped.get("income") or session.get("incomeMonthly") or 0
    )
    deps = int(session.get("dependents") or 0)
    age = int(session.get("age") or 0)
    cpf_age = age if age else 40
    session["expenseMonthly"] = expenses_from_gross(
        session["incomeMonthly"],
        deps,
        cpf_age,
        session.get("residency"),
    )
    take_home = take_home_income(session["incomeMonthly"], cpf_age, session.get("residency"))
    surplus = take_home - session["expenseMonthly"]
    if session["incomeMonthly"] and session["expenseMonthly"] and age > 21:
        assets = max(0.0, surplus * 12 * 0.5 * (age - 21))
        session["cash"] = round(assets * CASH_SAVINGS_SHARE)
        session["investments"] = round(assets * INVESTMENTS_SHARE)
    else:
        assets = float(finance.get("liquidAssetValue") or mapped.get("assets") or 0)
        if assets:
            session["cash"] = round(assets * CASH_SAVINGS_SHARE)
            session["investments"] = round(assets * INVESTMENTS_SHARE)
    own = bool((mapped.get("ownershipInformation") or {}).get("property"))
    _seed_home(session, own=own)
    life = _assumed_life_policy(session)
    others = [p for p in (session.get("policies") or []) if p.get("type") != "Life Protection"]
    session["policies"] = ([life] if life else []) + others
    session["plu"] = mapped
    session["source"] = "people-like-you"
    # Do not copy People Like You risk_ability onto the session. Score capacity
    # is calculated in the UI from Your money (frontend/src/lib/riskCapacity.ts).
    return session


def _needs_from_profiler(session: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    onb = (result.get("onboarding") or {}).get("data") or {}
    needs_map = onb.get("needs") or {}
    ranked = (result.get("result") or {}).get("rankedNeeds") or []
    rows = []
    if needs_map:
        for t, row in needs_map.items():
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
        enable = set(select_unified_top(ranked))
        for t in UNIFIED_TYPES:
            rows.append({"type": t, "enabled": t in enable, "needAmount": 0, "priority": 3})
    session["needs"] = [r for r in rows if r.get("type") in UNIFIED_TYPES]
    session["needProfiler"] = result.get("result")
    return session


def _apply_calculator(session: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    needs_map = (result.get("onboarding") or {}).get("data", {}).get("needs") or result.get("needs") or {}
    amounts = result.get("amounts") or (result.get("result") or {}).get("amounts") or {}
    rows = []
    existing_by_type = {n["type"]: n for n in session.get("needs") or []}
    types = list(needs_map.keys()) if needs_map else list(existing_by_type.keys())
    for t in types:
        row = dict(needs_map.get(t) or existing_by_type.get(t) or {"type": t, "enabled": True})
        amt = float(row.get("needAmount") or amounts.get(t) or 0)
        existing = float(row.get("existing") or 0)
        rows.append(
            {
                "type": t,
                "enabled": bool(row.get("enabled", True)),
                "needAmount": amt,
                "existing": existing,
                "gap": float(row.get("gap") or max(0, amt - existing)),
                "priority": existing_by_type.get(t, {}).get("priority") or 3,
                "weightageScore": row.get("weightageScore") or existing_by_type.get(t, {}).get("weightageScore"),
                "existingSumAssured": existing if t in PROTECTION else None,
                "existingInvestment": existing if t not in PROTECTION else None,
            }
        )
    if rows:
        session["needs"] = [r for r in rows if r.get("type") in UNIFIED_TYPES]
    session["needCalculator"] = result
    return session

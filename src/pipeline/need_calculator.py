"""
Need / gaps calculator — single seam for UNIFIED need amounts, projected have, and gap.

Swap point for a later engine: ``evaluate_session`` is what ``POST /v1/needs``
and ``POST /v1/predict`` call. Does not rank needs.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from src.hu_payload import need_existing
from src.pipeline.goal_math import (
    ACCUMULATION_TYPES,
    CI_COST,
    CI_YEARS,
    EDU_TOTAL_COST,
    HOSP_MONTHS,
    PROTECTION_TYPES,
    RETIREMENT_AGE,
    TPD_COST,
    TPD_YEARS,
    UNIFIED_TYPES,
    age_from_dob,
    fv,
    fv_annuity,
    life_support_years,
    lifestyle_rate,
    pv_annuity,
    pv_annuity_due,
    real_return,
    remaining_gap,
    round_money,
    round_to,
    years_in_retirement,
    years_to_retirement,
)
from src.pipeline.onboarding import UNIFIED_NEED_TYPES, ensure_needs_map
from src.session_rates import session_rate

_ROW_PASSTHROUGH = (
    "priority",
    "weightageScore",
    "existingAnnualPremium",
    "existingMaturityYear",
)


def _session_age(session: dict[str, Any]) -> int:
    age = session.get("age")
    try:
        n = int(age)
    except (TypeError, ValueError):
        n = 0
    if 18 <= n <= 90:
        return n
    dob = (session.get("dateOfBirth") or "").strip()
    return age_from_dob(dob) if dob else 40


def _num(val: Any, default: float = 0.0) -> float:
    try:
        if val is None or val == "":
            return default
        return float(val)
    except (TypeError, ValueError):
        return default


def _int(val: Any, default: int = 0) -> int:
    try:
        if val is None or val == "":
            return default
        return int(val)
    except (TypeError, ValueError):
        return default


def _existing_input(row: dict[str, Any], session: dict[str, Any]) -> float:
    for key in ("existing", "existingInvestment", "existingSumAssured"):
        if key in row and row.get(key) is not None:
            return max(0.0, _num(row.get(key)))
    return max(0.0, need_existing(row, session))


def _fill_defaults(session: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    t = row.get("type") or ""
    income = _num(session.get("incomeMonthly"))
    dependents = _int(session.get("dependents"))
    age = _session_age(session)
    now_year = date.today().year
    lifestyle = _int(row.get("lifestyle"), 0)
    if lifestyle not in (1, 3):
        lifestyle = 2
    ret_age = _int(row.get("retAge") or session.get("ageOfRetirement"), RETIREMENT_AGE)
    if ret_age <= 0:
        ret_age = RETIREMENT_AGE
    target_year = _int(row.get("targetYear") or row.get("fundsNeededYear"), 0)
    if target_year <= 0:
        target_year = now_year + 10
    years_to = max(1, target_year - now_year)
    existing = _existing_input(row, session)
    income_replace = row.get("incomeReplaceMonthly")
    if income_replace is None:
        income_replace = income
    else:
        income_replace = _num(income_replace)
    out = dict(row)
    out["type"] = t
    out["enabled"] = bool(row.get("enabled"))
    out["retAge"] = ret_age
    out["lifestyle"] = lifestyle
    out["retIncomeMonthly"] = round_to(_num(session.get("expenseMonthly")) * lifestyle_rate(lifestyle), 50)
    out["incomeReplaceMonthly"] = income_replace
    support_years = life_support_years(age)
    out["dependYears"] = _int(row.get("dependYears"), support_years)
    if out["dependYears"] <= 0:
        out["dependYears"] = support_years
    out["dependants"] = min(6, _int(row.get("dependants"), dependents))
    out["liabilities"] = _num(row.get("liabilities"), _num(session.get("mortgage")))
    out["bequest"] = max(0.0, _num(row.get("bequest")))
    out["existing"] = existing
    out["targetYear"] = target_year
    out["fundsNeededYear"] = target_year
    out["monthlyContribution"] = max(0.0, _num(row.get("monthlyContribution")))
    yrs_to_ret = years_to_retirement(ret_age, age)
    if t == "N_RET":
        out["contributeYears"] = yrs_to_ret
    else:
        out["contributeYears"] = _int(row.get("contributeYears"), years_to)
        if out["contributeYears"] <= 0:
            out["contributeYears"] = years_to
    out["_age"] = age
    return out


def _need_amount(session: dict[str, Any], filled: dict[str, Any]) -> float:
    t = filled["type"]
    inf = session_rate(session, "inflationRate")
    r = real_return(session_rate(session, "investmentReturn"), inf)
    if t == "N_RET":
        annual = _num(session.get("expenseMonthly")) * 12.0 * lifestyle_rate(filled["lifestyle"])
        t_yrs = years_to_retirement(_int(filled.get("retAge")), _int(filled.get("_age"), _session_age(session)))
        n = years_in_retirement(_int(filled.get("retAge")))
        return round_money(pv_annuity(fv(annual, r, t_yrs), r, n))
    if t == "N_INC":
        # Excel: bequest + liabilities + PV of annual spend over the support years.
        return round_money(
            _num(filled.get("bequest"))
            + _num(filled.get("liabilities"))
            + pv_annuity(_num(session.get("expenseMonthly")) * 12.0, r, _int(filled.get("dependYears")))
        )
    if t == "N_CRI":
        return round_money(
            pv_annuity_due(_num(filled.get("incomeReplaceMonthly")) * 12.0, r, CI_YEARS) + CI_COST
        )
    if t == "N_TPD":
        return round_money(
            pv_annuity_due(_num(filled.get("incomeReplaceMonthly")) * 12.0, r, TPD_YEARS) + TPD_COST
        )
    if t == "N_HOS":
        return round_money(_num(session.get("incomeMonthly")) * HOSP_MONTHS)
    if t == "N_EDU":
        yrs = max(0, _int(filled.get("targetYear")) - date.today().year)
        return round_money(EDU_TOTAL_COST * ((1 + inf) ** yrs))
    stored = _num(filled.get("needAmount"))
    if stored > 0:
        return round_money(stored)
    income = _num(session.get("incomeMonthly")) * 12.0
    if t == "N_SAV":
        return round_money(income)
    if t == "N_PRP":
        return round_money(5 * income)
    return round_money(stored)


def _have(session: dict[str, Any], filled: dict[str, Any]) -> float:
    t = filled["type"]
    existing = _num(filled.get("existing"))
    if t not in ACCUMULATION_TYPES:
        return round_money(existing)
    r = real_return(session_rate(session, "investmentReturn"), session_rate(session, "inflationRate"))
    age = _int(filled.get("_age"), _session_age(session))
    if t == "N_RET":
        yrs = years_to_retirement(_int(filled.get("retAge")), age)
        return round_money(
            fv(existing, r, yrs)
            + fv_annuity(_num(filled.get("monthlyContribution")) * 12.0, r, yrs)
        )
    yrs = max(0, _int(filled.get("targetYear")) - date.today().year)
    grown = fv(existing, r, yrs)
    if t == "N_EDU":
        return round_money(grown)
    return round_money(
        grown
        + fv_annuity(_num(filled.get("monthlyContribution")) * 12.0, r, _int(filled.get("contributeYears")))
    )


def evaluate_need(session: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    """Fill defaults and compute needAmount / have / gap for one UNIFIED row."""
    filled = _fill_defaults(session, row)
    amount = _need_amount(session, filled)
    have = _have(session, filled)
    out: dict[str, Any] = {
        "type": filled["type"],
        "enabled": filled["enabled"],
        "needAmount": amount,
        "have": have,
        "existing": filled["existing"],
        "gap": remaining_gap(amount, have),
        "retAge": filled["retAge"],
        "lifestyle": filled["lifestyle"],
        "retIncomeMonthly": filled["retIncomeMonthly"],
        "incomeReplaceMonthly": filled["incomeReplaceMonthly"],
        "dependYears": filled["dependYears"],
        "dependants": filled["dependants"],
        "liabilities": filled["liabilities"],
        "bequest": filled["bequest"],
        "targetYear": filled["targetYear"],
        "fundsNeededYear": filled["fundsNeededYear"],
        "monthlyContribution": filled["monthlyContribution"],
        "contributeYears": filled["contributeYears"],
    }
    if filled["type"] in PROTECTION_TYPES:
        out["existingSumAssured"] = filled["existing"]
        out["existingInvestment"] = None
    else:
        out["existingInvestment"] = filled["existing"]
        out["existingSumAssured"] = None
    for key in _ROW_PASSTHROUGH:
        if key in filled and filled[key] is not None:
            out[key] = filled[key]
    return out


def evaluate_session(session: dict[str, Any]) -> dict[str, Any]:
    """
    Recompute every UNIFIED need on the GP session.

    Returns a shallow copy with ``needs`` (list of rows) and ``ageOfRetirement``.
    """
    out = dict(session)
    by_type: dict[str, dict[str, Any]] = {}
    for row in out.get("needs") or []:
        t = row.get("type")
        if t:
            by_type[t] = dict(row)
    rows = []
    for t in UNIFIED_TYPES:
        row = by_type.get(t) or {"type": t, "enabled": t in ("N_INC", "N_RET"), "needAmount": 0}
        row["type"] = t
        rows.append(evaluate_need(out, row))
    out["needs"] = rows
    ret = next((r for r in rows if r.get("type") == "N_RET"), None)
    if ret:
        out["ageOfRetirement"] = int(ret.get("retAge") or RETIREMENT_AGE)
    return out


def calculate_gaps_for_onboarding(
    data: dict[str, Any],
    *,
    only_empty: bool = True,
) -> dict[str, Any]:
    """
    Onboarding-map wrapper around ``evaluate_session``.

    ``only_empty`` is ignored: derived types always recompute. Kept so older
    callers (``run_need_calculator``) still work.
    """
    del only_empty
    po = data.get("policyOwner") or {}
    fin = data.get("finance") or {}
    dob = (po.get("dateOfBirth") or "").strip()
    if not dob:
        raise ValueError("dateOfBirth is required to calculate need amounts")

    income = float(fin.get("monthlyIncome") or 0)
    expense = float(fin.get("monthlyExpense") or 0)
    if income <= 0 and expense <= 0:
        raise ValueError("monthlyIncome or monthlyExpense is required")

    needs_map = ensure_needs_map(data)
    session: dict[str, Any] = {
        "dateOfBirth": dob,
        "ageOfRetirement": int(po.get("ageOfRetirement") or RETIREMENT_AGE),
        "incomeMonthly": income,
        "expenseMonthly": expense,
        "cash": float(fin.get("cash") or 0),
        "investments": float(fin.get("investments") or 0),
        "mortgage": float(fin.get("mortgage") or fin.get("totalLiabilities") or 0),
        "dependents": int(po.get("dependents") or 0),
        "policies": list(fin.get("policies") or data.get("policies") or []),
        "inflationRate": data.get("inflationRate"),
        "investmentReturn": data.get("investmentReturn"),
        "needs": [{**dict(row), "type": t} for t, row in needs_map.items()],
    }
    liquid = float(fin.get("liquidAssetValue") or 0)
    if liquid and not session["cash"] and not session["investments"]:
        session["cash"] = liquid
    evaluated = evaluate_session(session)
    updated = {n["type"]: n for n in evaluated["needs"]}
    amounts = {t: float((updated.get(t) or {}).get("needAmount") or 0) for t in UNIFIED_NEED_TYPES}
    calculated_types = [t for t in UNIFIED_NEED_TYPES if (updated.get(t) or {}).get("enabled")]
    return {
        "needs": updated,
        "amounts": amounts,
        "onlyEmpty": False,
        "calculatedTypes": calculated_types,
    }

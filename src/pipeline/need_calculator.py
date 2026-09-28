"""
Need / gaps calculator — session adapter around the USD Need Calculator service.

``evaluate_session`` is what ``POST /v1/needs`` and ``POST /v1/predict`` call. It
converts the session into USD, calls the service, and writes the rounded user-currency
amounts back onto the same rows the UI already knows.
"""

from __future__ import annotations

from typing import Any

from src.hu_payload import apply_investment_pot, need_existing
from src.money import round_half_up, to_usd, to_user
from src.needs import CALCULATOR_NEEDS, PROTECTION_NEEDS
from src.pipeline.goal_math import (
    RETIREMENT_AGE,
    UNIFIED_TYPES,
    age_from_dob,
    income_support_years,
    lifestyle_rate,
    remaining_gap,
    round_to,
    years_to_retirement,
)
from src.pipeline.onboarding import UNIFIED_NEED_TYPES, ensure_needs_map
from src.predict import session_fx
from src.services.config import service as config_service
from src.services.need_calculator import service as calculator
from src.services.need_calculator.models import GoalInputs, NeedCalculatorRequest
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
    lifestyle = _int(row.get("lifestyle"), 0)
    if lifestyle not in (1, 3):
        lifestyle = 2
    ret_age = _int(row.get("retAge") or session.get("ageOfRetirement"), RETIREMENT_AGE)
    if ret_age <= 0:
        ret_age = RETIREMENT_AGE
    target_year = _int(row.get("targetYear") or row.get("fundsNeededYear"), 0)
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
    support_years = income_support_years(age)
    out["dependYears"] = _int(row.get("dependYears"), support_years)
    if out["dependYears"] <= 0:
        out["dependYears"] = support_years
    out["dependants"] = min(6, _int(row.get("dependants"), dependents))
    out["liabilities"] = _num(row.get("liabilities"), _num(session.get("mortgage")))
    out["bequest"] = max(0.0, _num(row.get("bequest")))
    out["existing"] = existing
    if target_year > 0:
        out["targetYear"] = target_year
        out["fundsNeededYear"] = target_year
    out["monthlyContribution"] = max(0.0, _num(row.get("monthlyContribution")))
    yrs_to_ret = years_to_retirement(ret_age, age)
    if t == "N_RET":
        out["contributeYears"] = yrs_to_ret
    out["_age"] = age
    return out


def _goal_inputs(filled: dict[str, Any], fx) -> GoalInputs:
    t = filled["type"]
    tagged = filled["existing"] if t in ("N_RET", "N_EDU", "N_SAV", "N_PRP") else 0.0
    stored = _num(filled.get("needAmount")) if t in ("N_SAV", "N_PRP") else 0.0
    return GoalInputs(
        lifestyle=filled.get("lifestyle"),
        retAge=filled.get("retAge"),
        targetYear=filled.get("targetYear") or None,
        bequestUsd=to_usd(filled.get("bequest") or 0, fx),
        liabilitiesUsd=to_usd(filled.get("liabilities") or 0, fx) if t == "N_INC" else None,
        dependYears=filled.get("dependYears"),
        incomeReplaceMonthlyUsd=to_usd(filled.get("incomeReplaceMonthly") or 0, fx),
        monthlyContributionUsd=to_usd(filled.get("monthlyContribution") or 0, fx),
        storedAmountUsd=to_usd(stored, fx) if stored > 0 else None,
        ltcStartAge=filled.get("ltcStartAge"),
        taggedInvestmentsUsd=to_usd(tagged, fx),
    )


def request_from_session(session: dict[str, Any], rows: list[dict[str, Any]]) -> NeedCalculatorRequest:
    fx = session_fx(session)
    cover = {}
    inputs = {}
    for row in rows:
        t = row["type"]
        inputs[t] = _goal_inputs(row, fx)
        if t in PROTECTION_NEEDS:
            cover[t] = to_usd(row.get("existing") or 0, fx)
    return NeedCalculatorRequest(
        age=_session_age(session),
        ageOfRetirement=_int(session.get("ageOfRetirement"), RETIREMENT_AGE),
        lifeExpectancy=_int(session.get("lifeExpectancy"), 0) or 85,
        incomeMonthlyUsd=to_usd(session.get("incomeMonthly") or 0, fx),
        expenseMonthlyUsd=to_usd(session.get("expenseMonthly") or 0, fx),
        cashUsd=to_usd(session.get("cash") or 0, fx),
        investmentsUsd=to_usd(session.get("investments") or 0, fx),
        mortgageUsd=to_usd(session.get("mortgage") or 0, fx),
        existingCoverUsd=cover,
        enabled={row["type"]: bool(row.get("enabled")) for row in rows},
        inputs=inputs,
        inflationRate=session_rate(session, "inflationRate"),
        investmentReturn=session_rate(session, "investmentReturn"),
        priceLevel=float(fx.priceLevel or 1.0),
        parametersVersion=str(session.get("parametersVersion") or ""),
    )


def _to_user(amount_usd: float, fx) -> float:
    return round_half_up(to_user(amount_usd, fx), 0)


def evaluate_need(session: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    """Fill one row. Prefer ``evaluate_session``; this exists for older callers."""
    session = evaluate_session({**session, "needs": [row]})
    return next(n for n in session["needs"] if n["type"] == row.get("type"))


def evaluate_session(session: dict[str, Any]) -> dict[str, Any]:
    """
    Recompute every calculator need on the GP session.

    Returns a shallow copy with ``needs`` (list of rows), ``ageOfRetirement``,
    ``horizons`` and the R_LON block.
    """
    out = dict(session)
    fx = session_fx(out)
    by_type: dict[str, dict[str, Any]] = {}
    for row in out.get("needs") or []:
        t = row.get("type")
        if t:
            by_type[t] = dict(row)
    rows_in = []
    for t in UNIFIED_TYPES:
        row = by_type.get(t) or {"type": t, "enabled": t in ("N_INC", "N_RET"), "needAmount": 0}
        row["type"] = t
        rows_in.append(_fill_defaults(out, row))
    apply_investment_pot(rows_in, _num(out.get("investments")))

    result = calculator.calculate(request_from_session(out, rows_in))
    by_result = {n.type: n for n in result.needs}
    year = int(config_service.value("currentYear", str(out.get("parametersVersion") or "")))
    horizon_years = {
        "N_RET": result.horizons.yearsToRet,
        "N_EDU": result.horizons.eduYears,
        "N_SAV": result.horizons.savYears,
        "N_PRP": result.horizons.prpYears,
    }

    rows = []
    for filled in rows_in:
        t = filled["type"]
        calc = by_result[t]
        amount = _to_user(calc.needAmountUsd, fx)
        have = _to_user(calc.haveUsd, fx)
        target = year + horizon_years[t] if t in horizon_years else filled.get("targetYear")
        out_row: dict[str, Any] = {
            "type": t,
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
            "targetYear": target,
            "fundsNeededYear": target,
            "monthlyContribution": filled["monthlyContribution"],
            "contributeYears": horizon_years.get(t, filled.get("contributeYears")),
            "needAmountUsd": calc.needAmountUsd,
            "haveUsd": calc.haveUsd,
            "gapUsd": calc.gapUsd,
        }
        if t == "N_LTC":
            out_row["ltcStartAge"] = filled.get("ltcStartAge") or int(
                config_service.value("LTC_START_AGE", str(out.get("parametersVersion") or ""))
            )
            out_row["careYears"] = result.horizons.careYears
        if t in PROTECTION_NEEDS:
            out_row["existingSumAssured"] = filled["existing"]
            out_row["existingInvestment"] = None
        else:
            out_row["existingInvestment"] = filled["existing"]
            out_row["existingSumAssured"] = None
        for key in _ROW_PASSTHROUGH:
            if key in filled and filled[key] is not None:
                out_row[key] = filled[key]
        rows.append(out_row)

    out["needs"] = rows
    out["horizons"] = result.horizons.model_dump()
    lon = result.stress.get("R_LON")
    if lon:
        out["stress"] = {
            "R_LON": {
                "yearsInRetirement": lon.yearsInRetirement,
                "careYears": lon.careYears,
                "needAmount": {k: _to_user(v, fx) for k, v in lon.needAmountUsd.items()},
                "gap": {k: _to_user(v, fx) for k, v in lon.gapUsd.items()},
                "extraNeed": {k: _to_user(v, fx) for k, v in lon.extraNeedUsd.items()},
            }
        }
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

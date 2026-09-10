"""
Local goal / need amount math — Python port of shared/input_model goalMath.ts
(amount + gap core; premium bands optional / unused by onboarding calculator v1).
"""

from __future__ import annotations

from datetime import date
from typing import Any

RETIREMENT_AGE = 65
INC_PROTECTION_MAX_AGE = 85
INC_PROTECTION_MAX_YEARS = 30
RETIREMENT_DURATION_YEARS = 20
DEFAULT_INFLATION_RATE = 0.03

ACCUMULATION_TYPES = frozenset({"N_RET", "N_EDU", "N_SAV", "N_PRP"})
UNIFIED_TYPES = ("N_INC", "N_CRI", "N_TPD", "N_RET", "N_EDU", "N_SAV", "N_PRP")


def age_from_dob(dob: str, as_of: date | None = None) -> int:
    try:
        born = date.fromisoformat(dob[:10])
    except Exception:
        return 40
    today = as_of or date.today()
    age = today.year - born.year
    if (today.month, today.day) < (born.month, born.day):
        age -= 1
    return max(0, age)


def round_money(n: float) -> float:
    return max(0.0, round(n))


def monthly_to_annual(monthly: float) -> float:
    return float(monthly or 0) * 12.0


def pv_annuity(pmt: float, rate: float, periods: int) -> float:
    if periods <= 0 or pmt <= 0:
        return 0.0
    if abs(rate) < 1e-12:
        return pmt * periods
    return (pmt * (1 - (1 + rate) ** (-periods))) / rate


def remaining_gap(need_amount: float, existing_cover: float | None) -> float:
    return max(0.0, float(need_amount or 0) - float(existing_cover or 0))


def compute_need_amounts(
    *,
    date_of_birth: str,
    monthly_income: float,
    monthly_expense: float,
    age_of_retirement: int = RETIREMENT_AGE,
    inflation_rate: float | None = None,
) -> dict[str, float]:
    """Return needAmount per UNIFIED type (same formulas as TS recalculateNeedAmounts)."""
    age = age_from_dob(date_of_birth)
    r = DEFAULT_INFLATION_RATE if inflation_rate is None else float(inflation_rate)
    income = monthly_to_annual(monthly_income)
    expense = monthly_to_annual(monthly_expense)
    ret_age = age_of_retirement if age_of_retirement > 0 else RETIREMENT_AGE

    inc_years = min(INC_PROTECTION_MAX_YEARS, max(0, INC_PROTECTION_MAX_AGE - age))
    income_protection = round_money(pv_annuity(0.5 * expense, r, inc_years))
    critical_illness = round_money(5 * income)
    tpd = round_money(0.5 * income_protection)

    years_to_ret = max(0, ret_age - age)
    expense_at_ret = expense * ((1 + r) ** years_to_ret)
    retirement = round_money(pv_annuity(expense_at_ret, r, RETIREMENT_DURATION_YEARS))

    return {
        "N_INC": income_protection,
        "N_CRI": critical_illness,
        "N_TPD": tpd,
        "N_RET": retirement,
        "N_EDU": round_money(3 * income),
        "N_SAV": round_money(income),
        "N_PRP": round_money(5 * income),
    }


def apply_amounts_to_needs(
    needs_map: dict[str, dict[str, Any]],
    amounts: dict[str, float],
    *,
    only_empty: bool = True,
) -> dict[str, dict[str, Any]]:
    """
    Fill needAmount/gap for enabled UNIFIED needs.

    When ``only_empty`` is True, skip rows whose needAmount is already > 0.
    """
    out: dict[str, dict[str, Any]] = {}
    for ut, row in needs_map.items():
        row = dict(row)
        if not row.get("enabled"):
            out[ut] = row
            continue
        existing = float(row.get("existing") or 0)
        current_amount = float(row.get("needAmount") or 0)
        computed = float(amounts.get(ut) or 0)
        if only_empty and current_amount > 0:
            amount = current_amount
        else:
            amount = computed
        row["needAmount"] = amount
        row["gap"] = remaining_gap(amount, existing)
        out[ut] = row
    return out

"""
Local goal / need amount math — Python port of shared/input_model goalMath.ts
(amount + gap core; premium bands optional / unused by onboarding calculator v1).
"""

from __future__ import annotations

from datetime import date
from typing import Any

from src.needs import CALCULATOR_NEEDS, PROTECTION_NEEDS, WEALTH_NEEDS

RETIREMENT_AGE = 65
LIFE_EXPECTANCY = 85
LIFE_EXPECTANCY_MAX = 99
MAX_RETIREMENT_AGE = 70
LOAN_TERM_YEARS = 20
DEFAULT_LOAN_RATE = 0.035
INC_PROTECTION_MAX_AGE = 85
INC_PROTECTION_MAX_YEARS = 30
RETIREMENT_DURATION_YEARS = 20  # 65 → 85; live N_RET uses years_in_retirement()
DEFAULT_INFLATION_RATE = 0.03

ACCUMULATION_TYPES = WEALTH_NEEDS
PROTECTION_TYPES = PROTECTION_NEEDS
UNIFIED_TYPES = CALCULATOR_NEEDS

# Retirement lifestyle: frugal / stress-free / only the best, as a share of today's spend.
RET_LIFESTYLE_FRUGAL = 0.75
RET_LIFESTYLE_STRESSFREE = 1.0
RET_LIFESTYLE_ONLYTHEBEST = 1.25
LIFESTYLE_RATES = {
    1: RET_LIFESTYLE_FRUGAL,
    2: RET_LIFESTYLE_STRESSFREE,
    3: RET_LIFESTYLE_ONLYTHEBEST,
}

# Singapore constants (SGD) for the Excel Needs Calculator shapes. The model holds these
# in USD; WP8 moves the calculator to USD and reads them from the admin parameters.
INC_SUPPORT_MIN = 10
INC_SUPPORT_MAX = 25
INC_SUPPORT_PIVOT_AGE = 50
CRI_YEARS = 3
CRI_COST = 200_000.0
TPD_YEARS = 5
TPD_COST = 200_000.0
HOS_MONTHS = 6
EDU_COST = 75_000.0


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


def pv_annuity_due(pmt: float, rate: float, periods: int) -> float:
    """Annuity with the first payment undiscounted (Excel CI / disability shape)."""
    if periods <= 0 or pmt <= 0:
        return 0.0
    if abs(rate) < 1e-12:
        return pmt * periods
    v = 1.0 / (1.0 + rate)
    return pmt * (1 - v**periods) / (1 - v)


def income_support_years(age: int) -> int:
    """Years the family is supported by life cover (Excel: MIN(MAX(10, 50 - age), 25))."""
    return min(
        max(INC_SUPPORT_MIN, INC_SUPPORT_PIVOT_AGE - int(age or 0)),
        INC_SUPPORT_MAX,
    )


# Old name, for one release. Removed in WP15.
life_support_years = income_support_years


def remaining_gap(need_amount: float, existing_cover: float | None) -> float:
    return max(0.0, float(need_amount or 0) - float(existing_cover or 0))


def round_to(n: float, step: float) -> float:
    if step <= 0:
        return max(0.0, n)
    return max(0.0, round(n / step) * step)


def fv(present: float, rate: float, periods: int) -> float:
    if periods <= 0:
        return max(0.0, float(present or 0))
    return float(present or 0) * ((1 + rate) ** periods)


def fv_annuity(pmt: float, rate: float, periods: int) -> float:
    if periods <= 0 or pmt <= 0:
        return 0.0
    if abs(rate) < 1e-12:
        return pmt * periods
    return (pmt * ((1 + rate) ** periods - 1)) / rate


def real_return(nominal: float, inflation: float) -> float:
    inf = float(inflation or 0)
    nom = float(nominal or 0)
    return max(0.0, (1 + nom) / (1 + inf) - 1)


def lifestyle_rate(lifestyle: int) -> float:
    return LIFESTYLE_RATES.get(int(lifestyle or 2), 1.0)


def years_in_retirement(ret_age: int, life_expectancy: int = LIFE_EXPECTANCY) -> int:
    """Years from retirement age through life expectancy (Excel: LE − retAge)."""
    return max(0, int(life_expectancy) - int(ret_age or RETIREMENT_AGE))


def session_life_expectancy(session: dict[str, Any] | None, default: int = LIFE_EXPECTANCY) -> int:
    """Session life expectancy, capped at 99. Missing or ≤ 0 → default (85)."""
    try:
        n = int((session or {}).get("lifeExpectancy") or 0)
    except (TypeError, ValueError):
        n = 0
    if n <= 0:
        n = int(default)
    return min(n, LIFE_EXPECTANCY_MAX)


def monthly_loan_payment(
    principal: float,
    annual_rate: float,
    years: int = LOAN_TERM_YEARS,
) -> float:
    """Level monthly PMT. annual_rate 0 → principal / (years × 12)."""
    p = float(principal or 0)
    if p <= 0:
        return 0.0
    n = max(1, int(years or LOAN_TERM_YEARS) * 12)
    r = float(annual_rate or 0) / 12.0
    if abs(r) < 1e-12:
        return p / n
    return p * r / (1.0 - (1.0 + r) ** (-n))


def annual_loan_payment(
    principal: float,
    annual_rate: float,
    years: int = LOAN_TERM_YEARS,
) -> float:
    """Level annual PMT that clears the loan in `years` yearly steps. annual_rate 0 → principal / years."""
    p = float(principal or 0)
    if p <= 0:
        return 0.0
    n = max(1, int(years or LOAN_TERM_YEARS))
    r = float(annual_rate or 0)
    if abs(r) < 1e-12:
        return p / n
    return p * r / (1.0 - (1.0 + r) ** (-n))


def years_to_retirement(ret_age: int, age: int) -> int:
    return max(0, int(ret_age or RETIREMENT_AGE) - int(age or 0))

"""Need Calculator: amount, have and gap per need, in USD.

Inputs arrive already converted. Fixed USD amounts are multiplied by the country's
relative price level here (option B), so a course of treatment costs less in a cheaper
country and the same income replacement costs the same everywhere. Results stay in USD;
the orchestrator converts them back and rounds in the user currency.

Formulas are the Need Calculator tab of the V0-24 workbook. Two annuity shapes, because
the original Excel is not consistent: life and retirement use an ordinary annuity (first
payment a year out), critical illness, TPD, personal accident and long-term care use an
annuity-due (first payment now).
"""

from __future__ import annotations

from src.needs import CALCULATOR_NEEDS, PROTECTION_NEEDS, WEALTH_NEEDS
from src.pipeline.goal_math import fv, fv_annuity, pv_annuity, pv_annuity_due, real_return
from src.services.config import service as config_service
from src.services.config.service import default_horizon_years
from src.services.need_calculator.models import (
    GoalInputs,
    Horizons,
    LongevityStress,
    NeedCalculatorRequest,
    NeedCalculatorResponse,
    NeedResult,
)

WEALTH_TAG_ORDER = ("N_RET", "N_EDU", "N_SAV", "N_PRP")


def _params(version: str) -> dict:
    return config_service.values(version)


def _lifestyle_share(lifestyle: int, params: dict) -> float:
    if int(lifestyle or 2) == 1:
        return float(params["RET_LIFESTYLE_FRUGAL"])
    if int(lifestyle or 2) == 3:
        return float(params["RET_LIFESTYLE_ONLYTHEBEST"])
    return float(params["RET_LIFESTYLE_STRESSFREE"])


def _support_years(age: int, params: dict) -> int:
    lo = int(params["INC_SUPPORT_MIN"])
    hi = int(params["INC_SUPPORT_MAX"])
    pivot = int(params["INC_SUPPORT_PIVOT_AGE"])
    return min(max(lo, pivot - int(age or 0)), hi)


def _inputs(req: NeedCalculatorRequest, need: str) -> GoalInputs:
    return req.inputs.get(need) or GoalInputs()


def _life_expectancy(req: NeedCalculatorRequest, params: dict) -> int:
    cap = int(params["LON_AGE"])
    raw = int(req.lifeExpectancy or 0)
    if raw <= 0:
        raw = int(params["lifeExpectancyDefault"])
    return min(raw, cap)


def _ret_age(req: NeedCalculatorRequest) -> int:
    ret = _inputs(req, "N_RET").retAge
    if ret and ret > 0:
        return int(ret)
    return int(req.ageOfRetirement or 65)


def _ltc_start(req: NeedCalculatorRequest, params: dict) -> int:
    start = _inputs(req, "N_LTC").ltcStartAge
    if start and start > 0:
        return int(start)
    return int(params["LTC_START_AGE"])


def _horizon_years(req: NeedCalculatorRequest, need: str, params: dict) -> int:
    """Years from now to the goal. A slider year wins; otherwise the age rule."""
    year = int(params["currentYear"])
    given = _inputs(req, need).targetYear
    if given and given > 0:
        return max(0, int(given) - year)
    return default_horizon_years(int(req.age or 0), need, params)


def _fixed(amount_usd: float, price_level: float) -> float:
    return float(amount_usd or 0) * (float(price_level or 0) or 1.0)


def _income_replace(req: NeedCalculatorRequest) -> float:
    given = _inputs(req, "N_CRI").incomeReplaceMonthlyUsd
    if given is None:
        given = _inputs(req, "N_TPD").incomeReplaceMonthlyUsd
    if given is None:
        given = _inputs(req, "N_PAC").incomeReplaceMonthlyUsd
    if given is None:
        return float(req.incomeMonthlyUsd or 0)
    return float(given)


def _depend_years(req: NeedCalculatorRequest, params: dict) -> int:
    given = _inputs(req, "N_INC").dependYears
    if given and given > 0:
        return int(given)
    return _support_years(req.age, params)


def _tagged(req: NeedCalculatorRequest) -> dict[str, float]:
    """The investment pot walk: RET → EDU → SAV → PRP, each taking only what is left."""
    remaining = max(0.0, float(req.investmentsUsd or 0))
    taken: dict[str, float] = {}
    for need in WEALTH_TAG_ORDER:
        want = max(0.0, float(_inputs(req, need).taggedInvestmentsUsd or 0))
        take = min(want, remaining)
        remaining -= take
        taken[need] = take
    return taken


def _amount(req: NeedCalculatorRequest, need: str, params: dict, rate: float, horizons: Horizons) -> float:
    pl = req.priceLevel
    income = float(req.incomeMonthlyUsd or 0)
    expense = float(req.expenseMonthlyUsd or 0)
    replace = _income_replace(req)
    lifestyle = int(_inputs(req, "N_RET").lifestyle or 2)
    if lifestyle not in (1, 3):
        lifestyle = 2

    if need == "N_RET":
        annual = expense * 12.0 * _lifestyle_share(lifestyle, params)
        grown = fv(annual, rate, horizons.yearsToRet)
        return max(0.0, pv_annuity(grown, rate, horizons.yearsInRet))
    if need == "N_INC":
        bequest = float(_inputs(req, "N_INC").bequestUsd or 0)
        liabilities = _inputs(req, "N_INC").liabilitiesUsd
        mortgage = float(req.mortgageUsd if liabilities is None else liabilities)
        return max(0.0, bequest + mortgage + pv_annuity(expense * 12.0, rate, _depend_years(req, params)))
    if need == "N_CRI":
        return max(
            0.0,
            pv_annuity_due(replace * 12.0, rate, int(params["CRI_YEARS"]))
            + _fixed(float(params["CRI_COST"]), pl),
        )
    if need == "N_TPD":
        return max(
            0.0,
            pv_annuity_due(replace * 12.0, rate, int(params["TPD_YEARS"]))
            + _fixed(float(params["TPD_COST"]), pl),
        )
    if need == "N_HOS":
        return max(0.0, income * float(params["HOS_MONTHS"]))
    if need == "N_PAC":
        return max(
            0.0,
            pv_annuity_due(replace * 12.0, rate, int(params["PAC_YEARS"]))
            + _fixed(float(params["PAC_COST"]), pl),
        )
    if need == "N_LTC":
        return max(
            0.0,
            pv_annuity_due(_fixed(float(params["LTC_COST"]), pl), rate, horizons.careYears),
        )
    if need == "N_EDU":
        return max(0.0, _fixed(float(params["EDU_COST"]), pl) * ((1 + float(req.inflationRate)) ** horizons.eduYears))
    stored = float(_inputs(req, need).storedAmountUsd or 0)
    if stored > 0:
        return stored
    annual_income = income * 12.0
    if need == "N_SAV":
        return max(0.0, annual_income * float(params["SAV_INCOME_MULT"]))
    if need == "N_PRP":
        return max(0.0, annual_income * float(params["PRP_INCOME_MULT"]))
    return 0.0


def _have(req: NeedCalculatorRequest, need: str, rate: float, horizons: Horizons, tagged: dict[str, float]) -> float:
    if need in PROTECTION_NEEDS:
        return max(0.0, float(req.existingCoverUsd.get(need) or 0))
    years = {
        "N_RET": horizons.yearsToRet,
        "N_EDU": horizons.eduYears,
        "N_SAV": horizons.savYears,
        "N_PRP": horizons.prpYears,
    }[need]
    contribution = float(_inputs(req, need).monthlyContributionUsd or 0) * 12.0
    return max(0.0, fv(tagged.get(need, 0.0), rate, years) + fv_annuity(contribution, rate, years))


def _horizons(req: NeedCalculatorRequest, params: dict) -> Horizons:
    ret = _ret_age(req)
    le = _life_expectancy(req, params)
    start = _ltc_start(req, params)
    return Horizons(
        yearsToRet=max(0, ret - int(req.age or 0)),
        yearsInRet=max(0, le - ret),
        eduYears=_horizon_years(req, "N_EDU", params),
        savYears=_horizon_years(req, "N_SAV", params),
        prpYears=_horizon_years(req, "N_PRP", params),
        careYears=max(0, le - start),
    )


def _longevity(req: NeedCalculatorRequest, params: dict, rate: float, horizons: Horizons, have: dict[str, float]) -> LongevityStress:
    lon_age = int(params["LON_AGE"])
    ret = _ret_age(req)
    start = _ltc_start(req, params)
    years_in = max(0, lon_age - ret)
    care = max(0, lon_age - start)
    lifestyle = int(_inputs(req, "N_RET").lifestyle or 2)
    if lifestyle not in (1, 3):
        lifestyle = 2
    annual = float(req.expenseMonthlyUsd or 0) * 12.0 * _lifestyle_share(lifestyle, params)
    grown = fv(annual, rate, horizons.yearsToRet)
    ret_need = max(0.0, pv_annuity(grown, rate, years_in))
    ltc_need = max(0.0, pv_annuity_due(_fixed(float(params["LTC_COST"]), req.priceLevel), rate, care))
    return LongevityStress(
        yearsInRetirement=years_in,
        careYears=care,
        needAmountUsd={"N_RET": ret_need, "N_LTC": ltc_need},
        gapUsd={
            "N_RET": max(0.0, ret_need - have.get("N_RET", 0.0)),
            "N_LTC": max(0.0, ltc_need - have.get("N_LTC", 0.0)),
        },
        extraNeedUsd={
            "N_RET": max(0.0, ret_need - have.get("_ret_amount", ret_need)),
            "N_LTC": max(0.0, ltc_need - have.get("_ltc_amount", ltc_need)),
        },
    )


def calculate(req: NeedCalculatorRequest) -> NeedCalculatorResponse:
    params = _params(req.parametersVersion)
    rate = real_return(req.investmentReturn, req.inflationRate)
    horizons = _horizons(req, params)
    tagged = _tagged(req)

    amounts: dict[str, float] = {}
    haves: dict[str, float] = {}
    needs: list[NeedResult] = []
    for need in CALCULATOR_NEEDS:
        amount = _amount(req, need, params, rate, horizons)
        have = _have(req, need, rate, horizons, tagged)
        amounts[need] = amount
        haves[need] = have
        needs.append(NeedResult(type=need, needAmountUsd=amount, haveUsd=have, gapUsd=max(0.0, amount - have)))

    lon_have = {
        **haves,
        "_ret_amount": amounts["N_RET"],
        "_ltc_amount": amounts["N_LTC"],
    }
    return NeedCalculatorResponse(
        needs=needs,
        horizons=horizons,
        stress={"R_LON": _longevity(req, params, rate, horizons, lon_have)},
    )

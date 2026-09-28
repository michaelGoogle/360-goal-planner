"""Map a GP session into an SV POST /api/v2/scenario-visualizer body."""
from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from src.cpf import session_take_home
from src.hu_payload import ACCUMULATION, PROTECTION, dob_from_age
from src.money import to_user
from src.needs import risk_code
from src.pipeline.goal_math import (
    LOAN_TERM_YEARS,
    annual_loan_payment,
    years_in_retirement,
)
from src.services.config import service as config_service
from src.services.fx.models import FxLock
from src.session_rates import session_rate

ASSET_CASH = "7c3a91e2-4b8f-4d21-9e6a-2f5c8b1d0a44"
ASSET_LIQUID = "d3ee1790-c469-4fb6-979a-fa4276f6d488"
ASSET_PROPERTY = "3f0413bb-e985-4ba2-8286-2f8fc54184c5"


def _need_id(need_type: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"gp-need-{need_type}"))


# HTML prototype: about two-thirds of the invested book sits outside SGD.
_FX_SHARE = 2.0 / 3.0

# Fraction / rate events. Lump sizes come from R_xxx_SIZE in the admin parameters.
_RATE_DEFAULTS = {
    "R_MKT": 0.35,
    "R_CCY": 0.14,
    "R_INF": 0.03,
    "R_ICT": -0.2,
    "R_EXP": 0.15,
}
_AGE_LUMPS = ("R_DEA", "R_CRI", "R_TPD", "R_PAC", "R_HOS")
_YEAR_LUMPS = ("R_WED", "R_BAB")


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return default if value is None else int(value)
    except (TypeError, ValueError):
        return default


def _as_float(value: Any, default: float) -> float:
    try:
        return default if value is None else float(value)
    except (TypeError, ValueError):
        return default


def _sv_year(offset: int) -> int:
    return max(1, offset + 1)


def _event_window(ev: dict[str, Any]) -> tuple[int, int, int]:
    year_off = _as_int(ev.get("year"), 0)
    if ev.get("year") is None and ev.get("from") is not None:
        year_off = _as_int(ev.get("from"), 0)
    start_off = _as_int(ev.get("from"), year_off)
    end_off = _as_int(ev.get("to"), year_off)
    start = _sv_year(start_off)
    end = max(start, _sv_year(end_off))
    return _sv_year(year_off), start, end


def _shock(event_type: str, year: int, **config: Any) -> dict[str, Any]:
    return {"flag": True, "eventType": event_type, "year": year, "config": config}


def _range_event(event_type: str, start: int, end: int, measurement: str, impact: float) -> dict[str, Any]:
    return {
        "flag": True,
        "eventType": event_type,
        "startYear": start,
        "endYear": end,
        "measurement": measurement,
        "impact": impact,
    }


def _fx(session: dict[str, Any]) -> FxLock:
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


def _params(session: dict[str, Any]) -> dict[str, Any]:
    return config_service.values(str(session.get("parametersVersion") or ""))


def _longevity_on(session: dict[str, Any]) -> bool:
    for ev in session.get("events") or []:
        if ev.get("on") and risk_code(str(ev.get("id") or ev.get("eventType") or "")) == "R_LON":
            return True
    return bool(session.get("longevityOn"))


def _life_expectancy(session: dict[str, Any], params: dict[str, Any]) -> int:
    cap = int(params["LON_AGE"])
    default = int(params["lifeExpectancyDefault"])
    try:
        n = int(session.get("lifeExpectancy") or 0)
    except (TypeError, ValueError):
        n = 0
    if n <= 0:
        n = default
    return min(n, cap)


def _path_end(params: dict[str, Any]) -> int:
    return int(params["LON_AGE"])


def _chart_horizon(session: dict[str, Any], params: dict[str, Any]) -> int:
    return _path_end(params) if _longevity_on(session) else _life_expectancy(session, params)


def _lump_size(risk: str, ev: dict[str, Any], params: dict[str, Any], fx: FxLock) -> float:
    if ev.get("v") is not None:
        return abs(_as_float(ev.get("v"), 0))
    usd = float(params.get(f"{risk}_SIZE") or 0)
    return abs(to_user(usd, fx))


def _age_engine_year(when_age: int, age: int) -> int:
    """Age-based events: already older than the age → next year (SV year 1)."""
    return max(1, int(when_age) - int(age))


def _horizon_years(need: dict[str, Any], session: dict[str, Any], t: str) -> int:
    for key in ("contributeYears", "horizonYears"):
        try:
            n = int(need.get(key) or 0)
        except (TypeError, ValueError):
            n = 0
        if n > 0:
            return n
    horizons = session.get("horizons") or {}
    named = {"N_RET": "yearsToRet", "N_EDU": "eduYears", "N_SAV": "savYears", "N_PRP": "prpYears"}
    if t in named:
        try:
            n = int(horizons.get(named[t]) or 0)
        except (TypeError, ValueError):
            n = 0
        if n > 0:
            return n
    return 0


def session_manual_events(session: dict[str, Any]) -> list[dict[str, Any]]:
    """Map GP stress-test rows onto SV manualEvents (1-based year + config).

    Rows arrive keyed by R_ code; ``risk_code`` also accepts the ids a session saved
    before the rename used, so an old plan still stresses the same way. Lump sizes
    and ages come from the admin parameters when the row does not set them.
    """
    params = _params(session)
    fx = _fx(session)
    age = int(session.get("age") or 40)
    le = _life_expectancy(session, params)
    inflation = session_rate(session, "inflationRate")
    out: list[dict[str, Any]] = []
    for ev in session.get("events") or []:
        if not ev.get("on"):
            continue
        risk = risk_code(str(ev.get("id") or ev.get("eventType") or ""))
        if risk == "R_LON":
            continue
        slider_set = ev.get("year") is not None or ev.get("from") is not None
        year, start, end = _event_window(ev) if slider_set else (1, 1, 1)
        if risk in _AGE_LUMPS and not slider_set:
            year = _age_engine_year(int(params.get(f"{risk}_WHEN") or age + 1), age)
        elif risk in _YEAR_LUMPS and not slider_set:
            year = max(1, int(params.get(f"{risk}_WHEN") or 0) + 1)
        elif risk == "R_LTC" and not slider_set:
            ltc_age = int(session.get("ltcStartAge") or params.get("LTC_START_AGE") or 80)
            start = max(1, ltc_age - age)
            end = max(start, le - age - 1)
            year = start
        v = (
            _as_float(ev.get("v"), _RATE_DEFAULTS[risk])
            if risk in _RATE_DEFAULTS
            else _lump_size(risk, ev, params, fx)
        )
        if risk == "R_DEA":
            out.append(_shock("Death", year, oneTimeCost=abs(v), stopSalary=True, stopCpfWage=True))
        elif risk == "R_CRI":
            out.append(_shock("CI", year, oneTimeCost=abs(v)))
        elif risk == "R_TPD":
            out.append(_shock("PTD", year, oneTimeCost=abs(v)))
        elif risk == "R_PAC":
            out.append(_shock("PersonalAccident", year, oneTimeCost=abs(v)))
        elif risk == "R_BAB":
            out.append(_shock("Newborn", year, oneTimeCost=abs(v)))
        elif risk == "R_WED":
            out.append(_shock("Marriage", year, oneTimeCost=abs(v)))
        elif risk == "R_MKT":
            out.append(_shock("MarketCrash", year, marketShock=abs(v)))
        elif risk == "R_CCY":
            out.append(_shock("CurrencyShock", year, currencyShock=abs(v) * _FX_SHARE))
        elif risk == "R_INF":
            out.append(_shock("Inflation", start, inflationRate=inflation + abs(v), length=max(1, end - start + 1)))
        elif risk == "R_ICT":
            out.append(_range_event("Income", start, end, "percentage", v if v <= 0 else -abs(v)))
        elif risk == "R_EXP":
            out.append(_range_event("Expense", start, end, "percentage", abs(v)))
        elif risk == "R_HOS":
            out.append(_shock("Hospitalization", year, oneTimeCost=abs(v)))
        elif risk == "R_LTC":
            out.append(_range_event("Expense", start, end, "amount", abs(v)))
    return out


_PLAN_PRODUCT = {
    "N_INC": ("GPP", "Life cover", "TermLife"),
    "N_CRI": ("CEJ", "Critical illness cover", "TermLife"),
    "N_TPD": ("TPD", "Disability cover", "TermLife"),
    "N_HOS": ("HSP", "Hospitalisation cover", "TermLife"),
    "N_PAC": ("PAC", "Personal accident cover", "TermLife"),
    "N_LTC": ("LTC", "Long-term care cover", "TermLife"),
    "N_RET": ("AIARS", "Retirement plan", "Savings"),
    "N_EDU": ("ERX", "Education plan", "Savings"),
    "N_SAV": ("SAV", "Saving plan", "Savings"),
    "N_PRP": ("PRP", "Property plan", "Savings"),
}


def _num_map(value: Any) -> dict[str, float]:
    if not isinstance(value, dict):
        return {}
    out: dict[str, float] = {}
    for key, raw in value.items():
        try:
            out[str(key)] = float(raw or 0)
        except (TypeError, ValueError):
            continue
    return out


def _cover_prem(sum_assured: float) -> float:
    return max(0.0, round((sum_assured * 0.00078) / 10) * 10)


def _bvo_product(code: str, name: str, category: str, columns: dict[str, list[float]]) -> dict[str, Any]:
    return {
        "productCode": code,
        "productName": name,
        "productVersion": "1",
        "productCategory": category,
        "productPlans": [
            {
                "isAddedToSummary": True,
                "benefitProjection": [{"column": col, "values": vals} for col, vals in columns.items()],
            }
        ],
    }


def _grow_pot(lump: float, annual: float, rate: float, years: int, pay_years: int) -> tuple[list[float], list[float]]:
    paid = 0.0
    acc = 0.0
    premiums: list[float] = []
    account: list[float] = []
    for t in range(years):
        if t < pay_years:
            contrib = annual + (lump if t == 0 else 0.0)
            paid += contrib
            acc = (acc + contrib) * (1 + rate)
        else:
            acc *= 1 + rate
        premiums.append(round(paid, 2))
        account.append(round(max(0.0, acc), 2))
    return premiums, account


def plan_benefit_visualizer(session: dict[str, Any]) -> list[dict[str, Any]]:
    """Illustrate the D2C suggested mix so SV's post path is 'with this plan'."""
    params = _params(session)
    age = int(session.get("age") or 40)
    ret_age = int(session.get("ageOfRetirement") or 65)
    now_year = int(params.get("currentYear") or date.today().year)
    inv_ret = session_rate(session, "investmentReturn")
    off = {str(t) for t in (session.get("plansOff") or [])}
    plan_mth = _num_map(session.get("planMth"))
    plan_lump = _num_map(session.get("planLump"))
    plan_sum = _num_map(session.get("planSum"))
    plan_prem = _num_map(session.get("planPrem"))
    n_years = max(1, _path_end(params) - age)
    out: list[dict[str, Any]] = []
    for need in session.get("needs") or []:
        t = str(need.get("type") or "")
        if t not in _PLAN_PRODUCT or t in off or not need.get("enabled"):
            continue
        meta = _PLAN_PRODUCT[t]
        if t in ACCUMULATION:
            mth = plan_mth.get(t, 0.0)
            lump = plan_lump.get(t, 0.0)
            if mth <= 0 and lump <= 0:
                continue
            if t == "N_RET":
                pay = max(1, ret_age - age)
            else:
                pay = max(1, _horizon_years(need, session, t))
                if pay <= 1:
                    funds = int(need.get("fundsNeededYear") or 0)
                    if funds:
                        pay = max(1, funds - now_year)
            premiums, account = _grow_pot(lump, mth * 12, inv_ret, n_years, pay)
            out.append(
                _bvo_product(
                    meta[0],
                    meta[1],
                    meta[2],
                    {"totalPremiumPaidToDate": premiums, "totalAccountValue": account},
                )
            )
            continue
        if t not in PROTECTION:
            continue
        sum_assured = plan_sum.get(t, 0.0)
        prem = plan_prem.get(t, _cover_prem(sum_assured) if sum_assured else 0.0)
        if sum_assured <= 0 and prem <= 0:
            continue
        pay = max(1, ret_age - age)
        paid = 0.0
        premiums: list[float] = []
        benefit: list[float] = []
        for t_i in range(n_years):
            if t_i < pay:
                paid += prem
            premiums.append(round(paid, 2))
            benefit.append(round(sum_assured, 2) if t_i < pay else 0.0)
        col = "guaranteedCriticalIllnessBenefit" if t == "N_CRI" else "guaranteedDeathBenefit"
        out.append(
            _bvo_product(
                meta[0],
                meta[1],
                meta[2],
                {"totalPremiumPaidToDate": premiums, col: benefit},
            )
        )
    return out


def build_sv_payload(session: dict[str, Any]) -> dict[str, Any]:
    age = int(session.get("age") or 40)
    dob = session.get("dateOfBirth") or dob_from_age(age)
    gender = session.get("gender") or "Male"
    income = float(session.get("incomeMonthly") or 0)
    take_home = session_take_home(session)
    expense = float(session.get("expenseMonthly") or 0)
    cash = float(session.get("cash") or 0)
    investments = float(session.get("investments") or 0)
    property_v = float(session.get("property") or 0)
    mortgage = float(session.get("mortgage") or 0)
    ret_age = int(session.get("ageOfRetirement") or 65)
    inflation = session_rate(session, "inflationRate")
    income_grow = session_rate(session, "incomeGrowthRate")
    cash_ret = session_rate(session, "interestRate")
    inv_ret = session_rate(session, "investmentReturn")
    asset_ret = session_rate(session, "assetReturn")
    prop_ret = max(0.0, asset_ret + 0.004)
    params = _params(session)
    now_year = int(params.get("currentYear") or date.today().year)
    le = _life_expectancy(session, params)
    path_end = _path_end(params)
    chart_end = _chart_horizon(session, params)
    needs = [n for n in (session.get("needs") or []) if n.get("enabled")]
    if not needs:
        needs = [{"type": "N_RET", "enabled": True, "needAmount": expense * 12 * years_in_retirement(ret_age, le), "priority": 5}]

    pd_needs = []
    nco = []
    for n in needs:
        t = str(n.get("type") or "")
        code = "N_HSP" if t == "N_HOS" else t
        nid = _need_id(code)
        years = _horizon_years(n, session, t)
        if t == "N_RET":
            funds_year = now_year + max(0, ret_age - age)
        elif years:
            funds_year = now_year + years
        else:
            funds_year = int(n.get("fundsNeededYear") or now_year + 10)
        amount = float(n.get("needAmount") or 0)
        tagged = [] if t in ACCUMULATION else [ASSET_PROPERTY]
        pd_needs.append(
            {
                "needId": nid,
                "type": code,
                "targetYear": funds_year if t in ACCUMULATION else None,
                "taggedAsset": tagged,
                "existingSumAssured": 0 if t in ACCUMULATION else int(n.get("existingSumAssured") or 0),
                "existingAnnualPremium": 0 if t in ACCUMULATION else int(n.get("existingAnnualPremium") or 0),
                "ageOfRetirement": ret_age,
                "numYearDependents": _as_int(n.get("dependYears"), 10),
            }
        )
        result: dict[str, Any] = {
            "capitalSumRequired": amount,
            "totalNeed": amount,
            "ageOfRetirement": ret_age,
            "targetYear": funds_year if t in ACCUMULATION else None,
        }
        if t == "N_RET":
            result["retirementAge"] = ret_age
            result["durationOfRetirement"] = years_in_retirement(ret_age, le)
            result["fundsNeededYear"] = now_year + max(0, ret_age - age)
        elif t in ("N_SAV", "N_PRP", "N_EDU"):
            result["fundsNeededYear"] = funds_year
        elif t == "N_HOS":
            result["medicalCost"] = amount
        nco.append({"type": code, "needId": nid, "result": result})

    events = session_manual_events(session)

    existing_ins: list[dict[str, Any]] = []
    for p in session.get("policies") or []:
        kind = str(p.get("type") or "")
        existing_ins.append(
            {
                "category": "Wealth Protection" if "Life" in kind or "Critical" in kind else "Wealth Accumulation",
                "death": float(p.get("sum") or 0) if "Life" in kind else 0,
                "criticalIllness": float(p.get("sum") or 0) if "Critical" in kind else 0,
                "totalPermanentDisability": float(p.get("sum") or 0) if "Disability" in kind else 0,
                "personalAccident": 0,
                "currentCashValue": 0,
                "regularPremium": float(p.get("premium") or 0),
                "policyTerm": 20,
                "projectedMaturityValue": 0,
                "maturityDate": None,
            }
        )

    cpf_on = session.get("residency") != "Foreigner"
    payload = {
        "sessionId": str(uuid.uuid4()),
        "noDeathFlag": True,
        "numSims": max(10, min(200, int(session.get("svNumSims") or 20))),
        "manualEvents": events,
        "configurableEvents": [],
        "modelParameters": {
            "ignoreIlliquidAssets": False,
            "showExpenseFunding": True,
            "subtractLoanBalances": True,
            "inflationRate": inflation,
            "incomeGrowthRate": income_grow,
            "lifeExpectancy": path_end,
            "chartHorizon": chart_end,
            "numYears": max(1, path_end - age),
        },
        "personalDetails": [
            {
                "dateOfBirth": dob,
                "gender": gender,
                "age": 0,
                "isSmoker": bool(session.get("isSmoker") or False),
                "ageOfRetirement": ret_age,
                "isPolicyOwner": True,
                "partnerId": "00000000-0000-4000-8000-000000000001",
                "needs": pd_needs,
                "cashFlows": {
                    "income": [
                        {"type": "I_SAL", "absoluteValue": int(round(income * 12)), "frequency": 2},
                        {"type": "I_BNS", "absoluteValue": 0, "frequency": 2},
                        {"type": "I_OTH", "absoluteValue": 0, "frequency": 2},
                    ],
                    "expenses": [
                        {
                            "type": "PERSONAL_EXPENSE",
                            "absoluteValue": int(round(expense * 12)),
                            "frequency": 2,
                            "targetYear": None,
                        }
                    ],
                },
                "liabilities": {
                    "loans": (
                        [
                            {
                                "type": "Mortgage",
                                "currentValue": int(mortgage),
                                "interestRate": session_rate(session, "loanRate"),
                                "remainingYears": LOAN_TERM_YEARS,
                                "frequency": 2,
                                "installments": int(round(
                                    annual_loan_payment(mortgage, session_rate(session, "loanRate"))
                                )) if mortgage else 0,
                            }
                        ]
                        if mortgage
                        else []
                    ),
                    "tax": {"value": 0},
                },
                "assets": [
                    {
                        "id": ASSET_CASH,
                        "type": "A_SAV",
                        "otherAssetType": None,
                        "currentValue": int(round(cash)),
                        "interestRate": cash_ret,
                        "recurringContribution": {"value": 0, "duration": 100},
                        "isLiquid": True,
                    },
                    {
                        "id": ASSET_LIQUID,
                        "type": "INVESTMENT_PORTFOLIO",
                        "otherAssetType": None,
                        "currentValue": int(round(investments)),
                        "interestRate": inv_ret,
                        "recurringContribution": {
                            "value": int(round(max(0, take_home - expense))),
                            "duration": 100,
                        },
                        "isLiquid": True,
                    },
                    {
                        "id": ASSET_PROPERTY,
                        "type": "RESIDENTIAL_PROPERTY",
                        "otherAssetType": None,
                        "currentValue": int(round(property_v)),
                        "interestRate": prop_ret,
                        "recurringContribution": {"value": 0, "duration": 100},
                        "isLiquid": False,
                    },
                ],
                "socialSecurity": {
                    # R_SGP = CPF engine. R_OTH = no CPF (SV SocialSecurityR_OTH / BaseClass).
                    "region": "R_SGP" if cpf_on else "R_OTH",
                    "ageStartPayout": max(65, ret_age),
                    "cpfInitialBalanceOA": 0,
                    "cpfInitialBalanceMA": 0,
                    "cpfInitialBalanceSA": 0,
                    "cpfInitialBalanceRA": 0,
                },
                "existingInsurance": existing_ins,
            }
        ],
        "needCalculatorOutput": nco,
    }
    bvo = plan_benefit_visualizer(session)
    if bvo:
        payload["benefitVisualizerOutput"] = bvo
    return payload

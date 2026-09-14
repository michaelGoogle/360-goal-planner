"""Map a GP session into an SV POST /api/v2/scenario-visualizer body."""
from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from src.cpf import session_take_home
from src.hu_payload import ACCUMULATION, PROTECTION, dob_from_age, hu_need_code
from src.pipeline.goal_math import years_in_retirement
from src.session_rates import session_rate

ASSET_CASH = "7c3a91e2-4b8f-4d21-9e6a-2f5c8b1d0a44"
ASSET_LIQUID = "d3ee1790-c469-4fb6-979a-fa4276f6d488"
ASSET_PROPERTY = "3f0413bb-e985-4ba2-8286-2f8fc54184c5"


def _need_id(need_type: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"gp-need-{need_type}"))


# GP sliders use 0 = this year. SV columns are 1-based (1 = this year).
_EVENT_ALIAS = {
    "crash": "crash",
    "Crash": "crash",
    "MarketCrash": "crash",
    "death": "death",
    "Death": "death",
    "ci": "ci",
    "CI": "ci",
    "tpd": "tpd",
    "PTD": "tpd",
    "pa": "pa",
    "PersonalAccident": "pa",
    "inc": "inc",
    "Unemployment": "inc",
    "infl": "infl",
    "Inflation": "infl",
    "hosp": "hosp",
    "care": "care",
    "wed": "wed",
    "Wedding": "wed",
    "Marriage": "wed",
    "baby": "baby",
    "Newborn": "baby",
    "exp": "exp",
    "ccy": "ccy",
}

# HTML prototype: about two-thirds of the invested book sits outside SGD.
_FX_SHARE = 2.0 / 3.0

_DEFAULT_V = {
    "crash": 0.35,
    "ccy": 0.14,
    "infl": 0.03,
    "inc": -0.2,
    "death": 20_000,
    "ci": 150_000,
    "tpd": 200_000,
    "pa": 80_000,
    "hosp": 120_000,
    "care": 90_000,
    "wed": 60_000,
    "baby": 35_000,
    "exp": 0.15,
}


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


def session_manual_events(session: dict[str, Any]) -> list[dict[str, Any]]:
    """Map GP stress-test rows onto SV manualEvents (1-based year + config)."""
    inflation = session_rate(session, "inflationRate")
    out: list[dict[str, Any]] = []
    for ev in session.get("events") or []:
        if not ev.get("on"):
            continue
        kind = _EVENT_ALIAS.get(str(ev.get("id") or ev.get("eventType") or ""))
        if not kind:
            continue
        year, start, end = _event_window(ev)
        v = _as_float(ev.get("v"), _DEFAULT_V[kind])
        if kind == "death":
            out.append(_shock("Death", year, oneTimeCost=abs(v)))
        elif kind == "ci":
            out.append(_shock("CI", year, oneTimeCost=abs(v)))
        elif kind == "tpd":
            out.append(_shock("PTD", year, oneTimeCost=abs(v)))
        elif kind == "pa":
            out.append(_shock("PersonalAccident", year, oneTimeCost=abs(v)))
        elif kind == "baby":
            out.append(_shock("Newborn", year, oneTimeCost=abs(v)))
        elif kind == "wed":
            out.append(_shock("Marriage", year, oneTimeCost=abs(v)))
        elif kind == "crash":
            out.append(_shock("MarketCrash", year, marketShock=abs(v)))
        elif kind == "ccy":
            out.append(_shock("CurrencyShock", year, currencyShock=abs(v) * _FX_SHARE))
        elif kind == "infl":
            out.append(_shock("Inflation", start, inflationRate=inflation + abs(v), length=max(1, end - start + 1)))
        elif kind == "inc":
            out.append(_range_event("Income", start, end, "percentage", v if v <= 0 else -abs(v)))
        elif kind == "exp":
            out.append(_range_event("Expense", start, end, "percentage", abs(v)))
        elif kind == "hosp":
            out.append(_shock("Hospitalization", year, oneTimeCost=abs(v)))
        elif kind == "care":
            out.append(_range_event("Expense", start, end, "amount", abs(v)))
    return out


_PLAN_PRODUCT = {
    "N_INC": ("GPP", "Life cover", "TermLife"),
    "N_CRI": ("CEJ", "Critical illness cover", "TermLife"),
    "N_TPD": ("TPD", "Disability cover", "TermLife"),
    "N_HOS": ("HSP", "Hospitalisation cover", "TermLife"),
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
    age = int(session.get("age") or 40)
    ret_age = int(session.get("ageOfRetirement") or 65)
    now_year = date.today().year
    inv_ret = session_rate(session, "investmentReturn")
    off = {str(t) for t in (session.get("plansOff") or [])}
    plan_mth = _num_map(session.get("planMth"))
    plan_lump = _num_map(session.get("planLump"))
    plan_sum = _num_map(session.get("planSum"))
    plan_prem = _num_map(session.get("planPrem"))
    n_years = max(20, 100 - age)
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
                funds = int(need.get("fundsNeededYear") or now_year + 10)
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
    now_year = date.today().year
    needs = [n for n in (session.get("needs") or []) if n.get("enabled")]
    if not needs:
        needs = [{"type": "N_RET", "enabled": True, "needAmount": expense * 12 * years_in_retirement(ret_age), "priority": 5}]

    pd_needs = []
    nco = []
    for n in needs:
        t = str(n.get("type") or "")
        code = hu_need_code(t)
        nid = _need_id(code)
        funds_year = int(n.get("fundsNeededYear") or now_year + (ret_age - age if t == "N_RET" else 10))
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
            result["durationOfRetirement"] = years_in_retirement(ret_age)
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
                                "interestRate": 0.035,
                                "remainingYears": 20,
                                "frequency": 2,
                                "installments": int(round(mortgage / 20)) if mortgage else 0,
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

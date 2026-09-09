"""Map a GP session into an SV POST /api/v2/scenario-visualizer body."""
from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from src.cpf import session_take_home
from src.hu_payload import ACCUMULATION, dob_from_age

ASSET_LIQUID = "d3ee1790-c469-4fb6-979a-fa4276f6d488"
ASSET_PROPERTY = "3f0413bb-e985-4ba2-8286-2f8fc54184c5"


def _need_id(need_type: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"gp-need-{need_type}"))


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
    inflation = float(session.get("inflationRate") if session.get("inflationRate") is not None else 0.023)
    income_grow = float(session.get("incomeGrowthRate") if session.get("incomeGrowthRate") is not None else 0.028)
    inv_ret = float(session.get("investmentReturn") if session.get("investmentReturn") is not None else 0.042)
    asset_ret = float(session.get("assetReturn") if session.get("assetReturn") is not None else 0.03)
    prop_ret = max(0.0, asset_ret + 0.004)
    now_year = date.today().year
    needs = [n for n in (session.get("needs") or []) if n.get("enabled")]
    if not needs:
        needs = [{"type": "N_RET", "enabled": True, "needAmount": expense * 12 * 20, "priority": 5}]

    pd_needs = []
    nco = []
    for n in needs:
        t = n["type"]
        nid = _need_id(t)
        funds_year = int(n.get("fundsNeededYear") or now_year + (ret_age - age if t == "N_RET" else 10))
        amount = float(n.get("needAmount") or 0)
        tagged = [] if t in ACCUMULATION else [ASSET_PROPERTY]
        pd_needs.append(
            {
                "needId": nid,
                "type": t,
                "targetYear": funds_year if t in ACCUMULATION else None,
                "taggedAsset": tagged,
                "existingSumAssured": 0 if t in ACCUMULATION else int(n.get("existingSumAssured") or 0),
                "existingAnnualPremium": 0 if t in ACCUMULATION else int(n.get("existingAnnualPremium") or 0),
            }
        )
        result: dict[str, Any] = {"capitalSumRequired": amount, "totalNeed": amount}
        if t == "N_RET":
            result["retirementAge"] = ret_age
            result["durationOfRetirement"] = 20
            result["fundsNeededYear"] = now_year + max(0, ret_age - age)
        elif t in ("N_SAV", "N_PRP", "N_EDU"):
            result["fundsNeededYear"] = funds_year
        nco.append({"type": t, "needId": nid, "result": result})

    events = []
    for ev in session.get("events") or []:
        if not ev.get("on"):
            continue
        raw = str(ev.get("id") or ev.get("eventType") or "")
        events.append(
            {
                "eventType": "MarketCrash" if raw == "Crash" else raw,
                "year": int(ev.get("year") or 1),
                "flag": True,
            }
        )

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
    return {
        "sessionId": str(uuid.uuid4()),
        "noDeathFlag": True,
        "numSims": max(10, min(200, int(session.get("svNumSims") or 20))),
        "manualEvents": events,
        "configurableEvents": [],
        "modelParameters": {
            "ignoreIlliquidAssets": False,
            "showExpenseFunding": True,
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
                        "id": ASSET_LIQUID,
                        "type": "INVESTMENT_PORTFOLIO",
                        "otherAssetType": None,
                        "currentValue": int(round(cash + investments)),
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

"""Map a GP session into a HappiU POST /v1/happi-u body."""
from __future__ import annotations

import uuid
from datetime import date
from typing import Any


PARTNER_ID = "2807cba0-5698-11ec-855c-b5536ab81d64"
PRODUCT_CODES = {
    "N_EDU": "ERX",
    "N_RET": "AIARS",
    "N_INC": "GPP",
    "N_CRI": "CEJ",
    "N_TPD": "TPD",
    "N_SAV": "SAV",
    "N_PRP": "PRP",
}

NEED_BASE: dict[str, dict[str, Any]] = {
    "N_EDU": {"region": "R_CAN", "lifestyle": 2, "numYearDependents": None},
    "N_SAV": {"region": "R_CAN", "lifestyle": 2, "numYearDependents": None},
    "N_PRP": {"region": "R_CAN", "lifestyle": 2, "numYearDependents": None},
    "N_RET": {"region": "R_SGP", "lifestyle": 1, "numYearDependents": None},
    "N_INC": {"region": "R_ASI", "lifestyle": 1, "numYearDependents": 10},
    "N_TPD": {"region": "R_ASI", "lifestyle": 1, "numYearDependents": 10},
    "N_CRI": {"region": "R_ASI", "lifestyle": 1, "numYearDependents": None},
}

ACCUMULATION = {"N_RET", "N_EDU", "N_SAV", "N_PRP"}
PROTECTION = {"N_INC", "N_CRI", "N_TPD"}
POLICY_TYPE = {
    "N_INC": "Life Protection",
    "N_CRI": "Critical Illness",
    "N_TPD": "Permanent Disability",
}


def need_existing(need: dict[str, Any], session: dict[str, Any]) -> float:
    """Cover or savings already allocated to this need."""
    for key in ("existingInvestment", "existingSumAssured", "existing"):
        val = need.get(key)
        if val:
            return float(val)
    t = need.get("type") or ""
    if t in POLICY_TYPE:
        want = POLICY_TYPE[t]
        return sum(float(p.get("sum") or 0) for p in (session.get("policies") or []) if p.get("type") == want)
    return float(session.get("cash") or 0) + float(session.get("investments") or 0)


def dob_from_age(age: int) -> str:
    today = date.today()
    year = today.year - max(18, min(90, int(age or 40)))
    return f"{year:04d}-{today.month:02d}-{min(today.day, 28):02d}"


def _need_row(need: dict[str, Any], age_of_retirement: int, session: dict[str, Any]) -> dict[str, Any]:
    t = need["type"]
    base = NEED_BASE.get(t, {"region": "R_SGP", "lifestyle": 1, "numYearDependents": None})
    tagged = {"id": None, "type": None, "partner": None}
    funds_year = need.get("fundsNeededYear") or need.get("targetYear")
    existing_sa = need_existing(need, session) if t in PROTECTION else need.get("existingSumAssured")
    return {
        "needId": t,
        "type": t,
        "value": None,
        "priority": int(need.get("priority") or 3),
        "existingSumAssured": existing_sa,
        "existingAnnualPremium": need.get("existingAnnualPremium"),
        "existingMaturityYear": need.get("existingMaturityYear"),
        "numYearDependents": need.get("dependYears") if need.get("dependYears") is not None else base["numYearDependents"],
        "targetYear": funds_year,
        "ageOfRetirement": age_of_retirement if t == "N_RET" else None,
        "taggedAsset": tagged,
        "region": need.get("region") or base["region"],
        "lifestyle": int(need.get("lifestyle") or base["lifestyle"]),
        "field": None,
        "chosenNeedGoalFlag": 1,
    }


def _calc_entry(
    need: dict[str, Any],
    monthly_expense: float,
    age_of_retirement: int,
    age: int,
    session: dict[str, Any],
) -> dict[str, Any]:
    t = need["type"]
    total_need = float(need.get("needAmount") or 0)
    existing = need_existing(need, session)
    tagged = existing if t in ACCUMULATION else 0.0
    shortfall = max(0.0, total_need - existing)
    now_year = date.today().year
    annual_expense = monthly_expense * 12
    funds_year = int(need.get("fundsNeededYear") or need.get("targetYear") or now_year + 10)
    primary: dict[str, Any] = {
        "needId": t,
        "totalNeed": total_need,
        "totalShortfall": shortfall,
        "taggedFundValue": tagged,
        "taggedAssetCurrentValue": tagged,
        "socialSecurity": 0,
    }
    meta: dict[str, Any] = {}
    if t == "N_RET":
        ret_m = need.get("retIncomeMonthly")
        living = (float(ret_m) if ret_m not in (None, "") else monthly_expense) * 12
        primary.update(
            {
                "retirementAge": age_of_retirement,
                "livingExpenses": living,
                "expectedLivingExpenseInTheCountry": living * 0.75,
                "durationOfRetirement": 20,
                "numYearsToRetirement": max(0, age_of_retirement - age),
                "socialSecurityValue": 0,
            }
        )
        meta = {"livingExpenses": {PARTNER_ID: {}}}
    elif t in ("N_EDU", "N_SAV", "N_PRP"):
        primary.update(
            {
                "fundsNeededYear": funds_year,
                "numYearsToSave": max(0, funds_year - now_year),
            }
        )
    elif t == "N_CRI":
        primary.update(
            {
                "livingExpenses": annual_expense,
                "numYearsIncomeNeeded": 5,
                "medicalCost": 62400,
                "proportionOfExpenses": 1,
            }
        )
        meta = {"livingExpenses": {PARTNER_ID: {}}}
    elif t in ("N_INC", "N_TPD"):
        primary.update({"funeralExpense": 10000, "lumpSumNeeded": total_need, "existingLifeCover": existing or None})
        meta = {"lumpSumNeeded": {PARTNER_ID: {}}}
    return {"primaryOutput": {PARTNER_ID: [primary]}, "metaOutput": meta}


def _budget_line(need: dict[str, Any]) -> dict[str, Any]:
    t = need["type"]
    rec_benefit = max(0, round(float(need.get("needAmount") or 0) / 50000) * 50000)
    return {
        "partnerId": PARTNER_ID,
        "goalId": t,
        "goalType": t,
        "productCode": PRODUCT_CODES.get(t, t),
        "paymentFrequency": "Monthly",
        "riders": [],
        "policyTerm": 10,
        "benefitAmount": rec_benefit,
        "paymentTerm": 10,
        "actualPolicyTerm": 15,
        "actualPaymentTerm": 10,
        "budget": float(need.get("annualPremium") or 200),
        "gfr": 0.05,
        "growthRate": 0.035 if t in ACCUMULATION else 0,
    }


def build_happiu_payload(session: dict[str, Any]) -> dict[str, Any]:
    age = int(session.get("age") or 40)
    dob = session.get("dateOfBirth") or dob_from_age(age)
    gender = session.get("gender") or "Male"
    income = float(session.get("incomeMonthly") or 0)
    expense = float(session.get("expenseMonthly") or 0)
    liquid = float(session.get("cash") or 0) + float(session.get("investments") or 0)
    ret_age = int(session.get("ageOfRetirement") or 65)
    needs = [n for n in (session.get("needs") or []) if n.get("enabled")]
    if not any(n.get("type") == "N_RET" for n in needs):
        needs = list(needs) + [
            {
                "type": "N_RET",
                "enabled": True,
                "needAmount": expense * 12 * 20,
                "priority": 5,
                "existingInvestment": liquid,
            }
        ]

    calc: dict[str, Any] = {}
    by_type = {n["type"]: n for n in needs}
    for t, n in by_type.items():
        calc[t] = _calc_entry(n, expense, ret_age, age, session)
    if "N_RET" not in calc:
        calc["N_RET"] = _calc_entry(
            {"type": "N_RET", "needAmount": expense * 12 * 20, "existingInvestment": liquid},
            expense,
            ret_age,
            age,
            session,
        )

    return {
        "sessionId": str(uuid.uuid4()),
        "noDeathFlag": True,
        "manualEvents": {"flag": False, "eventType": "", "year": 0},
        "preHappiURequired": True,
        "postHappiURequired": True,
        "numSims": int(session.get("numSims") or 200),
        "personalDetails": [
            {
                "tenantId": None,
                "partnerId": PARTNER_ID,
                "partnerType": "IND",
                "dateOfBirth": dob,
                "gender": gender,
                "riskProfile": int(session.get("riskProfile") or 4),
                "ageOfRetirement": ret_age,
                "isSmoker": bool(session.get("isSmoker") or False),
                "isFatca": None,
                "isPolicyOwner": True,
                "relationshipToPO": None,
                "isFinanciallyIndependent": True,
                "needs": [_need_row(n, ret_age, session) for n in needs],
                "cashFlows": {
                    "monthlyIncome": income,
                    "expenses": [],
                    "income": [
                        {
                            "type": "I_SAL",
                            "absoluteValue": income,
                            "targetYear": None,
                            "frequency": 1,
                        }
                    ],
                },
                "liabilities": {
                    "loans": [
                        {
                            "type": None,
                            "currentValue": None,
                            "interestRate": None,
                            "remainingYears": None,
                            "frequency": None,
                            "installments": None,
                            "proportion": None,
                        }
                    ],
                    "tax": {"value": 0},
                },
                "assets": [
                    {
                        "type": "A_SAV",
                        "currentValue": liquid,
                        "interestRate": 0.0225,
                        "id": "A_SAV_Main",
                        "recurringContribution": {"value": 0, "frequency": 1, "duration": 0},
                        "proportion": 1,
                    }
                ],
                "socialSecurity": {
                    "retirement": None,
                    "health": None,
                    "other": None,
                    "installmentsPayCash": None,
                    "installmentsPayCpf": None,
                    "cpfSalaryContribution": session.get("residency") != "Foreigner",
                    "mortgageSelect": {"id": None, "remainingTenure": None, "installments": None},
                },
            }
        ],
        "commonDetails": {
            "planningCurrency": "SGD",
            "isIncomePayoutReqd": False,
            "totalMonthlyRegularIncome": income,
            "totalMonthlyRegularExpense": expense,
            "annualBudget": 1500,
            "numDependents": int(session.get("dependents") or 0),
        },
        "solutionOptimizerOutput": {
            "packageCode": "P002",
            "segregatedBudget": [_budget_line(n) for n in needs],
        },
        "needCalculatorOutput": calc,
        "soAllOutput": [],
    }

"""Map a GP session into a HappiU POST /v1/happi-u body."""
from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from src.money import nice_step, round_half_up, to_user
from src.needs import WEALTH_NEEDS
from src.pipeline.goal_math import lifestyle_rate, years_in_retirement
from src.services.config import service as config_service
from src.services.fx.models import FxLock
from src.session_rates import session_rate

PARTNER_ID = "2807cba0-5698-11ec-855c-b5536ab81d64"
PRODUCT_CODES = {
    "N_EDU": "ERX",
    "N_RET": "AIARS",
    "N_INC": "GPP",
    "N_CRI": "CEJ",
    "N_TPD": "TPD",
    "N_HOS": "HSP",
    "N_PAC": "PAC",
    "N_SAV": "SAV",
    "N_PRP": "PRP",
}

# Identity: the model code is what HU accepts. The old hospitalisation alias lives in HU.
HU_NEED_CODE: dict[str, str] = {}

NEED_BASE: dict[str, dict[str, Any]] = {
    "N_EDU": {"region": "R_CAN", "lifestyle": 2, "numYearDependents": None},
    "N_SAV": {"region": "R_CAN", "lifestyle": 2, "numYearDependents": None},
    "N_PRP": {"region": "R_CAN", "lifestyle": 2, "numYearDependents": None},
    "N_RET": {"region": "R_SGP", "lifestyle": 1, "numYearDependents": None},
    "N_INC": {"region": "R_ASI", "lifestyle": 1, "numYearDependents": 10},
    "N_TPD": {"region": "R_ASI", "lifestyle": 1, "numYearDependents": 10},
    "N_CRI": {"region": "R_ASI", "lifestyle": 1, "numYearDependents": None},
    "N_HOS": {"region": "R_ASI", "lifestyle": 1, "numYearDependents": None},
    "N_PAC": {"region": "R_ASI", "lifestyle": 1, "numYearDependents": None},
}

ACCUMULATION = set(WEALTH_NEEDS)
# What the HU engine can score. N_LTC never: the engine has no long-term care goal.
PROTECTION = {"N_INC", "N_CRI", "N_TPD", "N_HOS", "N_PAC"}
POLICY_TYPE = {
    "N_INC": "Life Protection",
    "N_CRI": "Critical Illness",
    "N_TPD": "Permanent Disability",
    "N_HOS": "Hospitalisation",
    "N_PAC": "Personal Accident",
}


def hu_need_code(need_type: str) -> str:
    return HU_NEED_CODE.get(need_type, need_type)


# Wealth tags draw from investments only, in this order. Cash is never a need pot.
WEALTH_TAG_ORDER = ("N_RET", "N_EDU", "N_SAV", "N_PRP")


def _explicit_tag(need: dict[str, Any]) -> float:
    """Amount the customer assigned to this need. Missing means not tagged."""
    for key in ("existingInvestment", "existing", "existingSumAssured"):
        if key in need and need.get(key) not in (None, ""):
            try:
                return max(0.0, float(need.get(key) or 0))
            except (TypeError, ValueError):
                return 0.0
    return 0.0


def need_existing(need: dict[str, Any], session: dict[str, Any]) -> float:
    """Cover or savings already allocated to this need.

    Protection uses the matching policy sum. Wealth uses only an amount the
    customer tagged. Cash is never allocated, and untagged investments stay
    in the central pot (see ``apply_investment_pot``).
    """
    t = need.get("type") or ""
    if t in POLICY_TYPE:
        for key in ("existingSumAssured", "existing"):
            if key in need and need.get(key) not in (None, ""):
                try:
                    tagged = float(need.get(key) or 0)
                except (TypeError, ValueError):
                    tagged = 0.0
                if tagged > 0:
                    return tagged
        want = POLICY_TYPE[t]
        return sum(float(p.get("sum") or 0) for p in (session.get("policies") or []) if p.get("type") == want)
    if any(key in need and need.get(key) not in (None, "") for key in ("existingInvestment", "existing")):
        return _explicit_tag(need)
    return 0.0


def apply_investment_pot(needs: list[dict[str, Any]], investments: float) -> None:
    """Keep tagged savings inside one investments pot.

    Walk wealth needs in ``WEALTH_TAG_ORDER``. Each tagged amount takes from
    what is left. A later need cannot use savings already assigned.
    """
    remaining = max(0.0, float(investments or 0))
    by_type = {n.get("type"): n for n in needs if n.get("type")}
    for t in WEALTH_TAG_ORDER:
        row = by_type.get(t)
        if row is None:
            continue
        tagged = _explicit_tag(row) if any(
            key in row and row.get(key) not in (None, "") for key in ("existingInvestment", "existing")
        ) else 0.0
        take = min(tagged, remaining)
        remaining -= take
        row["existing"] = take
        row["existingInvestment"] = take


def dob_from_age(age: int) -> str:
    today = date.today()
    year = today.year - max(18, min(90, int(age or 40)))
    return f"{year:04d}-{today.month:02d}-{min(today.day, 28):02d}"


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


def _life_expectancy(session: dict[str, Any], params: dict[str, Any]) -> int:
    """Session life expectancy, defaulted and capped the way the workbook is."""
    cap = int(params["LON_AGE"])
    default = int(params["lifeExpectancyDefault"])
    try:
        n = int(session.get("lifeExpectancy") or 0)
    except (TypeError, ValueError):
        n = 0
    if n <= 0:
        n = default
    return min(n, cap)


def _user_amount(usd: float, fx: FxLock) -> float:
    """A USD parameter as user-currency money. HappiU tab is CRI_COST / FX, no PPP."""
    return float(to_user(usd, fx))


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
    year = int(need.get("fundsNeededYear") or need.get("targetYear") or 0)
    if year > 0:
        now = int((session.get("horizons") or {}).get("currentYear") or 0)
        if not now:
            now = int(_params(session).get("currentYear") or date.today().year)
        return max(0, year - now)
    return 0


def _need_row(need: dict[str, Any], age_of_retirement: int, session: dict[str, Any]) -> dict[str, Any]:
    t = need["type"]
    base = NEED_BASE.get(t, {"region": "R_SGP", "lifestyle": 1, "numYearDependents": None})
    tagged = {"id": None, "type": None, "partner": None}
    funds_year = need.get("fundsNeededYear") or need.get("targetYear")
    existing_sa = need_existing(need, session) if t in PROTECTION else need.get("existingSumAssured")
    code = hu_need_code(t)
    return {
        "needId": code,
        "type": code,
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
    params: dict[str, Any],
    fx: FxLock,
    le: int,
) -> dict[str, Any]:
    t = need["type"]
    total_need = float(need.get("needAmount") or 0)
    existing = need_existing(need, session)
    tagged = existing if t in ACCUMULATION else 0.0
    shortfall = max(0.0, total_need - existing)
    now_year = int(params.get("currentYear") or date.today().year)
    annual_expense = monthly_expense * 12
    years = _horizon_years(need, session, t)
    funds_year = int(need.get("fundsNeededYear") or need.get("targetYear") or (now_year + years if years else now_year))
    primary: dict[str, Any] = {
        "needId": hu_need_code(t),
        "totalNeed": total_need,
        "totalShortfall": shortfall,
        "taggedFundValue": tagged,
        "taggedAssetCurrentValue": tagged,
        "socialSecurity": 0,
    }
    meta: dict[str, Any] = {}
    if t == "N_RET":
        living = monthly_expense * lifestyle_rate(int(need.get("lifestyle") or 2)) * 12
        primary.update(
            {
                "retirementAge": age_of_retirement,
                "livingExpenses": living,
                "expectedLivingExpenseInTheCountry": living * 0.75,
                "durationOfRetirement": years_in_retirement(age_of_retirement, le),
                "numYearsToRetirement": max(0, age_of_retirement - age),
                "socialSecurityValue": 0,
            }
        )
        meta = {"livingExpenses": {PARTNER_ID: {}}}
    elif t in ("N_EDU", "N_SAV", "N_PRP"):
        save_years = years if years else max(0, funds_year - now_year)
        primary.update(
            {
                "fundsNeededYear": now_year + save_years,
                "numYearsToSave": save_years,
            }
        )
    elif t == "N_CRI":
        primary.update(
            {
                "livingExpenses": annual_expense,
                "numYearsIncomeNeeded": int(params["CRI_YEARS"]),
                "medicalCost": _user_amount(float(params["CRI_COST"]), fx),
                "proportionOfExpenses": 1,
            }
        )
        meta = {"livingExpenses": {PARTNER_ID: {}}}
    elif t == "N_TPD":
        primary.update(
            {
                "lumpSumNeeded": total_need,
                "existingLifeCover": existing or None,
                "medicalCost": _user_amount(float(params["TPD_COST"]), fx),
                "numYearsIncomeNeeded": int(params["TPD_YEARS"]),
            }
        )
        meta = {"lumpSumNeeded": {PARTNER_ID: {}}}
    elif t == "N_HOS":
        primary.update({"medicalCost": total_need, "proportionOfExpenses": 1})
    elif t == "N_PAC":
        primary.update(
            {
                "livingExpenses": annual_expense,
                "numYearsIncomeNeeded": int(params["PAC_YEARS"]),
                "medicalCost": _user_amount(float(params["PAC_COST"]), fx),
                "proportionOfExpenses": 1,
            }
        )
    elif t == "N_INC":
        primary.update({"lumpSumNeeded": total_need, "existingLifeCover": existing or None})
        meta = {"lumpSumNeeded": {PARTNER_ID: {}}}
    return {"primaryOutput": {PARTNER_ID: [primary]}, "metaOutput": meta}


def _asset(kind: str, value: float, rate: float, asset_id: str) -> dict[str, Any]:
    return {
        "type": kind,
        "currentValue": value,
        "interestRate": rate,
        "id": asset_id,
        "recurringContribution": {"value": 0, "frequency": 1, "duration": 0},
        "proportion": 1,
    }


def _session_assets(session: dict[str, Any]) -> list[dict[str, Any]]:
    cash = float(session.get("cash") or 0)
    investments = float(session.get("investments") or 0)
    cash_ret = session_rate(session, "interestRate")
    inv_ret = session_rate(session, "investmentReturn")
    return [
        _asset("A_SAV", cash, cash_ret, "A_SAV_Main"),
        _asset("A_INV", investments, inv_ret, "A_INV_Main"),
    ]


def _plans_off(session: dict[str, Any]) -> set[str]:
    return {str(t) for t in (session.get("plansOff") or [])}


def _budget_line(
    need: dict[str, Any],
    inv_ret: float,
    session: dict[str, Any],
    params: dict[str, Any],
    fx: FxLock,
) -> dict[str, Any]:
    t = need["type"]
    code = hu_need_code(t)
    off = t in _plans_off(session)
    plan_sum = (session.get("planSum") or {}).get(t)
    plan_prem = (session.get("planPrem") or {}).get(t)
    placeholder = _user_amount(float(params["placeholderNeedBudget"]), fx)
    step = nice_step(float(params["benefitRound"]), fx)
    if off:
        rec_benefit = 0.0
        budget = 0.0
    elif plan_sum is not None:
        rec_benefit = max(0.0, float(plan_sum or 0))
        budget = float(plan_prem if plan_prem is not None else placeholder)
    else:
        amount = float(need.get("needAmount") or 0)
        rec_benefit = max(0.0, round_half_up(amount / step, 0) * step) if step else max(0.0, amount)
        budget = float(need.get("annualPremium") or placeholder)
    return {
        "partnerId": PARTNER_ID,
        "goalId": code,
        "goalType": code,
        "productCode": PRODUCT_CODES.get(t, t),
        "paymentFrequency": "Monthly",
        "riders": [],
        "policyTerm": 10,
        "benefitAmount": rec_benefit,
        "paymentTerm": 10,
        "actualPolicyTerm": 15,
        "actualPaymentTerm": 10,
        "budget": budget,
        "gfr": 0.05,
        "growthRate": inv_ret if t in ACCUMULATION else 0,
    }


def build_happiu_payload(session: dict[str, Any]) -> dict[str, Any]:
    params = _params(session)
    fx = _fx(session)
    age = int(session.get("age") or 40)
    dob = session.get("dateOfBirth") or dob_from_age(age)
    gender = session.get("gender") or "Male"
    income = float(session.get("incomeMonthly") or 0)
    expense = float(session.get("expenseMonthly") or 0)
    ret_age = int(session.get("ageOfRetirement") or params.get("ageOfRetirement") or 65)
    inflation = session_rate(session, "inflationRate")
    income_grow = session_rate(session, "incomeGrowthRate")
    cash_ret = session_rate(session, "interestRate")
    inv_ret = session_rate(session, "investmentReturn")
    le = _life_expectancy(session, params)
    currency = session.get("currency") or fx.currency or "SGD"
    needs = [
        dict(n)
        for n in (session.get("needs") or [])
        if n.get("enabled") and n.get("type") in PROTECTION | ACCUMULATION
    ]
    apply_investment_pot(needs, float(session.get("investments") or 0))
    if not any(n.get("type") == "N_RET" for n in needs):
        needs = list(needs) + [
            {
                "type": "N_RET",
                "enabled": True,
                "needAmount": expense * 12 * years_in_retirement(ret_age, le),
                "priority": 5,
                "existingInvestment": 0,
            }
        ]

    calc: dict[str, Any] = {}
    by_type = {n["type"]: n for n in needs}
    for t, n in by_type.items():
        calc[hu_need_code(t)] = _calc_entry(n, expense, ret_age, age, session, params, fx, le)
    if "N_RET" not in calc:
        calc["N_RET"] = _calc_entry(
            {
                "type": "N_RET",
                "needAmount": expense * 12 * years_in_retirement(ret_age, le),
                "existingInvestment": 0,
            },
            expense,
            ret_age,
            age,
            session,
            params,
            fx,
            le,
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
                "lifeExpectancy": le,
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
                "assets": _session_assets(session),
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
            "planningCurrency": currency,
            "isIncomePayoutReqd": False,
            "totalMonthlyRegularIncome": income,
            "totalMonthlyRegularExpense": expense,
            "annualBudget": _user_amount(float(params["annualBudget"]), fx),
            "placeholderNeedBudget": _user_amount(float(params["placeholderNeedBudget"]), fx),
            "criMedicalCost": _user_amount(float(params["CRI_COST"]), fx),
            "tpdMedicalCost": _user_amount(float(params["TPD_COST"]), fx),
            "lifeExpectancy": le,
            "lifeExpectancyDefault": int(params["lifeExpectancyDefault"]),
            "numDependents": int(session.get("dependents") or 0),
            "inflationRate": inflation,
            "incomeGrowthRate": income_grow,
            "interestRate": cash_ret,
        },
        "solutionOptimizerOutput": {
            "packageCode": "P002",
            "segregatedBudget": [
                _budget_line(n, inv_ret, session, params, fx)
                for n in needs
                if n.get("type") not in _plans_off(session)
            ],
        },
        "needCalculatorOutput": calc,
        "soAllOutput": [],
    }

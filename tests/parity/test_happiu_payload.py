"""WP12: the HappiU payload against the HappiU tab fields GP sends."""

from __future__ import annotations

import pytest
from src.hu_payload import build_happiu_payload
from src.needs import CALCULATOR_NEEDS, PROTECTION_NEEDS

from tests.parity.conftest import load, personas

HORIZON = {
    "N_RET": "NC_yearsToRet",
    "N_EDU": "NC_eduYears",
    "N_SAV": "NC_savYears",
    "N_PRP": "NC_prpYears",
}


def session_of(case: dict) -> dict:
    plu = case["peopleLikeYou"]["values"]
    nc = case["needCalculator"]["values"]
    prof = case["needProfiler"]["values"]
    plan = case["plan"]["values"]
    inputs = case["inputs"]
    fx = case["fx"]["values"]
    needs = []
    for code in CALCULATOR_NEEDS:
        row = {
            "type": code,
            "enabled": bool(nc[f"NC_on_{code}"]),
            "needAmount": float(nc[f"NC_amount_{code}"]),
            "have": float(nc.get(f"NC_have_{code}") or 0),
            "priority": int(prof.get(f"NP_priority_{code}") or 3),
        }
        if code in HORIZON:
            row["contributeYears"] = int(nc[HORIZON[code]])
        if code == "N_INC":
            row["existingSumAssured"] = float(plu.get("PLU_lifeSum") or 0)
        needs.append(row)
    return {
        "age": int(plu["PLU_age"]),
        "gender": inputs.get("gender") or "Male",
        "country": inputs.get("country") or "Singapore",
        "currency": inputs.get("currency") or "SGD",
        "residency": inputs.get("residency") or "Citizen",
        "isSmoker": bool(inputs.get("is_smoker")),
        "incomeMonthly": float(plu["PLU_incomeMonthly"]),
        "expenseMonthly": float(plu["PLU_expenseMonthly"]),
        "cash": float(plu["PLU_cash"]),
        "investments": float(plu["PLU_investments"]),
        "dependents": int(plu["PLU_dependents"]),
        "lifeExpectancy": int(plu["PLU_leUsed"]),
        "ageOfRetirement": 65,
        "needs": needs,
        "planSum": {c: float(plan.get(f"PLAN_sum_{c}") or 0) for c in PROTECTION_NEEDS},
        "planPrem": {c: float(plan.get(f"PLAN_prem_{c}") or 0) for c in PROTECTION_NEEDS},
        "plansOff": [c for c in CALCULATOR_NEEDS if not plan.get(f"PLAN_included_{c}") and plan.get(f"PLAN_sug_{c}")],
        "fx": {
            "currency": inputs.get("currency") or "SGD",
            "usdPerLocal": float(fx["FX_usdPerLocal"]),
            "priceLevel": float(fx["FX_priceLevel"]),
        },
    }


def _primary(body: dict, code: str) -> dict:
    return next(iter(body["needCalculatorOutput"][code]["primaryOutput"].values()))[0]


@pytest.mark.parametrize("case_name", personas())
def test_payload_money_matches_the_happiu_tab(case_name):
    case = load(case_name)
    want = case["happiU"]["values"]
    body = build_happiu_payload(session_of(case))
    cd = body["commonDetails"]
    assert cd["criMedicalCost"] == pytest.approx(float(want["HU_medCost"]), rel=1e-6)
    assert cd["tpdMedicalCost"] == pytest.approx(float(want["HU_tpdCost"]), rel=1e-6)
    assert cd["lifeExpectancy"] == want["HU_leS"]
    assert cd["lifeExpectancyDefault"] == want["HU_defaultLE"]
    assert cd["totalMonthlyRegularIncome"] == pytest.approx(float(want["HU_income"]), abs=0.05)
    assert cd["totalMonthlyRegularExpense"] == pytest.approx(float(want["HU_expense"]), abs=0.05)
    assert round(cd["annualBudget"]) == 1500 or cd["planningCurrency"] != "SGD"


@pytest.mark.parametrize("case_name", personas())
def test_wealth_horizons_are_the_need_calculator_years(case_name):
    case = load(case_name)
    nc = case["needCalculator"]["values"]
    body = build_happiu_payload(session_of(case))
    calc = body["needCalculatorOutput"]
    for code, key in (("N_EDU", "NC_eduYears"), ("N_SAV", "NC_savYears"), ("N_PRP", "NC_prpYears")):
        if code not in calc:
            continue
        assert _primary(body, code)["numYearsToSave"] == int(nc[key])


@pytest.mark.parametrize("case_name", personas())
def test_funeral_lump_is_not_sent(case_name):
    body = build_happiu_payload(session_of(load(case_name)))
    for entry in body["needCalculatorOutput"].values():
        primary = next(iter(entry["primaryOutput"].values()))[0]
        assert "funeralExpense" not in primary


def test_n_pac_is_sent_when_it_is_on():
    case = load("scenarios/P03_PAC_LTC_on")
    body = build_happiu_payload(session_of(case))
    types = {n["type"] for n in body["personalDetails"][0]["needs"]}
    assert "N_PAC" in types
    assert "N_LTC" not in types
    assert "N_PAC" in body["needCalculatorOutput"]
    assert _primary(body, "N_PAC")["medicalCost"] > 0


def test_n_hos_keeps_the_model_code():
    case = load("personas/P03")
    body = build_happiu_payload(session_of(case))
    types = {n["type"] for n in body["personalDetails"][0]["needs"]}
    assert "N_HOS" in types
    assert "N_HSP" not in types
    assert "N_HOS" in body["needCalculatorOutput"]

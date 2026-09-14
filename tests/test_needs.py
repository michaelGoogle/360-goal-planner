"""Need calculator session seam and POST /v1/needs."""

from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient
from src.app import api
from src.pipeline.goal_math import (
    CI_COST,
    CI_YEARS,
    EDU_TOTAL_COST,
    life_support_years,
    pv_annuity_due,
)
from src.pipeline.need_calculator import evaluate_session


def _ret_session(*, ret_age: int, lifestyle: int = 2, existing: float = 154224) -> dict:
    return {
        "dateOfBirth": "1984-06-15",
        "age": 42,
        "incomeMonthly": 6800,
        "expenseMonthly": 4000,
        "cash": 70000,
        "investments": 84224,
        "inflationRate": 0.023,
        "investmentReturn": 0.035,
        "ageOfRetirement": ret_age,
        "dependents": 2,
        "needs": [
            {
                "type": "N_RET",
                "enabled": True,
                "retAge": ret_age,
                "lifestyle": lifestyle,
                "existing": existing,
            }
        ],
    }


def test_later_retirement_does_not_increase_shortfall():
    early = evaluate_session(_ret_session(ret_age=55))
    late = evaluate_session(_ret_session(ret_age=69))
    early_ret = next(n for n in early["needs"] if n["type"] == "N_RET")
    late_ret = next(n for n in late["needs"] if n["type"] == "N_RET")
    assert late_ret["needAmount"] < early_ret["needAmount"]
    assert late_ret["have"] > early_ret["have"]
    assert late_ret["gap"] < early_ret["gap"]
    assert late["ageOfRetirement"] == 69
    assert early_ret["contributeYears"] == 13
    assert late_ret["contributeYears"] == 27


def test_lifestyle_raises_retirement_need():
    stress = evaluate_session(_ret_session(ret_age=65, lifestyle=2))
    best = evaluate_session(_ret_session(ret_age=65, lifestyle=3))
    a = next(n for n in stress["needs"] if n["type"] == "N_RET")
    b = next(n for n in best["needs"] if n["type"] == "N_RET")
    assert b["needAmount"] > a["needAmount"]
    assert a["retIncomeMonthly"] == 4000
    assert b["retIncomeMonthly"] == 5000


def _goal_session(*types: str, **extra) -> dict:
    """Sample profile behind the Excel-aligned goldens: age 42, S$4,000/mo spend."""
    session = {
        "dateOfBirth": "1984-06-15",
        "age": 42,
        "incomeMonthly": 6800,
        "expenseMonthly": 4000,
        "mortgage": 200000,
        "dependents": 2,
        "cash": 0,
        "investments": 0,
        "needs": [{"type": t, "enabled": True, "existing": 0} for t in types],
    }
    session.update(extra)
    return session


def _amount(session: dict, need_type: str) -> float:
    return next(n["needAmount"] for n in evaluate_session(session)["needs"] if n["type"] == need_type)


def test_life_support_years_boundaries():
    assert life_support_years(25) == 25
    assert life_support_years(30) == 20
    assert life_support_years(42) == 10
    assert life_support_years(45) == 10


def test_protection_goldens_match_excel_shapes():
    """Excel `Input Output` C64 / C73 / C82 / C91 on the sample profile."""
    session = _goal_session("N_INC", "N_CRI", "N_TPD", "N_HOS")
    assert _amount(session, "N_INC") == 634401
    assert _amount(session, "N_CRI") == 440363
    assert _amount(session, "N_TPD") == 593390
    assert _amount(session, "N_HOS") == 40800


def test_life_cover_is_spend_based_plus_liabilities_and_bequest():
    session = _goal_session("N_INC")
    base = _amount(session, "N_INC")
    session["needs"][0]["bequest"] = 100000
    assert _amount(session, "N_INC") == base + 100000
    session["needs"][0]["bequest"] = 0
    session["needs"][0]["liabilities"] = 0
    assert _amount(session, "N_INC") == base - 200000


def test_hospitalisation_is_six_months_of_income():
    session = _goal_session("N_HOS", incomeMonthly=10000)
    assert _amount(session, "N_HOS") == 60000


def test_disability_no_longer_mirrors_life_cover():
    session = _goal_session("N_INC", "N_TPD")
    assert _amount(session, "N_TPD") != _amount(session, "N_INC")


def test_education_inflates_single_cost_to_target_year():
    year = date.today().year
    near = _goal_session("N_EDU")
    near["needs"][0]["targetYear"] = year + 10
    far = _goal_session("N_EDU")
    far["needs"][0]["targetYear"] = year + 15
    a = _amount(near, "N_EDU")
    b = _amount(far, "N_EDU")
    assert a == 94149
    assert b == round(EDU_TOTAL_COST * 1.023**15)
    assert b > a


def test_needs_endpoint_returns_have_and_gap():
    client = TestClient(api)
    r = client.post("/v1/needs", json=_ret_session(ret_age=65))
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    by_type = {n["type"]: n for n in body["session"]["needs"]}
    ret = by_type["N_RET"]
    assert ret["needAmount"] > 0
    assert ret["have"] > 0
    assert ret["gap"] == max(0, ret["needAmount"] - ret["have"])
    assert ret["lifestyle"] == 2
    assert body["session"]["ageOfRetirement"] == 65
    cri = by_type["N_CRI"]
    real = (1 + 0.035) / (1 + 0.023) - 1
    assert cri["needAmount"] == round(pv_annuity_due(6800 * 12, real, CI_YEARS) + CI_COST)
    hos = by_type["N_HOS"]
    assert hos["needAmount"] == 6 * 6800


def test_retirement_contribution_raises_have_not_need():
    base = evaluate_session(_ret_session(ret_age=65))
    extra = _ret_session(ret_age=65)
    extra["needs"][0]["monthlyContribution"] = 500
    with_c = evaluate_session(extra)
    a = next(n for n in base["needs"] if n["type"] == "N_RET")
    b = next(n for n in with_c["needs"] if n["type"] == "N_RET")
    assert a["needAmount"] == b["needAmount"]
    assert b["have"] > a["have"]
    assert b["gap"] < a["gap"]


def test_retirement_existing_excludes_cpf():
    session = _ret_session(ret_age=65)
    session["cpfOa"] = 999_999
    session["cpfSa"] = 999_999
    del session["needs"][0]["existing"]
    ret = next(n for n in evaluate_session(session)["needs"] if n["type"] == "N_RET")
    assert ret["existing"] == 70_000 + 84_224

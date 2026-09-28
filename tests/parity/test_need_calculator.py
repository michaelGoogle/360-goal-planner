"""WP8: the Need Calculator against the Need Calculator tab, for all fifty personas."""

from __future__ import annotations

import pytest
from src.needs import CALCULATOR_NEEDS
from src.services.need_calculator import service
from src.services.need_calculator.models import GoalInputs, NeedCalculatorRequest

from tests.parity.conftest import load, personas

USD_TOLERANCE = 0.5
USER_TOLERANCE = 1


def request_of(case: dict) -> NeedCalculatorRequest:
    plu = case["peopleLikeYou"]["values"]
    fx = case["fx"]["values"]
    rate = float(fx["FX_usdPerLocal"])
    return NeedCalculatorRequest(
        age=int(plu["PLU_age"]),
        ageOfRetirement=65,
        lifeExpectancy=int(plu["PLU_leUsed"]),
        incomeMonthlyUsd=float(plu["PLU_incomeMonthly"]) * rate,
        expenseMonthlyUsd=float(plu["PLU_expenseMonthly"]) * rate,
        investmentsUsd=float(plu["PLU_investments"]) * rate,
        mortgageUsd=float(plu["PLU_mortgage"]) * rate,
        existingCoverUsd={"N_INC": float(plu["PLU_lifeSum"]) * rate},
        inputs={"N_RET": GoalInputs(lifestyle=2, retAge=65)},
        inflationRate=0.023,
        investmentReturn=0.042,
        priceLevel=float(fx["FX_priceLevel"]),
    )


@pytest.mark.parametrize("case_name", personas())
def test_horizons_match_the_workbook(case_name):
    from src.services.config.service import default_horizon_years, values as param_values

    case = load(case_name)
    want = case["needCalculator"]["values"]
    age = int(case["peopleLikeYou"]["values"]["PLU_age"])
    params = param_values("")
    got = service.calculate(request_of(case)).horizons
    assert got.yearsToRet == want["NC_yearsToRet"]
    assert got.yearsInRet == want["NC_yearsInRet"]
    assert got.eduYears == want["NC_eduYears"]
    # V0-26 floors: fixtures still record the V0-24 1-year cliff for SAV/PRP.
    assert got.savYears == default_horizon_years(age, "N_SAV", params)
    assert got.prpYears == default_horizon_years(age, "N_PRP", params)
    assert got.careYears == want["NC_careYears"]


@pytest.mark.parametrize("case_name", personas())
def test_usd_amounts_match_the_workbook(case_name):
    case = load(case_name)
    want = case["needCalculator"]["values"]
    by_type = {n.type: n for n in service.calculate(request_of(case)).needs}
    for code in CALCULATOR_NEEDS:
        assert by_type[code].needAmountUsd == pytest.approx(want[f"NC_amountUSD_{code}"], abs=USD_TOLERANCE), code
        assert by_type[code].gapUsd == pytest.approx(want[f"NC_gapUSD_{code}"], abs=USD_TOLERANCE), code


@pytest.mark.parametrize("case_name", personas())
def test_user_currency_amounts_match_the_workbook(case_name):
    """The orchestrator rounds in the user currency the way the tab does: ROUND(usd / rate)."""
    from src.money import round_half_up

    case = load(case_name)
    want = case["needCalculator"]["values"]
    rate = float(case["fx"]["values"]["FX_usdPerLocal"])
    by_type = {n.type: n for n in service.calculate(request_of(case)).needs}
    for code in CALCULATOR_NEEDS:
        amount = round_half_up(by_type[code].needAmountUsd / rate, 0)
        gap = round_half_up(by_type[code].gapUsd / rate, 0)
        assert amount == pytest.approx(want[f"NC_amount_{code}"], abs=USER_TOLERANCE), code
        assert gap == pytest.approx(want[f"NC_gap_{code}"], abs=USER_TOLERANCE), f"gap {code}"


@pytest.mark.parametrize("case_name", personas())
def test_the_longevity_block_matches_the_workbook(case_name):
    case = load(case_name)
    want = case["needCalculator"]["values"]
    rate = float(case["fx"]["values"]["FX_usdPerLocal"])
    lon = service.calculate(request_of(case)).stress["R_LON"]
    from src.money import round_half_up

    assert lon.yearsInRetirement == want["NC_lonYearsInRet"]
    assert round_half_up(lon.needAmountUsd["N_RET"] / rate, 0) == pytest.approx(
        want["NC_lonAmount_N_RET"], abs=USER_TOLERANCE
    )
    assert round_half_up(lon.needAmountUsd["N_LTC"] / rate, 0) == pytest.approx(
        want["NC_lonAmount_N_LTC"], abs=USER_TOLERANCE
    )


def test_personal_accident_is_one_year_of_income_plus_the_treatment_cost():
    from src.pipeline.goal_math import pv_annuity_due, real_return
    from src.services.config import service as config

    params = config.values("")
    rate = real_return(0.042, 0.023)
    income = 5000.0
    req = NeedCalculatorRequest(age=40, incomeMonthlyUsd=income, expenseMonthlyUsd=3000)
    got = next(n for n in service.calculate(req).needs if n.type == "N_PAC")
    expect = pv_annuity_due(income * 12, rate, int(params["PAC_YEARS"])) + float(params["PAC_COST"])
    assert got.needAmountUsd == pytest.approx(expect, abs=0.01)


def test_long_term_care_is_the_nursing_home_cost_from_start_age_to_life_expectancy():
    from src.pipeline.goal_math import pv_annuity_due, real_return
    from src.services.config import service as config

    params = config.values("")
    rate = real_return(0.042, 0.023)
    req = NeedCalculatorRequest(age=34, lifeExpectancy=88, inputs={"N_LTC": GoalInputs(ltcStartAge=80)})
    got = next(n for n in service.calculate(req).needs if n.type == "N_LTC")
    expect = pv_annuity_due(float(params["LTC_COST"]), rate, 8)
    assert got.needAmountUsd == pytest.approx(expect, abs=0.01)
    assert service.calculate(req).horizons.careYears == 8


def test_a_cheaper_country_shrinks_the_treatment_lump_not_the_income_replacement():
    base = NeedCalculatorRequest(age=34, incomeMonthlyUsd=5578, expenseMonthlyUsd=3236, priceLevel=1.0)
    cheap = base.model_copy(update={"priceLevel": 0.4602})
    base_n = {n.type: n for n in service.calculate(base).needs}
    cheap_n = {n.type: n for n in service.calculate(cheap).needs}
    assert cheap_n["N_HOS"].needAmountUsd == pytest.approx(base_n["N_HOS"].needAmountUsd)
    assert cheap_n["N_CRI"].needAmountUsd < base_n["N_CRI"].needAmountUsd
    assert cheap_n["N_EDU"].needAmountUsd == pytest.approx(base_n["N_EDU"].needAmountUsd * 0.4602, rel=1e-6)


def test_education_defaults_to_the_year_the_customer_turns_fifty():
    """P03 is 34: 16 years to 50. Savings still has 6 years to 40; property floors at 3."""
    got = service.calculate(NeedCalculatorRequest(age=34))
    assert got.horizons.eduYears == 16
    assert got.horizons.savYears == 6
    assert got.horizons.prpYears == 3


def test_already_older_than_the_target_age_keeps_the_savings_and_property_floors():
    got = service.calculate(NeedCalculatorRequest(age=66))
    assert got.horizons.eduYears == 1
    assert got.horizons.savYears == 5
    assert got.horizons.prpYears == 3


def test_the_vietnamese_persona_matches_its_fixture():
    case = load("scenarios/P03_VND_Vietnam")
    want = case["needCalculator"]["values"]
    got = {n.type: n for n in service.calculate(request_of(case)).needs}
    assert got["N_CRI"].needAmountUsd == pytest.approx(want["NC_amountUSD_N_CRI"], abs=USD_TOLERANCE)
    assert got["N_INC"].needAmountUsd == pytest.approx(want["NC_amountUSD_N_INC"], abs=USD_TOLERANCE)


def test_the_route_answers_the_contract():
    from fastapi.testclient import TestClient

    from src.app import api

    response = TestClient(api).post("/v1/need-calculator", json={"age": 40, "incomeMonthlyUsd": 4000})
    assert response.status_code == 200
    data = response.json()
    assert {n["type"] for n in data["needs"]} == set(CALCULATOR_NEEDS)
    assert "R_LON" in data["stress"]

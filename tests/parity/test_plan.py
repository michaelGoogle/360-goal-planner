"""WP10: the Plan service against the Plan Calculator tab."""

from __future__ import annotations

import pytest
from src.needs import CALCULATOR_NEEDS, PROTECTION_NEEDS, WEALTH_NEEDS
from src.services.plan import service
from src.services.plan.models import PlanNeedInput, PlanRequest

from tests.parity.conftest import load, personas

HORIZON = {
    "N_RET": "NC_yearsToRet",
    "N_EDU": "NC_eduYears",
    "N_SAV": "NC_savYears",
    "N_PRP": "NC_prpYears",
}


def request_of(case: dict) -> PlanRequest:
    plu = case["peopleLikeYou"]["values"]
    nc = case["needCalculator"]["values"]
    inputs = case["inputs"]
    needs = []
    for code in CALCULATOR_NEEDS:
        needs.append(
            PlanNeedInput(
                type=code,
                enabled=bool(nc[f"NC_on_{code}"]),
                needAmount=float(nc[f"NC_amount_{code}"]),
                have=float(nc.get(f"NC_have_{code}") or 0),
                gap=float(nc[f"NC_gap_{code}"]),
                horizonYears=int(nc[HORIZON[code]]) if code in HORIZON else None,
            )
        )
    return PlanRequest(
        age=int(plu["PLU_age"]),
        gender=inputs.get("gender") or "Male",
        country=inputs.get("country") or "Singapore",
        currency=inputs.get("currency") or "SGD",
        takeHomeMonthly=float(plu["PLU_takeHome"]),
        expenseMonthly=float(plu["PLU_expenseMonthly"]),
        needs=needs,
    )


@pytest.mark.parametrize("case_name", personas())
def test_suggested_flags_match_the_workbook(case_name):
    case = load(case_name)
    want = case["plan"]["values"]
    got = {n.type: n for n in service.build_plan(request_of(case)).needs}
    for code in CALCULATOR_NEEDS:
        assert got[code].suggested is bool(want[f"PLAN_sug_{code}"]), code
        assert got[code].included is bool(want[f"PLAN_included_{code}"]), code


@pytest.mark.parametrize("case_name", personas())
def test_protection_sums_and_premiums_match_the_workbook(case_name):
    case = load(case_name)
    want = case["plan"]["values"]
    got = {n.type: n for n in service.build_plan(request_of(case)).needs}
    for code in PROTECTION_NEEDS:
        assert got[code].planSum == pytest.approx(float(want.get(f"PLAN_sum_{code}") or 0), abs=1), code
        assert got[code].planPrem == pytest.approx(float(want.get(f"PLAN_prem_{code}") or 0), abs=1), code


@pytest.mark.parametrize("case_name", personas())
def test_wealth_contributions_match_the_workbook(case_name):
    case = load(case_name)
    want = case["plan"]["values"]
    result = service.build_plan(request_of(case))
    got = {n.type: n for n in result.needs}
    for code in WEALTH_NEEDS:
        assert got[code].planMth == pytest.approx(float(want.get(f"PLAN_mth_{code}") or 0), abs=1), code
        assert got[code].planLump == pytest.approx(float(want.get(f"PLAN_lump_{code}") or 0), abs=1), code
    assert result.investMth == pytest.approx(float(want["PLAN_investMth"]), abs=1)
    assert result.investLump == pytest.approx(float(want["PLAN_investLump"]), abs=1)
    assert result.protPremYear == pytest.approx(float(want["PLAN_protPremYr"]), abs=1)


def test_p06_default_plan_fits_inside_the_free_budget():
    """Share is rounded down, then capped: P06 lands at 1,500 against a free 1,693."""
    case = load("personas/P06")
    result = service.build_plan(request_of(case))
    assert result.investMth == case["plan"]["values"]["PLAN_investMth"]
    free = case["budget"]["values"]["free (50%)"]
    monthly = result.investMth + result.protPremYear / 12
    assert monthly <= free + 1


def test_a_touched_monthly_contribution_is_not_reseeded():
    req = request_of(load("personas/P03"))
    for need in req.needs:
        if need.type == "N_RET":
            need.touchedMth = True
            need.planMth = 99
    got = next(n for n in service.build_plan(req).needs if n.type == "N_RET")
    assert got.planMth == 99


def test_plans_off_keeps_the_need_suggested_but_not_included():
    req = request_of(load("personas/P03"))
    req.plansOff = ["N_RET"]
    got = {n.type: n for n in service.build_plan(req).needs}
    assert got["N_RET"].suggested is True
    assert got["N_RET"].included is False
    assert got["N_RET"].planMth > 0

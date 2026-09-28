"""WP11: the Budget service against the Budget Calculator tab."""

from __future__ import annotations

import pytest
from src.services.budget import service
from src.services.budget.models import BudgetRequest
from src.services.plan import service as plan_service

from tests.parity.conftest import load, personas
from tests.parity.test_plan import request_of as plan_request


def request_of(case: dict) -> BudgetRequest:
    plu = case["peopleLikeYou"]["values"]
    plan = plan_service.build_plan(plan_request(case))
    included_prem = sum(n.planPrem for n in plan.needs if n.included and n.planPrem)
    return BudgetRequest(
        takeHomeMonthly=float(plu["PLU_takeHome"]),
        expenseMonthly=float(plu["PLU_expenseMonthly"]),
        investments=float(plu["PLU_investments"]),
        includedPremiumsYear=included_prem,
        investMth=plan.investMth,
        investLump=plan.investLump,
        currency=case["inputs"].get("currency") or "SGD",
    )


@pytest.mark.parametrize("case_name", personas())
def test_budget_matches_the_workbook(case_name):
    case = load(case_name)
    want = case["budget"]["values"]
    got = service.budget(request_of(case))
    assert got.available == pytest.approx(float(want["available"]), abs=0.05)
    assert got.free == pytest.approx(float(want["free (50%)"]), abs=1)
    assert got.monthly == pytest.approx(float(want["monthly"]), abs=1)
    assert got.monthlyOver == pytest.approx(float(want["monthlyOver"]), abs=1)
    assert got.lumps == pytest.approx(float(want["lumps"]), abs=1)
    assert got.lumpOver == pytest.approx(float(want["lumpOver"]), abs=1)


@pytest.mark.parametrize("case_name", personas())
def test_the_default_plan_never_overspends_the_free_budget(case_name):
    got = service.budget(request_of(load(case_name)))
    assert got.monthlyOver <= 0


def test_the_route_answers_the_contract():
    from fastapi.testclient import TestClient

    from src.app import api

    response = TestClient(api).post(
        "/v1/budget",
        json={"takeHomeMonthly": 5712, "expenseMonthly": 4141.2, "includedPremiumsYear": 380, "investMth": 700},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["free"] == 785
    assert data["monthlyOver"] < 0

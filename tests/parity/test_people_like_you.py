"""WP5: People Like You against the workbook's tab, all 50 personas.

The LLM income comes from the fixture rather than being generated, so what is under
test is everything that follows from it.
"""

from __future__ import annotations

import pytest
from src.money import nice_step, to_user
from src.services.fx.client import SnapshotFxClient
from src.services.people_like_you import service as plu

from tests.parity.conftest import load, parameters, personas


def _lock(inputs: dict):
    return SnapshotFxClient().lock(
        inputs.get("currency") or "SGD", inputs.get("country") or "Singapore"
    )


def _derive(doc: dict):
    inputs = doc["inputs"]
    return plu.derive(
        income_monthly=float(inputs["income"]),
        age=int(inputs["age"]),
        dependents=int(inputs["dependents"] or 0),
        residency=inputs.get("residency"),
        country=inputs.get("country") or "Singapore",
        currency=inputs.get("currency") or "SGD",
        owns_property=bool(inputs.get("property")),
        reported_life_expectancy=inputs.get("life_expectancy"),
        fx=_lock(inputs),
    )


@pytest.mark.parametrize("case", personas())
def test_income_expense_and_take_home_equal_the_tab(case):
    doc = load(case)
    want = doc["peopleLikeYou"]["values"]
    got = _derive(doc)
    assert got.incomeMonthly == pytest.approx(want["PLU_incomeMonthly"], abs=0.5)
    assert got.takeHomeMonthly == pytest.approx(want["PLU_takeHome"], abs=0.5)
    assert got.expenseMonthly == pytest.approx(want["PLU_expenseMonthly"], abs=0.5)


@pytest.mark.parametrize("case", personas())
def test_the_asset_split_equals_the_tab(case):
    doc = load(case)
    want = doc["peopleLikeYou"]["values"]
    got = _derive(doc)
    assert got.cash == pytest.approx(want["PLU_cash"], abs=1)
    assert got.investments == pytest.approx(want["PLU_investments"], abs=1)
    assert got.liabilities == pytest.approx(want["PLU_liabilities"], abs=1)


@pytest.mark.parametrize("case", personas())
def test_the_home_seed_equals_the_tab(case):
    doc = load(case)
    want = doc["peopleLikeYou"]["values"]
    got = _derive(doc)
    assert got.property == pytest.approx(want["PLU_property"], abs=1)
    assert got.mortgage == pytest.approx(want["PLU_mortgage"], abs=1)


@pytest.mark.parametrize("case", personas())
def test_the_assumed_life_cover_equals_the_tab(case):
    doc = load(case)
    want = doc["peopleLikeYou"]["values"]
    got = _derive(doc)
    sum_assured = got.policies[0].sum if got.policies else 0
    premium = got.policies[0].premium if got.policies else 0
    assert sum_assured == pytest.approx(want["PLU_lifeSum"], abs=1)
    assert premium == pytest.approx(want["PLU_lifePrem"], abs=1)


@pytest.mark.parametrize("case", personas())
def test_the_life_expectancy_used_equals_the_tab(case):
    doc = load(case)
    assert _derive(doc).lifeExpectancy == doc["peopleLikeYou"]["values"]["PLU_leUsed"]


# --- what WP5 added ----------------------------------------------------------


def test_the_life_cover_step_is_a_hundred_thousand_in_singapore():
    """The old code hard-coded S$100,000; it now falls out of a USD parameter."""
    params = parameters()
    step = nice_step(float(params["lifeRoundUnit"]["value"]), SnapshotFxClient().lock("SGD", "Singapore"))
    assert step == 100_000


def test_the_life_cover_step_is_a_round_number_in_dong():
    step = nice_step(
        float(parameters()["lifeRoundUnit"]["value"]),
        SnapshotFxClient().lock("VND", "Vietnam"),
    )
    assert step == 2_000_000_000


def test_the_expense_floor_is_a_hundred_dollars_worth():
    fx = SnapshotFxClient().lock("SGD", "Singapore")
    floor = plu.expense_floor(fx, {"MIN_EXPENSE_MONTHLY": 100})
    assert floor == pytest.approx(100 / fx.usdPerLocal, abs=0.005)
    assert floor == 127.94


def test_the_expense_floor_applies_when_spend_would_round_to_nothing():
    fx = SnapshotFxClient().lock("SGD", "Singapore")
    got = plu.derive(
        income_monthly=10.0, age=30, dependents=0, residency="Citizen",
        country="Singapore", currency="SGD", owns_property=False, fx=fx,
    )
    assert got.expenseMonthly == pytest.approx(plu.expense_floor(fx, {"MIN_EXPENSE_MONTHLY": 100}))


def test_no_income_means_no_floor():
    """Someone with no income has no spend to floor; inventing one would be a fiction."""
    fx = SnapshotFxClient().lock("SGD", "Singapore")
    got = plu.derive(
        income_monthly=0.0, age=30, dependents=0, residency="Citizen",
        country="Singapore", currency="SGD", owns_property=False, fx=fx,
    )
    assert got.expenseMonthly == 0.0


def test_the_home_seed_costs_less_in_a_cheaper_country():
    """The bands are USD; a Vietnamese home is not a Singapore home at the market rate."""
    sgd = SnapshotFxClient().lock("SGD", "Singapore")
    vnd = SnapshotFxClient().lock("VND", "Vietnam")
    params = {k: v["value"] for k, v in parameters().items()}
    in_sgd = plu.property_seed(50_000, sgd, params)
    in_vnd = plu.property_seed(500_000_000, vnd, params)
    assert to_user(0, sgd) == 0
    assert in_vnd * vnd.usdPerLocal < in_sgd * sgd.usdPerLocal


def test_a_life_expectancy_above_the_cap_is_capped():
    assert plu.life_expectancy(140, {"LON_AGE": 99, "lifeExpectancyDefault": 85}) == 99


def test_an_unusable_life_expectancy_falls_back_to_the_default():
    for reported in (None, "", "unknown", 0, -5):
        assert plu.life_expectancy(reported, {"LON_AGE": 99, "lifeExpectancyDefault": 85}) == 85

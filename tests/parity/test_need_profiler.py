"""WP7: the Need Profiler against the Need Profiler tab, for all fifty personas.

The fixtures carry the option weights and the raw scores as well as the picks, so a
failure says which factor disagreed rather than only that a need was picked wrongly.
"""

from __future__ import annotations

import pytest
from src.needs import CALCULATOR_NEEDS, NEED_PROFILER_LABEL, PARKED_NEEDS
from src.services.need_profiler import service
from src.services.need_profiler.models import NeedProfilerRequest

from tests.parity.conftest import load, personas

SCORE_TOLERANCE = 0.05
WEIGHT_TOLERANCE = 1e-9


def request_of(case: dict) -> NeedProfilerRequest:
    """Build the request from the workbook's own inputs to the Need Profiler tab."""
    plu = case["peopleLikeYou"]["values"]
    fx = case["fx"]["values"]
    inputs = case["inputs"]
    return NeedProfilerRequest(
        age=int(plu["PLU_age"]),
        dependents=int(plu["PLU_dependents"] or 0),
        gender=inputs.get("gender") or "",
        ownsProperty=bool(plu["PLU_ownsProperty"]),
        incomeMonthlyUsd=float(plu["PLU_incomeMonthly"]) * float(fx["FX_usdPerLocal"]),
        expenseMonthlyUsd=float(plu["PLU_expenseMonthly"]) * float(fx["FX_usdPerLocal"]),
        liquidAssetsUsd=(float(plu["PLU_cash"]) + float(plu["PLU_investments"]))
        * float(fx["FX_usdPerLocal"]),
        liabilitiesUsd=float(plu["PLU_liabilities"]) * float(fx["FX_usdPerLocal"]),
        priceLevel=float(fx["FX_priceLevel"]),
        flags={
            "occupation": inputs.get("occupation"),
            "isSmoker": bool(inputs.get("is_smoker")),
            "hospitalType": inputs.get("hospitalization_type"),
            "wardType": inputs.get("ward_type"),
            "retirementLifestyle": inputs.get("retirement_lifestyle"),
            "sports": inputs.get("sports"),
        },
    )


@pytest.mark.parametrize("case_name", personas())
def test_the_option_weights_match_the_workbook(case_name):
    case = load(case_name)
    expected = case["needProfiler"]["optionWeights"]
    result = service.profile(request_of(case))
    for key, want in expected.items():
        assert result.optionWeights[key] == pytest.approx(want, rel=1e-9, abs=WEIGHT_TOLERANCE), key


@pytest.mark.parametrize("case_name", personas())
def test_the_raw_scores_match_the_workbook(case_name):
    case = load(case_name)
    result = service.profile(request_of(case))
    for key, want in case["needProfiler"]["raw"].items():
        label = key.removeprefix("raw ")
        label = {"TPD": "Disability"}.get(label, label)
        assert result.raw[label] == pytest.approx(want, abs=0.005), key


@pytest.mark.parametrize("case_name", personas())
def test_the_scaled_scores_match_the_workbook(case_name):
    case = load(case_name)
    result = service.profile(request_of(case))
    for key, want in case["needProfiler"]["scaled"].items():
        label = key.removeprefix("scaled ")
        label = {"TPD": "Disability"}.get(label, label)
        assert result.scaled[label] == pytest.approx(want, abs=SCORE_TOLERANCE), key


@pytest.mark.parametrize("case_name", personas())
def test_the_picks_match_the_workbook(case_name):
    case = load(case_name)
    values = case["needProfiler"]["values"]
    result = service.profile(request_of(case))
    assert result.picks["prot1"] == values["NP_prot1"]
    assert result.picks["prot2"] == values["NP_prot2"]
    assert result.picks["grow2"] == values["NP_grow2"]


@pytest.mark.parametrize("case_name", personas())
def test_the_needs_switched_on_match_the_workbook(case_name):
    case = load(case_name)
    values = case["needProfiler"]["values"]
    result = service.profile(request_of(case))
    by_type = {need.type: need for need in result.needs}
    for code in CALCULATOR_NEEDS:
        assert by_type[code].enabled is bool(values[f"NP_on_{code}"]), code


@pytest.mark.parametrize("case_name", personas())
def test_the_priorities_match_the_workbook(case_name):
    case = load(case_name)
    values = case["needProfiler"]["values"]
    result = service.profile(request_of(case))
    by_type = {need.type: need for need in result.needs}
    for code in CALCULATOR_NEEDS + PARKED_NEEDS:
        assert by_type[code].priority == values[f"NP_priority_{code}"], code


@pytest.mark.parametrize("case_name", personas())
def test_the_parked_scores_match_the_workbook(case_name):
    case = load(case_name)
    values = case["needProfiler"]["values"]
    result = service.profile(request_of(case))
    for code in PARKED_NEEDS:
        assert result.scores[code] == pytest.approx(values[f"NP_score_{code}"], abs=SCORE_TOLERANCE)


# --- what WP7 changed, stated once -------------------------------------------


def test_farewell_is_not_scored():
    case = load(personas()[0])
    result = service.profile(request_of(case))
    assert len(result.raw) == 11
    assert "Farewell" not in result.raw


def test_a_cheaper_country_scores_a_salary_as_if_it_were_richer():
    """The whole point of PPP-USD: 5,000 VND a month is not a Singapore salary."""
    base = NeedProfilerRequest(age=40, incomeMonthlyUsd=3908.0, priceLevel=1.0)
    cheap = base.model_copy(update={"priceLevel": 0.4602})
    assert service.option_weights(base)["Income"] == 2.0
    assert service.option_weights(cheap)["Income"] == 1.0


def test_the_price_level_divides_rather_than_multiplies():
    assert service.ppp_usd(1000.0, 0.4602) == pytest.approx(2172.97, abs=0.01)


def test_a_missing_price_level_is_treated_as_one():
    assert service.ppp_usd(1000.0, 0) == 1000.0


@pytest.mark.parametrize(
    ("word", "weight"),
    [("Basic", 1.0), ("frugal", 1.0), ("Comfortable", 2.0), ("stress-free", 2.0),
     ("Luxurious", 4.0), ("only the best", 4.0)],
)
def test_the_lifestyle_words_of_people_like_you_now_score(word, weight):
    req = NeedProfilerRequest(age=40, flags={"retirementLifestyle": word})
    assert service.option_weights(req)["Lifestyle"] == weight


@pytest.mark.parametrize(
    ("word", "weight"), [("Single", 3.0), ("A", 3.0), ("Double", 2.0), ("Ward", 2.0), ("B", 2.0)]
)
def test_the_ward_words_of_people_like_you_now_score(word, weight):
    req = NeedProfilerRequest(age=40, flags={"wardType": word})
    assert service.option_weights(req)["Ward Type"] == weight


@pytest.mark.parametrize(
    ("answer", "weight"),
    [("I love scuba diving", 4.0), ("Adventurous", 4.0), ("rock climbing", 4.0),
     ("I dont do sports", 0.0), ("none", 0.0), ("", 0.0), ("running", 1.0), ("yoga", 1.0),
     ("golf", 1.0)],
)
def test_the_sports_answer_now_scores(answer, weight):
    req = NeedProfilerRequest(age=40, flags={"sports": answer})
    assert service.option_weights(req)["Sports"] == weight


def test_the_protection_tie_break_follows_the_label_order():
    scaled = dict.fromkeys(NEED_PROFILER_LABEL.values(), 5.0)
    assert service.pick_protection(scaled) == ("N_INC", "N_CRI")


def test_personal_accident_can_win_the_protection_pick():
    scaled = dict.fromkeys(NEED_PROFILER_LABEL.values(), 1.0)
    scaled["Personal Accident"] = 9.0
    assert service.pick_protection(scaled)[0] == "N_PAC"


def test_education_wins_the_growth_tie():
    assert service.pick_growth({"Education": 4.0, "General Savings": 4.0}) == "N_EDU"


def test_a_home_owner_no_longer_has_savings_swapped_for_a_home_purchase():
    """V0-16 separated home purchase from home protection; N_PRP has no label."""
    owner = NeedProfilerRequest(age=40, ownsProperty=True, incomeMonthlyUsd=5000)
    by_type = {need.type: need for need in service.profile(owner).needs}
    assert by_type["N_PRP"].enabled is False
    assert by_type["N_LTC"].enabled is False


def test_retirement_is_always_on():
    result = service.profile(NeedProfilerRequest(age=30))
    assert next(n for n in result.needs if n.type == "N_RET").enabled is True


def test_the_parked_needs_are_scored_but_never_on():
    result = service.profile(NeedProfilerRequest(age=45, incomeMonthlyUsd=4000))
    parked = [need for need in result.needs if need.parked]
    assert [need.type for need in parked] == list(PARKED_NEEDS)
    for need in parked:
        assert need.enabled is False
        assert need.score is not None


def test_a_need_with_no_label_has_no_score_and_a_normal_priority():
    result = service.profile(NeedProfilerRequest(age=45))
    by_type = {need.type: need for need in result.needs}
    for code in ("N_PRP", "N_LTC"):
        assert by_type[code].score is None
        assert by_type[code].priority == 3


def test_priority_is_five_above_seven_and_three_otherwise():
    assert service.priority(7.1) == 5
    assert service.priority(7.0) == 3
    assert service.priority(0.0) == 3
    assert service.priority(None) == 3


def test_every_score_is_zero_when_no_factor_separates_the_needs():
    """The workbook forces the divisor to 1, so the numerator decides: all zero."""
    assert service.scale(dict.fromkeys(("a", "b"), 4.0)) == {"a": 0.0, "b": 0.0}


def test_the_fallback_enables_four_needs_and_says_so():
    result = service.fallback(age=40, dependents=0, owns_property=True)
    assert result.fallback is True
    on = {need.type for need in result.needs if need.enabled}
    assert on == {"N_INC", "N_CRI", "N_RET", "N_SAV"}


def test_the_fallback_swaps_savings_for_education_when_there_are_dependants():
    on = {n.type for n in service.fallback(40, 2, False).needs if n.enabled}
    assert on == {"N_INC", "N_CRI", "N_RET", "N_EDU"}


def test_the_route_answers_the_contract():
    from fastapi.testclient import TestClient

    from src.app import api

    body = {"age": 40, "dependents": 1, "incomeMonthlyUsd": 4000, "expenseMonthlyUsd": 2400}
    response = TestClient(api).post("/v1/need-profiler", json=body)
    assert response.status_code == 200
    data = response.json()
    assert set(data["picks"]) == {"prot1", "prot2", "grow2"}
    assert len(data["needs"]) == len(CALCULATOR_NEEDS) + len(PARKED_NEEDS)
    assert data["fallback"] is False


def test_the_fixtures_cover_fifty_personas():
    assert len(personas()) == 50

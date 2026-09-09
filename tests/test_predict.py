from unittest.mock import patch

from fastapi.testclient import TestClient
from src.app import api
from src.cpf import expenses_from_gross
from src.predict import _apply_plu, _assumed_life_policy, seed_property_value
from src.upstream import UpstreamError


def test_predict_errors_when_people_like_you_down():
    client = TestClient(api)
    with patch("src.app.fm_public", side_effect=UpstreamError(503, "down")):
        r = client.post("/v1/predict", json={"age": 42, "occupation": "CEO"})
    assert r.status_code == 503
    assert "360-PeopleLikeU" in r.json()["detail"]


def test_predict_errors_when_people_like_you_returns_failure():
    client = TestClient(api)

    def fake(path, body, authorization):  # noqa: ARG001
        if path == "people-like-you":
            return 200, {"success": False, "detail": "missing key"}
        return 200, {}

    with patch("src.app.fm_public", side_effect=fake):
        r = client.post("/v1/predict", json={"age": 42, "occupation": "CEO"})
    assert r.status_code == 503
    assert "360-PeopleLikeU" in r.json()["detail"]


def test_predict_uses_fm_when_ok():
    def fake(path, body, authorization):  # noqa: ARG001
        if path == "people-like-you":
            return 200, {
                "success": True,
                "result": {"income": 9000, "expenses": 5000, "assets": 100000},
                "onboarding": {
                    "data": {
                        "finance": {
                            "monthlyIncome": 9000,
                            "monthlyExpense": 5000,
                            "liquidAssetValue": 100000,
                        }
                    }
                },
            }
        if path == "need-profiler":
            return 200, {
                "success": True,
                "result": {"rankedNeeds": [{"unifiedType": "N_RET"}, {"unifiedType": "N_INC"}]},
                "onboarding": {
                    "data": {
                        "needs": {
                            "N_RET": {"enabled": True, "needAmount": 0, "weightageScore": 9},
                            "N_INC": {"enabled": True, "needAmount": 0, "weightageScore": 8},
                        }
                    }
                },
            }
        if path == "need-calculator":
            return 200, {
                "success": True,
                "amounts": {"N_RET": 1_200_000, "N_INC": 500_000},
                "onboarding": {
                    "data": {
                        "needs": {
                            "N_RET": {
                                "enabled": True,
                                "needAmount": 1_200_000,
                                "existing": 0,
                                "gap": 1_200_000,
                            },
                            "N_INC": {
                                "enabled": True,
                                "needAmount": 500_000,
                                "existing": 0,
                                "gap": 500_000,
                            },
                        }
                    }
                },
            }
        return 404, {}

    client = TestClient(api)
    with patch("src.app.fm_public", side_effect=fake):
        r = client.post("/v1/predict", json={"age": 42, "occupation": "Engineer"})
    assert r.status_code == 200
    session = r.json()["session"]
    assert session["source"] == "people-like-you"
    assert session["incomeMonthly"] == 9000
    assert session["policies"] == []
    by_type = {n["type"]: n for n in session["needs"]}
    assert by_type["N_RET"]["needAmount"] == 1_200_000


def test_life_cover_from_mortgage_when_property():
    pol = _assumed_life_policy({"property": 650000, "mortgage": 199000, "incomeMonthly": 9000, "dependents": 0})
    assert pol is not None
    assert pol["sum"] == 200000
    assert pol["type"] == "Life Protection"


def test_life_cover_from_dependents_is_five_times_annual_income():
    pol = _assumed_life_policy({"property": 0, "mortgage": 0, "incomeMonthly": 9000, "dependents": 2})
    assert pol is not None
    assert pol["sum"] == 9000 * 12 * 5


def test_life_cover_one_dependent_triggers_income_rule():
    pol = _assumed_life_policy({"property": 0, "mortgage": 0, "incomeMonthly": 9000, "dependents": 1})
    assert pol is not None
    assert pol["sum"] == 9000 * 12 * 5


def test_life_cover_zero_dependents_does_not_trigger_income_rule():
    assert _assumed_life_policy({"property": 0, "mortgage": 0, "incomeMonthly": 9000, "dependents": 0}) is None


def test_life_cover_takes_higher_of_mortgage_and_dependents():
    mortgage_wins = _assumed_life_policy(
        {"property": 650000, "mortgage": 780000, "incomeMonthly": 9000, "dependents": 2}
    )
    dependents_win = _assumed_life_policy(
        {"property": 650000, "mortgage": 199000, "incomeMonthly": 9000, "dependents": 2}
    )
    assert mortgage_wins is not None and mortgage_wins["sum"] == 800000
    assert dependents_win is not None and dependents_win["sum"] == 9000 * 12 * 5


def test_apply_plu_seeds_life_cover_when_property_owned():
    session = _apply_plu(
        {"incomeMonthly": 0, "expenseMonthly": 0, "property": 0, "mortgage": 0, "dependents": 0, "policies": []},
        {
            "result": {
                "income": 9000,
                "expenses": 5000,
                "assets": 100000,
                "liabilities": 380000,
                "ownershipInformation": {"property": True},
            },
            "onboarding": {"data": {"finance": {"monthlyIncome": 9000, "monthlyExpense": 5000, "liquidAssetValue": 100000}}},
        },
    )
    assert session["property"] == 350000
    assert session["mortgage"] == 192500
    assert session["policies"][0]["sum"] == 200000
    assert session["source"] == "people-like-you"


def _plu(income, expenses, assets, liabilities, *, own=True):
    return {
        "result": {
            "income": income,
            "expenses": expenses,
            "assets": assets,
            "liabilities": liabilities,
            "ownershipInformation": {"property": own},
        },
        "onboarding": {
            "data": {"finance": {"monthlyIncome": income, "monthlyExpense": expenses, "liquidAssetValue": assets}}
        },
    }


def test_apply_plu_refreshes_mortgage_when_property_already_seeded():
    session = _apply_plu(
        {
            "incomeMonthly": 35000,
            "expenseMonthly": 23625,
            "property": 650000,
            "mortgage": 1_003_275,
            "dependents": 2,
            "policies": [],
        },
        _plu(3800, 2693.25, 139450.5, 97615.35),
    )
    assert session["property"] == 350000
    assert session["mortgage"] == 192500
    assert session["cash"] + session["investments"] + session["property"] - session["mortgage"] > 0


def test_apply_plu_mortgage_is_55_percent_of_property():
    session = _apply_plu(
        {"property": 800000, "mortgage": 1_003_275, "dependents": 2, "policies": []},
        _plu(35000, 23625, 1_433_250, 1_003_275),
    )
    assert session["property"] == 850000
    assert session["mortgage"] == 467500


def test_seed_property_value_from_income_bands():
    assert seed_property_value(0) == 350_000
    assert seed_property_value(9_999) == 350_000
    assert seed_property_value(10_000) == 650_000
    assert seed_property_value(20_000) == 650_000
    assert seed_property_value(20_001) == 850_000


def test_apply_plu_property_follows_income_band():
    low = _apply_plu({"dependents": 0, "policies": []}, _plu(9500, 5000, 100000, 0))
    mid = _apply_plu({"dependents": 0, "policies": []}, _plu(15000, 8000, 100000, 0))
    high = _apply_plu({"dependents": 0, "policies": []}, _plu(25000, 12000, 100000, 0))
    assert low["property"] == 350_000
    assert mid["property"] == 650_000
    assert high["property"] == 850_000
    assert low["mortgage"] == 192_500
    assert mid["mortgage"] == 357_500
    assert high["mortgage"] == 467_500


def test_apply_plu_clears_home_when_not_owned():
    session = _apply_plu(
        {"property": 650000, "mortgage": 1_003_275, "dependents": 2, "policies": []},
        _plu(3800, 2693.25, 139450.5, 97615.35, own=False),
    )
    assert session["property"] == 0
    assert session["mortgage"] == 0


def test_apply_plu_spend_is_share_of_take_home_after_cpf():
    assert expenses_from_gross(9500, 2, 42, "Singapore Citizen") == round((9500 - 1600) * 0.775, 2)
    session = _apply_plu(
        {"age": 42, "dependents": 2, "residency": "Singapore Citizen", "policies": []},
        _plu(9500, 5890, 215460, 150822),
    )
    assert session["incomeMonthly"] == 9500
    assert session["expenseMonthly"] == round(7900 * 0.775, 2)
    surplus = 7900 - session["expenseMonthly"]
    assets = surplus * 12 * 0.5 * 21
    assert session["cash"] + session["investments"] == round(assets * 0.45) + round(assets * 0.55)

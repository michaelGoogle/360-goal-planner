"""WP9: the mock premium equals the Plan Calculator tab."""

from __future__ import annotations

import pytest
from src.needs import PROTECTION_NEEDS
from src.services.premium import service
from src.services.premium.models import PremiumQuoteRequest

from tests.parity.conftest import load, personas


@pytest.mark.parametrize("case_name", personas())
def test_mock_premiums_equal_the_plan_tab(case_name):
    case = load(case_name)
    plan = case["plan"]["values"]
    inputs = case["inputs"]
    for code in PROTECTION_NEEDS:
        sum_assured = float(plan.get(f"PLAN_sum_{code}") or 0)
        got = service.quote(
            PremiumQuoteRequest(
                needType=code,
                sumAssured=sum_assured,
                currency=inputs.get("currency") or "SGD",
                age=int(inputs["age"]),
                gender=inputs.get("gender") or "Male",
                country=inputs.get("country") or "Singapore",
            )
        )
        assert got.annualPremium == pytest.approx(float(plan.get(f"PLAN_prem_{code}") or 0), abs=1)
        assert got.indicative is True


def test_a_zero_sum_is_a_zero_premium():
    got = service.quote(PremiumQuoteRequest(needType="N_INC", sumAssured=0, age=40))
    assert got.annualPremium == 0


def test_the_route_answers_the_contract():
    from fastapi.testclient import TestClient

    from src.app import api

    response = TestClient(api).post(
        "/v1/premium/quote",
        json={"needType": "N_CRI", "sumAssured": 681033, "age": 46, "currency": "SGD"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["indicative"] is True
    assert data["source"].startswith("mock:")
    assert data["annualPremium"] == 530


def test_http_mode_talks_to_a_stub(monkeypatch):
    from src.services import registry
    from src.services.premium.models import PremiumQuoteRequest

    monkeypatch.setenv("GP_SVC_PREMIUM", "http")
    monkeypatch.setenv("GP_SVC_PREMIUM_URL", "http://premium.test")

    def fake(_method, _base, _path, _dep, body=None):
        return {
            "annualPremium": 12,
            "currency": body["currency"],
            "source": "stub",
            "rate": 0.001,
            "indicative": True,
        }

    monkeypatch.setattr("src.services.premium.client.request_json", fake)
    got = registry.get_premium_client().quote(
        PremiumQuoteRequest(needType="N_INC", sumAssured=100000, age=40)
    )
    assert got.annualPremium == 12
    assert got.source == "stub"

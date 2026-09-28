"""Singapore and Vietnam sessions through predict → plan → budget (mocked PLU)."""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient
from src.app import api

client = TestClient(api)


def _plu(income: float, expenses: float, assets: float = 100_000) -> dict:
    result = {
        "income": income,
        "expenses": expenses,
        "assets": assets,
        "ownershipInformation": {"property": False},
        "clientPreferences": {},
    }
    return {
        "success": True,
        "result": result,
        "onboarding": {
            "data": {
                "finance": {
                    "monthlyIncome": income,
                    "monthlyExpense": expenses,
                    "liquidAssetValue": assets,
                },
                "peopleLikeYou": {"response": {}, "result": result},
            }
        },
    }


def _plan_body(session: dict) -> dict:
    return {
        "age": session.get("age") or 40,
        "gender": session.get("gender") or "Male",
        "country": session.get("country") or "Singapore",
        "currency": session.get("currency") or "SGD",
        "takeHomeMonthly": session.get("incomeMonthly") or 0,
        "expenseMonthly": session.get("expenseMonthly") or 0,
        "ageOfRetirement": session.get("ageOfRetirement") or 65,
        "needs": [
            {
                "type": n["type"],
                "enabled": bool(n.get("enabled")),
                "needAmount": n.get("needAmount") or 0,
                "have": n.get("have") or 0,
                "gap": n.get("gap") or max(0, (n.get("needAmount") or 0) - (n.get("have") or 0)),
                "horizonYears": n.get("contributeYears"),
            }
            for n in session.get("needs") or []
        ],
    }


def _run_session(country: str, currency: str, income: float, expenses: float) -> tuple[dict, dict, dict]:
    with patch("src.orchestration.predict.run_people_like_you", return_value=_plu(income, expenses)):
        predict = client.post(
            "/v1/predict",
            json={
                "age": 42,
                "occupation": "Engineer",
                "dependents": 2,
                "country": country,
                "currency": currency,
                "nationality": country,
            },
        )
    assert predict.status_code == 200, predict.text
    session = predict.json()["session"]
    plan = client.post("/v1/plan", json=_plan_body(session))
    assert plan.status_code == 200, plan.text
    plan_body = plan.json()
    budget = client.post(
        "/v1/budget",
        json={
            "takeHomeMonthly": session.get("incomeMonthly") or 0,
            "expenseMonthly": session.get("expenseMonthly") or 0,
            "investments": session.get("investments") or 0,
            "includedPremiumsYear": plan_body.get("protPremYear") or 0,
            "investMth": plan_body.get("investMth") or 0,
            "investLump": plan_body.get("investLump") or 0,
            "currency": currency,
        },
    )
    assert budget.status_code == 200, budget.text
    return session, plan_body, budget.json()


def test_singapore_session_locks_sgd_and_returns_plan_and_budget():
    lock = client.post("/v1/fx/lock", json={"currency": "SGD", "country": "Singapore"})
    assert lock.status_code == 200
    assert lock.json()["currency"] == "SGD"
    assert lock.json()["asOf"]

    defaults = client.get("/v1/config/session-defaults", params={"age": 42, "country": "Singapore"})
    assert defaults.status_code == 200
    assert "N_EDU" in defaults.json()["targetYear"]
    assert defaults.json()["ltcStartAge"] >= 60

    session, plan, budget = _run_session("Singapore", "SGD", 9000, 5000)
    assert session["currency"] == "SGD"
    assert session["fx"]["currency"] == "SGD"
    assert session["parkedNeeds"]
    assert {n["type"] for n in session["parkedNeeds"]} == {"N_HOM", "N_CAR", "N_TRV"}
    assert plan["currency"] == "SGD"
    assert budget["currency"] == "SGD"
    assert "available" in budget


def test_vietnam_session_locks_vnd_and_returns_plan_and_budget():
    lock = client.post("/v1/fx/lock", json={"currency": "VND", "country": "Vietnam"})
    assert lock.status_code == 200
    assert lock.json()["currency"] == "VND"
    assert lock.json()["country"] == "Vietnam"
    assert lock.json()["asOf"]

    session, plan, budget = _run_session("Vietnam", "VND", 30_000_000, 18_000_000)
    assert session["currency"] == "VND"
    assert session["country"] == "Vietnam"
    assert session["fx"]["currency"] == "VND"
    assert session["fx"]["usdPerLocal"] < 0.001
    assert session["parkedNeeds"]
    assert plan["currency"] == "VND"
    assert budget["currency"] == "VND"
    assert budget["available"] >= 0

"""Prototype InsApi mapping and upsert (HTTP mocked)."""
from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient
from src.app import api
from src.heygen.mobile import split_e164
from src.insapi_client import InsApiError
from src.insapi_sync import build_contact_body, build_plan_body, split_name, sync_contact_and_plan

USER_ID = "07e06e98-da76-496c-9ccc-9502ca535b03"


def _session(**extra):
    data = {
        "name": "Ada Lovelace",
        "age": 42,
        "dateOfBirth": "1984-01-15",
        "gender": "Female",
        "occupation": "Engineer",
        "dependents": 2,
        "incomeMonthly": 8000,
        "expenseMonthly": 4500,
        "cash": 20000,
        "investments": 100000,
        "property": 350000,
        "mortgage": 50000,
        "isSmoker": False,
        "ageOfRetirement": 65,
        "needs": [
            {
                "type": "N_INC",
                "enabled": True,
                "needAmount": 500000,
                "existing": 100000,
                "gap": 400000,
                "priority": 1,
            }
        ],
        "extraNeeds": ["hosp"],
        "planSum": {"N_INC": 400000},
        "planPrem": {"N_INC": 120},
    }
    data.update(extra)
    return data


def test_split_name_and_e164():
    assert split_name("Ada Lovelace") == ("Ada", "Lovelace")
    assert split_name("Ada") == ("Ada", "-")
    assert split_name("") == ("Customer", "-")
    assert split_e164("+6591234567") == ("+65", "91234567")
    assert split_e164("+919687319515") == ("+91", "9687319515")


def test_contact_body_maps_session():
    body = build_contact_body(USER_ID, "ada@example.com", "+6591234567", _session())
    assert body["userId"] == USER_ID
    assert body["category"] == "Individual"
    assert body["personalDetails"]["firstName"] == "Ada"
    assert body["personalDetails"]["lastName"] == "Lovelace"
    assert body["personalDetails"]["dob"] == "1984-01-15"
    assert body["personalDetails"]["gender"] == "Female"
    assert body["correspondenceDetails"]["primaryCountryCode"] == "+65"
    assert body["correspondenceDetails"]["primaryMobileNumber"] == "91234567"
    assert body["correspondenceDetails"]["emailAddress"] == "ada@example.com"
    assert body["employmentDetails"]["jobTitle"] == "Engineer"
    assert body["relationshipDetails"]["numberOfDependents"] == 2


def test_plan_body_uses_insapi_categories_and_skips_oversize_mortgage():
    body = build_plan_body(USER_ID, "c1", _session(), 40, 70)
    assert body["leadSource"] == "Goal Planner"
    assert body["contactId"] == "c1"
    income = body["financialDetail"]["income"]
    assert income[0]["accountCategory"] == "TOTAL"
    assert income[1]["accountCategory"] == "SALARY"
    assert income[0]["frequency"] == "M"
    assets = {r["accountCategory"] for r in body["financialDetail"]["asset"]}
    assert assets == {"TOTAL", "CASH", "MUTUAL_FUNDS", "REAL_ESTATE"}
    assert "frequency" not in body["financialDetail"]["asset"][0]
    keys = {n["needKey"] for n in body["need"]}
    assert "lifeProtection" in keys
    assert "hospitalization" in keys
    assert "preHappiU=40" in body["notes"]

    heavy = _session(mortgage=999999999, cash=0, investments=0, property=0)
    skipped = build_plan_body(USER_ID, "c1", heavy, None, None)
    assert "liability" not in skipped.get("financialDetail") or not skipped["financialDetail"].get("liability")


def test_sync_creates_contact_and_plan():
    with (
        patch("src.insapi_sync.enabled", return_value=True),
        patch("src.insapi_sync.resolve_advisor_user_id", return_value=USER_ID),
        patch("src.insapi_sync._find_contact", return_value=""),
        patch("src.insapi_sync.create_contact", return_value=(200, {"contactId": "cid-1"})),
        patch("src.insapi_sync.create_financial_plan", return_value=(200, {"planId": "pid-1"})) as create_fp,
    ):
        ids = sync_contact_and_plan("ada@example.com", "91234567", _session())
    assert ids == {"contactId": "cid-1", "planId": "pid-1"}
    assert create_fp.call_count == 1


def test_sync_updates_when_ids_known():
    with (
        patch("src.insapi_sync.enabled", return_value=True),
        patch("src.insapi_sync.resolve_advisor_user_id", return_value=USER_ID),
        patch("src.insapi_sync.update_contact") as upd,
        patch("src.insapi_sync.update_financial_plan", return_value=(200, {"planId": "pid-9"})) as upd_fp,
    ):
        ids = sync_contact_and_plan(
            "ada@example.com",
            "91234567",
            _session(insapiContactId="cid-9", insapiPlanId="pid-9"),
        )
    assert ids["contactId"] == "cid-9"
    assert ids["planId"] == "pid-9"
    upd.assert_called_once()
    upd_fp.assert_called_once()


def test_sync_uses_existing_contact_id_on_duplicate_email():
    with (
        patch("src.insapi_sync.enabled", return_value=True),
        patch("src.insapi_sync.resolve_advisor_user_id", return_value=USER_ID),
        patch("src.insapi_sync._find_contact", return_value=""),
        patch(
            "src.insapi_sync.create_contact",
            return_value=(400, {"detail": {"existingContactId": "cid-dup"}}),
        ),
        patch("src.insapi_sync.update_contact"),
        patch("src.insapi_sync.create_financial_plan", return_value=(200, {"planId": "pid-2"})),
    ):
        ids = sync_contact_and_plan("ada@example.com", "91234567", _session())
    assert ids["contactId"] == "cid-dup"


def test_crm_sync_requires_email():
    client = TestClient(api)
    with patch("src.app.sync_contact_and_plan", side_effect=InsApiError(400, "Email is required")):
        r = client.post("/v1/crm-sync", json={"mobile": "91234567", "session": {"name": "A"}})
    assert r.status_code == 400
    assert "Email" in r.json()["detail"]


def test_crm_sync_returns_ids():
    client = TestClient(api)
    with patch("src.app.sync_contact_and_plan", return_value={"contactId": "c1", "planId": "p1"}):
        r = client.post(
            "/v1/crm-sync",
            json={"email": "ada@example.com", "mobile": "91234567", "session": {"name": "Ada"}},
        )
    assert r.status_code == 200
    assert r.json()["contactId"] == "c1"
    assert r.json()["planId"] == "p1"


def test_predict_still_ok_when_insapi_down():
    client = TestClient(api)
    plu = {
        "success": True,
        "result": {
            "income": 9000,
            "expenses": 5000,
            "assets": 100000,
            "ownershipInformation": {"property": False},
            "clientPreferences": {},
        },
        "onboarding": {"data": {"peopleLikeYou": {"result": {}}}},
    }
    with (
        patch("src.app.run_people_like_you", return_value=plu),
        patch("src.app.schedule_insapi_sync"),
    ):
        r = client.post(
            "/v1/predict",
            json={
                "age": 42,
                "occupation": "Engineer",
                "reportEmail": "ada@example.com",
                "reportMobile": "91234567",
            },
        )
    assert r.status_code == 200
    assert r.json()["success"] is True

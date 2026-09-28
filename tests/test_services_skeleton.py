"""WP1: the service seams exist before any of them does arithmetic.

Two promises are worth testing now, because WP2 to WP11 land against them: every
service route answers 501 until its work package fills it in, and every service
can be pointed at a different implementation with one environment variable.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from src.app import api
from src.services import registry
from src.services.errors import ValidationFailed

client = TestClient(api)


def test_new_routes_use_the_error_envelope_and_old_ones_keep_detail():
    """Services answer {"error": ...}; /v1/needs and friends must keep {"detail": ...}."""
    assert client.post("/v1/plan", json={}).json()["error"] == "validation_failed"

    with patch("src.orchestration.needs.evaluate_session", side_effect=RuntimeError("down")):
        old = client.post("/v1/needs", json={})
    assert old.status_code == 503
    assert old.json() == {"detail": "Need Calculator unavailable"}


def test_validation_failure_is_named_and_lists_its_fields():
    body = client.post("/v1/plan", json={}).json()
    assert body["error"] == "validation_failed"
    assert any(e["loc"][-1] == "age" for e in body["fields"])


def test_every_service_has_a_default_mode(monkeypatch):
    for name, spec in registry.SERVICES.items():
        # conftest pins FX to snapshot for the suite; the default is what is asserted.
        monkeypatch.delenv(registry.env_mode(name), raising=False)
        assert registry.mode(name) == spec.default_mode


@pytest.mark.parametrize("name", sorted(registry.SERVICES))
def test_mode_follows_the_env_var(name, monkeypatch):
    spec = registry.SERVICES[name]
    for wanted in spec.modes:
        monkeypatch.setenv(registry.env_mode(name), wanted.upper())
        assert registry.mode(name) == wanted


def test_unknown_mode_is_rejected_rather_than_silently_ignored(monkeypatch):
    monkeypatch.setenv("GP_SVC_FX", "guess")
    with pytest.raises(ValidationFailed):
        registry.mode("fx")


def test_http_mode_without_a_url_fails_at_the_registry(monkeypatch):
    monkeypatch.setenv("GP_SVC_PLAN", "http")
    monkeypatch.delenv("GP_SVC_PLAN_URL", raising=False)
    with pytest.raises(ValidationFailed):
        registry.get_plan_client()


def test_fx_falls_back_to_the_fm_upstream(monkeypatch):
    monkeypatch.setenv("GP_SVC_FX", "http")
    monkeypatch.delenv("GP_SVC_FX_URL", raising=False)
    monkeypatch.setenv("FM_UPSTREAM", "http://fm.example:8062")
    assert registry.get_fx_client().base_url == "http://fm.example:8062"


def test_hu_and_sv_switch_to_mocks(monkeypatch):
    monkeypatch.setenv("GP_SVC_HU", "mock")
    monkeypatch.setenv("GP_SVC_SV", "mock")
    assert registry.get_hu_client().score({})["result"]["preHappiU"] == 50.0
    assert "preWealth" in registry.get_sv_client().project({})["data"]


def test_premium_is_a_mock_until_a_real_rate_card_exists():
    assert registry.mode("premium") == "mock"


def test_modes_reports_every_service():
    assert set(registry.modes()) == set(registry.SERVICES)

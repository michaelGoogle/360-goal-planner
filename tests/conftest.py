"""Keep HeyGen ops emails from firing against live SMTP during pytest."""

from unittest.mock import MagicMock

import pytest


@pytest.fixture(autouse=True)
def _test_env(monkeypatch):
    monkeypatch.setenv("INSAPI_UPSTREAM", "")
    monkeypatch.setattr("src.heygen.ops_alert.send_email", MagicMock(return_value={"ok": True, "skipped": True}))
    monkeypatch.setattr("src.heygen.agent.wallet_remaining_usd", lambda: None)

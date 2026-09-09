"""Live LLM simulation of Your Money via FM People Like You.

Skipped unless GP_LIVE_PLU=1. Uses ANTHROPIC_API_KEY from the workspace .env.

  $env:GP_LIVE_PLU = "1"
  python -m pytest tests/test_simulate_people_like_you.py -q
  python scripts/simulate_people_like_you.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from simulate_people_like_you import simulate  # noqa: E402

pytestmark = pytest.mark.skipif(
    os.environ.get("GP_LIVE_PLU", "").lower() not in ("1", "true", "yes"),
    reason="Set GP_LIVE_PLU=1 to call live FM People Like You",
)


def test_live_plu_ceo_profile_maps_to_money_page():
    result = simulate()
    money = result["money"]
    llm = result["llm"]
    assert result["money"]["source"] == "people-like-you"
    assert money["incomeMonthly"] > 0
    assert llm["income"] == money["incomeMonthly"]
    assert money["expenseMonthly"] > 0
    assert money["expenseMonthly"] < money["incomeMonthly"]
    assert money["savings"] > 0
    cover = result["life_cover"]
    assert cover["fiveTimesAnnual"] == int(round(money["incomeMonthly"] * 12 * 5))
    assert cover["chosen"] == max(cover["mortgageRounded"], cover["fiveTimesAnnual"])
    if llm["property"]:
        from src.predict import seed_property_value

        assert money["property"] == seed_property_value(money["incomeMonthly"])
        assert money["mortgage"] > 0
    else:
        assert money["property"] == 0
        assert money["mortgage"] == 0

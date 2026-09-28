"""WP6: the need and risk codes, and that Python and TypeScript still agree.

The codes exist twice, once per language. A test is the only thing that stops them
drifting, and a drift would silently drop a need on the way through the app.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from src.needs import (
    ALL_NEEDS,
    ALL_RISKS,
    CALCULATOR_NEEDS,
    NEED_LABEL,
    NEED_RISK,
    PARKED_NEEDS,
    RISK_LABEL,
    is_need,
    is_risk,
    need_code,
    risk_code,
)

FRONTEND = Path(__file__).resolve().parents[1] / "frontend" / "src" / "lib"


def _ts_array(text: str, name: str) -> list[str]:
    match = re.search(rf"export const {name}[^=]*=\s*\[(.*?)\];", text, re.S)
    assert match, f"{name} not found"
    return re.findall(r"'([^']+)'", match.group(1))


def _ts_union(text: str, name: str) -> list[str]:
    match = re.search(rf"export type {name}\s*=(.*?);", text, re.S)
    assert match, f"{name} not found"
    return re.findall(r"'([^']+)'", match.group(1))


def _ts_record(text: str, name: str) -> dict[str, str]:
    match = re.search(rf"export const {name}[^=]*=\s*\{{(.*?)\n\}};", text, re.S)
    assert match, f"{name} not found"
    return dict(re.findall(r"(\w+):\s*'([^']+)'", match.group(1)))


@pytest.fixture(scope="module")
def needs_ts() -> str:
    return (FRONTEND / "needs.ts").read_text(encoding="utf-8")


# --- the codes themselves ----------------------------------------------------


def test_the_calculator_needs_are_the_ten_of_the_dictionary():
    assert CALCULATOR_NEEDS == (
        "N_INC", "N_CRI", "N_TPD", "N_HOS", "N_PAC", "N_LTC",
        "N_RET", "N_EDU", "N_SAV", "N_PRP",
    )


def test_personal_accident_and_long_term_care_are_calculator_needs_now():
    """Both were agreed in V0-18 and V0-19; the code only had eight needs."""
    assert "N_PAC" in CALCULATOR_NEEDS
    assert "N_LTC" in CALCULATOR_NEEDS


def test_farewell_is_gone():
    assert not any("FAR" in code for code in ALL_NEEDS)


def test_parked_coverage_is_known_but_not_calculated():
    assert PARKED_NEEDS == ("N_HOM", "N_CAR", "N_TRV")
    for code in PARKED_NEEDS:
        assert code in ALL_NEEDS
        assert code not in CALCULATOR_NEEDS


def test_every_need_has_a_label():
    for code in ALL_NEEDS:
        assert NEED_LABEL[code]


def test_every_risk_has_a_label():
    for code in ALL_RISKS:
        assert RISK_LABEL[code]


def test_the_risk_of_a_need_is_a_known_risk():
    for need, risk in NEED_RISK.items():
        assert need in ALL_NEEDS or need == "N_ADB", need
        assert risk in ALL_RISKS or risk == "R_ADB", risk


def test_the_thirteen_stress_events_plus_the_horizon_toggle():
    assert len(ALL_RISKS) == 14
    assert "R_LON" in ALL_RISKS


# --- old ids keep loading ----------------------------------------------------


@pytest.mark.parametrize(("old", "new"), [("N_HSP", "N_HOS"), ("N_PTD", "N_TPD")])
def test_an_old_need_code_still_resolves(old, new):
    assert need_code(old) == new
    assert is_need(old)


@pytest.mark.parametrize(
    ("old", "new"),
    [("crash", "R_MKT"), ("MarketCrash", "R_MKT"), ("ci", "R_CRI"), ("CI", "R_CRI"),
     ("tpd", "R_TPD"), ("PTD", "R_TPD"), ("pa", "R_PAC"), ("hosp", "R_HOS"),
     ("care", "R_LTC"), ("wed", "R_WED"), ("baby", "R_BAB"), ("exp", "R_EXP"),
     ("inc", "R_ICT"), ("Unemployment", "R_ICT"), ("infl", "R_INF"), ("ccy", "R_CCY"),
     ("death", "R_DEA")],
)
def test_an_old_stress_event_id_still_resolves(old, new):
    assert risk_code(old) == new
    assert is_risk(old)


def test_a_new_code_passes_through_unchanged():
    assert need_code("N_RET") == "N_RET"
    assert risk_code("R_LON") == "R_LON"


def test_an_unknown_code_is_not_invented():
    assert need_code("N_ZZZ") == "N_ZZZ"
    assert not is_need("N_ZZZ")
    assert not is_risk("whatever")


def test_a_missing_code_does_not_raise():
    assert need_code(None) == ""
    assert risk_code(None) == ""


# --- Python and TypeScript agree ---------------------------------------------


def test_the_calculator_needs_match_the_frontend(needs_ts):
    assert _ts_array(needs_ts, "CALCULATOR_NEEDS") == list(CALCULATOR_NEEDS)
    assert _ts_union(needs_ts, "CalculatorNeed") == list(CALCULATOR_NEEDS)


def test_the_parked_needs_match_the_frontend(needs_ts):
    assert _ts_array(needs_ts, "PARKED_NEEDS") == list(PARKED_NEEDS)
    assert _ts_union(needs_ts, "ParkedNeed") == list(PARKED_NEEDS)


def test_the_risk_codes_match_the_frontend(needs_ts):
    assert sorted(_ts_union(needs_ts, "RiskCode")) == sorted(ALL_RISKS)


def test_the_aliases_match_the_frontend(needs_ts):
    from src.needs import NEED_ALIAS, RISK_ALIAS

    assert _ts_record(needs_ts, "NEED_ALIAS") == NEED_ALIAS
    assert _ts_record(needs_ts, "RISK_ALIAS") == RISK_ALIAS


def test_the_stress_event_catalog_uses_the_risk_codes():
    text = (FRONTEND / "stressEvents.ts").read_text(encoding="utf-8")
    ids = re.findall(r"\{ id: '([^']+)'", text)
    assert len(ids) == 13
    for code in ids:
        assert code in ALL_RISKS, code
    assert "R_LON" not in ids, "R_LON is a horizon toggle, not a costed event"


def test_the_need_metadata_covers_every_calculator_need():
    text = (FRONTEND / "types.ts").read_text(encoding="utf-8")
    meta = re.findall(r"^  (N_\w+): \{$", text, re.M)
    assert sorted(meta) == sorted(CALCULATOR_NEEDS)

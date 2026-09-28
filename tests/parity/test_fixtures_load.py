"""WP0: the model V0-24 parity fixtures are present and complete."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "model_v0_24"
GROUPS = ("fx", "cpf", "peopleLikeYou", "needProfiler", "needCalculator", "plan", "budget", "happiU",
          "scenarioVisualizer")
NEEDS = ("N_INC", "N_CRI", "N_TPD", "N_HOS", "N_PAC", "N_LTC", "N_RET", "N_EDU", "N_SAV", "N_PRP")


def _cases():
    return json.loads((FIX / "index.json").read_text(encoding="utf-8"))["cases"]


def test_fixtures_load_index_and_parameters():
    cases = _cases()
    assert len([c for c in cases if c["case"].startswith("personas/")]) == 50
    params = json.loads((FIX / "parameters.json").read_text(encoding="utf-8"))["parameters"]
    for name in ("CRI_COST", "TPD_COST", "LTC_COST", "LON_AGE", "EDU_TARGET_AGE", "PPP_BASE_COUNTRY"):
        assert name in params


@pytest.mark.parametrize("case", [c["case"] for c in json.loads((FIX / "index.json").read_text(encoding="utf-8"))["cases"]])
def test_fixtures_load_case(case):
    doc = json.loads((FIX / f"{case}.json").read_text(encoding="utf-8"))
    assert doc["formulaErrors"] == []
    for g in GROUPS:
        assert doc[g]["values"], f"{case}: {g} empty"
    nc = doc["needCalculator"]["values"]
    for t in NEEDS:
        for k in ("NC_amount_", "NC_have_", "NC_gap_", "NC_on_"):
            assert nc.get(k + t) is not None, f"{case}: {k}{t} missing"


def test_fixtures_load_known_values():
    p03 = json.loads((FIX / "personas" / "P03.json").read_text(encoding="utf-8"))
    assert p03["needCalculator"]["values"]["NC_amount_N_CRI"] == 452382
    p06 = json.loads((FIX / "personas" / "P06.json").read_text(encoding="utf-8"))
    assert p06["plan"]["values"]["PLAN_investMth"] == 1500
    assert p06["budget"]["values"]["monthly"] <= p06["budget"]["values"]["free (50%)"]

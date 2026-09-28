"""WP13: the Scenario Visualizer payload against the Scenario Visualizer tab."""

from __future__ import annotations

import pytest
from src.sv_payload import build_sv_payload, session_manual_events

from tests.parity.conftest import load, personas
from tests.parity.test_happiu_payload import session_of as hu_session

HORIZON = {
    "N_EDU": "NC_eduYears",
    "N_SAV": "NC_savYears",
    "N_PRP": "NC_prpYears",
}

ON_TO_RISK = {
    "SV_crashOn": "R_MKT",
    "SV_ccyOn": "R_CCY",
    "SV_inflOn": "R_INF",
    "SV_incOn": "R_ICT",
    "SV_expOn": "R_EXP",
    "SV_deaOn": "R_DEA",
    "SV_criOn": "R_CRI",
    "SV_tpdOn": "R_TPD",
    "SV_pacOn": "R_PAC",
    "SV_hosOn": "R_HOS",
    "SV_ltcOn": "R_LTC",
    "SV_wedOn": "R_WED",
    "SV_babOn": "R_BAB",
    "SV_lonOn": "R_LON",
}


def session_of(case: dict) -> dict:
    session = hu_session(case)
    plu = case["peopleLikeYou"]["values"]
    nc = case["needCalculator"]["values"]
    plan = case["plan"]["values"]
    sv = case["scenarioVisualizer"]["values"]
    session["property"] = float(plu.get("PLU_property") or 0)
    session["mortgage"] = float(plu.get("PLU_mortgage") or 0)
    session["planMth"] = {c: float(plan.get(f"PLAN_mth_{c}") or 0) for c in ("N_RET", "N_EDU", "N_SAV", "N_PRP")}
    session["planLump"] = {c: float(plan.get(f"PLAN_lump_{c}") or 0) for c in ("N_RET", "N_EDU", "N_SAV", "N_PRP")}
    for need in session["needs"]:
        if need["type"] in HORIZON:
            need["contributeYears"] = int(nc[HORIZON[need["type"]]])
    session["events"] = [
        {"id": risk, "on": True} for flag, risk in ON_TO_RISK.items() if sv.get(flag)
    ]
    session["ltcStartAge"] = int(nc.get("NC_ltcStartAge") or 80)
    return session


@pytest.mark.parametrize("case_name", personas())
def test_path_runs_to_lon_age(case_name):
    case = load(case_name)
    want = case["scenarioVisualizer"]["values"]
    body = build_sv_payload(session_of(case))
    mp = body["modelParameters"]
    assert mp["lifeExpectancy"] == want["SV_LE"]
    assert mp["numYears"] == want["SV_T"]
    assert mp["chartHorizon"] == case["peopleLikeYou"]["values"]["PLU_leUsed"]


@pytest.mark.parametrize("case_name", personas())
def test_wealth_pay_years_match_the_need_horizons(case_name):
    case = load(case_name)
    nc = case["needCalculator"]["values"]
    session = session_of(case)
    for need in session["needs"]:
        if need["type"] in HORIZON:
            assert need["contributeYears"] == int(nc[HORIZON[need["type"]]])


def test_all_events_use_the_assumption_ages_and_sizes():
    case = load("scenarios/P03_all_stress_events")
    want = case["scenarioVisualizer"]["values"]
    session = session_of(case)
    events = {e["eventType"]: e for e in session_manual_events(session)}
    assert events["CI"]["year"] == want["SV_criM"]
    assert events["CI"]["config"]["oneTimeCost"] == pytest.approx(float(want["SV_criAmt"]), rel=1e-6)
    assert events["PTD"]["year"] == want["SV_tpdM"]
    assert events["Death"]["year"] == want["SV_deaM"]
    assert events["Death"]["config"]["stopSalary"] is True
    assert events["PersonalAccident"]["year"] == want["SV_pacM"]
    assert events["Hospitalization"]["year"] == want["SV_hosM"]
    assert events["Marriage"]["year"] == want["SV_wedM"]
    assert events["Newborn"]["year"] == want["SV_babM"]
    care = next(e for e in session_manual_events(session) if e["eventType"] == "Expense" and e.get("measurement") == "amount")
    assert care["startYear"] == want["SV_ltcM"]
    assert care["endYear"] == want["SV_ltcE"]
    body = build_sv_payload(session)
    assert body["modelParameters"]["chartHorizon"] == want["SV_LE"]
    assert body["modelParameters"]["lifeExpectancy"] == want["SV_LE"]


def test_n_pac_is_in_the_plan_block_when_included():
    case = load("scenarios/P03_PAC_LTC_on")
    session = session_of(case)
    session["plansOff"] = []
    session["planSum"]["N_PAC"] = 165680
    session["planPrem"]["N_PAC"] = 130
    body = build_sv_payload(session)
    names = {p["productName"] for p in body.get("benefitVisualizerOutput") or []}
    assert "Personal accident cover" in names

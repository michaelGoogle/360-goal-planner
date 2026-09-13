from src.cpf import employee_cpf_monthly
from src.hu_payload import build_happiu_payload
from src.sv_payload import build_sv_payload


def _session():
    return {
        "age": 42,
        "occupation": "Software Engineer",
        "gender": "Male",
        "residency": "Singapore Citizen",
        "incomeMonthly": 9000,
        "expenseMonthly": 5500,
        "cash": 40000,
        "investments": 80000,
        "property": 650000,
        "mortgage": 300000,
        "dependents": 2,
        "ageOfRetirement": 65,
        "needs": [
            {"type": "N_RET", "enabled": True, "needAmount": 1_200_000, "existingInvestment": 80000},
            {"type": "N_INC", "enabled": True, "needAmount": 500_000, "existingSumAssured": 0},
        ],
        "events": [{"id": "CI", "on": True, "year": 1}],
        "policies": [{"type": "Life Protection", "sum": 400000, "premium": 1200}],
        "inflationRate": 0.03,
    }


def test_happiu_payload_includes_retirement_horizon():
    body = build_happiu_payload(_session())
    assert body["personalDetails"][0]["needs"]
    ret = body["needCalculatorOutput"]["N_RET"]["primaryOutput"]
    primary = next(iter(ret.values()))[0]
    assert primary["numYearsToRetirement"] == 23
    assert primary["expectedLivingExpenseInTheCountry"] == 5500 * 12 * 0.75
    assert primary["taggedFundValue"] == 80000
    inc_needs = [n for n in body["personalDetails"][0]["needs"] if n["type"] == "N_INC"]
    assert inc_needs[0]["existingSumAssured"] == 400000
    assert body["preHappiURequired"] is True


def test_sv_payload_has_wealth_and_events():
    body = build_sv_payload(_session())
    assert body["personalDetails"][0]["existingInsurance"]
    assert body["manualEvents"][0]["eventType"] == "CI"
    assert body["manualEvents"][0]["year"] == 2
    assert body["manualEvents"][0]["config"]["oneTimeCost"] == 150000
    assert body["needCalculatorOutput"]
    assets = body["personalDetails"][0]["assets"]
    assert any(a["isLiquid"] for a in assets)


def test_sv_payload_maps_crash_to_market_crash():
    session = _session()
    session["events"] = [{"id": "crash", "on": True, "year": 8}]
    body = build_sv_payload(session)
    assert body["manualEvents"][0]["eventType"] == "MarketCrash"
    assert body["manualEvents"][0]["year"] == 9
    assert body["manualEvents"][0]["config"]["marketShock"] == 0.35


def test_sv_payload_death_is_this_year_and_stops_income():
    session = _session()
    session["events"] = [{"id": "death", "on": True, "year": 0, "v": 20000}]
    body = build_sv_payload(session)
    ev = body["manualEvents"][0]
    assert ev["eventType"] == "Death"
    assert ev["year"] == 1
    assert ev["flag"] is True
    assert ev["config"]["oneTimeCost"] == 20000


def test_sv_payload_income_shock_is_a_range():
    session = _session()
    session["events"] = [{"id": "inc", "on": True, "from": 5, "to": 10, "year": 5, "v": -0.2}]
    body = build_sv_payload(session)
    ev = body["manualEvents"][0]
    assert ev["eventType"] == "Income"
    assert ev["startYear"] == 6
    assert ev["endYear"] == 11
    assert ev["measurement"] == "percentage"
    assert ev["impact"] == -0.2
    assert "year" not in ev


def test_every_gp_stress_event_maps_to_sv():
    """All 13 Goal Planner stress rows must land on an SV type the engine applies."""
    session = _session()
    session["events"] = [
        {"id": "crash", "on": True, "year": 8, "v": 0.35},
        {"id": "ccy", "on": True, "year": 6, "v": 0.14},
        {"id": "infl", "on": True, "from": 4, "to": 9, "year": 4, "v": 0.03},
        {"id": "inc", "on": True, "from": 5, "to": 10, "year": 5, "v": -0.2},
        {"id": "death", "on": True, "year": 17, "v": 20000},
        {"id": "ci", "on": True, "year": 12, "v": 150000},
        {"id": "tpd", "on": True, "year": 15, "v": 200000},
        {"id": "pa", "on": True, "year": 10, "v": 80000},
        {"id": "hosp", "on": True, "year": 9, "v": 120000},
        {"id": "care", "on": True, "from": 30, "to": 35, "year": 30, "v": 90000},
        {"id": "wed", "on": True, "year": 5, "v": 60000},
        {"id": "baby", "on": True, "year": 3, "v": 35000},
        {"id": "exp", "on": True, "from": 6, "to": 12, "year": 6, "v": 0.15},
    ]
    by_type = {e["eventType"]: e for e in build_sv_payload(session)["manualEvents"]}
    assert by_type["MarketCrash"]["year"] == 9
    assert by_type["MarketCrash"]["config"]["marketShock"] == 0.35
    assert abs(by_type["CurrencyShock"]["config"]["currencyShock"] - 0.14 * 2 / 3) < 1e-12
    assert by_type["CurrencyShock"]["year"] == 7
    assert by_type["Inflation"]["year"] == 5
    assert by_type["Inflation"]["config"]["length"] == 6
    assert abs(by_type["Inflation"]["config"]["inflationRate"] - 0.06) < 1e-12
    assert by_type["Income"]["startYear"] == 6 and by_type["Income"]["endYear"] == 11
    assert by_type["Death"]["year"] == 18 and by_type["Death"]["config"]["oneTimeCost"] == 20000
    assert by_type["CI"]["config"]["oneTimeCost"] == 150000
    assert by_type["PTD"]["config"]["oneTimeCost"] == 200000
    assert by_type["PersonalAccident"]["config"]["oneTimeCost"] == 80000
    assert by_type["Hospitalization"]["year"] == 10
    assert by_type["Hospitalization"]["config"]["oneTimeCost"] == 120000
    assert by_type["Expense"]["measurement"] == "percentage"
    assert by_type["Expense"]["impact"] == 0.15
    assert by_type["Marriage"]["config"]["oneTimeCost"] == 60000
    assert by_type["Newborn"]["config"]["oneTimeCost"] == 35000
    # Long-term care is a second Expense row (amount over a span).
    expenses = [e for e in build_sv_payload(session)["manualEvents"] if e["eventType"] == "Expense"]
    assert len(expenses) == 2
    care = next(e for e in expenses if e["measurement"] == "amount")
    assert care["startYear"] == 31 and care["endYear"] == 36
    assert care["impact"] == 90000



def test_sv_payload_maps_assumption_rates():
    body = build_sv_payload(_session())
    assert body["modelParameters"]["inflationRate"] == 0.03
    assert body["modelParameters"]["incomeGrowthRate"] == 0.028
    assets = body["personalDetails"][0]["assets"]
    cash = next(a for a in assets if a["type"] == "A_SAV")
    inv = next(a for a in assets if a["type"] == "INVESTMENT_PORTFOLIO")
    prop = next(a for a in assets if not a["isLiquid"])
    assert cash["interestRate"] == 0.012
    assert cash["currentValue"] == 40000
    assert inv["interestRate"] == 0.042
    assert inv["currentValue"] == 80000
    assert prop["interestRate"] == 0.034


def test_sv_payload_uses_overridden_returns():
    session = _session()
    session["incomeGrowthRate"] = 0.04
    session["interestRate"] = 0.02
    session["investmentReturn"] = 0.06
    session["assetReturn"] = 0.05
    body = build_sv_payload(session)
    assert body["modelParameters"]["incomeGrowthRate"] == 0.04
    assets = body["personalDetails"][0]["assets"]
    cash = next(a for a in assets if a["type"] == "A_SAV")
    inv = next(a for a in assets if a["type"] == "INVESTMENT_PORTFOLIO")
    prop = next(a for a in assets if not a["isLiquid"])
    assert cash["interestRate"] == 0.02
    assert inv["interestRate"] == 0.06
    assert abs(prop["interestRate"] - 0.054) < 1e-12


def test_happiu_payload_uses_assumption_rates():
    session = _session()
    session["inflationRate"] = 0.03
    session["incomeGrowthRate"] = 0.04
    session["interestRate"] = 0.018
    session["investmentReturn"] = 0.06
    hu = build_happiu_payload(session)
    cd = hu["commonDetails"]
    assert cd["inflationRate"] == 0.03
    assert cd["incomeGrowthRate"] == 0.04
    assert cd["interestRate"] == 0.018
    assets = {a["type"]: a for a in hu["personalDetails"][0]["assets"]}
    assert assets["A_SAV"]["currentValue"] == 40000
    assert assets["A_SAV"]["interestRate"] == 0.018
    assert assets["A_INV"]["currentValue"] == 80000
    assert assets["A_INV"]["interestRate"] == 0.06
    ret_budget = next(b for b in hu["solutionOptimizerOutput"]["segregatedBudget"] if b["goalId"] == "N_RET")
    assert ret_budget["growthRate"] == 0.06


def test_happiu_and_sv_send_gross_income():
    assert employee_cpf_monthly(9500, 42, "Singapore Citizen") == 1600
    assert employee_cpf_monthly(35000, 42, "Singapore Citizen") == 1600
    assert employee_cpf_monthly(35000, 42, "Foreigner") == 0
    session = _session()
    session["incomeMonthly"] = 9500
    session["expenseMonthly"] = round(7900 * 0.775, 2)
    hu = build_happiu_payload(session)
    assert hu["personalDetails"][0]["cashFlows"]["monthlyIncome"] == 9500
    assert hu["personalDetails"][0]["cashFlows"]["income"][0]["absoluteValue"] == 9500
    sv = build_sv_payload(session)
    assert sv["personalDetails"][0]["cashFlows"]["income"][0]["absoluteValue"] == 9500 * 12
    inv = next(a for a in sv["personalDetails"][0]["assets"] if a["type"] == "INVESTMENT_PORTFOLIO")
    assert inv["recurringContribution"]["value"] == round(7900 - session["expenseMonthly"])


def test_sv_payload_route_maps_without_calling_sv():
    from fastapi.testclient import TestClient
    from src.app import api

    client = TestClient(api)
    r = client.post(
        "/v1/sv-payload",
        json={
            "age": 42,
            "needs": [{"type": "N_RET", "enabled": True, "needAmount": 1_200_000}],
            "planMth": {"N_RET": 400},
        },
    )
    assert r.status_code == 200
    payload = r.json()["payload"]
    assert payload["needCalculatorOutput"]
    assert payload["benefitVisualizerOutput"]


def test_sv_payload_omits_bvo_without_plan():
    body = build_sv_payload(_session())
    assert "benefitVisualizerOutput" not in body


def test_sv_payload_plan_mix_becomes_post_path():
    session = _session()
    session["planMth"] = {"N_RET": 400}
    session["planLump"] = {"N_RET": 10_000}
    session["planSum"] = {"N_INC": 500_000}
    session["planPrem"] = {"N_INC": 390}
    body = build_sv_payload(session)
    bvo = body["benefitVisualizerOutput"]
    names = {p["productName"] for p in bvo}
    assert names == {"Retirement plan", "Life cover"}
    ret = next(p for p in bvo if p["productName"] == "Retirement plan")
    cols = {c["column"]: c["values"] for c in ret["productPlans"][0]["benefitProjection"]}
    assert cols["totalAccountValue"][0] > 10_000
    assert cols["totalPremiumPaidToDate"][-1] > cols["totalPremiumPaidToDate"][0]
    life = next(p for p in bvo if p["productName"] == "Life cover")
    life_cols = {c["column"]: c["values"] for c in life["productPlans"][0]["benefitProjection"]}
    assert life_cols["guaranteedDeathBenefit"][0] == 500_000


def test_sv_payload_foreigner_uses_non_cpf_region():
    session = _session()
    session["residency"] = "Foreigner"
    body = build_sv_payload(session)
    assert body["personalDetails"][0]["socialSecurity"]["region"] == "R_OTH"
    citizen = build_sv_payload(_session())
    assert citizen["personalDetails"][0]["socialSecurity"]["region"] == "R_SGP"


def test_sv_payload_plans_off_skips_bvo_product():
    session = _session()
    session["planMth"] = {"N_RET": 400}
    session["plansOff"] = ["N_RET"]
    body = build_sv_payload(session)
    assert "benefitVisualizerOutput" not in body

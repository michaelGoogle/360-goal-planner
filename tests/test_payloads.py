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
    assert body["needCalculatorOutput"]
    assets = body["personalDetails"][0]["assets"]
    assert any(a["isLiquid"] for a in assets)


def test_sv_payload_maps_crash_to_market_crash():
    session = _session()
    session["events"] = [{"id": "Crash", "on": True, "year": 5}]
    body = build_sv_payload(session)
    assert body["manualEvents"][0]["eventType"] == "MarketCrash"
    assert body["manualEvents"][0]["year"] == 5


def test_sv_payload_maps_assumption_rates():
    body = build_sv_payload(_session())
    assert body["modelParameters"]["inflationRate"] == 0.03
    assert body["modelParameters"]["incomeGrowthRate"] == 0.028
    liquid = next(a for a in body["personalDetails"][0]["assets"] if a["isLiquid"])
    prop = next(a for a in body["personalDetails"][0]["assets"] if not a["isLiquid"])
    assert liquid["interestRate"] == 0.042
    assert prop["interestRate"] == 0.034


def test_sv_payload_uses_overridden_returns():
    session = _session()
    session["incomeGrowthRate"] = 0.04
    session["investmentReturn"] = 0.06
    session["assetReturn"] = 0.05
    body = build_sv_payload(session)
    assert body["modelParameters"]["incomeGrowthRate"] == 0.04
    liquid = next(a for a in body["personalDetails"][0]["assets"] if a["isLiquid"])
    prop = next(a for a in body["personalDetails"][0]["assets"] if not a["isLiquid"])
    assert liquid["interestRate"] == 0.06
    assert abs(prop["interestRate"] - 0.054) < 1e-12


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
    liquid = next(a for a in sv["personalDetails"][0]["assets"] if a["isLiquid"])
    assert liquid["recurringContribution"]["value"] == round(7900 - session["expenseMonthly"])

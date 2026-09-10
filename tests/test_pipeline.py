"""Unit tests for in-process Need Profiler + Need Calculator (ported from FM)."""

from __future__ import annotations

from src.pipeline.goal_math import compute_need_amounts, remaining_gap
from src.pipeline.need_calculator import calculate_gaps_for_onboarding
from src.pipeline.need_profiler import apply_top_needs_to_onboarding, identify_needs
from src.pipeline.onboarding import AI_NEED_TO_UNIFIED, ensure_needs_map
from src.pipeline.run import run_need_calculator, run_need_profiler


def test_goal_math_cri_is_five_times_annual_income():
    amounts = compute_need_amounts(
        date_of_birth="1985-06-15",
        monthly_income=10000,
        monthly_expense=6000,
        age_of_retirement=65,
    )
    assert amounts["N_CRI"] == 5 * 10000 * 12
    assert amounts["N_SAV"] == 10000 * 12
    assert amounts["N_EDU"] == 3 * 10000 * 12
    assert amounts["N_PRP"] == 5 * 10000 * 12
    assert amounts["N_TPD"] == round(0.5 * amounts["N_INC"])
    assert amounts["N_INC"] > 0
    assert amounts["N_RET"] > 0


def test_remaining_gap():
    assert remaining_gap(1000, 200) == 800
    assert remaining_gap(1000, 1500) == 0


def test_need_profiler_scores_twelve_and_maps_unified():
    profile = {
        "Age": 40,
        "Gender": "Male",
        "Dependents": 2,
        "Occupation": "Software Engineer",
        "Smoker": False,
        "MonthlyIncome": 10000,
        "MonthlyExpense": 6000,
        "TotalAssets": 150000,
        "TotalLiabilities": 50000,
        "CarOwnership": True,
        "HomeOwnership": True,
    }
    result = identify_needs(profile, top_n=5)
    assert result["totalNeedsScored"] == 12
    assert len(result["rankedNeeds"]) == 12
    assert len(result["topNeeds"]) == 5
    assert all(0 <= n["weightage_score"] <= 10 for n in result["rankedNeeds"])

    data: dict = {}
    needs = ensure_needs_map(data)
    apply_top_needs_to_onboarding(needs, result["rankedNeeds"], top_n=5)
    enabled = [t for t, row in needs.items() if row.get("enabled")]
    assert 1 <= len(enabled) <= 5
    for t in enabled:
        assert t in AI_NEED_TO_UNIFIED.values()


def test_calculator_only_empty_preserves_manual_amount():
    data = {
        "policyOwner": {
            "dateOfBirth": "1985-06-15",
            "ageOfRetirement": 65,
            "gender": "Male",
        },
        "finance": {
            "monthlyIncome": 10000,
            "monthlyExpense": 6000,
            "liquidAssetValue": 50000,
        },
        "needs": {
            "N_INC": {"enabled": True, "needAmount": 99999, "existing": 0},
            "N_CRI": {"enabled": True, "needAmount": 0, "existing": 0},
            "N_TPD": {"enabled": False, "needAmount": 0, "existing": 0},
            "N_RET": {"enabled": True, "needAmount": 0, "existing": 0},
            "N_EDU": {"enabled": False, "needAmount": 0, "existing": 0},
            "N_SAV": {"enabled": False, "needAmount": 0, "existing": 0},
            "N_PRP": {"enabled": False, "needAmount": 0, "existing": 0},
        },
    }
    calc = calculate_gaps_for_onboarding(data, only_empty=True)
    assert calc["needs"]["N_INC"]["needAmount"] == 99999
    assert calc["needs"]["N_CRI"]["needAmount"] == 5 * 10000 * 12
    assert "N_CRI" in calc["calculatedTypes"]
    assert "N_INC" not in calc["calculatedTypes"]


def test_run_profiler_then_calculator():
    po = {
        "dateOfBirth": "1985-06-15",
        "gender": "Male",
        "occupation": "Software Engineer",
        "dependents": 2,
        "isSmoker": False,
        "ageOfRetirement": 65,
    }
    fin = {"monthlyIncome": 10000, "monthlyExpense": 6000, "liquidAssetValue": 150000}
    prof = run_need_profiler(po, fin, top_n=5)
    assert prof["success"] is True
    enabled = [t for t, row in prof["onboarding"]["data"]["needs"].items() if row.get("enabled")]
    assert len(enabled) >= 1

    calc = run_need_calculator(po, fin, prof["onboarding"]["data"]["needs"], only_empty=True)
    assert calc["success"] is True
    assert calc["amounts"]["N_CRI"] == 5 * 10000 * 12

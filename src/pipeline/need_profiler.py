"""
Need Profiler — weighted scoring of insurance needs from a client profile.

Ported from AI ``NeedProfilerAgent`` / ``Need_profiler.json`` (no LLM, no Contact API).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from src.fx import to_usd
from src.needs import CUSTOMER_ONLY_NEEDS, PROTECTION_PICK_ORDER
from src.pipeline.onboarding import (
    AI_NEED_LABELS,
    AI_NEED_TO_UNIFIED,
    snake_to_camel,
)

MONEY_FACTORS = ("Income", "Expense", "Assets", "Liabilities")

logger = logging.getLogger(__name__)

DEFAULT_TOP_N = 4
MANDATORY_UNIFIED = ("N_RET",)
PROTECTION_UNIFIED = PROTECTION_PICK_ORDER
GROWTH_UNIFIED = ("N_RET", "N_EDU", "N_SAV")
GROUP_N = 2


def select_unified_top(
    ranked: list[dict[str, Any]],
    top_n: int = DEFAULT_TOP_N,
    *,
    mandatory: tuple[str, ...] = MANDATORY_UNIFIED,
    has_property: bool | None = None,
) -> list[str]:
    """Two protection needs and two growth needs. Retirement is always one of the growth pair.

    N_PRP and N_LTC have no profiler label, so they are never auto-picked. Home ownership
    does not swap savings for a home-purchase goal. ``has_property`` is unused; it stays
    on the signature because leftover callers still pass it.
    """
    _ = (top_n, mandatory, has_property)
    ranked_uts: list[str] = []
    for need in ranked:
        ut = need.get("unifiedType")
        if ut and ut not in ranked_uts and ut not in CUSTOMER_ONLY_NEEDS:
            ranked_uts.append(ut)
    prot: list[str] = []
    grow: list[str] = ["N_RET"]
    for ut in ranked_uts:
        if ut in PROTECTION_UNIFIED and ut not in prot and len(prot) < GROUP_N:
            prot.append(ut)
        elif ut in GROWTH_UNIFIED and ut not in grow and len(grow) < GROUP_N:
            grow.append(ut)
        if len(prot) >= GROUP_N and len(grow) >= GROUP_N:
            break
    for ut in PROTECTION_UNIFIED:
        if len(prot) >= GROUP_N:
            break
        if ut not in prot:
            prot.append(ut)
    for ut in ("N_EDU", "N_SAV"):
        if len(grow) >= GROUP_N:
            break
        if ut not in grow:
            grow.append(ut)
    return prot[:GROUP_N] + grow[:GROUP_N]


def load_needs_config() -> dict[str, Any]:
    path = Path(__file__).resolve().parent / "prompts" / "Need_profiler.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning("Could not load Need_profiler.json: %s", e)
        return {"weight_options": {}, "needs_factor_weights": {}}


def _get_option_weight(
    factor_name: str,
    value: Any,
    weight_options: dict[str, Any],
) -> float:
    if factor_name == "Smoking":
        options = weight_options.get("Smoking") or weight_options.get("Smoker") or []
        is_smoker = value is True or (
            isinstance(value, str) and value.lower() in ("true", "yes", "smoker")
        )
        if options:
            if is_smoker:
                return next(
                    (
                        o["weight"]
                        for o in options
                        if "smoker" in o["option"].lower()
                        and "non" not in o["option"].lower()
                    ),
                    3.0,
                )
            return next(
                (o["weight"] for o in options if "non-smoker" in o["option"].lower()),
                1.0,
            )
        return 3.0 if is_smoker else 1.0

    name_map = {
        "Date of Birth": "Age",
        "Hospitalization": "Existing Hospitalization Insurance",
        "Disability": "Existing Disability Insurance",
    }
    lookup_name = name_map.get(factor_name, factor_name)
    if lookup_name not in weight_options:
        return 0.0
    options = weight_options[lookup_name]

    if factor_name in ("Date of Birth", "Age") and isinstance(value, (int, float)):
        if value < 21:
            return next((o["weight"] for o in options if o["option"] == "Below 21"), 0.0)
        if 21 <= value <= 30:
            return next(
                (o["weight"] for o in options if o["option"] == "21 to 30 years"), 0.0
            )
        if 31 <= value <= 40:
            return next(
                (o["weight"] for o in options if o["option"] == "31 to 40 years"), 0.0
            )
        return next(
            (o["weight"] for o in options if o["option"] == "above 40 years"), 0.0
        )

    if factor_name == "Dependants" and isinstance(value, (int, float)):
        if value == 0:
            return next(
                (o["weight"] for o in options if o["option"] == "No Dependant"), 0.0
            )
        if value == 1:
            return next(
                (o["weight"] for o in options if o["option"] == "1 Dependant"), 0.0
            )
        return next(
            (o["weight"] for o in options if o["option"] == "2 or More Dependants"),
            0.0,
        )

    if factor_name in MONEY_FACTORS and isinstance(value, (int, float)):
        return _usd_band_weight(options, float(value))

    # Booleans (ownership / existing cover)
    if isinstance(value, bool):
        target = "True" if value else "False"
        return next((o["weight"] for o in options if o["option"] == target), 0.0)

    # Occupation coarse bucket
    if factor_name == "Occupation" and isinstance(value, str):
        lower = value.lower()
        if any(x in lower for x in ("self", "entrepreneur", "own business", "freelance")):
            return next(
                (
                    o["weight"]
                    for o in options
                    if "self-employed" in o["option"].lower()
                ),
                2.0,
            )
        return next(
            (o["weight"] for o in options if o["option"].lower() == "salaried"),
            1.0,
        )

    for opt in options:
        if str(opt["option"]).lower() == str(value).lower():
            return float(opt["weight"])

    return 0.0


def _usd_band_weight(options: list[dict[str, Any]], usd_value: float) -> float:
    """Read ``lt`` cut-overs from Need_profiler.json weight_options (USD after FX)."""
    if not options:
        return 0.0
    for opt in options:
        lt = opt.get("lt")
        if lt is None:
            return float(opt["weight"])
        if usd_value < float(lt):
            return float(opt["weight"])
    return float(options[-1]["weight"])


def _calculate_weighted_score(
    need_name: str,
    profile: dict[str, Any],
    needs_config: dict[str, Any],
) -> float:
    weight_options = needs_config.get("weight_options") or {}
    needs_factor_weights = needs_config.get("needs_factor_weights") or {}
    total = 0.0

    factor_mappings = {
        "Age": ("Date of Birth", profile.get("Age")),
        "Gender": ("Gender", profile.get("Gender")),
        "Dependents": ("Dependants", profile.get("Dependents")),
        "Occupation": ("Occupation", profile.get("Occupation")),
        "Smoker": ("Smoking", profile.get("Smoker")),
        "MonthlyIncome": ("Income", profile.get("MonthlyIncome")),
        "MonthlyExpense": ("Expense", profile.get("MonthlyExpense")),
        "TotalAssets": ("Assets", profile.get("TotalAssets")),
        "TotalLiabilities": ("Liabilities", profile.get("TotalLiabilities")),
        "ExistingLifeProtection": (
            "Life Protection",
            (profile.get("ExistingLifeProtection") or 0) > 0,
        ),
        "ExistingCriticalIllnessCoverage": (
            "Critical Illness",
            (profile.get("ExistingCriticalIllnessCoverage") or 0) > 0,
        ),
        "ExistingHospitalizationCoverage": (
            "Hospitalization",
            (profile.get("ExistingHospitalizationCoverage") or 0) > 0,
        ),
        "ExistingDisabilityProtection": (
            "Disability",
            (profile.get("ExistingDisabilityProtection") or 0) > 0,
        ),
        "CarOwnership": ("Car Ownership", profile.get("CarOwnership")),
        "HomeOwnership": ("Home Ownership", profile.get("HomeOwnership")),
        "InternationalTraveling": (
            "International Traveling",
            profile.get("InternationalTraveling"),
        ),
        "HospitalType": ("Hospital Type", profile.get("HospitalType")),
        "WardType": ("Ward Type", profile.get("WardType")),
        "Lifestyle": ("Lifestyle", profile.get("Lifestyle")),
        "Sports": ("Sports", profile.get("Sports")),
    }

    for _field, (factor_name, value) in factor_mappings.items():
        if value is None:
            continue
        if factor_name not in needs_factor_weights:
            continue
        factor_weights = needs_factor_weights[factor_name]
        if need_name not in factor_weights:
            continue
        need_weight = float(factor_weights[need_name])
        option_value = value
        if factor_name in MONEY_FACTORS and isinstance(value, (int, float)):
            option_value = to_usd(float(value), profile.get("Currency"))
        option_weight = _get_option_weight(factor_name, option_value, weight_options)
        total += need_weight * option_weight

    return round(total, 2)


def score_all_needs(
    profile: dict[str, Any],
    needs_config: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    cfg = needs_config if needs_config is not None else load_needs_config()
    scored: list[dict[str, Any]] = []
    for snake, label in AI_NEED_LABELS.items():
        score = _calculate_weighted_score(label, profile, cfg)
        need_key = snake_to_camel(snake)
        scored.append(
            {
                "needKey": need_key,
                "needLabel": label,
                "weightage_score": score,
                "unifiedType": AI_NEED_TO_UNIFIED.get(need_key),
            }
        )
    scored.sort(key=lambda x: x["weightage_score"], reverse=True)
    return scored


def scale_scores(scored_needs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not scored_needs:
        return scored_needs
    max_score = max(n["weightage_score"] for n in scored_needs)
    min_score = min(n["weightage_score"] for n in scored_needs)
    score_range = max_score - min_score if max_score > min_score else 1.0
    for need in scored_needs:
        original = need["weightage_score"]
        scaled = ((original - min_score) / score_range) * 10 if score_range > 0 else 5.0
        need["weightage_score"] = round(scaled, 1)
    return scored_needs


def annotate_priority(scored_needs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for idx, need in enumerate(scored_needs, 1):
        need["ranking"] = idx
        need["selected"] = True
        score = need.get("weightage_score", 0)
        if score <= 5:
            need["lifePriority"] = "low"
            need["colorCode"] = "#00FF00"
        elif score <= 7:
            need["lifePriority"] = "medium"
            need["colorCode"] = "#FFA500"
        else:
            need["lifePriority"] = "high"
            need["colorCode"] = "#FF0000"
    return scored_needs


def apply_top_needs_to_onboarding(
    needs_map: dict[str, dict[str, Any]],
    ranked: list[dict[str, Any]],
    *,
    top_n: int = DEFAULT_TOP_N,
    has_property: bool | None = None,
) -> dict[str, dict[str, Any]]:
    """
    Enable UNIFIED needs corresponding to the top-N ranked AI needs (mapped only).
    Disable other UNIFIED types. Preserve existing needAmount values.
    """
    enable_set = set(select_unified_top(ranked, top_n, has_property=has_property))
    for ut, row in needs_map.items():
        row = dict(row)
        row["enabled"] = ut in enable_set
        # Attach score from first matching ranked need
        score = next(
            (n.get("weightage_score") for n in ranked if n.get("unifiedType") == ut),
            None,
        )
        if score is not None:
            row["weightageScore"] = score
        needs_map[ut] = row
    return needs_map


def identify_needs(
    profile: dict[str, Any],
    *,
    top_n: int = DEFAULT_TOP_N,
    preferred_needs: list[str] | None = None,
) -> dict[str, Any]:
    """
    Score and rank needs from a profiler profile.

    ``preferred_needs``: optional AI needKeys (camelCase or snake) to boost (no LLM).
    """
    cfg = load_needs_config()
    scored = score_all_needs(profile, cfg)

    if preferred_needs:
        preferred_camel = {
            snake_to_camel(p) if "_" in p else p for p in preferred_needs
        }
        max_score = max((n["weightage_score"] for n in scored), default=0)
        boost_threshold = max_score * 0.5
        for need in scored:
            if need["needKey"] in preferred_camel:
                if need["weightage_score"] < boost_threshold:
                    need["weightage_score"] = max_score * 0.75
        scored.sort(key=lambda x: x["weightage_score"], reverse=True)

    scored = scale_scores(scored)
    scored = annotate_priority(scored)
    top = scored[: max(1, top_n)]
    return {
        "rankedNeeds": scored,
        "topNeeds": top,
        "topN": top_n,
        "totalNeedsScored": len(scored),
    }

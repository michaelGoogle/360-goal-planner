"""Run People Like You / Need Profiler / Need Calculator in-process.

Returns the same JSON envelopes GP mapping (``_apply_plu`` etc.) already
consumed from FM's public routes.
"""

from __future__ import annotations

from typing import Any

from src.pipeline.need_calculator import calculate_gaps_for_onboarding
from src.pipeline.need_profiler import apply_top_needs_to_onboarding, identify_needs
from src.pipeline.onboarding import build_profiler_profile, ensure_needs_map
from src.pipeline.people_like_you import (
    calculate_age_from_dob,
    format_location,
    map_predictions_to_onboarding,
    predict_people_like_you,
)


def run_people_like_you(session: dict[str, Any]) -> dict[str, Any]:
    dob = (session.get("dateOfBirth") or session.get("dob") or "").strip()
    occupation = (session.get("occupation") or "Professional").strip()
    if not dob:
        raise RuntimeError("dateOfBirth is required")
    if not occupation:
        raise RuntimeError("occupation is required")

    country = session.get("country") or "Singapore"
    city = session.get("city") or "Singapore"
    dependents = int(session.get("dependents") or 0)
    demographics = {
        "dob": dob,
        "dateOfBirth": dob,
        "occupation": occupation,
        "country": country,
        "city": city,
        "dependents": dependents,
        "maritalStatus": session.get("maritalStatus"),
        "yearsEmployed": session.get("yearsEmployed"),
        "gender": session.get("gender"),
    }
    predictions = predict_people_like_you(
        dob=dob,
        occupation=occupation,
        country=country,
        city=city,
        dependents=dependents,
        marital_status=session.get("maritalStatus"),
        years_employed=session.get("yearsEmployed"),
        gender=session.get("gender"),
        residency=session.get("residency"),
    )
    mapped = map_predictions_to_onboarding(predictions, demographics=demographics)
    response_clean = {k: v for k, v in predictions.items() if k != "_timing"}
    data = {
        "policyOwner": mapped["policyOwner"],
        "finance": mapped["finance"],
        "peopleLikeYou": {
            "input": demographics,
            "response": response_clean,
            "result": mapped["result"],
        },
    }
    return {
        "success": True,
        "dbStored": False,
        "result": mapped["result"],
        "demographics": {
            "dob": dob,
            "age": calculate_age_from_dob(dob),
            "occupation": occupation,
            "country": country,
            "city": city,
            "location": format_location(country, city),
            "dependents": dependents,
            "gender": session.get("gender"),
        },
        "onboarding": {"data": data, "home_currency": mapped["home_currency"]},
        "timing": mapped["timing"],
    }


def run_need_profiler(
    policy_owner: dict[str, Any],
    finance: dict[str, Any],
    *,
    people_like_you: dict[str, Any] | None = None,
    top_n: int = 4,
    preferred_needs: list[str] | None = None,
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "policyOwner": dict(policy_owner or {}),
        "finance": dict(finance or {}),
    }
    if people_like_you:
        data["peopleLikeYou"] = people_like_you
    profile = build_profiler_profile(data)
    if profile.get("Age") is None:
        raise ValueError("dateOfBirth is required on policyOwner before need profiler")
    n = max(1, min(int(top_n or 4), 12))
    result = identify_needs(profile, top_n=n, preferred_needs=preferred_needs)
    needs_map = ensure_needs_map(data)
    has_property = bool(profile.get("HomeOwnership")) or float(
        (finance or {}).get("property") or 0
    ) > 0
    apply_top_needs_to_onboarding(
        needs_map, result["rankedNeeds"], top_n=n, has_property=has_property
    )
    data["needs"] = needs_map
    return {
        "success": True,
        "dbStored": False,
        "result": result,
        "onboarding": {"data": data},
    }


def run_need_calculator(
    policy_owner: dict[str, Any],
    finance: dict[str, Any],
    needs: dict[str, Any],
    *,
    only_empty: bool = True,
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "policyOwner": dict(policy_owner or {}),
        "finance": dict(finance or {}),
        "needs": dict(needs or {}),
    }
    calc = calculate_gaps_for_onboarding(data, only_empty=only_empty)
    data["needs"] = calc["needs"]
    return {
        "success": True,
        "dbStored": False,
        "result": calc,
        "amounts": calc.get("amounts"),
        "needs": calc.get("needs"),
        "onboarding": {"data": data},
    }

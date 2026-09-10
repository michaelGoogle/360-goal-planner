"""Shared helpers for the predictive onboarding pipeline (PLU → profiler → calculator)."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

UNIFIED_NEED_TYPES = (
    "N_INC",
    "N_CRI",
    "N_TPD",
    "N_RET",
    "N_EDU",
    "N_SAV",
    "N_PRP",
)

# AI needKey (camelCase) → UNIFIED catalog type
AI_NEED_TO_UNIFIED: dict[str, str] = {
    "lifeProtection": "N_INC",
    "criticalIllness": "N_CRI",
    "disability": "N_TPD",
    "retirement": "N_RET",
    "education": "N_EDU",
    "generalSavings": "N_SAV",
    "home": "N_PRP",
}

AI_NEED_LABELS: dict[str, str] = {
    "life_protection": "Life Protection",
    "critical_illness": "Critical Illness",
    "disability": "Disability",
    "retirement": "Retirement",
    "education": "Education",
    "hospitalization": "Hospitalization",
    "general_savings": "General Savings",
    "farewell": "Farewell",
    "personal_accident": "Personal Accident",
    "motor": "Car Protection",
    "home": "Home Protection",
    "travel": "Travel Protection",
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def snake_to_camel(snake: str) -> str:
    parts = snake.split("_")
    return parts[0] + "".join(p.title() for p in parts[1:])


def demographics_source_hash(demographics: dict[str, Any]) -> str:
    """Stable-ish hash of demographics used for a pipeline run."""
    keys = (
        "dob",
        "dateOfBirth",
        "occupation",
        "country",
        "city",
        "dependents",
        "maritalStatus",
        "yearsEmployed",
        "gender",
    )
    payload = {k: demographics.get(k) for k in keys}
    raw = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def update_pipeline_snapshot(
    data: dict[str, Any],
    *,
    step: str,
    demographics: dict[str, Any] | None = None,
    reset: bool = False,
) -> None:
    """
    Update ``pipelineSnapshot`` on onboarding data.

    ``reset=True`` (e.g. after PLU alone) sets stepsCompleted to only this step.
    Otherwise appends ``step`` if missing.
    """
    snap = dict(data.get("pipelineSnapshot") or {})
    if reset:
        steps = [step]
    else:
        steps = list(snap.get("stepsCompleted") or [])
        if step not in steps:
            steps.append(step)
    snap["stepsCompleted"] = steps
    snap["lastRunAt"] = utc_now_iso()
    if demographics is not None:
        snap["sourceHash"] = demographics_source_hash(demographics)
    data["pipelineSnapshot"] = snap


def default_needs_map() -> dict[str, dict[str, Any]]:
    needs: dict[str, dict[str, Any]] = {}
    for t in UNIFIED_NEED_TYPES:
        needs[t] = {
            "enabled": t in ("N_INC", "N_RET"),
            "needAmount": 0,
            "gap": 0,
            "existing": 0,
        }
    return needs


def ensure_needs_map(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    existing = dict(data.get("needs") or {})
    base = default_needs_map()
    for t, row in base.items():
        if t in existing and isinstance(existing[t], dict):
            merged = {**row, **existing[t]}
            base[t] = merged
        elif t in existing:
            base[t] = row
    data["needs"] = base
    return base


def build_profiler_profile(data: dict[str, Any]) -> dict[str, Any]:
    """Flatten onboarding + PLU lifestyle into NeedProfiler factor fields."""
    po = data.get("policyOwner") or {}
    fin = data.get("finance") or {}
    plu = (data.get("peopleLikeYou") or {}).get("response") or {}
    result = (data.get("peopleLikeYou") or {}).get("result") or {}
    ownership = result.get("ownershipInformation") or {}
    prefs = result.get("clientPreferences") or {}

    dob = po.get("dateOfBirth") or ""
    age = None
    if dob:
        from src.pipeline.people_like_you import calculate_age_from_dob

        age = calculate_age_from_dob(dob)

    profile: dict[str, Any] = {
        "Age": age,
        "Gender": po.get("gender"),
        "Dependents": int(po.get("dependents") or 0),
        "Occupation": po.get("occupation") or "Salaried",
        "Smoker": bool(po.get("isSmoker", False)),
        "MonthlyIncome": float(fin.get("monthlyIncome") or 0),
        "MonthlyExpense": float(fin.get("monthlyExpense") or 0),
        "TotalAssets": float(fin.get("liquidAssetValue") or 0),
        "TotalLiabilities": float(plu.get("liabilities") or result.get("liabilities") or 0),
        "ExistingLifeProtection": 0,
        "ExistingCriticalIllnessCoverage": 0,
        "ExistingDisabilityProtection": 0,
        "ExistingHospitalizationCoverage": 0,
        "CarOwnership": bool(
            ownership.get("car", plu.get("car", False))
        ),
        "HomeOwnership": bool(
            ownership.get("property", plu.get("property", False))
        ),
        "InternationalTraveling": bool(
            prefs.get("travelling", plu.get("travelling", False))
        ),
        "Sports": prefs.get("sports") or plu.get("sports"),
        "HospitalType": prefs.get("hospitalType") or plu.get("hospitalization_type"),
        "WardType": prefs.get("wardType") or plu.get("ward_type"),
        "Lifestyle": prefs.get("retirementLifestyle")
        or plu.get("retirement_lifestyle"),
    }
    return {k: v for k, v in profile.items() if v is not None}

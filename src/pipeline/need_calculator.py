"""
Need / gaps calculator — local goalMath amounts for UNIFIED needs.

Separated from Need Profiler: does not score or rank; only fills amounts/gaps.
"""

from __future__ import annotations

from typing import Any

from src.pipeline.goal_math import apply_amounts_to_needs, compute_need_amounts
from src.pipeline.onboarding import UNIFIED_NEED_TYPES, ensure_needs_map


def calculate_gaps_for_onboarding(
    data: dict[str, Any],
    *,
    only_empty: bool = True,
) -> dict[str, Any]:
    """
    Compute need amounts/gaps from current policyOwner + finance + enabled needs.

    Returns ``{ needs, amounts, onlyEmpty, calculatedTypes }``.
    """
    po = data.get("policyOwner") or {}
    fin = data.get("finance") or {}
    dob = (po.get("dateOfBirth") or "").strip()
    if not dob:
        raise ValueError("dateOfBirth is required to calculate need amounts")

    income = float(fin.get("monthlyIncome") or 0)
    expense = float(fin.get("monthlyExpense") or 0)
    if income <= 0 and expense <= 0:
        raise ValueError("monthlyIncome or monthlyExpense is required")

    needs_map = ensure_needs_map(data)
    amounts = compute_need_amounts(
        date_of_birth=dob,
        monthly_income=income,
        monthly_expense=expense,
        age_of_retirement=int(po.get("ageOfRetirement") or 65),
    )
    updated = apply_amounts_to_needs(needs_map, amounts, only_empty=only_empty)
    calculated_types = [
        t
        for t in UNIFIED_NEED_TYPES
        if updated.get(t, {}).get("enabled")
        and (
            not only_empty
            or float((needs_map.get(t) or {}).get("needAmount") or 0) <= 0
        )
    ]

    return {
        "needs": updated,
        "amounts": amounts,
        "onlyEmpty": only_empty,
        "calculatedTypes": calculated_types,
    }

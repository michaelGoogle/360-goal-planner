"""Need Profiler contract.

Money arrives in **USD** and is divided by the country's relative price level before it
meets the USD option-weight bands, so "below 1,000 a month" means the same standard of
living everywhere. Eleven labels are scored: Farewell was dropped in V0-16.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class NeedProfilerRequest(BaseModel):
    age: int
    dependents: int = 0
    gender: str = ""
    ownsProperty: bool = False
    incomeMonthlyUsd: float = 0
    expenseMonthlyUsd: float = 0
    liquidAssetsUsd: float = 0
    liabilitiesUsd: float = 0
    priceLevel: float = 1.0
    flags: dict[str, Any] = Field(default_factory=dict)
    parametersVersion: str = ""


class ProfiledNeed(BaseModel):
    """``parked`` needs carry a score and a priority but have no calculator."""

    type: str
    enabled: bool = False
    priority: int = 3
    score: float | None = None
    parked: bool = False


class NeedProfilerResponse(BaseModel):
    #: Need code -> scaled score. Only needs with a profiler label appear.
    scores: dict[str, float] = Field(default_factory=dict)
    #: ``prot1`` / ``prot2`` / ``grow2``. N_RET is always on and is not a pick.
    picks: dict[str, str] = Field(default_factory=dict)
    needs: list[ProfiledNeed] = Field(default_factory=list)
    fallback: bool = False
    #: Profiler label -> weighted sum, before scaling. Shown on the Need Profiler tab.
    raw: dict[str, float] = Field(default_factory=dict)
    #: Profiler label -> 0-10. The same numbers as ``scores``, keyed the JSON's way.
    scaled: dict[str, float] = Field(default_factory=dict)
    #: Factor -> option weight, and the four PPP-USD amounts the bands read.
    optionWeights: dict[str, float] = Field(default_factory=dict)

"""Plan contract (decision D2: the maths moves off the frontend).

A need is suggested when it is enabled and its gap is above 0. Protection is sized
at the gap; a wealth goal gets its own horizon. The default monthly share is the
free budget minus protection premiums, split across the suggested wealth goals and
rounded **down**, so the suggested plan always fits inside the free budget.

Customer edits win: a need whose ``planSum`` / ``planMth`` / ``planLump`` the
customer has touched is never re-seeded.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class PlanNeedInput(BaseModel):
    type: str
    enabled: bool = False
    needAmount: float = 0
    have: float = 0
    gap: float = 0
    horizonYears: int | None = None
    touchedSum: bool = False
    touchedMth: bool = False
    touchedLump: bool = False
    planSum: float | None = None
    planMth: float | None = None
    planLump: float | None = None


class PlanRequest(BaseModel):
    age: int
    gender: str = "Male"
    smoker: bool = False
    country: str = "Singapore"
    currency: str = "SGD"
    takeHomeMonthly: float = 0
    expenseMonthly: float = 0
    ageOfRetirement: int = 65
    inflationRate: float = 0.023
    investmentReturn: float = 0.042
    needs: list[PlanNeedInput] = Field(default_factory=list)
    plansOff: list[str] = Field(default_factory=list)
    parametersVersion: str = ""


class PlanNeedResult(BaseModel):
    type: str
    suggested: bool = False
    included: bool = False
    planSum: float = 0
    planPrem: float = 0
    planMth: float = 0
    planLump: float = 0
    capMth: float = 0
    fv: float = 0
    remain: float = 0


class PlanResponse(BaseModel):
    needs: list[PlanNeedResult] = Field(default_factory=list)
    investMth: float = 0
    investLump: float = 0
    protPremYear: float = 0
    currency: str = "SGD"

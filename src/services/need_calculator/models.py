"""Need Calculator contract. Pure USD in, pure USD out.

The orchestrator converts the session into USD, calls this, then converts the
result back and rounds it in the user currency. Fixed amounts are multiplied by
``priceLevel`` inside the calculator, so a low-cost country gets a smaller
treatment lump but the same income replacement.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class GoalInputs(BaseModel):
    """Goal-card inputs for one need, already converted to USD where they are money."""

    lifestyle: int | None = None
    retAge: int | None = None
    targetYear: int | None = None
    bequestUsd: float | None = None
    liabilitiesUsd: float | None = None
    dependYears: int | None = None
    incomeReplaceMonthlyUsd: float | None = None
    monthlyContributionUsd: float | None = None
    storedAmountUsd: float | None = None
    ltcStartAge: int | None = None
    taggedInvestmentsUsd: float | None = None


class NeedCalculatorRequest(BaseModel):
    age: int
    ageOfRetirement: int = 65
    lifeExpectancy: int = 85
    incomeMonthlyUsd: float = 0
    expenseMonthlyUsd: float = 0
    cashUsd: float = 0
    investmentsUsd: float = 0
    mortgageUsd: float = 0
    existingCoverUsd: dict[str, float] = Field(default_factory=dict)
    enabled: dict[str, bool] = Field(default_factory=dict)
    inputs: dict[str, GoalInputs] = Field(default_factory=dict)
    inflationRate: float = 0.023
    investmentReturn: float = 0.042
    priceLevel: float = 1.0
    parametersVersion: str = ""


class NeedResult(BaseModel):
    type: str
    needAmountUsd: float = 0
    haveUsd: float = 0
    gapUsd: float = 0


class LongevityStress(BaseModel):
    """R_LON: N_RET and N_LTC recomputed at LON_AGE. Display only, the plan is not re-sized."""

    yearsInRetirement: int = 0
    careYears: int = 0
    needAmountUsd: dict[str, float] = Field(default_factory=dict)
    gapUsd: dict[str, float] = Field(default_factory=dict)
    extraNeedUsd: dict[str, float] = Field(default_factory=dict)


class Horizons(BaseModel):
    yearsToRet: int = 0
    yearsInRet: int = 0
    eduYears: int = 0
    savYears: int = 0
    prpYears: int = 0
    careYears: int = 0


class NeedCalculatorResponse(BaseModel):
    needs: list[NeedResult] = Field(default_factory=list)
    horizons: Horizons = Field(default_factory=Horizons)
    stress: dict[str, LongevityStress] = Field(default_factory=dict)

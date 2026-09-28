"""Social security contract (decision D8).

A country plug-in that runs in the **user currency**, not USD: the wage ceiling
and the age bands are local law. Singapore has the SG-CPF module; every other
country falls to the default module, which takes nothing and returns take-home
equal to gross.
"""

from __future__ import annotations

from pydantic import BaseModel


class ContributionRequest(BaseModel):
    country: str = "Singapore"
    residency: str = "Singapore Citizen"
    age: int
    grossMonthly: float
    currency: str = "SGD"


class ContributionResponse(BaseModel):
    module: str
    employeeContribution: float
    takeHome: float
    rate: float = 0.0
    currency: str = "SGD"

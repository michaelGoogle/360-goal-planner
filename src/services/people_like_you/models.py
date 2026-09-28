"""People Like You contract.

Runs in the **user currency** (the LLM income clamp is an occupation x country
band in that currency, per the PLU currency decision). The orchestrator converts
the response to USD before any calculator sees it.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from src.services.fx.models import FxLock


class PeopleLikeYouRequest(BaseModel):
    dateOfBirth: str = ""
    age: int | None = None
    occupation: str = ""
    gender: str = ""
    residency: str = "Singapore Citizen"
    dependents: int = 0
    maritalStatus: str | None = None
    yearsEmployed: int | None = None
    country: str = "Singapore"
    city: str = "Singapore"
    fx: FxLock | None = None
    parametersVersion: str = ""


class Policy(BaseModel):
    type: str = ""
    sum: float = 0
    premium: float = 0
    source: str = ""


class PeopleLikeYouResponse(BaseModel):
    """Money in the user currency. ``flags`` carries the LLM's lifestyle answers."""

    currency: str = "SGD"
    incomeMonthly: float = 0
    expenseMonthly: float = 0
    takeHomeMonthly: float = 0
    cash: float = 0
    investments: float = 0
    property: float = 0
    mortgage: float = 0
    liabilities: float = 0
    policies: list[Policy] = Field(default_factory=list)
    lifeExpectancy: int | None = None
    isSmoker: bool = False
    flags: dict[str, Any] = Field(default_factory=dict)
    source: str = "people-like-you"

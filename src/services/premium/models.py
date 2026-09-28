"""Premium contract (decision D9).

A real premium-quote API does not exist yet, so the default client is a mock that
reproduces the workbook placeholder: the sum times ``protectionPremiumRate``,
rounded to the premium step. ``indicative`` says so on every response, and the
adapter for the real API will implement this same interface.
"""

from __future__ import annotations

from pydantic import BaseModel


class PremiumQuoteRequest(BaseModel):
    needType: str
    sumAssured: float
    currency: str = "SGD"
    age: int
    gender: str = "Male"
    smoker: bool = False
    country: str = "Singapore"
    termYears: int | None = None


class PremiumQuoteResponse(BaseModel):
    annualPremium: float
    currency: str = "SGD"
    source: str = ""
    rate: float | None = None
    indicative: bool = True

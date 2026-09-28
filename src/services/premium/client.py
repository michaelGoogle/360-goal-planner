"""Premium clients. The mock is the default until a quote API exists (WP9)."""

from __future__ import annotations

from typing import Protocol

from src.services.http import request_json
from src.services.premium import service
from src.services.premium.models import PremiumQuoteRequest, PremiumQuoteResponse

DEPENDENCY = "premium"


class PremiumClient(Protocol):
    def quote(self, req: PremiumQuoteRequest) -> PremiumQuoteResponse: ...


class MockPremiumClient:
    """The workbook placeholder: sum x rate, rounded to the premium step.

    The per-need rate table lives in the admin parameters (all rows 0.078% today),
    so a better placeholder is a parameter change rather than a code change.
    """

    def quote(self, req: PremiumQuoteRequest) -> PremiumQuoteResponse:
        return service.quote(req)


class HttpPremiumClient:
    def __init__(self, base_url: str):
        self.base_url = base_url

    def quote(self, req: PremiumQuoteRequest) -> PremiumQuoteResponse:
        return PremiumQuoteResponse.model_validate(
            request_json("POST", self.base_url, "/v1/premium/quote", DEPENDENCY, body=req.model_dump())
        )

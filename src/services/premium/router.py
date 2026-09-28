"""Premium route."""

from __future__ import annotations

from fastapi import APIRouter

from src.services.premium import service
from src.services.premium.models import PremiumQuoteRequest, PremiumQuoteResponse

router = APIRouter(prefix="/v1/premium", tags=["premium"])


@router.post("/quote")
def post_quote(body: PremiumQuoteRequest) -> PremiumQuoteResponse:
    return service.quote(body)

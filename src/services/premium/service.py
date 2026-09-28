"""Placeholder premium: the workbook rate, rounded to the premium step.

A real quote API will implement the same ``quote`` shape. Until then the rate lives
in the admin parameters (``protectionPremiumRate``, or ``PREMIUM_RATE_<TYPE>`` when
a need has its own row) so a better placeholder is a data change.
"""

from __future__ import annotations

from src.money import nice_step, round_half_up
from src.services.config import service as config_service
from src.services.premium.models import PremiumQuoteRequest, PremiumQuoteResponse


def rate_for(need_type: str, params: dict) -> float:
    """Per-need rate if one exists, otherwise the single placeholder."""
    named = params.get(f"PREMIUM_RATE_{need_type}")
    if named is not None:
        return float(named)
    return float(params["protectionPremiumRate"])


def quote(req: PremiumQuoteRequest) -> PremiumQuoteResponse:
    params = config_service.values("")
    rate = rate_for(req.needType, params)
    if req.sumAssured <= 0:
        return PremiumQuoteResponse(
            annualPremium=0,
            currency=req.currency,
            source="mock:placeholder-rate",
            rate=rate,
            indicative=True,
        )
    from src.services.registry import get_fx_client

    fx = get_fx_client().lock(req.currency, req.country)
    step = nice_step(float(params["coverPremRoundStep"]), fx)
    raw = float(req.sumAssured) * rate
    annual = max(0.0, round_half_up(raw / step, 0) * step) if step else max(0.0, raw)
    return PremiumQuoteResponse(
        annualPremium=annual,
        currency=req.currency,
        source="mock:placeholder-rate",
        rate=rate,
        indicative=True,
    )

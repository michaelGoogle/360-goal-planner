"""FX routes in GP. Thin: they only expose the client, the rates live in FM.

The frontend needs the locked rate and its ``asOf`` to label amounts, and the
country list for the session, hence these two routes rather than a client alone.
"""

from __future__ import annotations

from fastapi import APIRouter

from src.services.fx.models import FxLock, FxLockRequest
from src.services.registry import get_fx_client

router = APIRouter(prefix="/v1/fx", tags=["fx"])


@router.post("/lock")
def post_lock(body: FxLockRequest) -> FxLock:
    return get_fx_client().lock(body.currency, body.country, body.baseCountry)


@router.get("/countries")
def get_countries() -> list[str]:
    return get_fx_client().countries()

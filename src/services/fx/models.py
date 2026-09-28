"""FX contract. The service runs in FM; GP holds the lock and the money helpers.

``FxLock`` is what GP stores on the session at the start of predict and reuses for
every later call, so a customer's needs do not move because the market moved
overnight. It is assembled from two FM calls, a rate and a price level.

``priceLevel`` is the *relative* price level: the country's price level divided by
the base country's (``PPP_BASE_COUNTRY``, Singapore). It multiplies every USD
fixed amount and divides local money on its way into Need Profiler bands. A
country with no usable PPP gets 1.0, which is plain option A.
"""

from __future__ import annotations

from pydantic import BaseModel


class FxLockRequest(BaseModel):
    currency: str
    country: str = "Singapore"
    baseCountry: str = "Singapore"


class FxLock(BaseModel):
    currency: str
    country: str = ""
    usdPerLocal: float
    priceLevel: float = 1.0
    priceLevelCountry: float | None = None
    priceLevelBase: float | None = None
    baseCountry: str = "Singapore"
    pppAvailable: bool = True
    asOf: str = ""
    source: str = ""


class FxRate(BaseModel):
    """FM ``GET /v1/fx/rate/{ccy}``. ``refRate`` is units per 1 USD, as stored."""

    currencyIso: str
    refRate: float
    usdPerLocal: float
    asOf: str = ""


class PriceLevel(BaseModel):
    """FM ``GET /v1/fx/price-level/{country}``.

    ``relative`` is the number a calculation uses; ``priceLevel`` and
    ``basePriceLevel`` are the two figures it came from, kept so a locked rate can
    be checked later rather than taken on trust.
    """

    country: str
    baseCountry: str = "Singapore"
    priceLevel: float = 1.0
    basePriceLevel: float = 1.0
    relative: float = 1.0
    pppYear: int | None = None

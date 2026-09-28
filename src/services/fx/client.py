"""FX clients.

``HttpFxClient`` is production and talks to the FX service in FM. ``SnapshotFxClient``
reads the same CSVs the workbook FX tab was built from, so parity tests reproduce the
model exactly at the 2026-09-25 snapshot without a database or a network. ``MockFxClient``
is for unit tests that only need some rate.

There is deliberately no fallback currency anywhere: an unknown ISO code raises
``UnknownCurrency``. The old ``src/fx.py`` silently used the Singapore rate for any code
it did not recognise, which is how a Vietnamese salary could be valued as Singapore
dollars and nobody would see an error.

A country with no World Bank PPP is different: that is not a mistake, so the lock falls
back to a relative price level of 1.0 and says so with ``pppAvailable = False``. With the
price level at 1.0 the pipeline is plain conversion, which is option A.
"""

from __future__ import annotations

import csv
import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Protocol

from src.services.errors import DependencyFailed, UnknownCurrency
from src.services.fx.models import FxLock, FxRate, PriceLevel
from src.services.http import request_json

logger = logging.getLogger(__name__)

DEPENDENCY = "fx"

# The rates and price levels the calculation workbook was built from. Checkout
# keeps a copy beside the workbook; Docker ships GP/config/fx_ppp because
# `.dockerignore` drops **/docs/.
SNAPSHOT_CANDIDATES = (
    Path(__file__).resolve().parents[3] / "docs" / "calculations" / "fx_ppp",
    Path(__file__).resolve().parents[3] / "config" / "fx_ppp",
)


def snapshot_dir() -> Path:
    override = os.environ.get("GP_FX_SNAPSHOT_DIR")
    if override:
        return Path(override)
    for candidate in SNAPSHOT_CANDIDATES:
        if (candidate / "currencies_fx.csv").is_file():
            return candidate
    return SNAPSHOT_CANDIDATES[0]


class FxClient(Protocol):
    def lock(self, currency: str, country: str = "Singapore", base_country: str = "Singapore") -> FxLock: ...
    def rate(self, currency: str) -> FxRate: ...
    def price_level(self, country: str, base_country: str = "Singapore") -> PriceLevel: ...
    def countries(self) -> list[str]: ...


class _LockMixin:
    """One rate call plus one price-level call, assembled into the session's lock."""

    source = ""

    def lock(
        self, currency: str, country: str = "Singapore", base_country: str = "Singapore"
    ) -> FxLock:
        rate = self.rate(currency)
        try:
            level = self.price_level(country, base_country)
            relative, available = level.relative, True
            level_country, level_base = level.priceLevel, level.basePriceLevel
        except (DependencyFailed, LookupError) as exc:
            # "This country has no World Bank PPP" is a known state, not a failure, so
            # the lock falls back to option A. An unreachable FX service is a failure
            # and must not quietly turn into a price level of 1.0.
            if isinstance(exc, DependencyFailed) and exc.extra.get("upstreamStatus") != 404:
                raise
            logger.info("No price level for %r, locking at 1.0: %s", country, exc)
            relative, available = 1.0, False
            level_country = level_base = None

        return FxLock(
            currency=rate.currencyIso,
            country=country,
            usdPerLocal=rate.usdPerLocal,
            priceLevel=relative,
            priceLevelCountry=level_country,
            priceLevelBase=level_base,
            baseCountry=base_country,
            pppAvailable=available,
            asOf=rate.asOf,
            source=self.source,
        )


class HttpFxClient(_LockMixin):
    """The FX service in the FM docker, reached through the existing FM upstream."""

    source = "fm"

    def __init__(self, base_url: str):
        self.base_url = base_url

    def rate(self, currency: str) -> FxRate:
        return FxRate.model_validate(
            request_json("GET", self.base_url, f"/v1/fx/rate/{currency}", DEPENDENCY)
        )

    def price_level(self, country: str, base_country: str = "Singapore") -> PriceLevel:
        return PriceLevel.model_validate(
            request_json(
                "GET", self.base_url, f"/v1/fx/price-level/{country}", DEPENDENCY,
                params={"base": base_country},
            )
        )

    def countries(self) -> list[str]:
        return list(request_json("GET", self.base_url, "/v1/fx/countries", DEPENDENCY) or [])


@lru_cache(maxsize=4)
def _snapshot_rates(directory: str) -> tuple[dict[str, float], str]:
    """``{ISO: usd_per_local}`` and the snapshot date, from currencies_fx.csv."""
    rates: dict[str, float] = {"USD": 1.0}
    as_of = ""
    path = Path(directory) / "currencies_fx.csv"
    with path.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            iso = (row.get("currency") or "").strip().upper()
            usd_per_1 = (row.get("usd_per_1") or "").strip()
            if len(iso) != 3 or not usd_per_1:
                continue
            rates[iso] = float(usd_per_1)
            as_of = as_of or (row.get("date") or "").strip()
    return rates, as_of


@lru_cache(maxsize=4)
def _snapshot_levels(directory: str) -> dict[str, float]:
    """``{country: absolute price level}``, skipping countries the World Bank has no PPP for."""
    levels: dict[str, float] = {}
    path = Path(directory) / "countries_ppp.csv"
    with path.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            country = (row.get("country") or "").strip()
            level = (row.get("price_level") or "").strip()
            if country and level:
                levels[country] = float(level)
    return levels


class SnapshotFxClient(_LockMixin):
    """Reads docs/calculations/fx_ppp/*.csv — the rates the workbook was built on."""

    source = "snapshot"

    def rate(self, currency: str) -> FxRate:
        rates, as_of = _snapshot_rates(str(snapshot_dir()))
        iso = (currency or "").strip().upper()
        usd_per_local = rates.get(iso)
        if not usd_per_local:
            raise UnknownCurrency(iso)
        return FxRate(
            currencyIso=iso,
            refRate=1.0 / usd_per_local,
            usdPerLocal=usd_per_local,
            asOf=as_of,
        )

    def price_level(self, country: str, base_country: str = "Singapore") -> PriceLevel:
        levels = _snapshot_levels(str(snapshot_dir()))
        here, base = levels.get(country), levels.get(base_country)
        if here is None or base is None:
            missing = country if here is None else base_country
            raise LookupError(f"No price level for {missing!r} in the snapshot")
        return PriceLevel(
            country=country,
            baseCountry=base_country,
            priceLevel=here,
            basePriceLevel=base,
            relative=round(here / base, 6),
        )

    def countries(self) -> list[str]:
        return sorted(_snapshot_levels(str(snapshot_dir())))


class MockFxClient(_LockMixin):
    """A fixed rate and price level, for tests that do not care which."""

    source = "mock"

    def __init__(
        self,
        usd_per_local: float = 0.78162734281267,
        price_level: float = 1.0,
        currency: str = "SGD",
        country: str = "Singapore",
    ):
        self.usd_per_local = usd_per_local
        self._price_level = price_level
        self.currency = currency
        self.country = country

    def rate(self, currency: str = "") -> FxRate:
        iso = (currency or self.currency).upper()
        return FxRate(
            currencyIso=iso,
            refRate=1.0 / self.usd_per_local,
            usdPerLocal=self.usd_per_local,
            asOf="2026-09-25",
        )

    def price_level(self, country: str = "", base_country: str = "Singapore") -> PriceLevel:
        return PriceLevel(
            country=country or self.country,
            baseCountry=base_country,
            priceLevel=self._price_level,
            basePriceLevel=1.0,
            relative=self._price_level,
        )

    def countries(self) -> list[str]:
        return [self.country]

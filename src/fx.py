"""Deprecated: local money to USD for the Need Profiler. Removed in WP7.

This used to hold nine hand-maintained rates and fall back to the Singapore rate for
any code it did not recognise, so a Vietnamese salary could be valued as Singapore
dollars with only a log line to show for it. Both are gone: the rates now come from
the committed FX snapshot (148 currencies, the same file the calculation workbook was
built from) and an unknown code raises.

It still reads a snapshot rather than the session's locked rate, because the Need
Profiler takes a currency code rather than an ``FxLock``. WP7 gives it PPP-USD money
from the orchestrator and this module goes away. Everything else already uses
``src.money`` with the lock on the session.
"""

from __future__ import annotations

import logging

from src.services.fx.client import SnapshotFxClient

logger = logging.getLogger(__name__)

_snapshot = SnapshotFxClient()


def usd_per_local(currency: str | None) -> float:
    """USD for 1 unit of ``currency``. Raises ``UnknownCurrency`` for an unknown code."""
    return _snapshot.rate(currency or "SGD").usdPerLocal


def to_usd(local_amount: float, currency: str | None) -> float:
    return float(local_amount or 0) * usd_per_local(currency)

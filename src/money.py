"""Currency conversion and rounding, used by the orchestrators and never by a calculator.

The model calculates in USD (``systemCurrency``) and the customer reads their own
currency, so every request follows the same shape:

    convert in  ->  calculate in USD  ->  convert back  ->  round in the user currency

Keeping that in one module means a calculator never sees a currency and can never
mix units. The rate comes from the ``FxLock`` on the session, so a customer's needs
do not move because the market moved overnight.

Two distinct uses of the price level, easy to confuse:

``ppp_usd`` **divides** by it, to ask "how well off is this person, in a way that
compares across countries" — that is what Need Profiler's bands need.

``fixed`` **multiplies** by it, to ask "what does this cost here" — a course of
cancer treatment costs less in Vietnam than in Singapore. That is option B
(``priceLevelOn``); with the price level at 1.0 both reduce to plain conversion.
"""

from __future__ import annotations

import math
from decimal import ROUND_HALF_UP, Decimal

from src.services.fx.models import FxLock

# Steps a rounded amount is allowed to land on, per power of ten.
_NICE_MULTIPLES = (1.0, 2.0, 5.0, 10.0)


def to_usd(amount_local: float, fx: FxLock) -> float:
    return float(amount_local or 0) * fx.usdPerLocal


def to_user(amount_usd: float, fx: FxLock) -> float:
    return float(amount_usd or 0) / fx.usdPerLocal


def round_user(amount: float) -> int:
    """Whole units of the user's currency, half to even as the existing code rounds."""
    return int(round(float(amount or 0)))


def round_half_up(amount: float, places: int = 0) -> float:
    """Round with halves going up, which is what Excel's ROUND does.

    The workbook mimics Python's half-to-even almost everywhere, deliberately, but two
    cells use plain ROUND: monthly expense and the home seed converted back. On an exact
    half those differ by a cent, which the assets estimate then multiplies by 216.
    """
    quantum = Decimal(1).scaleb(-places)
    rounded = Decimal(str(float(amount or 0))).quantize(quantum, rounding=ROUND_HALF_UP)
    return float(rounded)


def ppp_usd(amount_local: float, fx: FxLock) -> float:
    """Local money as purchasing-power USD, for bands that must compare countries."""
    level = fx.priceLevel or 1.0
    return to_usd(amount_local, fx) / level


def fixed(amount_usd: float, fx: FxLock) -> float:
    """A USD parameter as what it costs in the customer's country."""
    return float(amount_usd or 0) * (fx.priceLevel or 1.0)


def nice_step(step_usd: float, fx: FxLock) -> float:
    """A USD rounding step as a round-looking step in the user's currency.

    Converting SGD 1,000 to USD and back gives 999.9999; a slider that moves in steps
    of 999.9999 is worse than useless. So convert, then snap to the nearest 1, 2 or 5
    times a power of ten. SGD 50 stays 50 and VND becomes 1,000,000, not 1,279,383.

    The nearest is by ratio rather than by difference, because these span nine orders
    of magnitude: 700 is closer to 1,000 than to 500 in the sense that matters here.
    """
    local = to_user(step_usd, fx)
    if local <= 0 or not math.isfinite(local):
        return 0.0

    power = math.floor(math.log10(local))
    best = 0.0
    best_error = math.inf
    for multiple in _NICE_MULTIPLES:
        candidate = multiple * (10.0**power)
        if candidate <= 0:
            continue
        error = abs(math.log10(candidate / local))
        if error < best_error:
            best, best_error = candidate, error
    return best


def round_to_step(amount: float, step: float) -> float:
    """Round to the nearest multiple of ``step``. A step of 0 means no rounding."""
    if not step:
        return float(amount or 0)
    return round(float(amount or 0) / step) * step

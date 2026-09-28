"""People Like You: the LLM estimate, then everything that follows from it.

Runs in the **user currency**. The income estimate and its occupation × country clamp
are local-currency numbers by decision, so converting them here would break the clamp.
What is in USD are the admin parameters — the property bands, the expense floor, the
life-cover step — and those are converted out to the user's currency at the session's
locked rate before they are compared against anything.

WP5 replaces four things that were SGD constants in ``predict.py``: the property income
bands, the property values, the life-cover rounding step (a hard-coded S$100,000) and
the expense floor (which the frontend owned).
"""

from __future__ import annotations

import logging
from typing import Any

from src.money import fixed, nice_step, round_half_up, round_user, to_user
from src.services.config import service as config_service
from src.services.fx.models import FxLock
from src.services.people_like_you.models import (
    PeopleLikeYouRequest,
    PeopleLikeYouResponse,
    Policy,
)
from src.services.social_security.models import ContributionRequest

logger = logging.getLogger(__name__)

LIFE_COVER_INCOME_YEARS = 5


def spend_share(dependents: int, params: dict[str, Any]) -> float:
    base = float(params["spendShareBase"])
    per = float(params["spendSharePerDependant"])
    cap = float(params["spendShareCap"])
    return min(base + per * max(0, int(dependents or 0)), cap)


def expense_floor(fx: FxLock, params: dict[str, Any]) -> float:
    """The smallest monthly spend the model will record, in the user's currency.

    Plain conversion, no price level: the workbook's cell is
    ``ROUND(MIN_EXPENSE_MONTHLY / FX_usdPerLocal, 2)``. It reads as a plausibility
    threshold on what someone typed rather than as the cost of a basket of goods.
    """
    return round_half_up(to_user(float(params["MIN_EXPENSE_MONTHLY"]), fx), 2)


def property_seed(income_monthly: float, fx: FxLock, params: dict[str, Any]) -> float:
    """Assumed home value in the user's currency, from monthly gross income.

    Bands and values are USD; both sides of the comparison are converted, so the
    thresholds land where the workbook puts them whatever currency the session is in.
    """
    low_band = to_user(fixed(float(params["propertyIncomeLow"]), fx), fx)
    high_band = to_user(fixed(float(params["propertyIncomeHigh"]), fx), fx)
    if income_monthly < low_band:
        value_usd = float(params["propertyLow"])
    elif income_monthly <= high_band:
        value_usd = float(params["propertyMid"])
    else:
        value_usd = float(params["propertyHigh"])
    return round_half_up(to_user(fixed(value_usd, fx), fx))


def life_cover_step(fx: FxLock, params: dict[str, Any]) -> float:
    """The step assumed life cover is rounded to — S$100,000 in a Singapore session."""
    return nice_step(float(params["lifeRoundUnit"]), fx)


def round_up_to_step(amount: float, step: float) -> float:
    """Halves round up, which is what a person does when picking a cover amount."""
    if amount <= 0 or step <= 0:
        return 0.0
    return float(int((amount + step / 2) // step) * step)


def assumed_life_policy(
    *,
    property_value: float,
    mortgage: float,
    income_monthly: float,
    dependents: int,
    fx: FxLock,
    params: dict[str, Any],
) -> Policy | None:
    """Mortgage cover, or five years of income when someone depends on them."""
    mortgage_cover = 0.0
    if property_value > 0:
        mortgage_cover = round_up_to_step(mortgage, life_cover_step(fx, params))
    dependents_cover = 0.0
    if int(dependents or 0) > 0:
        dependents_cover = round_user(income_monthly * 12 * LIFE_COVER_INCOME_YEARS)
    sum_assured = max(mortgage_cover, dependents_cover)
    if sum_assured <= 0:
        return None
    return Policy(
        type="Life Protection",
        sum=sum_assured,
        premium=max(0.0, round_user(sum_assured * float(params["lifePremiumRate"]))),
        source="people-like-you",
    )


def life_expectancy(reported: Any, params: dict[str, Any]) -> int:
    """What the model will plan to. Capped at LON_AGE, defaulted when unusable."""
    cap = int(params["LON_AGE"])
    try:
        years = int(float(reported))
    except (TypeError, ValueError):
        years = 0
    if years <= 0:
        years = int(params["lifeExpectancyDefault"])
    return min(years, cap)


def derive(
    *,
    income_monthly: float,
    age: int,
    dependents: int,
    residency: str | None,
    country: str,
    currency: str,
    owns_property: bool,
    reported_life_expectancy: Any = None,
    liquid_assets: float = 0.0,
    fx: FxLock,
    parameters_version: str = "",
) -> PeopleLikeYouResponse:
    """Everything that follows deterministically from the LLM's income estimate.

    Pure: no LLM, no HTTP beyond the social-security client, so the parity tests can
    feed it the fixture's income and check the rest.
    """
    # Imported here, not at module scope: the registry builds every client, including
    # this service's own, so importing it at the top closes a cycle.
    from src.services.registry import get_social_security_client

    params = config_service.values(parameters_version)
    gross = max(0.0, float(income_monthly or 0))

    contribution = get_social_security_client().contribution(
        ContributionRequest(
            country=country or "Singapore",
            residency=residency or "",
            age=age or 40,
            grossMonthly=gross,
            currency=currency,
        )
    )
    take_home = contribution.takeHome
    expense = round_half_up(take_home * spend_share(dependents, params), 2)
    if gross > 0:
        expense = max(expense, expense_floor(fx, params))

    surplus = take_home - expense
    work_start = int(params["workStartAge"])
    save_share = float(params["assetsSaveShare"])
    if gross and expense and age > work_start:
        assets = max(0.0, surplus * 12 * save_share * (age - work_start))
    else:
        assets = max(0.0, float(liquid_assets or 0))

    cash = round_user(assets * float(params["CASH_SAVINGS_SHARE"]))
    investments = round_user(assets * float(params["INVESTMENTS_SHARE"]))

    property_value = property_seed(gross, fx, params) if owns_property else 0.0
    mortgage = round_user(property_value * float(params["PROPERTY_LTV"])) if property_value else 0.0

    life = assumed_life_policy(
        property_value=property_value,
        mortgage=mortgage,
        income_monthly=gross,
        dependents=dependents,
        fx=fx,
        params=params,
    )

    return PeopleLikeYouResponse(
        currency=currency,
        incomeMonthly=gross,
        expenseMonthly=expense,
        takeHomeMonthly=take_home,
        cash=cash,
        investments=investments,
        property=property_value,
        mortgage=mortgage,
        liabilities=round(assets * float(params["liabilityRatio"]), 2),
        policies=[life] if life else [],
        lifeExpectancy=life_expectancy(reported_life_expectancy, params),
    )


def predict(req: PeopleLikeYouRequest) -> PeopleLikeYouResponse:
    """The LLM estimate plus ``derive``. The route and the in-process client use this."""
    from src.pipeline.run import run_people_like_you

    fx = req.fx or FxLock(currency="SGD", usdPerLocal=1.0)
    raw = run_people_like_you(
        {
            "dateOfBirth": req.dateOfBirth,
            "occupation": req.occupation,
            "gender": req.gender,
            "residency": req.residency,
            "dependents": req.dependents,
            "maritalStatus": req.maritalStatus,
            "yearsEmployed": req.yearsEmployed,
            "country": req.country,
            "city": req.city,
        }
    )
    mapped = raw.get("result") or {}
    finance = (raw.get("onboarding") or {}).get("data", {}).get("finance") or {}
    age = req.age or int((raw.get("demographics") or {}).get("age") or 40)
    response = derive(
        income_monthly=float(finance.get("monthlyIncome") or mapped.get("income") or 0),
        age=age,
        dependents=req.dependents,
        residency=req.residency,
        country=req.country,
        currency=fx.currency,
        owns_property=bool((mapped.get("ownershipInformation") or {}).get("property")),
        reported_life_expectancy=mapped.get("lifeExpectancy"),
        liquid_assets=float(finance.get("liquidAssetValue") or mapped.get("assets") or 0),
        fx=fx,
        parameters_version=req.parametersVersion,
    )
    prefs = mapped.get("clientPreferences") or {}
    response.isSmoker = bool(prefs.get("isSmoker"))
    response.flags = mapped
    return response

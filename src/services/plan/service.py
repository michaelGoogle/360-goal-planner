"""Plan Calculator: suggested sums, premiums and contributions.

A need is suggested when it is enabled and its gap is above 0. Protection is sized
at the gap; a wealth goal gets its own horizon. The default monthly share is the
free budget minus protection premiums, split across the suggested wealth goals and
rounded **down**, so the suggested plan always fits.

Customer edits win: a touched ``planSum`` / ``planMth`` / ``planLump`` is kept.
Premiums come from the premium client, not from a rate constant here.
"""

from __future__ import annotations

import math

from src.money import nice_step
from src.needs import PROTECTION_NEEDS, WEALTH_NEEDS
from src.pipeline.goal_math import fv, fv_annuity, real_return
from src.services.config import service as config_service
from src.services.plan.models import PlanNeedInput, PlanNeedResult, PlanRequest, PlanResponse
from src.services.premium.models import PremiumQuoteRequest


def _round_down(amount: float, step: float) -> float:
    if amount <= 0 or step <= 0:
        return 0.0
    return math.floor(amount / step) * step


def _round_up(amount: float, step: float) -> float:
    if amount <= 0 or step <= 0:
        return 0.0
    return math.ceil(amount / step) * step


def _annual_pmt(target: float, rate: float, periods: int) -> float:
    if target <= 0 or periods <= 0:
        return 0.0
    if abs(rate) < 1e-12:
        return target / periods
    return (target * rate) / ((1 + rate) ** periods - 1)


def _premium(need: PlanNeedInput, req: PlanRequest, sum_assured: float) -> float:
    from src.services.registry import get_premium_client

    quote = get_premium_client().quote(
        PremiumQuoteRequest(
            needType=need.type,
            sumAssured=sum_assured,
            currency=req.currency,
            age=req.age,
            gender=req.gender,
            smoker=req.smoker,
            country=req.country,
        )
    )
    return float(quote.annualPremium)


def build_plan(req: PlanRequest) -> PlanResponse:
    from src.services.registry import get_fx_client

    params = config_service.values(req.parametersVersion)
    fx = get_fx_client().lock(req.currency, req.country)
    mth_step = nice_step(float(params["monthlyRoundStep"]), fx)
    free_share = float(params["FREE_BUDGET_SHARE"])
    rate = real_return(req.investmentReturn, req.inflationRate)

    suggested = {n.type: n.enabled and n.gap > 0 for n in req.needs}
    off = set(req.plansOff or [])
    included = {t: suggested[t] and t not in off for t in suggested}

    wealth_suggested = [n for n in req.needs if n.type in WEALTH_NEEDS and suggested.get(n.type)]
    n_wealth = len(wealth_suggested)

    prot_prem_year = 0.0
    sums: dict[str, float] = {}
    prems: dict[str, float] = {}
    for need in req.needs:
        if need.type not in PROTECTION_NEEDS:
            continue
        if need.touchedSum and need.planSum is not None:
            plan_sum = float(need.planSum)
        elif suggested.get(need.type):
            plan_sum = max(0.0, round(need.gap))
        else:
            plan_sum = 0.0
        sums[need.type] = plan_sum
        prem = _premium(need, req, plan_sum) if plan_sum > 0 else 0.0
        prems[need.type] = prem
        if suggested.get(need.type):
            prot_prem_year += prem

    surplus = max(0.0, req.takeHomeMonthly - req.expenseMonthly)
    free = surplus * free_share
    share = (
        _round_down(max(0.0, free - prot_prem_year / 12.0) / n_wealth, mth_step) if n_wealth else 0.0
    )

    rows: list[PlanNeedResult] = []
    invest_mth = 0.0
    invest_lump = 0.0
    for need in req.needs:
        t = need.type
        yrs = int(need.horizonYears or 0)
        if t in PROTECTION_NEEDS:
            plan_sum = sums.get(t, 0.0)
            plan_prem = prems.get(t, 0.0)
            remain = need.gap - plan_sum if included.get(t) else need.gap
            rows.append(
                PlanNeedResult(
                    type=t,
                    suggested=suggested.get(t, False),
                    included=included.get(t, False),
                    planSum=plan_sum,
                    planPrem=plan_prem,
                    remain=remain,
                )
            )
            continue

        cap = _round_up(_annual_pmt(need.gap, rate, yrs) / 12.0, mth_step)
        if need.touchedMth and need.planMth is not None:
            plan_mth = float(need.planMth)
        elif suggested.get(t):
            plan_mth = min(share, cap)
        else:
            plan_mth = 0.0
        if need.touchedLump and need.planLump is not None:
            plan_lump = float(need.planLump)
        else:
            plan_lump = 0.0
        growth = fv(plan_lump, rate, yrs) + fv_annuity(plan_mth * 12.0, rate, yrs) if included.get(t) else 0.0
        if included.get(t):
            invest_mth += plan_mth
            invest_lump += plan_lump
        rows.append(
            PlanNeedResult(
                type=t,
                suggested=suggested.get(t, False),
                included=included.get(t, False),
                planMth=plan_mth,
                planLump=plan_lump,
                capMth=cap,
                fv=growth,
                remain=need.needAmount - need.have - growth,
            )
        )

    return PlanResponse(
        needs=rows,
        investMth=invest_mth,
        investLump=invest_lump,
        protPremYear=prot_prem_year,
        currency=req.currency,
    )

"""Budget Calculator: half of monthly surplus against the included plan.

This is the affordability check on the Plan screen. It is not the HappiU envelope.
"""

from __future__ import annotations

from src.money import round_half_up
from src.services.budget.models import BudgetRequest, BudgetResponse
from src.services.config import service as config_service


def budget(req: BudgetRequest) -> BudgetResponse:
    params = config_service.values(req.parametersVersion)
    share = float(params["FREE_BUDGET_SHARE"])
    available = max(0.0, float(req.takeHomeMonthly or 0) - float(req.expenseMonthly or 0))
    free = round_half_up(available * share, 0)
    monthly = round_half_up(float(req.investMth or 0) + float(req.includedPremiumsYear or 0) / 12.0, 0)
    lumps = float(req.investLump or 0)
    return BudgetResponse(
        available=available,
        free=free,
        monthly=monthly,
        monthlyOver=monthly - free,
        lumps=lumps,
        lumpOver=lumps - float(req.investments or 0),
        currency=req.currency,
    )

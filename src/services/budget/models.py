"""Budget contract.

The affordability check on the Plan screen: half of the monthly surplus against
the premiums and contributions of the plans that are included. Separate from the
HappiU budget envelope, which is an admin parameter and scores something else.
"""

from __future__ import annotations

from pydantic import BaseModel


class BudgetRequest(BaseModel):
    takeHomeMonthly: float = 0
    expenseMonthly: float = 0
    investments: float = 0
    includedPremiumsYear: float = 0
    investMth: float = 0
    investLump: float = 0
    currency: str = "SGD"
    parametersVersion: str = ""


class BudgetResponse(BaseModel):
    available: float = 0
    free: float = 0
    monthly: float = 0
    monthlyOver: float = 0
    lumps: float = 0
    lumpOver: float = 0
    currency: str = "SGD"

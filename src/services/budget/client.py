"""Budget clients."""

from __future__ import annotations

from typing import Protocol

from src.services.budget import service
from src.services.budget.models import BudgetRequest, BudgetResponse
from src.services.http import request_json

DEPENDENCY = "budget"


class BudgetClient(Protocol):
    def budget(self, req: BudgetRequest) -> BudgetResponse: ...


class InProcessBudgetClient:
    def budget(self, req: BudgetRequest) -> BudgetResponse:
        return service.budget(req)


class HttpBudgetClient:
    def __init__(self, base_url: str):
        self.base_url = base_url

    def budget(self, req: BudgetRequest) -> BudgetResponse:
        return BudgetResponse.model_validate(
            request_json("POST", self.base_url, "/v1/budget", DEPENDENCY, body=req.model_dump())
        )

"""Budget route. New for the frontend, alongside /v1/plan."""

from __future__ import annotations

from fastapi import APIRouter

from src.services.budget import service
from src.services.budget.models import BudgetRequest, BudgetResponse

router = APIRouter(prefix="/v1", tags=["budget"])


@router.post("/budget")
def post_budget(body: BudgetRequest) -> BudgetResponse:
    return service.budget(body)

"""Plan route. New for the frontend, which currently does this arithmetic itself."""

from __future__ import annotations

from fastapi import APIRouter

from src.services.plan import service
from src.services.plan.models import PlanRequest, PlanResponse

router = APIRouter(prefix="/v1", tags=["plan"])


@router.post("/plan")
def post_plan(body: PlanRequest) -> PlanResponse:
    return service.build_plan(body)

"""Plan clients."""

from __future__ import annotations

from typing import Protocol

from src.services.http import request_json
from src.services.plan import service
from src.services.plan.models import PlanRequest, PlanResponse

DEPENDENCY = "plan"


class PlanClient(Protocol):
    def build_plan(self, req: PlanRequest) -> PlanResponse: ...


class InProcessPlanClient:
    def build_plan(self, req: PlanRequest) -> PlanResponse:
        return service.build_plan(req)


class HttpPlanClient:
    def __init__(self, base_url: str):
        self.base_url = base_url

    def build_plan(self, req: PlanRequest) -> PlanResponse:
        return PlanResponse.model_validate(
            request_json("POST", self.base_url, "/v1/plan", DEPENDENCY, body=req.model_dump())
        )

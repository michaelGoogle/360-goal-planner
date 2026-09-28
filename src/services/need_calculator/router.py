"""Need Calculator route."""

from __future__ import annotations

from fastapi import APIRouter

from src.services.need_calculator import service
from src.services.need_calculator.models import NeedCalculatorRequest, NeedCalculatorResponse

router = APIRouter(prefix="/v1", tags=["need-calculator"])


@router.post("/need-calculator")
def post_need_calculator(body: NeedCalculatorRequest) -> NeedCalculatorResponse:
    return service.calculate(body)

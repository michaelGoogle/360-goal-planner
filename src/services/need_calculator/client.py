"""Need Calculator clients."""

from __future__ import annotations

from typing import Protocol

from src.services.http import request_json
from src.services.need_calculator import service
from src.services.need_calculator.models import NeedCalculatorRequest, NeedCalculatorResponse

DEPENDENCY = "need-calculator"


class NeedCalculatorClient(Protocol):
    def calculate(self, req: NeedCalculatorRequest) -> NeedCalculatorResponse: ...


class InProcessNeedCalculatorClient:
    def calculate(self, req: NeedCalculatorRequest) -> NeedCalculatorResponse:
        return service.calculate(req)


class HttpNeedCalculatorClient:
    def __init__(self, base_url: str):
        self.base_url = base_url

    def calculate(self, req: NeedCalculatorRequest) -> NeedCalculatorResponse:
        return NeedCalculatorResponse.model_validate(
            request_json("POST", self.base_url, "/v1/need-calculator", DEPENDENCY, body=req.model_dump())
        )

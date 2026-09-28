"""Need Profiler clients."""

from __future__ import annotations

from typing import Protocol

from src.services.http import request_json
from src.services.need_profiler import service
from src.services.need_profiler.models import NeedProfilerRequest, NeedProfilerResponse

DEPENDENCY = "need-profiler"


class NeedProfilerClient(Protocol):
    def profile(self, req: NeedProfilerRequest) -> NeedProfilerResponse: ...


class InProcessNeedProfilerClient:
    def profile(self, req: NeedProfilerRequest) -> NeedProfilerResponse:
        return service.profile(req)


class HttpNeedProfilerClient:
    def __init__(self, base_url: str):
        self.base_url = base_url

    def profile(self, req: NeedProfilerRequest) -> NeedProfilerResponse:
        return NeedProfilerResponse.model_validate(
            request_json("POST", self.base_url, "/v1/need-profiler", DEPENDENCY, body=req.model_dump())
        )

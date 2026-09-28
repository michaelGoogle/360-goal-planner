"""Need Profiler route."""

from __future__ import annotations

from fastapi import APIRouter

from src.services.need_profiler import service
from src.services.need_profiler.models import NeedProfilerRequest, NeedProfilerResponse

router = APIRouter(prefix="/v1", tags=["need-profiler"])


@router.post("/need-profiler")
def post_need_profiler(body: NeedProfilerRequest) -> NeedProfilerResponse:
    return service.profile(body)

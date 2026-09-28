"""Social security route."""

from __future__ import annotations

from fastapi import APIRouter

from src.services.social_security import service
from src.services.social_security.models import ContributionRequest, ContributionResponse

router = APIRouter(prefix="/v1/social-security", tags=["social-security"])


@router.post("/contribution")
def post_contribution(body: ContributionRequest) -> ContributionResponse:
    return service.contribution(body)

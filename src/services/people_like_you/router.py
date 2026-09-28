"""People Like You route."""

from __future__ import annotations

from fastapi import APIRouter

from src.services.people_like_you import service
from src.services.people_like_you.models import PeopleLikeYouRequest, PeopleLikeYouResponse

router = APIRouter(prefix="/v1", tags=["people-like-you"])


@router.post("/people-like-you")
def post_people_like_you(body: PeopleLikeYouRequest) -> PeopleLikeYouResponse:
    return service.predict(body)

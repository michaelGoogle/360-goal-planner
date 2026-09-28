"""People Like You clients. The LLM call sits inside the in-process service."""

from __future__ import annotations

from typing import Protocol

from src.services.http import request_json
from src.services.people_like_you import service
from src.services.people_like_you.models import PeopleLikeYouRequest, PeopleLikeYouResponse

DEPENDENCY = "people-like-you"


class PeopleLikeYouClient(Protocol):
    def predict(self, req: PeopleLikeYouRequest) -> PeopleLikeYouResponse: ...


class InProcessPeopleLikeYouClient:
    def predict(self, req: PeopleLikeYouRequest) -> PeopleLikeYouResponse:
        return service.predict(req)


class HttpPeopleLikeYouClient:
    def __init__(self, base_url: str):
        self.base_url = base_url

    def predict(self, req: PeopleLikeYouRequest) -> PeopleLikeYouResponse:
        return PeopleLikeYouResponse.model_validate(
            request_json("POST", self.base_url, "/v1/people-like-you", DEPENDENCY, body=req.model_dump())
        )

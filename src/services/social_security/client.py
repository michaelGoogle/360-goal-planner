"""Social security clients."""

from __future__ import annotations

from typing import Protocol

from src.services.errors import NotImplementedYet
from src.services.http import request_json
from src.services.social_security import service
from src.services.social_security.models import ContributionRequest, ContributionResponse

DEPENDENCY = "social-security"


class SocialSecurityClient(Protocol):
    def contribution(self, req: ContributionRequest) -> ContributionResponse: ...


class InProcessSocialSecurityClient:
    def contribution(self, req: ContributionRequest) -> ContributionResponse:
        return service.contribution(req)


class HttpSocialSecurityClient:
    def __init__(self, base_url: str):
        self.base_url = base_url

    def contribution(self, req: ContributionRequest) -> ContributionResponse:
        return ContributionResponse.model_validate(
            request_json(
                "POST", self.base_url, "/v1/social-security/contribution", DEPENDENCY,
                body=req.model_dump(),
            )
        )


class MockSocialSecurityClient:
    """Takes nothing off, like the default module, without needing the module table."""

    def contribution(self, req: ContributionRequest) -> ContributionResponse:
        return ContributionResponse(
            module="mock", employeeContribution=0.0, takeHome=req.grossMonthly,
            rate=0.0, currency=req.currency,
        )


__all__ = [
    "SocialSecurityClient",
    "InProcessSocialSecurityClient",
    "HttpSocialSecurityClient",
    "MockSocialSecurityClient",
    "NotImplementedYet",
]

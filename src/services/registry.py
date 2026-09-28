"""One client per service, with the mode picked by an environment variable.

``GP_SVC_<NAME>`` chooses the mode and ``GP_SVC_<NAME>_URL`` the base URL when that
mode is ``http``. Callers ask the registry for a client and never import an
implementation, so moving a service into its own deployable later is a change of
one environment variable.

Defaults follow the plan: everything runs in process except premium, which is a
mock until a quote API exists, and FX, HU and SV, which are genuinely elsewhere.
FX falls back to the FM upstream GP already uses for People Like You.

Clients are built per call rather than cached, so a test that sets an environment
variable takes effect immediately.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from src.services.budget.client import BudgetClient, HttpBudgetClient, InProcessBudgetClient
from src.services.config.client import ConfigClient, HttpConfigClient, InProcessConfigClient
from src.services.errors import ValidationFailed
from src.services.fx.client import FxClient, HttpFxClient, MockFxClient, SnapshotFxClient
from src.services.hu.client import HttpHuClient, HuClient, MockHuClient
from src.services.need_calculator.client import (
    HttpNeedCalculatorClient,
    InProcessNeedCalculatorClient,
    NeedCalculatorClient,
)
from src.services.need_profiler.client import (
    HttpNeedProfilerClient,
    InProcessNeedProfilerClient,
    NeedProfilerClient,
)
from src.services.people_like_you.client import (
    HttpPeopleLikeYouClient,
    InProcessPeopleLikeYouClient,
    PeopleLikeYouClient,
)
from src.services.plan.client import HttpPlanClient, InProcessPlanClient, PlanClient
from src.services.premium.client import HttpPremiumClient, MockPremiumClient, PremiumClient
from src.services.social_security.client import (
    HttpSocialSecurityClient,
    InProcessSocialSecurityClient,
    MockSocialSecurityClient,
    SocialSecurityClient,
)
from src.services.sv.client import HttpSvClient, MockSvClient, SvClient

FM_UPSTREAM_DEFAULT = "http://127.0.0.1:8062"


@dataclass(frozen=True)
class ServiceSpec:
    name: str
    default_mode: str
    modes: tuple[str, ...]


SERVICES: dict[str, ServiceSpec] = {
    "config": ServiceSpec("config", "inproc", ("inproc", "http")),
    "fx": ServiceSpec("fx", "http", ("http", "snapshot", "mock")),
    "social_security": ServiceSpec("social_security", "inproc", ("inproc", "http", "mock")),
    "people_like_you": ServiceSpec("people_like_you", "inproc", ("inproc", "http")),
    "need_profiler": ServiceSpec("need_profiler", "inproc", ("inproc", "http")),
    "need_calculator": ServiceSpec("need_calculator", "inproc", ("inproc", "http")),
    "premium": ServiceSpec("premium", "mock", ("mock", "http")),
    "plan": ServiceSpec("plan", "inproc", ("inproc", "http")),
    "budget": ServiceSpec("budget", "inproc", ("inproc", "http")),
    "hu": ServiceSpec("hu", "http", ("http", "mock")),
    "sv": ServiceSpec("sv", "http", ("http", "mock")),
}


def env_mode(name: str) -> str:
    """The variable that picks the mode, e.g. ``GP_SVC_NEED_CALCULATOR``."""
    return f"GP_SVC_{name.upper()}"


def env_url(name: str) -> str:
    """The variable that gives the base URL in ``http`` mode."""
    return f"{env_mode(name)}_URL"


def mode(name: str) -> str:
    """The configured mode for a service, validated against the modes it supports."""
    spec = SERVICES[name]
    value = (os.environ.get(env_mode(name)) or spec.default_mode).strip().lower()
    if value not in spec.modes:
        raise ValidationFailed(
            fields=[{"loc": [env_mode(name)], "msg": f"unknown mode {value!r}", "type": "value_error"}],
            detail=f"{name} supports {', '.join(spec.modes)}",
        )
    return value


def url(name: str, default: str = "") -> str:
    """The base URL for a service in ``http`` mode.

    Missing is an error rather than a relative request, so a half-configured
    deployment says so at the first call instead of failing inside ``requests``.
    """
    value = (os.environ.get(env_url(name)) or default).strip()
    if not value:
        raise ValidationFailed(
            fields=[{"loc": [env_url(name)], "msg": "required in http mode", "type": "missing"}],
            detail=f"{name} is in http mode but has no URL",
        )
    return value


def fm_url() -> str:
    """Where the FX service lives. Same upstream GP already uses for People Like You."""
    return (os.environ.get("FM_UPSTREAM") or FM_UPSTREAM_DEFAULT).strip()


def get_config_client() -> ConfigClient:
    if mode("config") == "http":
        return HttpConfigClient(url("config"))
    return InProcessConfigClient()


def get_fx_client() -> FxClient:
    chosen = mode("fx")
    if chosen == "snapshot":
        return SnapshotFxClient()
    if chosen == "mock":
        return MockFxClient()
    return HttpFxClient(url("fx", fm_url()))


def get_social_security_client() -> SocialSecurityClient:
    chosen = mode("social_security")
    if chosen == "http":
        return HttpSocialSecurityClient(url("social_security"))
    if chosen == "mock":
        return MockSocialSecurityClient()
    return InProcessSocialSecurityClient()


def get_people_like_you_client() -> PeopleLikeYouClient:
    if mode("people_like_you") == "http":
        return HttpPeopleLikeYouClient(url("people_like_you", fm_url()))
    return InProcessPeopleLikeYouClient()


def get_need_profiler_client() -> NeedProfilerClient:
    if mode("need_profiler") == "http":
        return HttpNeedProfilerClient(url("need_profiler"))
    return InProcessNeedProfilerClient()


def get_need_calculator_client() -> NeedCalculatorClient:
    if mode("need_calculator") == "http":
        return HttpNeedCalculatorClient(url("need_calculator"))
    return InProcessNeedCalculatorClient()


def get_premium_client() -> PremiumClient:
    if mode("premium") == "http":
        return HttpPremiumClient(url("premium"))
    return MockPremiumClient()


def get_plan_client() -> PlanClient:
    if mode("plan") == "http":
        return HttpPlanClient(url("plan"))
    return InProcessPlanClient()


def get_budget_client() -> BudgetClient:
    if mode("budget") == "http":
        return HttpBudgetClient(url("budget"))
    return InProcessBudgetClient()


def get_hu_client() -> HuClient:
    if mode("hu") == "mock":
        return MockHuClient()
    return HttpHuClient()


def get_sv_client() -> SvClient:
    if mode("sv") == "mock":
        return MockSvClient()
    return HttpSvClient()


def modes() -> dict[str, str]:
    """Every service and its current mode. Handy for /health and for debugging."""
    return {name: mode(name) for name in SERVICES}

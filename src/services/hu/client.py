"""HappiU clients. GP owns the payload mapping only; HU runs the Monte Carlo.

Wraps the existing ``src.upstream.hu_happiu`` so the orchestrator depends on a
client rather than on ``requests``, and so a test can swap in the mock.
"""

from __future__ import annotations

from typing import Any, Protocol

from src.services.errors import DependencyFailed
from src.upstream import UpstreamError, hu_happiu

DEPENDENCY = "hu"


class HuClient(Protocol):
    def score(self, payload: dict[str, Any]) -> dict[str, Any]: ...


class HttpHuClient:
    def score(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            status, data = hu_happiu(payload)
        except UpstreamError as exc:
            raise DependencyFailed(DEPENDENCY, exc.detail, upstream_status=exc.status) from exc
        if status >= 400:
            raise DependencyFailed(DEPENDENCY, data, upstream_status=status)
        return data if isinstance(data, dict) else {"result": data}


class MockHuClient:
    """Returns a recorded-looking response, for tests that only need a score."""

    def __init__(self, pre: float = 50.0, post: float = 60.0):
        self.pre = pre
        self.post = post

    def score(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {"result": {"preHappiU": self.pre, "postHappiU": self.post}, "breakdown": None}

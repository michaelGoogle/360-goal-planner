"""Scenario Visualizer clients. GP owns the payload mapping only."""

from __future__ import annotations

from typing import Any, Protocol

from src.services.errors import DependencyFailed
from src.upstream import UpstreamError, sv_project

DEPENDENCY = "sv"


class SvClient(Protocol):
    def project(self, payload: dict[str, Any]) -> dict[str, Any]: ...


class HttpSvClient:
    def project(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            status, data = sv_project(payload)
        except UpstreamError as exc:
            raise DependencyFailed(DEPENDENCY, exc.detail, upstream_status=exc.status) from exc
        if status >= 400:
            raise DependencyFailed(DEPENDENCY, data, upstream_status=status)
        return data if isinstance(data, dict) else {"data": data}


class MockSvClient:
    """An empty path, for tests that only need the call to succeed."""

    def project(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {"data": {"preWealth": [], "postWealth": []}}

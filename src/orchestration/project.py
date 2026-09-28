"""POST /v1/project — map the session into a Scenario Visualizer body and project it."""

from __future__ import annotations

from typing import Any

from src.insapi_sync import schedule_insapi_sync
from src.predict import session_dict
from src.services.errors import DependencyFailed, GpError
from src.services.registry import get_sv_client
from src.sv_payload import build_sv_payload


def run_project(body: dict[str, Any]) -> dict[str, Any]:
    session = session_dict(body)
    payload = build_sv_payload(session)
    try:
        data = get_sv_client().project(payload)
    except DependencyFailed as exc:
        raise GpError(exc.extra.get("upstreamStatus") or exc.status, exc.detail) from exc

    inner = data.get("data") if isinstance(data, dict) else data
    schedule_insapi_sync(session)
    return {"success": True, "data": inner, "raw": data, "payload": payload}


def build_payload_only(body: dict[str, Any]) -> dict[str, Any]:
    """POST /v1/sv-payload — the mapping without running the projection (debug)."""
    return {"success": True, "payload": build_sv_payload(session_dict(body))}

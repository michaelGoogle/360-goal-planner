"""HTTP helpers for FM / HU / SV upstreams."""
from __future__ import annotations

import os
from typing import Any

import requests

from src.env_bootstrap import load_env_files  # noqa: F401

_DEFAULT_FM = "http://127.0.0.1:8062"
_DEFAULT_HU = "http://127.0.0.1:8002"
_DEFAULT_SV = "http://127.0.0.1:8001"


def _env_url(name: str, default: str) -> str:
    return (os.environ.get(name) or default).rstrip("/")


def _timeout() -> float:
    return float(os.environ.get("GP_UPSTREAM_TIMEOUT_S") or "90")


class UpstreamError(Exception):
    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status = status
        self.detail = detail


def _post(
    url: str,
    body: dict[str, Any],
    *,
    headers: dict[str, str] | None = None,
    timeout: float | None = None,
) -> tuple[int, Any]:
    try:
        r = requests.post(url, json=body, headers=headers or {}, timeout=timeout or _timeout())
    except requests.RequestException as exc:
        raise UpstreamError(503, f"Unreachable {url}: {exc}") from exc
    try:
        data = r.json()
    except ValueError:
        data = {"detail": r.text[:500]}
    return r.status_code, data


def fm_public(
    path: str,
    body: dict[str, Any],
    bearer: str | None,
    *,
    timeout: float | None = None,
) -> tuple[int, Any]:
    headers: dict[str, str] = {}
    if bearer:
        headers["Authorization"] = bearer if bearer.lower().startswith("bearer ") else f"Bearer {bearer}"
        url = f"{_env_url('FM_UPSTREAM', _DEFAULT_FM)}/v1/me/onboarding/{path}"
    else:
        url = f"{_env_url('FM_UPSTREAM', _DEFAULT_FM)}/v1/public/{path}"
    return _post(url, body, headers=headers, timeout=timeout)


def hu_happiu(body: dict[str, Any]) -> tuple[int, Any]:
    return _post(f"{_env_url('HU_UPSTREAM', _DEFAULT_HU)}/v1/happi-u", body)


def sv_project(body: dict[str, Any], tenant_id: str = "helium") -> tuple[int, Any]:
    url = f"{_env_url('SV_UPSTREAM', _DEFAULT_SV)}/api/v2/scenario-visualizer?tenant_id={tenant_id}"
    return _post(url, body)

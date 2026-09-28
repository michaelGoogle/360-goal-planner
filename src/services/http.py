"""Shared HTTP plumbing for the out-of-process service clients.

One place decides how an upstream failure becomes a ``ServiceError``, so every
``Http*Client`` stays a couple of lines. A transport error or a 4xx/5xx from the
upstream is a 424 naming the dependency; the one exception is FM's
``unknown_currency``, which stays a 404 all the way to the caller.
"""

from __future__ import annotations

import os
from typing import Any

import requests

from src.services.errors import DependencyFailed, UnknownCurrency


def timeout_seconds() -> float:
    return float(os.environ.get("GP_SVC_TIMEOUT_S") or os.environ.get("GP_UPSTREAM_TIMEOUT_S") or "30")


def request_json(
    method: str,
    base_url: str,
    path: str,
    dependency: str,
    *,
    body: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
) -> Any:
    """Call an upstream service and return parsed JSON, or raise a ServiceError."""
    if not base_url:
        raise DependencyFailed(dependency, "no base URL configured")
    url = f"{base_url.rstrip('/')}/{path.lstrip('/')}"
    try:
        resp = requests.request(method, url, json=body, params=params, timeout=timeout_seconds())
    except requests.RequestException as exc:
        raise DependencyFailed(dependency, f"unreachable {url}: {exc}") from exc

    try:
        data = resp.json()
    except ValueError:
        data = {"detail": resp.text[:500]}

    # FM nests its error body under `detail`, being a FastAPI HTTPException.
    inner = data.get("detail") if isinstance(data, dict) else None
    for candidate in (data, inner):
        if isinstance(candidate, dict) and candidate.get("error") == "unknown_currency":
            raise UnknownCurrency(str(candidate.get("currency") or ""))

    if resp.status_code >= 400:
        raise DependencyFailed(dependency, data, upstream_status=resp.status_code)
    return data

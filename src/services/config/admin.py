"""Who may write a parameter version.

GP has no user table, so it asks FM: ``GET /v1/admin/whoami`` answers whether the
bearer the console handed us is a platform admin. GP never decides this itself.

``GP_CONFIG_ADMIN_MODE`` relaxes the check for local work:

    fm      ask FM (default, and the only setting for a deployment)
    open    trust the caller, for developing the admin screen without FM running
"""

from __future__ import annotations

import logging
import os

import requests
from fastapi import Request

from src.services.errors import ServiceError
from src.services.registry import fm_url

logger = logging.getLogger(__name__)


class NotAuthenticated(ServiceError):
    status = 401
    code = "not_authenticated"


class NotAuthorised(ServiceError):
    status = 403
    code = "not_authorised"


def _bearer(request: Request) -> str:
    header = request.headers.get("authorization") or ""
    if not header.strip():
        raise NotAuthenticated("This route needs the console bearer token")
    return header if header.lower().startswith("bearer ") else f"Bearer {header}"


def _timeout() -> float:
    return float(os.environ.get("GP_UPSTREAM_TIMEOUT_S") or "90")


def require_admin(request: Request) -> str:
    """Return the admin's user id, or raise. Used as a FastAPI dependency."""
    if (os.environ.get("GP_CONFIG_ADMIN_MODE") or "fm").strip().lower() == "open":
        logger.warning("GP_CONFIG_ADMIN_MODE=open: parameter writes are not authorised")
        return "local"

    url = f"{fm_url().rstrip('/')}/v1/admin/whoami"
    try:
        response = requests.get(url, headers={"Authorization": _bearer(request)}, timeout=_timeout())
    except requests.RequestException as exc:
        # Unreachable FM must not become an open door.
        raise NotAuthorised(f"Cannot check admin rights with FM: {exc}") from exc

    if response.status_code == 401:
        raise NotAuthenticated("FM rejected the bearer token")
    if response.status_code >= 400:
        raise NotAuthorised(f"FM answered {response.status_code} when asked who you are")

    try:
        body = response.json()
    except ValueError as exc:
        raise NotAuthorised("FM did not answer with JSON") from exc
    if not body.get("isPlatformAdmin"):
        raise NotAuthorised("Editing parameters needs platform admin rights")
    return str(body.get("userId") or "")

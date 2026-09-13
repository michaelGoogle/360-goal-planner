"""HTTP helpers for the 360 Prototype InsApi (contacts + financial plans)."""
from __future__ import annotations

import os
from typing import Any

import requests

from src.env_bootstrap import load_env_files  # noqa: F401

_DEFAULT_BASE = "https://demo-360-ai-prototype.360f.com"
_DEFAULT_USER_NAME = "mira.whatsapp"
_DEFAULT_USER_ID = "07e06e98-da76-496c-9ccc-9502ca535b03"
_FP_PREFIX = "/api/2025-11-25/financialPlan"


class InsApiError(Exception):
    def __init__(self, status: int, detail: str, body: Any = None):
        super().__init__(detail)
        self.status = status
        self.detail = detail
        self.body = body


def _timeout() -> float:
    return float(os.environ.get("INSAPI_TIMEOUT_S") or os.environ.get("GP_UPSTREAM_TIMEOUT_S") or "15")


def base_url() -> str:
    raw = os.environ.get("INSAPI_UPSTREAM")
    if raw is None:
        return _DEFAULT_BASE
    return raw.strip().rstrip("/")


def enabled() -> bool:
    return bool(base_url())


def advisor_user_name() -> str:
    return (os.environ.get("INSAPI_USER_NAME") or _DEFAULT_USER_NAME).strip()


def configured_user_id() -> str:
    return (os.environ.get("INSAPI_USER_ID") or _DEFAULT_USER_ID).strip()


def _post(path: str, body: dict[str, Any]) -> tuple[int, Any]:
    url = f"{base_url()}{path}"
    try:
        r = requests.post(
            url,
            json=body,
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            timeout=_timeout(),
        )
    except requests.RequestException as exc:
        raise InsApiError(503, f"Unreachable {url}: {exc}") from exc
    try:
        data = r.json()
    except ValueError:
        data = {"detail": (r.text or "")[:500]}
    return r.status_code, data


def _ok_or_raise(path: str, status: int, data: Any) -> Any:
    if status >= 400:
        detail = data
        if isinstance(data, dict):
            detail = data.get("detail") or data.get("message") or data
        raise InsApiError(status, f"InsApi {path} HTTP {status}: {detail}", data)
    return data


def search_user(user_name: str) -> dict[str, Any]:
    status, data = _post(
        "/users/searchUser",
        {"userName": user_name, "showSubordinates": False, "page": 1, "per_page": 10},
    )
    return _ok_or_raise("/users/searchUser", status, data)


def get_user(user_id: str) -> dict[str, Any]:
    status, data = _post(
        "/users/getUser",
        {
            "language": "en",
            "userId": user_id,
            "isAggregate": False,
            "showHistory": False,
            "page": 1,
            "per_page": 10,
        },
    )
    return _ok_or_raise("/users/getUser", status, data)


def get_contact(body: dict[str, Any]) -> dict[str, Any]:
    status, data = _post("/contact/getContact", body)
    return _ok_or_raise("/contact/getContact", status, data)


def create_contact(body: dict[str, Any]) -> tuple[int, Any]:
    """Return raw status+body so callers can handle duplicate-email 400."""
    return _post("/contact/createContact", body)


def update_contact(body: dict[str, Any]) -> dict[str, Any]:
    status, data = _post("/contact/updateContact", body)
    return _ok_or_raise("/contact/updateContact", status, data)


def get_financial_plan(body: dict[str, Any]) -> dict[str, Any]:
    status, data = _post(f"{_FP_PREFIX}/getFinancialPlan", body)
    return _ok_or_raise("getFinancialPlan", status, data)


def create_financial_plan(body: dict[str, Any]) -> tuple[int, Any]:
    return _post(f"{_FP_PREFIX}/createFinancialPlan", body)


def update_financial_plan(body: dict[str, Any]) -> tuple[int, Any]:
    return _post(f"{_FP_PREFIX}/updateFinancialPlan", body)

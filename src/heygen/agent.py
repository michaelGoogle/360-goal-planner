"""HeyGen Avatar III talking-head generate + poll (no Video Agent)."""

from __future__ import annotations

import logging
import os
import time
from typing import Optional

import requests

logger = logging.getLogger(__name__)

POLL_INTERVAL_SEC = 15
POLL_TIMEOUT_SEC = 2400

HEYGEN_NEEDS_CREDIT = (
    "HeyGen needs credits or a payment method before we can make the video"
)

DEFAULT_AVATAR_ID = "Juan_standing_office_front"
DEFAULT_VOICE_ID = "f081135e72934ddc82d4e9a26b513f91"


class GenerateError(Exception):
    def __init__(
        self,
        detail: str,
        *,
        status: int | None = None,
        endpoint: str = "",
        body: str = "",
    ):
        super().__init__(detail)
        self.detail = detail
        self.status = status
        self.endpoint = endpoint
        self.body = body


def heygen_configured() -> bool:
    return bool((os.environ.get("HEYGEN_API_KEY") or "").strip())


def _base_url() -> str:
    return (os.environ.get("HEYGEN_API_BASE_URL") or "https://api.heygen.com").rstrip("/")


def _headers() -> dict[str, str]:
    key = (os.environ.get("HEYGEN_API_KEY") or "").strip()
    return {
        "X-API-KEY": key,
        "x-api-key": key,
        "Content-Type": "application/json",
    }


def _clip_body(resp: requests.Response | None) -> str:
    if resp is None:
        return ""
    try:
        return (resp.text or "")[:800]
    except Exception:
        return ""


def _avatar_id() -> str:
    return (os.environ.get("HEYGEN_AVATAR_ID") or "").strip() or DEFAULT_AVATAR_ID


def _voice_id() -> str:
    return (os.environ.get("HEYGEN_VOICE_ID") or "").strip() or DEFAULT_VOICE_ID


def wallet_remaining_usd() -> float | None:
    """Prepaid API wallet USD, or None if unknown."""
    if not heygen_configured():
        return None
    url = f"{_base_url()}/v3/users/me"
    try:
        resp = requests.get(url, headers=_headers(), timeout=20)
        resp.raise_for_status()
        data = resp.json()
        inner = data.get("data") if isinstance(data.get("data"), dict) else data
        wallet = (inner or {}).get("wallet") or {}
        if str(wallet.get("currency") or "").lower() not in {"usd", ""}:
            return None
        raw = wallet.get("remaining_balance")
        if raw is None:
            return None
        return float(raw)
    except Exception:
        logger.warning("HeyGen wallet lookup failed", exc_info=True)
        return None


def _generate_payload(script: str) -> dict:
    body: dict = {
        "type": "avatar",
        "avatar_id": _avatar_id(),
        "script": script,
        "voice_id": _voice_id(),
        "title": "FinPlan360 plan report",
        "resolution": "1080p",
        "aspect_ratio": "16:9",
        "engine": {"type": "avatar_iii"},
    }
    return body


def start_video_generation(prompt: str) -> Optional[str]:
    if not heygen_configured():
        logger.warning("HEYGEN_API_KEY not set; skipping video generation")
        return None
    url = f"{_base_url()}/v3/videos"
    try:
        resp = requests.post(url, json=_generate_payload(prompt), headers=_headers(), timeout=60)
        if resp.status_code == 402:
            logger.error("HeyGen generate returned 402 payment required")
            raise GenerateError(
                HEYGEN_NEEDS_CREDIT,
                status=402,
                endpoint=url,
                body=_clip_body(resp),
            )
        try:
            resp.raise_for_status()
        except requests.HTTPError as exc:
            raise GenerateError(
                "Could not start the video",
                status=exc.response.status_code if exc.response is not None else resp.status_code,
                endpoint=url,
                body=_clip_body(exc.response or resp),
            ) from exc
        data = resp.json()
        inner = data.get("data") if isinstance(data.get("data"), dict) else data
        video_id = (inner or {}).get("video_id") or (inner or {}).get("id") or data.get("video_id")
        if video_id:
            logger.info("HeyGen Avatar III started video_id=%s", video_id)
            return str(video_id)
        logger.error("HeyGen generate did not return video_id: %r", data)
        raise GenerateError(
            "HeyGen did not start",
            endpoint=url,
            body=str(data)[:800],
        )
    except GenerateError:
        raise
    except Exception:
        logger.exception("HeyGen video generation failed")
        return None


def poll_video_status(video_id: str) -> tuple[Optional[str], Optional[str]]:
    """Return (status, video_url). status is completed | failed | processing | None."""
    if not heygen_configured():
        return (None, None)
    url = f"{_base_url()}/v3/videos/{video_id}"
    try:
        resp = requests.get(url, headers=_headers(), timeout=30)
        resp.raise_for_status()
        data = resp.json()
        inner = data.get("data") if isinstance(data.get("data"), dict) else data
        if not inner:
            inner = data
        status = str(inner.get("status") or "").lower()
        video_url = inner.get("video_url")
        if status == "completed" and video_url:
            return ("completed", str(video_url))
        if status == "failed":
            return ("failed", None)
        return ("processing", None)
    except Exception as exc:
        logger.warning("HeyGen status poll error for %s: %s", video_id, exc)
        return (None, None)


def wait_for_url(video_id: str) -> tuple[str, Optional[str]]:
    """Block until completed, failed, or timeout. Returns (status, url)."""
    started = time.monotonic()
    while (time.monotonic() - started) < POLL_TIMEOUT_SEC:
        status, url = poll_video_status(video_id)
        if status == "completed" and url:
            return ("completed", url)
        if status == "failed":
            return ("failed", None)
        time.sleep(POLL_INTERVAL_SEC)
    return ("timeout", None)

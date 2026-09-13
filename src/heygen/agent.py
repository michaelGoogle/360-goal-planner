"""HeyGen Video Agent generate + poll (session then video)."""

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


def _inner(payload: dict) -> dict:
    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    return data or payload


def _avatar_id() -> str:
    return (os.environ.get("HEYGEN_AVATAR_ID") or "").strip()


def _voice_id() -> str:
    return (os.environ.get("HEYGEN_VOICE_ID") or "").strip()


def wallet_remaining_usd() -> float | None:
    """Prepaid API wallet USD, or None if unknown."""
    if not heygen_configured():
        return None
    url = f"{_base_url()}/v3/users/me"
    try:
        resp = requests.get(url, headers=_headers(), timeout=20)
        resp.raise_for_status()
        wallet = _inner(resp.json()).get("wallet") or {}
        if str(wallet.get("currency") or "").lower() not in {"usd", ""}:
            return None
        raw = wallet.get("remaining_balance")
        if raw is None:
            return None
        return float(raw)
    except Exception:
        logger.warning("HeyGen wallet lookup failed", exc_info=True)
        return None


def _generate_payload(prompt: str) -> dict:
    body: dict = {
        "prompt": prompt,
        "mode": "generate",
        "orientation": "landscape",
    }
    avatar = _avatar_id()
    voice = _voice_id()
    if avatar:
        body["avatar_id"] = avatar
    if voice:
        body["voice_id"] = voice
    return body


def start_video_generation(prompt: str) -> Optional[str]:
    if not heygen_configured():
        logger.warning("HEYGEN_API_KEY not set; skipping video generation")
        return None
    url = f"{_base_url()}/v3/video-agents"
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
        inner = _inner(data)
        session_id = (
            inner.get("session_id")
            or inner.get("id")
            or data.get("session_id")
            or inner.get("video_id")
            or data.get("video_id")
        )
        if session_id:
            logger.info("HeyGen Video Agent started session_id=%s", session_id)
            return str(session_id)
        logger.error("HeyGen generate did not return session_id: %r", data)
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


def poll_session_status(session_id: str) -> tuple[Optional[str], Optional[str]]:
    """Return (status, video_id). status is ready | failed | processing | not_found | None."""
    if not heygen_configured():
        return (None, None)
    url = f"{_base_url()}/v3/video-agents/{session_id}"
    try:
        resp = requests.get(url, headers=_headers(), timeout=30)
        if resp.status_code in {400, 404}:
            return ("not_found", None)
        resp.raise_for_status()
        inner = _inner(resp.json())
        status = str(inner.get("status") or "").lower()
        video_id = inner.get("video_id")
        if status == "failed":
            return ("failed", None)
        if video_id:
            return ("ready", str(video_id))
        if status == "completed":
            return ("failed", None)
        return ("processing", None)
    except Exception as exc:
        logger.warning("HeyGen session poll error for %s: %s", session_id, exc)
        return (None, None)


def poll_video_status(video_id: str) -> tuple[Optional[str], Optional[str]]:
    """Return (status, video_url). status is completed | failed | processing | None."""
    if not heygen_configured():
        return (None, None)
    url = f"{_base_url()}/v3/videos/{video_id}"
    try:
        resp = requests.get(url, headers=_headers(), timeout=30)
        resp.raise_for_status()
        inner = _inner(resp.json())
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


def wait_for_url(heygen_id: str) -> tuple[str, Optional[str]]:
    """Block until completed, failed, or timeout. Returns (status, url).

    ``heygen_id`` is a Video Agent session id. Legacy Avatar III video ids still
    work: a missing session falls through to ``GET /v3/videos/{id}``.
    """
    started = time.monotonic()
    video_id: str | None = None
    while (time.monotonic() - started) < POLL_TIMEOUT_SEC:
        sess_status, sess_vid = poll_session_status(heygen_id)
        if sess_status == "failed":
            return ("failed", None)
        if sess_status == "not_found":
            video_id = heygen_id
            break
        if sess_vid:
            video_id = sess_vid
            break
        time.sleep(POLL_INTERVAL_SEC)
    if not video_id:
        return ("timeout", None)
    while (time.monotonic() - started) < POLL_TIMEOUT_SEC:
        status, url = poll_video_status(video_id)
        if status == "completed" and url:
            return ("completed", url)
        if status == "failed":
            return ("failed", None)
        time.sleep(POLL_INTERVAL_SEC)
    return ("timeout", None)

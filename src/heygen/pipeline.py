"""Start a report video job and finish it in a background thread."""

from __future__ import annotations

import json
import logging
import threading
from typing import Any

from src.heygen.agent import GenerateError, heygen_configured, start_video_generation, wait_for_url
from src.heygen.delivery import notify_ready
from src.heygen.jobs import (
    get_job,
    get_job_by_mobile,
    insert_job,
    pending_jobs,
    reset_job,
    update_job,
)
from src.heygen.media_store import StoreError, media_dir, public_base, save_html, save_mp4
from src.heygen.mobile import email_optional_ok, normalize_mobile
from src.heygen.ops_alert import (
    alert_api_failure,
    alert_from_generate_error,
    maybe_alert_low_balance,
)
from src.heygen.prompt import build_video_prompt
from src.heygen.public_id import new_job_id
from src.heygen.report_html import render_report_html

logger = logging.getLogger(__name__)


class NotifyError(Exception):
    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status = status
        self.detail = detail


def _first_name(session: dict[str, Any]) -> str:
    raw = str(session.get("name") or "").strip().split()
    return raw[0] if raw else ""


def persist_plan_report(payload: dict[str, Any]) -> None:
    """Best-effort write of contact + session + video ids to FM. Never raises."""
    try:
        from src.upstream import fm_public

        status, _data = fm_public("plan-report", payload, None, timeout=8)
        if status >= 400:
            logger.warning("FM plan-report persist status=%s", status)
    except Exception:
        logger.warning("FM plan-report persist failed", exc_info=True)


def _persist_from_job(job: dict[str, Any], session: dict[str, Any] | None = None, **extra: Any) -> None:
    payload = {
        "mobile": job.get("mobile") or "",
        "email": job.get("email") or "",
        "displayName": job.get("first_name") or "",
        "session": session or {},
        "happiPre": extra.get("pre"),
        "happiPost": extra.get("post"),
        "jobId": job.get("id") or "",
        "heygenId": extra.get("heygen_id", job.get("heygen_id") or ""),
        "heygenUrl": extra.get("heygen_url", job.get("heygen_url") or ""),
        "mediaUrl": extra.get("media_url", job.get("media_url") or ""),
        "status": extra.get("status", job.get("status") or "pending"),
        "error": extra.get("error", job.get("error") or ""),
    }
    persist_plan_report(payload)


def _still_current(job_id: str, heygen_id: str) -> bool:
    current = get_job(job_id)
    return bool(current and (current.get("heygen_id") or "") == heygen_id)


def _finish_job(job_id: str, heygen_id: str | None = None) -> None:
    job = get_job(job_id)
    if not job:
        return
    expected = heygen_id or job.get("heygen_id") or ""
    if not expected:
        update_job(job_id, status="failed", error="missing heygen id")
        _persist_from_job({**job, "status": "failed", "error": "missing heygen id"})
        return
    if not _still_current(job_id, expected):
        logger.info("Video job %s superseded before poll", job_id)
        return
    status, heygen_url = wait_for_url(expected)
    if not _still_current(job_id, expected):
        logger.info("Video job %s superseded after poll", job_id)
        return
    if status != "completed" or not heygen_url:
        err = status or "poll failed"
        update_job(job_id, status=status or "failed", error=err)
        job = get_job(job_id) or job
        _persist_from_job(job, status=status or "failed", error=err, heygen_id=expected)
        alert_api_failure(
            f"HeyGen poll ended {err}",
            job_id=job_id,
            endpoint=f"video_status {expected}",
        )
        return
    try:
        media_url = save_mp4(heygen_url, job_id)
        session = json.loads(job.get("session_json") or "{}")
        if not isinstance(session, dict):
            session = {}
        pre = job.get("happi_pre")
        post = job.get("happi_post")
        html = render_report_html(session, pre, post, video_url=media_url)
        report_url = save_html(html, job_id)
    except StoreError as exc:
        logger.warning("Media store failed for %s: %s", job_id, exc)
        if not _still_current(job_id, expected):
            return
        update_job(job_id, status="failed", heygen_url=heygen_url, error=str(exc))
        job = get_job(job_id) or job
        _persist_from_job(job, status="failed", heygen_url=heygen_url, error=str(exc), heygen_id=expected)
        return
    if not _still_current(job_id, expected):
        logger.info("Video job %s superseded after store", job_id)
        return
    update_job(job_id, status="completed", heygen_url=heygen_url, media_url=media_url)
    result = notify_ready(
        job.get("email") or "",
        job.get("mobile") or "",
        media_url,
        report_url,
        job_id,
        job.get("first_name") or "",
    )
    email_ok = not job.get("email") or (result.get("email") or {}).get("ok")
    wa_ok = not job.get("mobile") or (result.get("whatsapp") or {}).get("ok")
    job = get_job(job_id) or job
    if not email_ok and not wa_ok:
        update_job(job_id, error="delivery failed on all channels")
        _persist_from_job({**job, "error": "delivery failed on all channels"}, status="completed")
        return
    errs = []
    if job.get("email") and not email_ok:
        errs.append("email failed")
    if job.get("mobile") and not wa_ok:
        errs.append("whatsapp failed")
    if errs:
        update_job(job_id, error="; ".join(errs))
    latest = get_job(job_id) or job
    _persist_from_job(latest, status="completed", heygen_url=heygen_url, media_url=media_url or "")


def submit_notify(email: str, mobile: str, session: dict[str, Any], pre: float | None, post: float | None) -> str:
    email = (email or "").strip()
    try:
        mobile = normalize_mobile(mobile)
    except ValueError as exc:
        raise NotifyError(400, str(exc)) from exc
    if not email_optional_ok(email):
        raise NotifyError(400, "Check the email address")
    if not heygen_configured():
        raise NotifyError(503, "Video notify is not configured (HEYGEN_API_KEY)")
    if not media_dir() or not public_base():
        raise NotifyError(503, "Video notify needs MEDIA_DIR and MEDIA_PUBLIC_BASE_URL")
    maybe_alert_low_balance()
    prompt = build_video_prompt(session, pre, post, mobile)
    first = _first_name(session)
    existing = get_job_by_mobile(mobile)
    if existing:
        job_id = existing["id"]
        reset_job(
            job_id,
            email=email,
            mobile=mobile,
            first_name=first,
            prompt=prompt,
            session=session,
            pre=pre,
            post=post,
        )
    else:
        job_id = new_job_id()
        insert_job(
            job_id,
            email=email,
            mobile=mobile,
            first_name=first,
            prompt=prompt,
            session=session,
            pre=pre,
            post=post,
        )
    job = get_job(job_id) or {"id": job_id, "email": email, "mobile": mobile, "first_name": first}
    _persist_from_job(job, session, pre=pre, post=post, status="pending", heygen_id="", media_url="")
    try:
        from src.insapi_sync import schedule_insapi_sync

        tagged = dict(session)
        tagged["reportEmail"] = email
        tagged["reportMobile"] = mobile
        schedule_insapi_sync(tagged, email=email, mobile=mobile, pre=pre, post=post)
    except Exception:
        logger.warning("Prototype InsApi schedule failed", exc_info=True)
    try:
        video_id = start_video_generation(prompt)
    except GenerateError as exc:
        update_job(job_id, status="failed", error=exc.detail)
        _persist_from_job({**job, "status": "failed", "error": exc.detail})
        alert_from_generate_error(exc, job_id=job_id)
        raise NotifyError(503, exc.detail) from exc
    if not video_id:
        update_job(job_id, status="failed", error="HeyGen did not start")
        _persist_from_job({**job, "status": "failed", "error": "HeyGen did not start"})
        alert_api_failure("HeyGen did not start", job_id=job_id)
        raise NotifyError(503, "Could not start the video")
    update_job(job_id, heygen_id=video_id)
    _persist_from_job(
        {**job, "heygen_id": video_id},
        session,
        pre=pre,
        post=post,
        status="pending",
        heygen_id=video_id,
    )
    threading.Thread(
        target=_finish_job, args=(job_id, video_id), name=f"gp-video-{job_id}", daemon=True
    ).start()
    return job_id


def resume_pending() -> int:
    rows = pending_jobs()
    for job in rows:
        jid = job["id"]
        hid = job.get("heygen_id") or ""
        logger.info("Resuming pending video job %s", jid)
        threading.Thread(
            target=_finish_job, args=(jid, hid), name=f"gp-video-{jid}", daemon=True
        ).start()
    return len(rows)

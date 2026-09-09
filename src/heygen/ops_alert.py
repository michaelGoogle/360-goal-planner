"""Ops email when HeyGen wallet is low or an API call fails."""

from __future__ import annotations

import logging
import os
from typing import Any

from src.heygen.agent import wallet_remaining_usd
from src.heygen.delivery import send_email
from src.heygen.jobs import claim_ops_alert, note_ops_alert

logger = logging.getLogger(__name__)

DEFAULT_ALERT_TO = "michael.gerber@vitalus.ch"
LOW_BALANCE_KIND = "heygen_low_balance"
API_FAIL_KIND = "heygen_api_fail"
LOW_BALANCE_COOLDOWN_SEC = 12 * 3600
API_FAIL_COOLDOWN_SEC = 30 * 60


def alert_email() -> str:
    return (os.environ.get("HEYGEN_ALERT_EMAIL") or DEFAULT_ALERT_TO).strip()


def balance_threshold_usd() -> float:
    raw = (os.environ.get("HEYGEN_ALERT_BALANCE_USD") or "10").strip()
    try:
        return float(raw)
    except ValueError:
        return 10.0


def maybe_alert_low_balance() -> None:
    """Email ops if HeyGen wallet is under the threshold. Never raises."""
    try:
        to = alert_email()
        if not to:
            return
        bal = wallet_remaining_usd()
        if bal is None:
            return
        threshold = balance_threshold_usd()
        if bal >= threshold:
            note_ops_alert(LOW_BALANCE_KIND, "ok")
            return
        if not claim_ops_alert(LOW_BALANCE_KIND, "low", LOW_BALANCE_COOLDOWN_SEC):
            return
        send_email(
            to,
            f"HeyGen API wallet below ${threshold:.0f}",
            (
                f"HeyGen API wallet is ${bal:.2f} (threshold ${threshold:.0f}).\n\n"
                "Top up pay-as-you-go API credits at https://app.heygen.com "
                "(Settings → API). Web-plan credits are a separate pool.\n\n"
                "Account: michael.gerber@vitalus.ch\n"
            ),
        )
    except Exception:
        logger.warning("HeyGen low-balance alert failed", exc_info=True)


def alert_api_failure(
    summary: str,
    *,
    job_id: str = "",
    status: int | None = None,
    endpoint: str = "",
    body: str = "",
) -> None:
    """Email ops when a HeyGen API call fails. Debounced. Never raises."""
    try:
        to = alert_email()
        if not to:
            return
        fp = f"{status or 0}:{(endpoint or summary)[:80]}"
        if not claim_ops_alert(API_FAIL_KIND, fp, API_FAIL_COOLDOWN_SEC):
            return
        lines = [
            "A HeyGen API call failed on Goal Planner.",
            "",
            f"Summary: {summary}",
        ]
        if job_id:
            lines.append(f"Job id: {job_id}")
        if status is not None:
            lines.append(f"HTTP status: {status}")
        if endpoint:
            lines.append(f"Endpoint: {endpoint}")
        if body:
            lines.append("")
            lines.append("Response (truncated, no API key):")
            lines.append(body[:800])
        lines.append("")
        lines.append("Check https://app.heygen.com → Settings → API (wallet / logs).")
        send_email(to, f"HeyGen API failed: {summary[:80]}", "\n".join(lines))
    except Exception:
        logger.warning("HeyGen API-failure alert failed", exc_info=True)


def alert_from_generate_error(exc: Any, *, job_id: str = "") -> None:
    alert_api_failure(
        str(getattr(exc, "detail", None) or exc),
        job_id=job_id,
        status=getattr(exc, "status", None),
        endpoint=getattr(exc, "endpoint", "") or "",
        body=getattr(exc, "body", "") or "",
    )

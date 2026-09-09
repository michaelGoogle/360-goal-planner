"""Email + Baileys WhatsApp text-link delivery for a ready report video."""

from __future__ import annotations

import json
import logging
import os
import smtplib
import ssl
import urllib.error
import urllib.request
from email.message import EmailMessage
from typing import Any

logger = logging.getLogger(__name__)


def _env_bool(name: str, default: bool) -> bool:
    raw = (os.environ.get(name) or "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def send_email(to: str, subject: str, text_body: str) -> dict[str, Any]:
    host = (os.environ.get("SMTP_HOST") or "").strip()
    if not host:
        logger.info("SMTP_HOST unset — skip email to %s", to)
        return {"ok": True, "skipped": True}
    port = int(os.environ.get("SMTP_PORT") or "587")
    user = (os.environ.get("SMTP_USER") or "").strip()
    password = os.environ.get("SMTP_PASSWORD") or ""
    from_addr = (os.environ.get("SMTP_FROM") or user or "noreply@localhost").strip()
    use_ssl = _env_bool("SMTP_USE_SSL", False)
    use_tls = _env_bool("SMTP_USE_TLS", True) and not use_ssl
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to
    msg.set_content(text_body)
    try:
        if use_ssl:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(host, port, context=context, timeout=30) as smtp:
                if user:
                    smtp.login(user, password)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=30) as smtp:
                if use_tls:
                    smtp.starttls(context=ssl.create_default_context())
                if user:
                    smtp.login(user, password)
                smtp.send_message(msg)
        return {"ok": True}
    except Exception as exc:
        logger.warning("SMTP send failed to %s: %s", to, exc)
        return {"ok": False, "error": str(exc)}


def send_whatsapp(to: str, text: str, client_message_id: str) -> dict[str, Any]:
    gateway = (os.environ.get("WHATSAPP_GATEWAY_URL") or "http://127.0.0.1:8091").rstrip("/")
    body = json.dumps({"to": to, "text": text, "clientMessageId": client_message_id}).encode("utf-8")
    req = urllib.request.Request(
        f"{gateway}/send",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8")
            data = json.loads(raw) if raw else {}
        return {"ok": True, "data": data}
    except Exception as exc:
        detail = str(exc)
        if isinstance(exc, urllib.error.HTTPError):
            try:
                detail = exc.read().decode("utf-8", errors="replace")[:300]
            except Exception:
                detail = str(exc)
        logger.warning("WhatsApp send failed to %s: %s", to, detail)
        return {"ok": False, "error": detail}


def notify_ready(email: str, mobile: str, display_url: str, job_id: str, first_name: str) -> dict[str, Any]:
    who = first_name or "you"
    text = (
        f"Hi {who}, your FinPlan360 plan video is ready. Watch it here: {display_url}\n\n"
        f"Video id: {job_id}\n\n"
        "This is a sizing illustration, not a quote and not advice to buy."
    )
    subject = "Your FinPlan360 plan video is ready"
    out: dict[str, Any] = {"email": None, "whatsapp": None}
    if email:
        out["email"] = send_email(email, subject, text)
    if mobile:
        out["whatsapp"] = send_whatsapp(mobile, text, job_id)
    return out


def digits_or_email_ok(email: str, mobile: str) -> bool:
    em = email.strip()
    ph = "".join(c for c in mobile.strip() if c.isdigit())
    if em and "@" in em and "." in em.split("@")[-1]:
        return True
    return len(ph) >= 8

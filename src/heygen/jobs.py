"""sqlite job store for report video notify."""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_LOCK = threading.Lock()

_SCHEMA = """
CREATE TABLE IF NOT EXISTS video_jobs (
  id TEXT PRIMARY KEY,
  email TEXT,
  mobile TEXT,
  first_name TEXT,
  prompt TEXT,
  heygen_id TEXT,
  status TEXT NOT NULL,
  heygen_url TEXT,
  media_url TEXT,
  error TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ops_alerts (
  kind TEXT PRIMARY KEY,
  fingerprint TEXT,
  last_sent_at TEXT NOT NULL
);
"""


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def db_path() -> Path:
    raw = (os.environ.get("GP_VIDEO_JOBS") or "").strip()
    if raw:
        return Path(raw)
    data = _repo_root() / "data"
    data.mkdir(parents=True, exist_ok=True)
    return data / "video_jobs.sqlite"


def _connect() -> sqlite3.Connection:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(_SCHEMA)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(video_jobs)")}
    for name, spec in (("session_json", "TEXT"), ("happi_pre", "REAL"), ("happi_post", "REAL")):
        if name not in cols:
            conn.execute(f"ALTER TABLE video_jobs ADD COLUMN {name} {spec}")
    return conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def insert_job(
    job_id: str,
    *,
    email: str,
    mobile: str,
    first_name: str,
    prompt: str,
    session: dict[str, Any] | None = None,
    pre: float | None = None,
    post: float | None = None,
) -> None:
    now = _now()
    with _LOCK:
        conn = _connect()
        try:
            conn.execute(
                "INSERT INTO video_jobs (id, email, mobile, first_name, prompt, status, "
                "session_json, happi_pre, happi_post, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?)",
                (
                    job_id,
                    email,
                    mobile,
                    first_name,
                    prompt,
                    json.dumps(session or {}),
                    pre,
                    post,
                    now,
                    now,
                ),
            )
            conn.commit()
        finally:
            conn.close()


def update_job(job_id: str, **fields: Any) -> None:
    if not fields:
        return
    fields["updated_at"] = _now()
    cols = ", ".join(f"{k} = ?" for k in fields)
    vals = list(fields.values()) + [job_id]
    with _LOCK:
        conn = _connect()
        try:
            conn.execute(f"UPDATE video_jobs SET {cols} WHERE id = ?", vals)
            conn.commit()
        finally:
            conn.close()


def get_job(job_id: str) -> dict[str, Any] | None:
    with _LOCK:
        conn = _connect()
        try:
            row = conn.execute("SELECT * FROM video_jobs WHERE id = ?", (job_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()


def get_job_by_mobile(mobile: str) -> dict[str, Any] | None:
    with _LOCK:
        conn = _connect()
        try:
            row = conn.execute(
                "SELECT * FROM video_jobs WHERE mobile = ? ORDER BY updated_at DESC LIMIT 1",
                (mobile,),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()


def reset_job(
    job_id: str,
    *,
    email: str,
    mobile: str,
    first_name: str,
    prompt: str,
    session: dict[str, Any] | None = None,
    pre: float | None = None,
    post: float | None = None,
) -> None:
    update_job(
        job_id,
        email=email,
        mobile=mobile,
        first_name=first_name,
        prompt=prompt,
        session_json=json.dumps(session or {}),
        happi_pre=pre,
        happi_post=post,
        heygen_id="",
        heygen_url="",
        media_url="",
        error="",
        status="pending",
    )


def pending_jobs() -> list[dict[str, Any]]:
    with _LOCK:
        conn = _connect()
        try:
            rows = conn.execute(
                "SELECT * FROM video_jobs WHERE status = 'pending' AND heygen_id IS NOT NULL AND heygen_id != ''"
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()


def claim_ops_alert(kind: str, fingerprint: str, min_seconds: int) -> bool:
    """True if this alert should be sent now (and is recorded as sent)."""
    now = datetime.now(timezone.utc)
    with _LOCK:
        conn = _connect()
        try:
            row = conn.execute(
                "SELECT fingerprint, last_sent_at FROM ops_alerts WHERE kind = ?",
                (kind,),
            ).fetchone()
            if row:
                last_fp = row["fingerprint"] or ""
                try:
                    last = datetime.fromisoformat(str(row["last_sent_at"]).replace("Z", "+00:00"))
                    if last.tzinfo is None:
                        last = last.replace(tzinfo=timezone.utc)
                except ValueError:
                    last = None
                if last_fp == fingerprint and last is not None:
                    age = (now - last).total_seconds()
                    if age < min_seconds:
                        return False
            conn.execute(
                "INSERT INTO ops_alerts (kind, fingerprint, last_sent_at) VALUES (?, ?, ?) "
                "ON CONFLICT(kind) DO UPDATE SET fingerprint = excluded.fingerprint, "
                "last_sent_at = excluded.last_sent_at",
                (kind, fingerprint, now.isoformat(timespec="seconds")),
            )
            conn.commit()
            return True
        finally:
            conn.close()


def note_ops_alert(kind: str, fingerprint: str) -> None:
    """Record state without sending (e.g. balance recovered)."""
    now = datetime.now(timezone.utc)
    with _LOCK:
        conn = _connect()
        try:
            conn.execute(
                "INSERT INTO ops_alerts (kind, fingerprint, last_sent_at) VALUES (?, ?, ?) "
                "ON CONFLICT(kind) DO UPDATE SET fingerprint = excluded.fingerprint, "
                "last_sent_at = excluded.last_sent_at",
                (kind, fingerprint, now.isoformat(timespec="seconds")),
            )
            conn.commit()
        finally:
            conn.close()

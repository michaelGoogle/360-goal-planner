"""Download a HeyGen MP4 onto the lx43 media host directory."""

from __future__ import annotations

import logging
import os
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

DUMMY_VIDEO_ID = "generic-walkthrough"
_WORKSPACE_ROOT = Path(__file__).resolve().parents[3]


class StoreError(RuntimeError):
    """MEDIA_DIR is set but the file could not be written."""


def media_dir() -> Path | None:
    raw = (os.environ.get("MEDIA_DIR") or os.environ.get("MEDIA_HOST_DIR") or "").strip()
    if not raw:
        return None
    path = Path(raw)
    if not path.is_absolute():
        path = (_WORKSPACE_ROOT / path).resolve()
    return path


def public_base() -> str:
    return (os.environ.get("MEDIA_PUBLIC_BASE_URL") or "").rstrip("/")


def require_media() -> tuple[Path, str]:
    root = media_dir()
    base = public_base()
    if root is None:
        raise StoreError("MEDIA_DIR is required")
    if not base:
        raise StoreError("MEDIA_PUBLIC_BASE_URL is required")
    return root, base


def gp_public_url(short_id: str, ext: str) -> str:
    _, base = require_media()
    return f"{base}/gp/{short_id}.{ext.lstrip('.')}"


def dummy_media_url() -> str:
    """Public URL of the shared generic walkthrough (same file for every customer)."""
    base = public_base()
    return f"{base}/gp/{DUMMY_VIDEO_ID}.mp4" if base else ""


def save_mp4(heygen_url: str, short_id: str) -> str:
    """Write ``gp/{id}.mp4``. Return the public media URL.

    Raises StoreError when MEDIA_DIR / MEDIA_PUBLIC_BASE_URL is missing or the write fails.
    """
    root, base = require_media()
    dest_dir = root / "gp"
    dest = dest_dir / f"{short_id}.mp4"
    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
        resp = requests.get(heygen_url, timeout=120, stream=True)
        resp.raise_for_status()
        with dest.open("wb") as fh:
            for chunk in resp.iter_content(chunk_size=1024 * 256):
                if chunk:
                    fh.write(chunk)
        if dest.stat().st_size < 1000:
            dest.unlink(missing_ok=True)
            raise StoreError("downloaded video is empty")
    except StoreError:
        raise
    except Exception as exc:
        raise StoreError(f"could not write {dest}: {exc}") from exc
    url = f"{base}/gp/{short_id}.mp4"
    logger.info("Stored report video at %s", url)
    return url


def save_html(body: str, short_id: str) -> str:
    """Write ``gp/{id}.html``. Return the public media URL."""
    root, base = require_media()
    dest_dir = root / "gp"
    dest = dest_dir / f"{short_id}.html"
    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest.write_text(body, encoding="utf-8")
        if dest.stat().st_size < 40:
            dest.unlink(missing_ok=True)
            raise StoreError("report html is empty")
    except StoreError:
        raise
    except Exception as exc:
        raise StoreError(f"could not write {dest}: {exc}") from exc
    url = f"{base}/gp/{short_id}.html"
    logger.info("Stored report html at %s", url)
    return url

"""Download a HeyGen MP4 onto the lx43 media host directory."""

from __future__ import annotations

import logging
import os
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

DUMMY_VIDEO_ID = "generic-walkthrough"


class StoreError(RuntimeError):
    """MEDIA_DIR is set but the file could not be written."""


def media_dir() -> Path | None:
    raw = (os.environ.get("MEDIA_DIR") or "").strip()
    return Path(raw) if raw else None


def public_base() -> str:
    return (os.environ.get("MEDIA_PUBLIC_BASE_URL") or "").rstrip("/")


def dummy_media_url() -> str:
    """Public URL of the shared generic walkthrough (same file for every customer)."""
    base = public_base()
    return f"{base}/gp/{DUMMY_VIDEO_ID}.mp4" if base else ""


def save_mp4(heygen_url: str, short_id: str) -> str | None:
    """Write ``gp/{id}.mp4``. Return public URL, or None if MEDIA_DIR is unset.

    Raises StoreError when MEDIA_DIR is set but the write fails.
    """
    root = media_dir()
    if root is None:
        logger.info("MEDIA_DIR unset — skip local store, caller may use HeyGen URL")
        return None
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

    base = public_base()
    if not base:
        raise StoreError("MEDIA_PUBLIC_BASE_URL is required when MEDIA_DIR is set")
    url = f"{base}/gp/{short_id}.mp4"
    logger.info("Stored report video at %s", url)
    return url

"""lx43 release id written by deployment/sync_compose_lx43.py --release-notes."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def release_notes_path() -> Path:
    override = (os.environ.get("GP_RELEASE_NOTES_PATH") or os.environ.get("FM_RELEASE_NOTES_PATH") or "").strip()
    if override:
        return Path(override)
    here = Path(__file__).resolve()
    candidates = [
        Path("/app/release_notes/latest.json"),
        here.parents[2] / "deployment" / "release_notes" / "latest.json",
    ]
    for path in candidates:
        if path.is_file():
            return path
    return candidates[0]


def load_release_id(path: Path | None = None) -> str | None:
    """Return the release string, for example ``0.6-260923``."""
    notes = path or release_notes_path()
    if not notes.is_file():
        return None
    try:
        data: Any = json.loads(notes.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    release = data.get("R")
    if release in (None, ""):
        release = data.get("release")
    if isinstance(release, str) and release.strip():
        return release.strip()
    if isinstance(release, int) and release > 0:
        return str(release)
    return None

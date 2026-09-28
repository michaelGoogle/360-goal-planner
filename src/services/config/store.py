"""Where parameter versions live on disk.

Decision: versioned JSON files in the repo, one per version, plus an append-only
audit log beside them. A version is never edited, so an old session can always be
recalculated with the numbers it was produced under.

    config/parameters/v24.json      the version generated from the V0-24 workbook
    config/parameters/v25.json      whatever an admin saves next
    config/parameters/audit.jsonl   one line per write, with the diff
    config/parameters/schema.json   customer-level overrides, written by an admin

``GP_CONFIG_DIR`` moves the whole directory, which is how tests get a tmp_path and
how a container mounts it as a volume.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from src.services.errors import ValidationFailed

VERSION_RE = re.compile(r"^v(\d+)$")
DEFAULT_DIR = Path(__file__).resolve().parents[3] / "config" / "parameters"


def config_dir() -> Path:
    return Path(os.environ.get("GP_CONFIG_DIR") or DEFAULT_DIR)


def version_path(version: str) -> Path:
    """Guards against a version name escaping the config directory."""
    if not VERSION_RE.match(version):
        raise ValidationFailed(
            fields=[{"loc": ["version"], "msg": "expected v<number>", "type": "value_error"}],
            detail=f"{version!r} is not a parameter version",
        )
    return config_dir() / f"{version}.json"


def version_number(version: str) -> int:
    match = VERSION_RE.match(version)
    return int(match.group(1)) if match else -1


def versions() -> list[str]:
    """Every version on disk, oldest first."""
    directory = config_dir()
    if not directory.is_dir():
        return []
    found = [p.stem for p in directory.glob("v*.json") if VERSION_RE.match(p.stem)]
    return sorted(found, key=version_number)


def active_version() -> str:
    """The newest version, unless ``GP_PARAMETERS_VERSION`` pins an older one."""
    pinned = (os.environ.get("GP_PARAMETERS_VERSION") or "").strip()
    if pinned:
        return pinned
    found = versions()
    if not found:
        raise ValidationFailed(
            fields=[{"loc": ["GP_CONFIG_DIR"], "msg": "no parameter versions", "type": "missing"}],
            detail=f"No v<number>.json under {config_dir()}",
        )
    return found[-1]


def next_version() -> str:
    found = versions()
    return f"v{version_number(found[-1]) + 1}" if found else "v1"


def read_version(version: str) -> dict[str, Any]:
    path = version_path(version)
    if not path.is_file():
        raise ValidationFailed(
            fields=[{"loc": ["version"], "msg": "unknown version", "type": "value_error"}],
            detail=f"No parameter version {version!r}",
        )
    return json.loads(path.read_text(encoding="utf-8"))


def write_version(version: str, payload: dict[str, Any]) -> None:
    """Refuses to overwrite, because versions are immutable."""
    path = version_path(version)
    if path.exists():
        raise ValidationFailed(
            fields=[{"loc": ["version"], "msg": "already exists", "type": "value_error"}],
            detail=f"Parameter version {version!r} already exists; versions are immutable",
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def append_audit(entry: dict[str, Any]) -> None:
    path = config_dir() / "audit.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def read_audit() -> list[dict[str, Any]]:
    path = config_dir() / "audit.jsonl"
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def schema_path() -> Path:
    return config_dir() / "schema.json"


def read_schema_override() -> dict[str, Any] | None:
    """Admin overrides for the customer schema; absent means "derive it from the level"."""
    path = schema_path()
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def write_schema_override(payload: dict[str, Any]) -> None:
    path = schema_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

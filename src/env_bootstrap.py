"""Load GP/.env then the workspace-root .env into os.environ.

Workspace values win. Empty process env is treated as unset so a blank
Docker interpolation does not block the file.
"""

from __future__ import annotations

import os
from pathlib import Path


def _parse_env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        if s.startswith("export "):
            s = s[7:].strip()
        key, value = s.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        if key:
            out[key] = value
    return out


def load_env_files(
    *,
    gp_root: Path | None = None,
    workspace_root: Path | None = None,
) -> list[Path]:
    gp_root = gp_root or Path(__file__).resolve().parents[1]
    workspace_root = workspace_root or gp_root.parent
    loaded: list[Path] = []
    gp_env = gp_root / ".env"
    ws_env = workspace_root / ".env"

    if gp_env.is_file():
        loaded.append(gp_env)
        for key, value in _parse_env_file(gp_env).items():
            if not (os.environ.get(key) or "").strip():
                os.environ[key] = value

    if ws_env.is_file():
        loaded.append(ws_env)
        for key, value in _parse_env_file(ws_env).items():
            if value.strip() or not (os.environ.get(key) or "").strip():
                os.environ[key] = value

    return loaded


load_env_files()

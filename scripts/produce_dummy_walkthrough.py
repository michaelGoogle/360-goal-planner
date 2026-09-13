"""Generate the shared plan-report dummy video and copy it onto lx43 media.

  cd GP
  python scripts/produce_dummy_walkthrough.py

Downloads via HeyGen, writes MEDIA_DIR when set, and scp's to
lx43:.../media/gp/generic-walkthrough.mp4 so nginx :8042 / WAN :8442 can serve it.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

import requests

GP_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = GP_ROOT.parent
if str(GP_ROOT) not in sys.path:
    sys.path.insert(0, str(GP_ROOT))

from src.env_bootstrap import load_env_files  # noqa: E402
from src.heygen.agent import GenerateError, heygen_configured, start_video_generation, wait_for_url  # noqa: E402
from src.heygen.media_store import DUMMY_VIDEO_ID, dummy_media_url, media_dir, save_mp4  # noqa: E402
from src.heygen.prompt import build_dummy_video_prompt  # noqa: E402

load_env_files()

LX43_SSH_HOST = "lx43"
LX43_MEDIA_GP = "/home/michael.gerber/Drive/behavioralFinance/media/gp"
SSH_OPTS = [
    "-o",
    "BatchMode=yes",
    "-o",
    "ConnectTimeout=20",
    "-o",
    "ServerAliveInterval=30",
    "-o",
    "ServerAliveCountMax=3",
    "-o",
    "IPQoS=none",
]


def _scp_to_lx43(local: Path) -> None:
    remote_dir = LX43_MEDIA_GP
    remote = f"{remote_dir}/{DUMMY_VIDEO_ID}.mp4"
    mkdir = subprocess.run(
        ["ssh"] + SSH_OPTS + [LX43_SSH_HOST, f"mkdir -p {remote_dir}"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if mkdir.returncode != 0:
        raise RuntimeError(mkdir.stderr.strip() or "ssh mkdir failed")
    scp = subprocess.run(
        ["scp"] + SSH_OPTS + [str(local), f"{LX43_SSH_HOST}:{remote}"],
        capture_output=True,
        text=True,
        timeout=300,
    )
    if scp.returncode != 0:
        raise RuntimeError(scp.stderr.strip() or "scp failed")
    print(f"Copied to {LX43_SSH_HOST}:{remote}")


def main() -> int:
    prompt = build_dummy_video_prompt()
    print("Video Agent prompt:", flush=True)
    print(prompt, flush=True)
    print(flush=True)
    if not heygen_configured():
        print("HEYGEN_API_KEY is not set", file=sys.stderr)
        return 1
    try:
        session_id = start_video_generation(prompt)
    except GenerateError as exc:
        print(exc.detail, file=sys.stderr)
        return 1
    if not session_id:
        print("HeyGen did not start", file=sys.stderr)
        return 1
    print(f"HeyGen Video Agent started session_id={session_id}; waiting…")
    status, heygen_url = wait_for_url(session_id)
    if status != "completed" or not heygen_url:
        print(f"HeyGen ended {status or 'failed'}", file=sys.stderr)
        return 1
    print(f"HeyGen ready: {heygen_url}")

    stored = None
    if media_dir() is not None:
        stored = save_mp4(heygen_url, DUMMY_VIDEO_ID)
        print(f"MEDIA_DIR: {stored}")

    tmp = Path(tempfile.gettempdir()) / f"{DUMMY_VIDEO_ID}.mp4"
    resp = requests.get(heygen_url, timeout=120, stream=True)
    resp.raise_for_status()
    with tmp.open("wb") as fh:
        for chunk in resp.iter_content(chunk_size=1024 * 256):
            if chunk:
                fh.write(chunk)
    print(f"Local download: {tmp} ({tmp.stat().st_size} bytes)")
    try:
        _scp_to_lx43(tmp)
    except Exception as exc:
        print(f"Could not copy to lx43: {exc}", file=sys.stderr)
        print(f"File is at {tmp} — copy it to media/gp/{DUMMY_VIDEO_ID}.mp4", file=sys.stderr)
        return 1
    print(f"Public URL: {dummy_media_url() or '(set MEDIA_PUBLIC_BASE_URL)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

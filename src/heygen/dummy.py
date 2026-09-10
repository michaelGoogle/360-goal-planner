"""One shared generic walkthrough clip (HeyGen → media/gp/generic-walkthrough.mp4)."""

from __future__ import annotations

import logging

from src.heygen.agent import GenerateError, heygen_configured, start_video_generation, wait_for_url
from src.heygen.media_store import DUMMY_VIDEO_ID, dummy_media_url, save_mp4
from src.heygen.prompt import build_dummy_spoken_script

logger = logging.getLogger(__name__)


class DummyProduceError(RuntimeError):
    pass


def produce_dummy_walkthrough() -> str:
    """Generate the dummy clip, store it under gp/generic-walkthrough.mp4, return the public URL."""
    if not heygen_configured():
        raise DummyProduceError("HEYGEN_API_KEY is not set")
    script = build_dummy_spoken_script()
    try:
        video_id = start_video_generation(script)
    except GenerateError as exc:
        raise DummyProduceError(exc.detail) from exc
    if not video_id:
        raise DummyProduceError("HeyGen did not start")
    logger.info("Dummy walkthrough HeyGen id=%s", video_id)
    status, heygen_url = wait_for_url(video_id)
    if status != "completed" or not heygen_url:
        raise DummyProduceError(f"HeyGen ended {status or 'failed'}")
    media_url = save_mp4(heygen_url, DUMMY_VIDEO_ID)
    return media_url or dummy_media_url() or heygen_url

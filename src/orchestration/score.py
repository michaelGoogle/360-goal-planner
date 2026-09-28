"""POST /v1/score — map the session into a HappiU body and let HU score it.

GP owns the mapping only. HU returns both preHappiU and postHappiU on every call.
"""

from __future__ import annotations

from typing import Any

from src.hu_payload import build_happiu_payload
from src.insapi_sync import schedule_insapi_sync
from src.predict import session_dict
from src.services.errors import DependencyFailed, GpError
from src.services.registry import get_hu_client


def run_score(body: dict[str, Any]) -> dict[str, Any]:
    session = session_dict(body)
    payload = build_happiu_payload(session)
    try:
        data = get_hu_client().score(payload)
    except DependencyFailed as exc:
        raise GpError(exc.extra.get("upstreamStatus") or exc.status, exc.detail) from exc

    result = data.get("result") if isinstance(data, dict) else data
    pre = (result or {}).get("preHappiU") if isinstance(result, dict) else None
    post = (result or {}).get("postHappiU") if isinstance(result, dict) else None
    schedule_insapi_sync(session, pre=pre, post=post)
    return {
        "success": True,
        "preHappiU": pre,
        "postHappiU": post,
        "result": result,
        "breakdown": data.get("breakdown") if isinstance(data, dict) else None,
    }

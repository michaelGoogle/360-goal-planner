"""POST /v1/needs — recompute amount, have and gap from the current session inputs.

The UI sends slider and money edits; it never recomputes an amount itself. This and
predict call the same engine, so a pencil edit cannot switch formula set.
"""

from __future__ import annotations

import logging
from typing import Any

from src.pipeline.need_calculator import evaluate_session
from src.predict import session_dict
from src.services.errors import GpError

logger = logging.getLogger(__name__)


def run_needs(body: dict[str, Any]) -> dict[str, Any]:
    session = session_dict(body)
    try:
        session = evaluate_session(session)
    except Exception as exc:
        logger.warning("Need Calculator unavailable: %s", exc)
        raise GpError(503, "Need Calculator unavailable") from exc
    return {
        "success": True,
        "session": {
            "needs": session.get("needs") or [],
            "ageOfRetirement": session.get("ageOfRetirement"),
        },
    }

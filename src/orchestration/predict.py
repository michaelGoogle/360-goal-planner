"""POST /v1/predict — People Like You, then Need Profiler, then Need Calculator.

Sequence (§2.2 of the implementation plan):

    fx.lock -> social-security -> people-like-you -> need-profiler -> need-calculator

Social security is called from inside People Like You, which is where take-home is
needed. The remaining steps move onto their clients in WP7 and WP8.
"""

from __future__ import annotations

import logging
from typing import Any

from src.hu_payload import need_existing
from src.insapi_sync import schedule_insapi_sync
from src.needs import need_code
from src.pipeline.need_calculator import evaluate_session
from src.pipeline.run import run_people_like_you
from src.predict import _apply_plu, session_dict
from src.services.config import service as config_service
from src.services.errors import GpError
from src.services.need_profiler import service as profiler_service
from src.services.need_profiler.models import NeedProfilerRequest, NeedProfilerResponse
from src.services.registry import get_fx_client, get_need_profiler_client

logger = logging.getLogger(__name__)

PLU_UNAVAILABLE = (
    "360-PeopleLikeU(r) is not available, so we cannot predict your financial future."
)


def profiler_request(session: dict[str, Any]) -> NeedProfilerRequest:
    """Local amounts become USD here. The profiler divides by the price level itself."""
    prefs = (session.get("plu") or {}).get("clientPreferences") or {}
    fx = session.get("fx") or {}
    rate = float(fx.get("usdPerLocal") or 1.0)
    assets = float(session.get("cash") or 0) + float(session.get("investments") or 0)
    return NeedProfilerRequest(
        age=int(session.get("age") or 40),
        dependents=int(session.get("dependents") or 0),
        gender=str(session.get("gender") or ""),
        ownsProperty=float(session.get("property") or 0) > 0,
        incomeMonthlyUsd=float(session.get("incomeMonthly") or 0) * rate,
        expenseMonthlyUsd=float(session.get("expenseMonthly") or 0) * rate,
        liquidAssetsUsd=assets * rate,
        liabilitiesUsd=float(session.get("pluLiabilities") or 0) * rate,
        priceLevel=float(fx.get("priceLevel") or 1.0),
        flags={
            "occupation": session.get("occupation"),
            "isSmoker": bool(session.get("isSmoker") or prefs.get("isSmoker")),
            "hospitalType": prefs.get("hospitalType"),
            "wardType": prefs.get("wardType"),
            "retirementLifestyle": prefs.get("retirementLifestyle"),
            "sports": prefs.get("sports"),
        },
        parametersVersion=str(session.get("parametersVersion") or ""),
    )


def apply_profile(session: dict[str, Any], profile: NeedProfilerResponse) -> dict[str, Any]:
    """Put the profiler's answer on the session, keeping any amount already there."""
    previous = {need_code(n.get("type")): n for n in session.get("needs") or []}
    rows = []
    for need in profile.needs:
        if need.parked:
            continue
        prior = previous.get(need.type) or {}
        rows.append(
            {
                **prior,
                "type": need.type,
                "enabled": need.enabled,
                "needAmount": float(prior.get("needAmount") or 0),
                "priority": need.priority,
                "weightageScore": need.score,
            }
        )
    session["needs"] = rows
    session["parkedNeeds"] = [
        {"type": n.type, "priority": n.priority, "score": n.score}
        for n in profile.needs
        if n.parked
    ]
    session["needProfiler"] = {
        "scores": profile.scores,
        "picks": profile.picks,
        "fallback": profile.fallback,
    }
    return session


def ensure_fx_lock(session: dict[str, Any]) -> dict[str, Any]:
    """Lock the rate and price level once, and keep it for the life of the session.

    A lock the client already holds is honoured, so recalculating an old session
    reproduces its numbers rather than repricing it at today's rate.
    """
    if session.get("fx"):
        return session
    currency = session.get("currency") or "SGD"
    country = session.get("country") or "Singapore"
    base = str(config_service.value("PPP_BASE_COUNTRY", str(session.get("parametersVersion") or "")))
    session["fx"] = get_fx_client().lock(currency, country, base).model_dump()
    return session


def run_predict(body: dict[str, Any]) -> dict[str, Any]:
    """Fill a session from scratch. Fails if People Like You cannot run."""
    session = session_dict(body)
    notes: list[str] = []
    session = ensure_fx_lock(session)

    try:
        plu = run_people_like_you(session)
    except Exception as exc:
        logger.warning("People Like You unavailable: %s", exc)
        raise GpError(503, PLU_UNAVAILABLE) from exc
    session = _apply_plu(session, plu)

    try:
        profile = get_need_profiler_client().profile(profiler_request(session))
    except Exception as exc:
        logger.warning("Need Profiler unavailable: %s", exc)
        notes.append("Need Profiler unavailable; enabled default goals.")
        profile = profiler_service.fallback(
            age=int(session.get("age") or 40),
            dependents=int(session.get("dependents") or 0),
            owns_property=float(session.get("property") or 0) > 0,
        )
    session = apply_profile(session, profile)

    for need in session.get("needs") or []:
        need["existing"] = need_existing(need, session)

    try:
        session = evaluate_session(session)
    except Exception as exc:
        logger.warning("Need Calculator unavailable: %s", exc)
        notes.append("Need Calculator unavailable; amounts stay at zero until HU/SV.")

    schedule_insapi_sync(session)
    return {"success": True, "session": session, "notes": notes}

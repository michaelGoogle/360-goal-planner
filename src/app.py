"""Goal Planner FastAPI app — in-process People Like You / needs; HU / SV upstreams."""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from src.explain import KINDS, ROUTES, generate_explanation
from src.heygen.jobs import get_job
from src.heygen.media_store import dummy_media_url
from src.heygen.pipeline import NotifyError, resume_pending, submit_notify
from src.hu_payload import build_happiu_payload, need_existing
from src.insapi_client import InsApiError
from src.insapi_sync import schedule_insapi_sync, sync_contact_and_plan
from src.openai_client import llm_configured
from src.parse_sentence import extract_about_you
from src.pipeline.need_calculator import evaluate_session
from src.pipeline.run import run_need_profiler, run_people_like_you
from src.predict import (
    UNIFIED_TYPES,
    _apply_plu,
    _needs_from_profiler,
    session_dict,
)
from src.sv_payload import build_sv_payload
from src.upstream import UpstreamError, hu_happiu, sv_project

logger = logging.getLogger(__name__)
PLU_UNAVAILABLE = (
    "360-PeopleLikeU(r) is not available, so we cannot predict your financial future."
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    try:
        n = resume_pending()
        if n:
            logger.info("Resumed %s pending report video job(s)", n)
    except Exception:
        logger.exception("Could not resume pending report videos")
    try:
        from src.heygen.ops_alert import maybe_alert_low_balance

        maybe_alert_low_balance()
    except Exception:
        logger.exception("HeyGen balance alert on startup failed")
    yield


api = FastAPI(
    title="360-Goal Planner",
    description="D2C Goal Planner BFF — People Like You / Need Profiler / Need Calculator (in-process) / HappiU / Scenario Visualizer",
    version="0.1.0",
    lifespan=lifespan,
)

api.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ParseSentenceBody(BaseModel):
    text: str = ""


class ExplainBody(BaseModel):
    kind: str
    route: str = ""
    context: dict[str, Any] = Field(default_factory=dict)


class GpSession(BaseModel):
    name: str = ""
    age: int = 40
    gender: str = "Male"
    residency: str = "Singapore Citizen"
    nationality: str = "Singapore"
    occupation: str = ""
    dependents: int = 0
    dateOfBirth: str | None = None
    isSmoker: bool = False
    riskProfile: int = 4
    ageOfRetirement: int = 65
    incomeMonthly: float = 0
    expenseMonthly: float = 0
    cash: float = 0
    investments: float = 0
    property: float = 0
    mortgage: float = 0
    policies: list[dict[str, Any]] = Field(default_factory=list)
    needs: list[dict[str, Any]] = Field(default_factory=list)
    events: list[dict[str, Any]] = Field(default_factory=list)
    inflationRate: float = 0.023
    interestRate: float = 0.012
    incomeGrowthRate: float = 0.028
    investmentReturn: float = 0.042
    assetReturn: float = 0.03
    plansOff: list[str] = Field(default_factory=list)
    planMth: dict[str, float] = Field(default_factory=dict)
    planLump: dict[str, float] = Field(default_factory=dict)
    planSum: dict[str, float] = Field(default_factory=dict)
    planPrem: dict[str, float] = Field(default_factory=dict)
    extraNeeds: list[str] = Field(default_factory=list)
    cpfOa: float = 0
    cpfSa: float = 0
    cpfMa: float = 0
    reportEmail: str = ""
    reportMobile: str = ""
    insapiContactId: str = ""
    insapiPlanId: str = ""
    numSims: int = 200
    svNumSims: int = 20
    persist: bool = False


class VideoNotifyBody(BaseModel):
    email: str = ""
    mobile: str = ""
    pre: float | None = None
    post: float | None = None
    session: dict[str, Any] = Field(default_factory=dict)


@api.get("/health")
@api.get("/healthz")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "gp"}


@api.post("/v1/parse-sentence")
def parse_sentence(body: ParseSentenceBody) -> dict[str, Any]:
    """Extract About You fields from free-form text. Uses Claude when configured."""
    text = (body.text or "").strip()
    if len(text) < 4:
        return {"success": True, "source": "none", "fields": {}}
    if not llm_configured():
        return {"success": False, "source": "unavailable", "fields": {}}
    try:
        fields = extract_about_you(text)
    except Exception as exc:
        kind = type(exc).__name__
        logger.warning("parse-sentence LLM failed: %s", kind)
        detail = "Could not read that sentence"
        if kind in {"AuthenticationError", "PermissionDeniedError"}:
            detail = "AI is not available — the Anthropic API key was rejected"
        raise HTTPException(status_code=503, detail=detail) from exc
    return {"success": True, "source": "llm", "fields": fields}


@api.post("/v1/explain")
def explain(body: ExplainBody) -> dict[str, Any]:
    """Spoken explainer script. Uses Claude when configured; otherwise a local script."""
    kind = (body.kind or "").strip()
    route = (body.route or "").strip() or None
    if kind not in KINDS:
        raise HTTPException(status_code=400, detail=f"Unknown explainer '{body.kind}'")
    if kind == "mira" and route not in ROUTES:
        raise HTTPException(status_code=400, detail="Mira needs a known route")
    text, source = generate_explanation(kind, route, body.context)
    return {"success": True, "kind": kind, "source": source, "text": text}


@api.post("/v1/predict")
def predict(body: GpSession) -> dict[str, Any]:
    """People Like You → Need Profiler → Need Calculator. Errors if People Like You cannot run."""
    session = session_dict(body.model_dump())
    notes: list[str] = []

    try:
        plu = run_people_like_you(session)
    except Exception as exc:
        logger.warning("People Like You unavailable: %s", exc)
        raise HTTPException(status_code=503, detail=PLU_UNAVAILABLE) from exc
    session = _apply_plu(session, plu)

    plu_data = (plu.get("onboarding") or {}).get("data") or {}
    prefs = ((session.get("plu") or {}).get("clientPreferences") or {})
    policy_owner = {
        "dateOfBirth": session["dateOfBirth"],
        "gender": session.get("gender"),
        "occupation": session.get("occupation"),
        "dependents": session.get("dependents"),
        "country": "Singapore",
        "city": "Singapore",
        "isSmoker": bool(session.get("isSmoker") or prefs.get("isSmoker")),
        "ageOfRetirement": session.get("ageOfRetirement"),
    }
    finance = {
        "monthlyIncome": session["incomeMonthly"],
        "monthlyExpense": session["expenseMonthly"],
        "liquidAssetValue": float(session.get("cash") or 0) + float(session.get("investments") or 0),
        "property": float(session.get("property") or 0),
    }
    try:
        npr = run_need_profiler(
            policy_owner,
            finance,
            people_like_you=plu_data.get("peopleLikeYou"),
            top_n=4,
        )
        session = _needs_from_profiler(session, npr)
    except Exception as exc:
        logger.warning("Need Profiler unavailable: %s", exc)
        notes.append("Need Profiler unavailable; enabled default goals.")
        deps = int(session.get("dependents") or 0)
        has_property = float(session.get("property") or 0) > 0
        default_on = {"N_INC", "N_CRI", "N_RET", "N_PRP" if has_property else "N_SAV"}
        if deps:
            default_on = {"N_INC", "N_CRI", "N_RET", "N_EDU"}
        session["needs"] = [
            {"type": t, "enabled": t in default_on, "needAmount": 0, "priority": 3}
            for t in UNIFIED_TYPES
        ]

    for n in session.get("needs") or []:
        n["existing"] = need_existing(n, session)

    try:
        session = evaluate_session(session)
    except Exception as exc:
        logger.warning("Need Calculator unavailable: %s", exc)
        notes.append("Need Calculator unavailable; amounts stay at zero until HU/SV.")

    schedule_insapi_sync(session)
    return {"success": True, "session": session, "notes": notes}


@api.post("/v1/needs")
def needs(body: GpSession) -> dict[str, Any]:
    """Recompute needAmount, projected have, and gap from the current session inputs."""
    session = session_dict(body.model_dump())
    try:
        session = evaluate_session(session)
    except Exception as exc:
        logger.warning("Need Calculator unavailable: %s", exc)
        raise HTTPException(status_code=503, detail="Need Calculator unavailable") from exc
    return {
        "success": True,
        "session": {
            "needs": session.get("needs") or [],
            "ageOfRetirement": session.get("ageOfRetirement"),
        },
    }


@api.post("/v1/score")
def score(body: GpSession) -> dict[str, Any]:
    payload = build_happiu_payload(session_dict(body.model_dump()))
    try:
        status, data = hu_happiu(payload)
    except UpstreamError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.detail) from exc
    if status >= 400:
        raise HTTPException(status_code=status, detail=data)
    result = data.get("result") if isinstance(data, dict) else data
    pre = (result or {}).get("preHappiU") if isinstance(result, dict) else None
    post = (result or {}).get("postHappiU") if isinstance(result, dict) else None
    schedule_insapi_sync(session_dict(body.model_dump()), pre=pre, post=post)
    return {
        "success": True,
        "preHappiU": pre,
        "postHappiU": post,
        "result": result,
        "breakdown": data.get("breakdown") if isinstance(data, dict) else None,
    }


@api.post("/v1/project")
def project(body: GpSession) -> dict[str, Any]:
    payload = build_sv_payload(session_dict(body.model_dump()))
    try:
        status, data = sv_project(payload)
    except UpstreamError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.detail) from exc
    if status >= 400:
        raise HTTPException(status_code=status, detail=data)
    inner = data.get("data") if isinstance(data, dict) else data
    schedule_insapi_sync(session_dict(body.model_dump()))
    return {"success": True, "data": inner, "raw": data, "payload": payload}


@api.post("/v1/sv-payload")
def sv_payload(body: GpSession) -> dict[str, Any]:
    """Map the session to an SV body without running the projection (debug)."""
    payload = build_sv_payload(session_dict(body.model_dump()))
    return {"success": True, "payload": payload}


@api.get("/v1/report-walkthrough")
def report_walkthrough() -> dict[str, Any]:
    """Public URL of the shared dummy report video (same clip for every customer)."""
    return {"success": True, "dummyUrl": dummy_media_url()}


@api.post("/v1/crm-sync")
def crm_sync(body: VideoNotifyBody) -> dict[str, Any]:
    """Upsert the customer and financial plan on Prototype InsApi (mira.whatsapp)."""
    try:
        ids = sync_contact_and_plan(body.email, body.mobile, body.session or {}, body.pre, body.post)
    except InsApiError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.detail) from exc
    return {"success": True, "contactId": ids.get("contactId") or "", "planId": ids.get("planId") or ""}


@api.post("/v1/video-notify", status_code=202)
def video_notify(body: VideoNotifyBody) -> dict[str, Any]:
    """Queue a HeyGen report video (mobile required) and notify when it is ready."""
    try:
        job_id = submit_notify(body.email, body.mobile, body.session or {}, body.pre, body.post)
    except NotifyError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.detail) from exc
    return {"success": True, "jobId": job_id}


@api.get("/v1/video-notify/{job_id}")
def video_status(job_id: str) -> dict[str, Any]:
    """Poll a report video job. Returns status and the public lx media URL when ready."""
    job = get_job(job_id.strip())
    if not job:
        raise HTTPException(status_code=404, detail="Unknown video job")
    return {
        "success": True,
        "jobId": job["id"],
        "status": job.get("status") or "",
        "mediaUrl": job.get("media_url") or "",
        "error": job.get("error") or "",
    }


_repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_frontend_dist = os.environ.get("GP_FRONTEND_DIST") or os.path.join(_repo_root, "frontend", "dist")
if os.path.isdir(_frontend_dist):
    api.mount("/", StaticFiles(directory=_frontend_dist, html=True), name="frontend")

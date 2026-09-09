"""Goal Planner FastAPI app — BFF over FM / HU / SV."""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from src.explain import KINDS, ROUTES, generate_explanation
from src.heygen.jobs import get_job
from src.heygen.pipeline import NotifyError, resume_pending, submit_notify
from src.hu_payload import build_happiu_payload, need_existing
from src.openai_client import llm_configured
from src.parse_sentence import extract_about_you
from src.predict import (
    UNIFIED_TYPES,
    _apply_calculator,
    _apply_plu,
    _needs_from_profiler,
    plu_body,
    session_dict,
)
from src.sv_payload import build_sv_payload
from src.upstream import UpstreamError, fm_public, hu_happiu, sv_project

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
    description="D2C Goal Planner BFF — People Like You / Need Profiler / Need Calculator / HappiU / Scenario Visualizer",
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


def _people_like_you_failed(status: int, plu: Any) -> bool:
    if status != 200 or not isinstance(plu, dict):
        return True
    return plu.get("success") is False


@api.post("/v1/predict")
def predict(body: GpSession, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    """People Like You → Need Profiler → Need Calculator. Errors if People Like You is down."""
    session = session_dict(body.model_dump())
    persist = bool(body.persist and authorization)
    notes: list[str] = []

    status, plu = _safe_fm("people-like-you", plu_body(session, persist), authorization)
    if _people_like_you_failed(status, plu):
        detail = ""
        if isinstance(plu, dict):
            detail = str(plu.get("detail") or plu.get("error") or "")[:400]
        logger.warning("People Like You unavailable status=%s detail=%s", status, detail)
        raise HTTPException(status_code=503, detail=PLU_UNAVAILABLE)
    session = _apply_plu(session, plu)

    np_body: dict[str, Any] = {
        "topN": 5,
        "persist": persist,
        "policyOwner": {
            "dateOfBirth": session["dateOfBirth"],
            "gender": session.get("gender"),
            "occupation": session.get("occupation"),
            "dependents": session.get("dependents"),
            "country": "Singapore",
            "city": "Singapore",
            "isSmoker": session.get("isSmoker"),
            "ageOfRetirement": session.get("ageOfRetirement"),
        },
        "finance": {
            "monthlyIncome": session["incomeMonthly"],
            "monthlyExpense": session["expenseMonthly"],
            "liquidAssetValue": float(session.get("cash") or 0) + float(session.get("investments") or 0),
        },
    }
    status, npr = _safe_fm("need-profiler", np_body, authorization)
    if status == 200 and isinstance(npr, dict):
        session = _needs_from_profiler(session, npr)
    else:
        notes.append(f"Need Profiler unavailable ({status}); enabled default goals.")
        deps = int(session.get("dependents") or 0)
        default_on = {"N_INC", "N_RET"}
        if deps:
            default_on.add("N_EDU")
        session["needs"] = [
            {"type": t, "enabled": t in default_on, "needAmount": 0, "priority": 3}
            for t in UNIFIED_TYPES
        ]

    for n in session.get("needs") or []:
        n["existing"] = need_existing(n, session)

    nc_body = {
        "onlyEmpty": True,
        "persist": persist,
        "policyOwner": np_body["policyOwner"],
        "finance": np_body["finance"],
        "needs": {n["type"]: n for n in session.get("needs") or []},
    }
    status, ncalc = _safe_fm("need-calculator", nc_body, authorization)
    if status == 200 and isinstance(ncalc, dict):
        session = _apply_calculator(session, ncalc)
    else:
        notes.append(f"Need Calculator unavailable ({status}); amounts stay at zero until HU/SV.")

    return {"success": True, "session": session, "notes": notes}


def _safe_fm(path: str, body: dict[str, Any], authorization: str | None) -> tuple[int, Any]:
    try:
        return fm_public(path, body, authorization)
    except UpstreamError as exc:
        return exc.status, {"detail": exc.detail}


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
    return {
        "success": True,
        "preHappiU": (result or {}).get("preHappiU") if isinstance(result, dict) else None,
        "postHappiU": (result or {}).get("postHappiU") if isinstance(result, dict) else None,
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
    return {"success": True, "data": inner, "raw": data}


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

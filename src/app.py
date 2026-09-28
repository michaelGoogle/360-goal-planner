"""Goal Planner FastAPI app — in-process People Like You / needs; HU / SV upstreams."""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from src.explain import KINDS, ROUTES, generate_explanation
from src.heygen.jobs import get_job
from src.heygen.media_store import dummy_media_url
from src.heygen.pipeline import NotifyError, resume_pending, submit_notify
from src.insapi_client import InsApiError
from src.insapi_sync import sync_contact_and_plan
from src.openai_client import llm_configured
from src.orchestration.needs import run_needs
from src.orchestration.predict import run_predict
from src.orchestration.project import build_payload_only, run_project
from src.orchestration.score import run_score
from src.parse_sentence import extract_about_you
from src.release_info import load_release_id
from src.services import all_routers
from src.services.errors import GpError, ServiceError

logger = logging.getLogger(__name__)


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

for _service_router in all_routers():
    api.include_router(_service_router)


@api.exception_handler(ServiceError)
def _service_error(_request: Request, exc: ServiceError) -> JSONResponse:
    """The service envelope: {"error": <code>, ...}."""
    return JSONResponse(status_code=exc.status, content=jsonable_encoder(exc.payload()))


@api.exception_handler(RequestValidationError)
def _validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
    """FastAPI's own 422, plus the error code and field list the services promise.

    ``detail`` keeps its shape, because the frontend already reads it.
    """
    errors = jsonable_encoder(exc.errors())
    return JSONResponse(
        status_code=422,
        content={"error": "validation_failed", "detail": errors, "fields": errors},
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
    # Where they live and what they hold. The country picks the social-security module
    # and the price level; the currency picks the rate everything is converted at.
    country: str = "Singapore"
    currency: str = "SGD"
    # The rate and price level this session was calculated at, so a rate published
    # mid-session cannot change a number the customer has already been shown. Locked on
    # the first predict and sent back with every later call.
    fx: dict[str, Any] | None = None
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
    # Absent means "use the parameter version", which is how a published rate change
    # reaches a session that never touched the assumption box. See session_rates.py.
    inflationRate: float | None = None
    interestRate: float | None = None
    incomeGrowthRate: float | None = None
    investmentReturn: float | None = None
    loanRate: float | None = None
    assetReturn: float | None = None
    lifeExpectancy: int | None = None
    parametersVersion: str = ""
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


@api.get("/v1/release")
def release() -> dict[str, str | None]:
    """lx43 release id (N-YYYY-MM-DD) from deployment/release_notes/latest.json."""
    ident = load_release_id()
    return {"R": ident, "release": ident}


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


def _run(orchestrator, body: GpSession) -> dict[str, Any]:
    """Call an orchestrator and translate its GpError back into the old envelope."""
    try:
        return orchestrator(body.model_dump())
    except GpError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.detail) from exc


@api.post("/v1/predict")
def predict(body: GpSession) -> dict[str, Any]:
    """People Like You → Need Profiler → Need Calculator. Errors if People Like You cannot run."""
    return _run(run_predict, body)


@api.post("/v1/needs")
def needs(body: GpSession) -> dict[str, Any]:
    """Recompute needAmount, projected have, and gap from the current session inputs."""
    return _run(run_needs, body)


@api.post("/v1/score")
def score(body: GpSession) -> dict[str, Any]:
    return _run(run_score, body)


@api.post("/v1/project")
def project(body: GpSession) -> dict[str, Any]:
    return _run(run_project, body)


@api.post("/v1/sv-payload")
def sv_payload(body: GpSession) -> dict[str, Any]:
    """Map the session to an SV body without running the projection (debug)."""
    return _run(build_payload_only, body)


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

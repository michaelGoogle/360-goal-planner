"""Config routes. Reads are open; writing a version needs platform admin rights."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from src.services.config import service
from src.services.config.admin import require_admin
from src.services.config.models import (
    AssumptionSchema,
    AuditEntry,
    ParameterSet,
    ParameterWrite,
    SessionDefaults,
)

router = APIRouter(prefix="/v1/config", tags=["config"])


@router.get("/parameters")
def get_parameters() -> ParameterSet:
    return service.active_parameters()


@router.get("/versions")
def get_versions() -> list[str]:
    return service.versions()


@router.get("/audit")
def get_audit() -> list[AuditEntry]:
    return service.audit_log()


@router.get("/parameters/{version}")
def get_parameters_version(version: str) -> ParameterSet:
    return service.parameters_for_version(version)


@router.put("/parameters")
def put_parameters(body: ParameterWrite, author: str = Depends(require_admin)) -> ParameterSet:
    return service.write_parameters(body, author=author)


@router.get("/session-assumptions/schema")
def get_assumption_schema() -> AssumptionSchema:
    return service.assumption_schema()


@router.put("/session-assumptions/schema")
def put_assumption_schema(
    body: AssumptionSchema, author: str = Depends(require_admin)
) -> AssumptionSchema:
    return service.write_assumption_schema(body, author=author)


@router.get("/session-defaults")
def get_session_defaults(age: int = Query(...), country: str = "Singapore") -> SessionDefaults:
    return service.session_defaults(age, country)

"""Error model shared by the GP services and the orchestrators.

Two families, because the response envelopes differ.

``ServiceError`` is raised inside a service and rendered by the handlers in
``src.app`` as ``{"error": <code>, ...}``. That is the envelope the new
``/v1/<service>`` routes answer with: 422 on bad input, 424 when a dependency
fails, 404 ``unknown_currency``, and 501 while a service is still a stub.

``GpError`` carries a status and a detail straight through to the endpoints that
existed before the services (``/v1/predict``, ``/v1/needs``, ``/v1/score``,
``/v1/project``), whose bodies have to stay ``{"detail": ...}`` because the
frontend reads that key.
"""

from __future__ import annotations

from typing import Any


class GpError(Exception):
    """An orchestrator failure, rendered as ``{"detail": ...}`` at the old status."""

    def __init__(self, status: int, detail: Any):
        super().__init__(str(detail))
        self.status = status
        self.detail = detail


class ServiceError(Exception):
    """Base for the service routes. ``payload()`` is the response body."""

    status = 500
    code = "service_error"

    def __init__(self, detail: Any = None, **extra: Any):
        super().__init__(str(detail) if detail is not None else self.code)
        self.detail = detail
        self.extra = extra

    def payload(self) -> dict[str, Any]:
        body: dict[str, Any] = {"error": self.code}
        if self.detail is not None:
            body["detail"] = self.detail
        body.update(self.extra)
        return body


class NotImplementedYet(ServiceError):
    """The route exists and its contract is fixed, but the work package is open."""

    status = 501
    code = "not_implemented"

    def __init__(self, what: str, work_package: str = ""):
        super().__init__(f"{what} is not implemented yet", workPackage=work_package or None)
        self.extra = {k: v for k, v in self.extra.items() if v is not None}


class ValidationFailed(ServiceError):
    """Input a pydantic model cannot express (cross-field rules, unknown codes)."""

    status = 422
    code = "validation_failed"

    def __init__(self, fields: list[dict[str, Any]] | None = None, detail: Any = None):
        super().__init__(detail, fields=fields or [])


class DependencyFailed(ServiceError):
    """An upstream this service needs did not answer usefully."""

    status = 424
    code = "dependency_failed"

    def __init__(self, dependency: str, detail: Any = None, upstream_status: int | None = None):
        super().__init__(detail, dependency=dependency)
        if upstream_status is not None:
            self.extra["upstreamStatus"] = upstream_status


class UnknownCurrency(ServiceError):
    """No rate for this ISO code. There is deliberately no fallback currency."""

    status = 404
    code = "unknown_currency"

    def __init__(self, currency: str):
        super().__init__(f"No FX rate for {currency!r}", currency=currency)

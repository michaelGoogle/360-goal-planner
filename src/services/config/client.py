"""Config clients. Callers depend on the protocol, never on the implementation."""

from __future__ import annotations

from typing import Protocol

from src.services.config import service
from src.services.config.models import AssumptionSchema, ParameterSet, SessionDefaults
from src.services.http import request_json

DEPENDENCY = "config"


class ConfigClient(Protocol):
    def active_parameters(self) -> ParameterSet: ...
    def parameters_for_version(self, version: str) -> ParameterSet: ...
    def assumption_schema(self) -> AssumptionSchema: ...
    def session_defaults(self, age: int, country: str = "Singapore") -> SessionDefaults: ...


class InProcessConfigClient:
    def active_parameters(self) -> ParameterSet:
        return service.active_parameters()

    def parameters_for_version(self, version: str) -> ParameterSet:
        return service.parameters_for_version(version)

    def assumption_schema(self) -> AssumptionSchema:
        return service.assumption_schema()

    def session_defaults(self, age: int, country: str = "Singapore") -> SessionDefaults:
        return service.session_defaults(age, country)


class HttpConfigClient:
    def __init__(self, base_url: str):
        self.base_url = base_url

    def active_parameters(self) -> ParameterSet:
        return ParameterSet.model_validate(
            request_json("GET", self.base_url, "/v1/config/parameters", DEPENDENCY)
        )

    def parameters_for_version(self, version: str) -> ParameterSet:
        return ParameterSet.model_validate(
            request_json("GET", self.base_url, f"/v1/config/parameters/{version}", DEPENDENCY)
        )

    def assumption_schema(self) -> AssumptionSchema:
        return AssumptionSchema.model_validate(
            request_json("GET", self.base_url, "/v1/config/session-assumptions/schema", DEPENDENCY)
        )

    def session_defaults(self, age: int, country: str = "Singapore") -> SessionDefaults:
        return SessionDefaults.model_validate(
            request_json(
                "GET", self.base_url, "/v1/config/session-defaults", DEPENDENCY,
                params={"age": age, "country": country},
            )
        )

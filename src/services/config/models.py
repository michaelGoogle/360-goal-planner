"""Config service contract: admin parameters and the customer assumption schema.

Two levels, per decision D3. ``admin`` parameters are everything the customer
never sees (costs, years, bands, steps, the HappiU envelope); ``customer``
parameters are the assumption box and the goal cards. Resolution order at run
time is session value, then the active admin version, then the built-in default.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

Level = Literal["admin", "customer"]


class Parameter(BaseModel):
    """One Assumptions row, with the metadata the workbook carries beside it."""

    name: str
    value: float | int | str | bool
    unit: str = ""
    currency: str = ""
    level: Level = "admin"
    label: str = ""
    codeSource: str = ""
    changedIn: str = ""
    min: float | None = None
    max: float | None = None


class ParameterSet(BaseModel):
    """One immutable version of the admin parameters."""

    version: str
    model: str = ""
    createdAt: str = ""
    createdBy: str = ""
    note: str = ""
    parameters: dict[str, Parameter] = Field(default_factory=dict)


class ParameterWrite(BaseModel):
    """A new version. Only the changed rows need to be sent; the rest are carried over."""

    parameters: dict[str, float | int | str | bool] = Field(default_factory=dict)
    note: str = ""
    basedOn: str = ""


class AuditEntry(BaseModel):
    version: str
    createdAt: str
    createdBy: str
    note: str = ""
    diff: dict[str, dict[str, Any]] = Field(default_factory=dict)


class AssumptionSchema(BaseModel):
    """What the assumption box and the goal cards may edit, and within which limits.

    ``version`` is the parameter version the values came from, so a session can
    record which numbers it was calculated under.
    """

    version: str = ""
    fields: list[Parameter] = Field(default_factory=list)


class SessionDefaults(BaseModel):
    """Customer-level defaults the config service derives, so the UI never re-implements them.

    ``targetYear`` per goal comes from the customer's age and the target-age
    parameters (N_EDU at 50, N_SAV at 40, N_PRP at 33). Past that age, education
    aims at next year; savings and property keep a 5- and 3-year floor.
    """

    age: int
    country: str = "Singapore"
    ageOfRetirement: int = 65
    lifeExpectancy: int = 85
    ltcStartAge: int = 80
    targetYear: dict[str, int] = Field(default_factory=dict)
    parametersVersion: str = ""

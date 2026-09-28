"""Config service logic: read a version, write the next one, derive session defaults.

A version is immutable. Writing sends only the rows that changed; everything else is
carried over from the version it was based on, so a new version is always complete
and a session that pins ``v24`` keeps calculating with V0-24 numbers forever.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from src.services.config import store
from src.services.config.models import (
    AssumptionSchema,
    AuditEntry,
    Parameter,
    ParameterSet,
    ParameterWrite,
    SessionDefaults,
)
from src.services.errors import ValidationFailed

WP = "WP2"

# Goals whose target year the customer sets by an age rather than by a horizon.
TARGET_AGE_PARAMETER = {
    "N_EDU": "EDU_TARGET_AGE",
    "N_SAV": "SAV_TARGET_AGE",
    "N_PRP": "PRP_TARGET_AGE",
}
# Once the customer is at or past that age, keep a remaining horizon so a
# 40-year-old is not given one year to save five times income.
MIN_HORIZON_YEARS = {"N_EDU": 1, "N_SAV": 5, "N_PRP": 3}


def default_horizon_years(age: int, need: str, params: dict) -> int:
    """Years from now to the default target. Education still aims at next year
    once past EDU_TARGET_AGE; savings and property keep a 5- and 3-year floor.
    """
    target_age = int(params[TARGET_AGE_PARAMETER[need]])
    return max(MIN_HORIZON_YEARS[need], target_age - int(age or 0))


_cache: dict[str, tuple[float, ParameterSet]] = {}  # keyed by path, invalidated by mtime


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse(version: str, raw: dict[str, Any]) -> ParameterSet:
    return ParameterSet(
        version=raw.get("version") or version,
        model=raw.get("model", ""),
        createdAt=raw.get("createdAt", ""),
        createdBy=raw.get("createdBy", ""),
        note=raw.get("note", ""),
        parameters={
            name: Parameter(name=name, **row) for name, row in (raw.get("parameters") or {}).items()
        },
    )


def parameters_for_version(version: str) -> ParameterSet:
    """An earlier version, so an old session can be recalculated as it was."""
    path = store.version_path(version)
    stamp = path.stat().st_mtime if path.is_file() else 0.0
    cached = _cache.get(str(path))
    if cached and cached[0] == stamp:
        return cached[1]
    parsed = _parse(version, store.read_version(version))
    _cache[str(path)] = (stamp, parsed)
    return parsed


def active_parameters() -> ParameterSet:
    """The parameter version sessions use unless they pin an older one."""
    return parameters_for_version(store.active_version())


def versions() -> list[str]:
    """Every version on disk, oldest first. The admin screen lists these."""
    return store.versions()


def resolve(version: str = "") -> ParameterSet:
    """The version a session asked for, or the active one if it did not ask."""
    return parameters_for_version(version) if version else active_parameters()


def value(name: str, version: str = "") -> Any:
    """One parameter. Raises rather than returning a default, so a typo is visible."""
    params = resolve(version).parameters
    if name not in params:
        raise ValidationFailed(
            fields=[{"loc": ["parameter"], "msg": "unknown parameter", "type": "value_error"}],
            detail=f"No parameter named {name!r} in {resolve(version).version}",
        )
    return params[name].value


def values(version: str = "") -> dict[str, Any]:
    """Every parameter as a plain name to value mapping, for the calculators."""
    return {name: p.value for name, p in resolve(version).parameters.items()}


def _check(name: str, new: Any, existing: Parameter) -> Any:
    """A write may change a value, never its type, and never leave its bounds."""
    if isinstance(existing.value, str):
        if not isinstance(new, str):
            raise ValidationFailed(
                fields=[{"loc": [name], "msg": "expected a string", "type": "type_error"}],
                detail=f"{name} is a code, not a number",
            )
        return new
    if isinstance(new, bool) or not isinstance(new, int | float):
        raise ValidationFailed(
            fields=[{"loc": [name], "msg": "expected a number", "type": "type_error"}],
            detail=f"{name} is numeric",
        )
    if existing.min is not None and new < existing.min:
        raise ValidationFailed(
            fields=[{"loc": [name], "msg": f"below minimum {existing.min}", "type": "value_error"}],
            detail=f"{name} must be at least {existing.min}",
        )
    if existing.max is not None and new > existing.max:
        raise ValidationFailed(
            fields=[{"loc": [name], "msg": f"above maximum {existing.max}", "type": "value_error"}],
            detail=f"{name} must be at most {existing.max}",
        )
    return int(new) if isinstance(existing.value, int) and float(new).is_integer() else new


def write_parameters(write: ParameterWrite, author: str) -> ParameterSet:
    """Validate, write the next version, and append to the audit log. Never edits in place."""
    if not write.parameters:
        raise ValidationFailed(
            fields=[{"loc": ["parameters"], "msg": "no changes", "type": "missing"}],
            detail="A new version needs at least one changed parameter",
        )

    base = resolve(write.basedOn)
    unknown = sorted(set(write.parameters) - set(base.parameters))
    if unknown:
        raise ValidationFailed(
            fields=[{"loc": [n], "msg": "unknown parameter", "type": "value_error"} for n in unknown],
            detail=f"Not in {base.version}: {', '.join(unknown)}. Add it to the workbook first.",
        )

    rows = {name: p.model_copy() for name, p in base.parameters.items()}
    diff: dict[str, dict[str, Any]] = {}
    for name, new in write.parameters.items():
        checked = _check(name, new, rows[name])
        if checked == rows[name].value:
            continue
        diff[name] = {"from": rows[name].value, "to": checked}
        rows[name].value = checked

    if not diff:
        raise ValidationFailed(
            fields=[{"loc": ["parameters"], "msg": "no changes", "type": "value_error"}],
            detail=f"Every value sent already equals {base.version}",
        )

    version = store.next_version()
    payload = {
        "version": version,
        "model": base.model,
        "createdAt": _now(),
        "createdBy": author,
        "note": write.note,
        "basedOn": base.version,
        "parameters": {
            name: row.model_dump(exclude={"name"}, exclude_defaults=False) for name, row in rows.items()
        },
    }
    store.write_version(version, payload)
    store.append_audit(
        {
            "version": version,
            "basedOn": base.version,
            "createdAt": payload["createdAt"],
            "createdBy": author,
            "note": write.note,
            "diff": diff,
        }
    )
    return _parse(version, payload)


def audit_log() -> list[AuditEntry]:
    return [AuditEntry.model_validate(entry) for entry in store.read_audit()]


def assumption_schema() -> AssumptionSchema:
    """The customer-editable parameters, with the bounds an edit must stay inside.

    Derived from the ``customer`` level unless an admin has saved an override, so
    adding a customer parameter to the workbook is enough to expose it.
    """
    active = active_parameters()
    override = store.read_schema_override()
    if override:
        return AssumptionSchema.model_validate({**override, "version": active.version})
    return AssumptionSchema(
        version=active.version,
        fields=[p for p in active.parameters.values() if p.level == "customer"],
    )


def write_assumption_schema(schema: AssumptionSchema, author: str) -> AssumptionSchema:
    """Narrow or relabel what the assumption box shows. Cannot invent a parameter."""
    active = active_parameters()
    unknown = sorted({f.name for f in schema.fields} - set(active.parameters))
    if unknown:
        raise ValidationFailed(
            fields=[{"loc": [n], "msg": "unknown parameter", "type": "value_error"} for n in unknown],
            detail=f"Not in {active.version}: {', '.join(unknown)}",
        )
    store.write_schema_override(schema.model_dump())
    store.append_audit(
        {
            "version": active.version,
            "createdAt": _now(),
            "createdBy": author,
            "note": "assumption schema",
            "diff": {"fields": {"to": [f.name for f in schema.fields]}},
        }
    )
    return schema


def session_defaults(age: int, country: str = "Singapore") -> SessionDefaults:
    """What a new session starts from, so the UI never re-implements these rules."""
    if age < 0 or age > 120:
        raise ValidationFailed(
            fields=[{"loc": ["age"], "msg": "outside 0 to 120", "type": "value_error"}],
            detail=f"{age} is not a plausible age",
        )
    active = active_parameters()
    params = {name: p.value for name, p in active.parameters.items()}
    year = int(params.get("currentYear") or datetime.now(UTC).year)

    target_year: dict[str, int] = {}
    for need in TARGET_AGE_PARAMETER:
        target_year[need] = year + default_horizon_years(age, need, params)

    retirement = int(params["ageOfRetirement"])
    target_year["N_RET"] = year + max(1, retirement - age)

    return SessionDefaults(
        age=age,
        country=country or str(params.get("PPP_BASE_COUNTRY") or "Singapore"),
        ageOfRetirement=retirement,
        lifeExpectancy=int(params["lifeExpectancyDefault"]),
        ltcStartAge=int(params["LTC_START_AGE"]),
        targetYear=target_year,
        parametersVersion=active.version,
    )


def clear_cache() -> None:
    _cache.clear()

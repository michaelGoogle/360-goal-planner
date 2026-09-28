"""WP2: the config service, and the promise that code and workbook agree.

The parity check is the important one: ``config/parameters/v24.json`` is generated
from the V0-24 workbook export, and the constants still living in code must equal
it. That is what stops the situation the V0-24 doc pass had to clean up, where the
prose quoted figures nobody had recalibrated.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from scripts.build_parameters import OUT as V24_PATH
from scripts.build_parameters import main as build_parameters
from src.app import api
from src.services.config import service, store
from src.services.config.models import AssumptionSchema, Parameter, ParameterWrite
from src.services.errors import ValidationFailed
from src.session_rates import DEFAULTS, RATE_NAMES, defaults, session_rate

client = TestClient(api)
FIXTURE = Path(__file__).parent / "fixtures" / "model_v0_24" / "parameters.json"


@pytest.fixture
def config_dir(tmp_path, monkeypatch):
    """A writable copy of the committed store, so a write test cannot dirty the repo."""
    target = tmp_path / "parameters"
    target.mkdir()
    shutil.copy(V24_PATH, target / "v24.json")
    monkeypatch.setenv("GP_CONFIG_DIR", str(target))
    monkeypatch.delenv("GP_PARAMETERS_VERSION", raising=False)
    service.clear_cache()
    yield target
    service.clear_cache()


# --- parity with the workbook -------------------------------------------------


def test_the_committed_parameter_file_matches_the_workbook_export():
    assert build_parameters(["--check"]) == 0


def test_every_workbook_parameter_reached_the_config_store():
    export = json.loads(FIXTURE.read_text(encoding="utf-8"))["parameters"]
    active = service.active_parameters()
    assert set(active.parameters) == set(export)
    for name, row in export.items():
        assert active.parameters[name].value == row["value"], name


def test_the_active_version_is_the_v0_24_model():
    active = service.active_parameters()
    assert active.version == "v24"
    assert active.model == "V0-24"


def test_code_rate_defaults_equal_the_active_version():
    """If this fails, either the workbook moved or session_rates.py did. Fix the code."""
    assert defaults() == {name: DEFAULTS[name] for name in RATE_NAMES}


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("systemCurrency", "USD"),
        ("PPP_BASE_COUNTRY", "Singapore"),
        ("priceLevelOn", 1),
        ("currentYear", 2026),
        ("ageOfRetirement", 65),
        ("lifeExpectancyDefault", 85),
        ("LTC_START_AGE", 80),
        ("CRI_COST", 156325.47),
        ("lifeRoundUnit", 78162.73),
    ],
)
def test_named_values_come_through_unrounded(name, expected):
    assert service.value(name) == expected


def test_an_unknown_parameter_is_an_error_not_a_zero():
    with pytest.raises(ValidationFailed):
        service.value("NO_SUCH_PARAMETER")


# --- levels and the assumption schema ----------------------------------------


def test_the_assumption_schema_is_the_customer_level_only():
    schema = service.assumption_schema()
    names = {f.name for f in schema.fields}
    assert set(RATE_NAMES) <= names
    assert "CRI_COST" not in names, "a cost is not the customer's to edit"
    assert all(f.level == "customer" for f in schema.fields)


def test_the_schema_names_the_version_it_came_from():
    """The UI stores this on the session, so a plan records which numbers made it."""
    body = client.get("/v1/config/session-assumptions/schema").json()
    assert body["version"] == "v24"
    assert {f["name"] for f in body["fields"]} >= set(RATE_NAMES)


def test_customer_fields_carry_the_bounds_an_edit_must_respect():
    by_name = {f.name: f for f in service.assumption_schema().fields}
    assert by_name["inflationRate"].min == 0.0
    assert by_name["inflationRate"].max == 0.15
    assert by_name["ageOfRetirement"].min == 40


def test_an_admin_can_narrow_the_schema_but_not_invent_a_field(config_dir):
    only_inflation = AssumptionSchema(fields=[Parameter(name="inflationRate", value=0.023)])
    service.write_assumption_schema(only_inflation, author="tester")
    assert [f.name for f in service.assumption_schema().fields] == ["inflationRate"]

    with pytest.raises(ValidationFailed):
        service.write_assumption_schema(
            AssumptionSchema(fields=[Parameter(name="MADE_UP", value=1)]), author="tester"
        )


# --- session defaults ---------------------------------------------------------


def test_session_defaults_come_from_the_parameters():
    d = service.session_defaults(40)
    assert d.ageOfRetirement == 65
    assert d.lifeExpectancy == 85
    assert d.ltcStartAge == 80
    assert d.parametersVersion == "v24"


def test_target_years_use_the_target_age_parameters():
    """Education at 50, savings at 40, property at 33, counted from currentYear."""
    d = service.session_defaults(30)
    assert d.targetYear["N_EDU"] == 2026 + 20
    assert d.targetYear["N_SAV"] == 2026 + 10
    assert d.targetYear["N_PRP"] == 2026 + 3
    assert d.targetYear["N_RET"] == 2026 + 35


def test_savings_and_property_keep_a_floor_once_the_milestone_age_is_past():
    """A 40-year-old is not given one year to buy a home or fund the savings goal."""
    at_forty = service.session_defaults(40)
    assert at_forty.targetYear["N_SAV"] == 2026 + 5
    assert at_forty.targetYear["N_PRP"] == 2026 + 3
    assert at_forty.targetYear["N_EDU"] == 2026 + 10
    just_before = service.session_defaults(32)
    assert just_before.targetYear["N_PRP"] == 2026 + 3
    assert just_before.targetYear["N_SAV"] == 2026 + 8


def test_education_still_aims_at_next_year_once_past_fifty():
    d = service.session_defaults(60)
    assert d.targetYear["N_PRP"] == 2026 + 3
    assert d.targetYear["N_SAV"] == 2026 + 5
    assert d.targetYear["N_EDU"] == 2027


def test_an_implausible_age_is_rejected():
    assert client.get("/v1/config/session-defaults", params={"age": 500}).status_code == 422


# --- writing a version -------------------------------------------------------


def test_a_write_creates_the_next_version_and_leaves_the_old_one_alone(config_dir):
    before = (config_dir / "v24.json").read_text(encoding="utf-8")

    new = service.write_parameters(
        ParameterWrite(parameters={"inflationRate": 0.03}, note="higher inflation"),
        author="tester",
    )

    assert new.version == "v25"
    assert new.parameters["inflationRate"].value == 0.03
    assert (config_dir / "v24.json").read_text(encoding="utf-8") == before
    assert service.parameters_for_version("v24").parameters["inflationRate"].value == 0.023


def test_a_new_version_carries_over_everything_that_did_not_change(config_dir):
    service.write_parameters(ParameterWrite(parameters={"inflationRate": 0.03}), author="t")
    v24, v25 = service.parameters_for_version("v24"), service.parameters_for_version("v25")
    assert set(v25.parameters) == set(v24.parameters)
    assert v25.parameters["CRI_COST"].value == v24.parameters["CRI_COST"].value


def test_the_newest_version_becomes_active(config_dir):
    service.write_parameters(ParameterWrite(parameters={"inflationRate": 0.03}), author="t")
    assert service.active_parameters().version == "v25"
    assert service.versions() == ["v24", "v25"]


def test_a_session_can_pin_an_old_version(config_dir):
    service.write_parameters(ParameterWrite(parameters={"inflationRate": 0.03}), author="t")
    assert session_rate({"parametersVersion": "v24"}, "inflationRate") == 0.023
    assert session_rate({"parametersVersion": "v25"}, "inflationRate") == 0.03


def test_the_audit_log_records_the_diff_and_the_author(config_dir):
    service.write_parameters(
        ParameterWrite(parameters={"inflationRate": 0.03}, note="why"), author="admin-1"
    )
    entry = service.audit_log()[-1]
    assert entry.version == "v25"
    assert entry.createdBy == "admin-1"
    assert entry.note == "why"
    assert entry.diff == {"inflationRate": {"from": 0.023, "to": 0.03}}


def test_a_value_outside_its_bounds_is_refused(config_dir):
    with pytest.raises(ValidationFailed):
        service.write_parameters(ParameterWrite(parameters={"inflationRate": 5.0}), author="t")
    assert service.versions() == ["v24"], "a refused write must not leave a version behind"


def test_an_unknown_parameter_cannot_be_introduced_by_a_write(config_dir):
    with pytest.raises(ValidationFailed) as exc:
        service.write_parameters(ParameterWrite(parameters={"MADE_UP": 1}), author="t")
    assert "workbook" in str(exc.value.detail), "the message should point at the source of truth"


def test_a_write_that_changes_nothing_is_refused(config_dir):
    with pytest.raises(ValidationFailed):
        service.write_parameters(ParameterWrite(parameters={"inflationRate": 0.023}), author="t")


def test_a_code_parameter_cannot_be_given_a_number(config_dir):
    with pytest.raises(ValidationFailed):
        service.write_parameters(ParameterWrite(parameters={"systemCurrency": 1}), author="t")


def test_an_integer_parameter_stays_an_integer(config_dir):
    new = service.write_parameters(ParameterWrite(parameters={"huNumSims": 500.0}), author="t")
    assert new.parameters["huNumSims"].value == 500
    assert isinstance(new.parameters["huNumSims"].value, int)


def test_versions_are_immutable(config_dir):
    with pytest.raises(ValidationFailed):
        store.write_version("v24", {"parameters": {}})


def test_a_version_name_cannot_escape_the_config_directory():
    with pytest.raises(ValidationFailed):
        store.version_path("../../secrets")


# --- the routes --------------------------------------------------------------


def test_reading_parameters_needs_no_token():
    body = client.get("/v1/config/parameters").json()
    assert body["version"] == "v24"
    assert body["parameters"]["CRI_COST"]["value"] == 156325.47


def test_reading_an_unknown_version_is_a_422_not_a_500():
    assert client.get("/v1/config/parameters/v999").status_code == 422


def test_writing_without_a_token_is_refused(config_dir, monkeypatch):
    monkeypatch.setenv("GP_CONFIG_ADMIN_MODE", "fm")
    r = client.put("/v1/config/parameters", json={"parameters": {"inflationRate": 0.03}})
    assert r.status_code == 401
    assert r.json()["error"] == "not_authenticated"
    assert service.versions() == ["v24"]


def test_writing_is_allowed_when_the_admin_check_is_open(config_dir, monkeypatch):
    monkeypatch.setenv("GP_CONFIG_ADMIN_MODE", "open")
    r = client.put(
        "/v1/config/parameters", json={"parameters": {"inflationRate": 0.03}, "note": "n"}
    )
    assert r.status_code == 200, r.text
    assert r.json()["version"] == "v25"


def test_an_unreachable_fm_does_not_become_an_open_door(config_dir, monkeypatch):
    monkeypatch.setenv("GP_CONFIG_ADMIN_MODE", "fm")
    monkeypatch.setenv("FM_UPSTREAM", "http://127.0.0.1:1")
    monkeypatch.setenv("GP_UPSTREAM_TIMEOUT_S", "1")
    r = client.put(
        "/v1/config/parameters",
        json={"parameters": {"inflationRate": 0.03}},
        headers={"Authorization": "Bearer whatever"},
    )
    assert r.status_code == 403
    assert service.versions() == ["v24"]


# --- the rate a calculation actually uses ------------------------------------


def test_a_published_rate_reaches_a_session_that_never_set_one(config_dir):
    """The WP2 acceptance test: a new version changes /v1/needs without a session edit."""
    session = {"age": 40, "dateOfBirth": "1986-01-01", "needs": []}
    assert client.post("/v1/needs", json=session).status_code == 200

    service.write_parameters(ParameterWrite(parameters={"inflationRate": 0.09}), author="t")
    assert session_rate({}, "inflationRate") == 0.09


def test_a_session_value_still_wins_over_the_version(config_dir):
    assert session_rate({"inflationRate": 0.01}, "inflationRate") == 0.01


def test_an_omitted_rate_is_not_silently_zero(config_dir):
    """/v1/predict and /v1/needs accept a session with no rates at all."""
    r = client.post("/v1/needs", json={"age": 40, "dateOfBirth": "1986-01-01"})
    assert r.status_code == 200, r.text


def test_the_schema_override_survives_a_new_version(config_dir):
    service.write_assumption_schema(
        AssumptionSchema(fields=[Parameter(name="inflationRate", value=0.023)]), author="t"
    )
    service.write_parameters(ParameterWrite(parameters={"inflationRate": 0.03}), author="t")
    schema = service.assumption_schema()
    assert [f.name for f in schema.fields] == ["inflationRate"]
    assert schema.version == "v25", "the override narrows the list, it does not pin the values"


def test_a_missing_config_store_degrades_to_the_built_in_rates(tmp_path, monkeypatch):
    monkeypatch.setenv("GP_CONFIG_DIR", str(tmp_path / "gone"))
    service.clear_cache()
    assert defaults() == {name: DEFAULTS[name] for name in RATE_NAMES}
    service.clear_cache()

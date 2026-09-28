"""WP4: the social-security service against the workbook's CPF tab, all 50 personas."""

from __future__ import annotations

import pytest
from src.services.registry import get_social_security_client
from src.services.social_security.models import ContributionRequest
from src.services.social_security.service import OW_CEILING, SgCpfModule

from tests.parity.conftest import load, personas


def _contribution(inputs: dict) -> ContributionRequest:
    return ContributionRequest(
        country=inputs.get("country") or "Singapore",
        residency=inputs.get("residency") or "",
        age=int(inputs["age"]),
        grossMonthly=float(inputs["income"]),
        currency=inputs.get("currency") or "SGD",
    )


@pytest.mark.parametrize("case", personas())
def test_contribution_equals_the_cpf_tab(case):
    doc = load(case)
    want = doc["cpf"]["values"]
    got = get_social_security_client().contribution(_contribution(doc["inputs"]))
    assert got.rate == pytest.approx(want["CPF_rate"], rel=1e-9)
    assert got.employeeContribution == pytest.approx(want["CPF_employee"], abs=0.5)
    assert got.takeHome == pytest.approx(want["CPF_takeHome"], abs=0.5)


@pytest.mark.parametrize("case", personas())
def test_the_module_matches_the_cpf_on_flag(case):
    """``CPF_on`` is the workbook's "does this country have a scheme"."""
    doc = load(case)
    got = get_social_security_client().contribution(_contribution(doc["inputs"]))
    expected = "SG-CPF" if doc["cpf"]["values"]["CPF_on"] else "default"
    assert got.module == expected


# --- the module itself -------------------------------------------------------


@pytest.mark.parametrize(
    ("age", "rate"),
    [(22, 0.20), (55, 0.20), (56, 0.18), (60, 0.18), (61, 0.125), (65, 0.125),
     (66, 0.075), (70, 0.075), (71, 0.05), (90, 0.05)],
)
def test_the_age_bands_are_the_cpf_boards(age, rate):
    assert SgCpfModule().rate(age, "Citizen") == rate


def test_a_foreigner_contributes_nothing():
    assert SgCpfModule().rate(34, "Foreigner") == 0.0


def test_an_unrecognised_residency_still_contributes():
    """Exempting someone because a string was not in a list would understate take-home."""
    assert SgCpfModule().rate(34, "Permanent Resident (3rd year)") == 0.20
    assert SgCpfModule().rate(34, "") == 0.20


def test_the_wage_ceiling_caps_the_contribution():
    high = SgCpfModule().contribution(
        ContributionRequest(country="Singapore", residency="Citizen", age=40, grossMonthly=50_000)
    )
    assert high.employeeContribution == OW_CEILING * 0.20
    assert high.takeHome == 50_000 - OW_CEILING * 0.20


def test_a_country_without_a_module_takes_nothing():
    got = get_social_security_client().contribution(
        ContributionRequest(country="Vietnam", residency="Citizen", age=34,
                            grossMonthly=30_000_000, currency="VND")
    )
    assert got.module == "default"
    assert got.employeeContribution == 0.0
    assert got.takeHome == 30_000_000
    assert got.currency == "VND"


def test_the_country_is_matched_loosely_enough_to_be_useful():
    for country in ("Singapore", "singapore", " SINGAPORE ", "SG", "SGP"):
        got = get_social_security_client().contribution(
            ContributionRequest(country=country, residency="Citizen", age=34, grossMonthly=7140)
        )
        assert got.module == "SG-CPF", country


def test_no_income_is_not_an_error():
    got = get_social_security_client().contribution(
        ContributionRequest(country="Singapore", residency="Citizen", age=34, grossMonthly=0)
    )
    assert got.employeeContribution == 0.0
    assert got.takeHome == 0.0


def test_the_route_answers_the_contract_shape():
    from fastapi.testclient import TestClient
    from src.app import api

    body = {"country": "Singapore", "residency": "Citizen", "age": 34,
            "grossMonthly": 7140, "currency": "SGD"}
    got = TestClient(api).post("/v1/social-security/contribution", json=body)
    assert got.status_code == 200
    assert got.json() == {"module": "SG-CPF", "employeeContribution": 1428.0,
                          "takeHome": 5712.0, "rate": 0.2, "currency": "SGD"}

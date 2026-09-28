"""WP3b: the currency pipeline — the FX lock, and the money helpers built on it.

The rounding tests matter more than they look. Converting SGD 1,000 to USD and back
gives 999.9999, and a slider that moves in steps of 999.9999 is worse than useless, so
``nice_step`` has to produce a number a human would have chosen.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from src.app import api
from src.money import fixed, nice_step, ppp_usd, round_to_step, round_user, to_usd, to_user
from src.services.errors import DependencyFailed, UnknownCurrency
from src.services.fx.client import HttpFxClient, MockFxClient, SnapshotFxClient
from src.services.fx.models import FxLock

client = TestClient(api)
snapshot = SnapshotFxClient()

SGD_USD_PER_LOCAL = 0.78162734281267
VND_USD_PER_LOCAL = 3.849039994550423e-05
VIETNAM_RELATIVE = 0.4602


@pytest.fixture(autouse=True)
def _snapshot_mode(monkeypatch):
    monkeypatch.setenv("GP_SVC_FX", "snapshot")


# --- the snapshot client -----------------------------------------------------


def test_the_snapshot_holds_the_rate_the_model_was_calibrated_at():
    assert snapshot.rate("SGD").usdPerLocal == pytest.approx(SGD_USD_PER_LOCAL, rel=1e-12)
    assert snapshot.rate("VND").usdPerLocal == pytest.approx(VND_USD_PER_LOCAL, rel=1e-9)


def test_ref_rate_and_usd_per_local_are_reciprocal():
    rate = snapshot.rate("VND")
    assert rate.refRate == pytest.approx(1 / rate.usdPerLocal, rel=1e-12)


def test_an_unknown_currency_has_no_fallback():
    with pytest.raises(UnknownCurrency):
        snapshot.rate("ZZZ")


def test_the_snapshot_files_are_found_without_configuration():
    """The Docker image copies these to config/fx_ppp; a checkout has them under docs."""
    from src.services.fx.client import snapshot_dir

    directory = snapshot_dir()
    assert (directory / "currencies_fx.csv").is_file()
    assert (directory / "countries_ppp.csv").is_file()


def test_the_snapshot_directory_can_be_overridden(monkeypatch, tmp_path):
    from src.services.fx.client import snapshot_dir

    monkeypatch.setenv("GP_FX_SNAPSHOT_DIR", str(tmp_path))
    assert snapshot_dir() == tmp_path


def test_the_snapshot_covers_far_more_than_the_old_table():
    for iso in ("SGD", "VND", "MYR", "THB", "PHP", "AUD", "EUR", "HKD", "INR", "BRL", "KES"):
        assert snapshot.rate(iso).usdPerLocal > 0


# --- the lock ----------------------------------------------------------------


def test_a_singapore_lock_is_the_base_case():
    lock = snapshot.lock("SGD", "Singapore", "Singapore")
    assert lock.usdPerLocal == pytest.approx(SGD_USD_PER_LOCAL, rel=1e-12)
    assert lock.priceLevel == pytest.approx(1.0)
    assert lock.pppAvailable is True
    assert lock.asOf == "2026-09-25"
    assert lock.source == "snapshot"


def test_a_vietnam_lock_matches_the_workbook():
    lock = snapshot.lock("VND", "Vietnam", "Singapore")
    assert lock.usdPerLocal == pytest.approx(VND_USD_PER_LOCAL, rel=1e-9)
    assert lock.priceLevel == pytest.approx(VIETNAM_RELATIVE, abs=5e-4)


def test_the_lock_keeps_the_two_figures_behind_the_price_level():
    """A lock that says only "0.4602" cannot be checked a year later."""
    lock = snapshot.lock("VND", "Vietnam", "Singapore")
    assert lock.priceLevelCountry and lock.priceLevelBase
    assert lock.priceLevel == pytest.approx(lock.priceLevelCountry / lock.priceLevelBase, abs=1e-5)


def test_a_country_without_ppp_locks_at_one_and_says_so():
    """Not an error: no price level means plain conversion, which is option A."""
    lock = snapshot.lock("USD", "American Samoa", "Singapore")
    assert lock.priceLevel == 1.0
    assert lock.pppAvailable is False


def test_an_unreachable_fx_service_does_not_become_a_price_level_of_one():
    """The one failure that must never be swallowed, or Vietnam silently costs Singapore prices."""
    unreachable = HttpFxClient("http://127.0.0.1:1")
    with pytest.raises(DependencyFailed):
        unreachable.lock("SGD", "Singapore")


# --- conversion --------------------------------------------------------------


def test_a_round_trip_returns_the_amount():
    fx = snapshot.lock("VND", "Vietnam")
    assert to_user(to_usd(1_000_000, fx), fx) == pytest.approx(1_000_000, rel=1e-9)


def test_ppp_usd_divides_and_fixed_amounts_multiply():
    """Two uses of the same number, in opposite directions, and easy to confuse."""
    fx = snapshot.lock("VND", "Vietnam")
    # How well off is this person, comparably across countries: divide.
    assert ppp_usd(1_000_000, fx) == pytest.approx(to_usd(1_000_000, fx) / fx.priceLevel)
    # What does a fixed cost come to here: multiply.
    assert fixed(156_325.47, fx) == pytest.approx(156_325.47 * fx.priceLevel)


def test_treatment_costs_less_in_a_cheaper_country():
    sg = snapshot.lock("SGD", "Singapore")
    vn = snapshot.lock("VND", "Vietnam")
    assert fixed(156_325.47, vn) < fixed(156_325.47, sg)


def test_a_price_level_of_one_makes_both_plain_conversion():
    fx = MockFxClient(price_level=1.0).lock("SGD", "Singapore")
    assert ppp_usd(5000, fx) == pytest.approx(to_usd(5000, fx))
    assert fixed(1000, fx) == pytest.approx(1000)


def test_singapore_income_in_usd_matches_the_workbook():
    fx = snapshot.lock("SGD", "Singapore")
    assert to_usd(5000, fx) == pytest.approx(3908.14, abs=0.01)


def test_round_user_gives_whole_units():
    assert round_user(1234.49) == 1234
    assert round_user(1234.51) == 1235
    assert round_user(None) == 0


# --- nice_step ---------------------------------------------------------------

SGD = FxLock(currency="SGD", usdPerLocal=SGD_USD_PER_LOCAL)
VND = FxLock(currency="VND", usdPerLocal=VND_USD_PER_LOCAL)

# The USD steps in the workbook, and what a human would pick in each currency.
STEPS = [
    ("lumpRoundStep", 781.63, 1_000.0, 20_000_000.0),
    ("monthlyRoundStep", 39.08, 50.0, 1_000_000.0),
    ("coverPremRoundStep", 7.82, 10.0, 200_000.0),
    ("lifeRoundUnit", 78_162.73, 100_000.0, 2_000_000_000.0),
    ("benefitRound", 39_081.37, 50_000.0, 1_000_000_000.0),
]


@pytest.mark.parametrize(("name", "step_usd", "sgd", "vnd"), STEPS)
def test_nice_step_gives_a_step_a_human_would_choose(name, step_usd, sgd, vnd):
    assert nice_step(step_usd, SGD) == pytest.approx(sgd), name
    assert nice_step(step_usd, VND) == pytest.approx(vnd), name


def test_nice_step_snaps_rather_than_leaving_a_converted_remainder():
    """The whole point: 999.9999 is not a step."""
    assert nice_step(781.63, SGD) == 1000.0


def test_nice_step_handles_a_useless_input():
    assert nice_step(0, SGD) == 0.0
    assert nice_step(-5, SGD) == 0.0


def test_round_to_step_uses_the_step_it_is_given():
    assert round_to_step(1234, 1000) == 1000
    assert round_to_step(1600, 1000) == 2000
    assert round_to_step(1234, 0) == 1234


# --- the routes --------------------------------------------------------------


def test_the_lock_route_returns_a_usable_lock():
    body = client.post("/v1/fx/lock", json={"currency": "SGD", "country": "Singapore"}).json()
    assert body["usdPerLocal"] == pytest.approx(SGD_USD_PER_LOCAL, rel=1e-12)
    assert body["priceLevel"] == pytest.approx(1.0)


def test_the_lock_route_rejects_an_unknown_currency_with_a_404():
    res = client.post("/v1/fx/lock", json={"currency": "ZZZ"})
    assert res.status_code == 404
    assert res.json() == {"error": "unknown_currency", "currency": "ZZZ", "detail": "No FX rate for 'ZZZ'"}


def test_the_countries_route_lists_what_can_be_calculated_in():
    names = client.get("/v1/fx/countries").json()
    assert "Singapore" in names
    assert "Vietnam" in names
    assert "American Samoa" not in names

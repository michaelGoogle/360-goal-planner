"""Need Profiler FX → USD option weights.

The rates come from the committed snapshot the calculation workbook was built on
(2026-09-25), not from a hand-maintained table, so these are the workbook's numbers.
"""

import pytest
from src.fx import to_usd, usd_per_local
from src.pipeline.need_profiler import _get_option_weight, load_needs_config
from src.services.errors import UnknownCurrency


def test_rates_come_from_the_workbook_snapshot():
    assert usd_per_local("SGD") == pytest.approx(0.78162734281267)
    assert usd_per_local("VND") == pytest.approx(3.849039994550423e-05)
    assert usd_per_local("USD") == 1.0


def test_an_unknown_currency_raises_rather_than_becoming_singapore_dollars():
    """The old fallback made a Vietnamese salary look Singaporean. See Discrepancies row 2."""
    with pytest.raises(UnknownCurrency):
        usd_per_local("ZZZ")


def test_a_missing_currency_still_defaults_to_the_singapore_session():
    assert usd_per_local(None) == pytest.approx(0.78162734281267)


def test_income_option_weight_after_fx():
    options = load_needs_config()["weight_options"]
    sgd = _get_option_weight("Income", to_usd(5000, "SGD"), options)
    vnd = _get_option_weight("Income", to_usd(5000, "VND"), options)
    high = _get_option_weight("Income", to_usd(20_000, "SGD"), options)
    assert sgd == 2.0  # 3,908 USD → below 5,000
    assert vnd == 4.0  # 0.19 USD
    assert high == 0.0  # 15,633 USD

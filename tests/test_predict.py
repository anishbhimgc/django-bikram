"""Tests for the astronomical predictor and the provisional calendar tier.

The accuracy figures here are asserted deliberately: if the model or its fitted
constants change, these numbers move, and a reviewer should see exactly how far.
The predictor is *allowed* to be imperfect -- it is a prediction -- but it must
never quietly claim to be better than it is.

Activation of provisional years mutates process-global calendar state, so those
paths run in a clean subprocess rather than polluting the rest of the suite.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap

import pytest

from django_bikram.calendar_data import (
    MONTHS_IN_YEAR,
    VERIFIED_MAX_BS_YEAR,
    install_provisional,
)
from django_bikram.predict import (
    build_provisional_table,
    predicted_month_days,
    validate,
)

# -- the predictor's honesty ------------------------------------------------


def test_validate_reproduces_the_documented_accuracy() -> None:
    """The self-check pins the exact backtest result the docs quote.

    ~87% of months exact, the rest off by exactly one day, ~53% of years fully
    correct. These constants encode the *ceiling* an independent computation
    reaches against the official calendar; they are the reason predicted data is
    never treated as verified.
    """
    report = validate()
    assert report["months_total"] == 1308
    assert report["months_exact"] == 1142
    assert report["years_total"] == 109
    assert report["years_exact"] == 58
    assert report["max_error_days"] == 1
    assert report["error_histogram"] == {-1: 83, 0: 1142, 1: 83}


def test_validate_month_accuracy_is_in_the_expected_band() -> None:
    """A guard rail: accuracy stays in the mid-80s, never silently regresses."""
    accuracy = validate()["month_accuracy"]
    assert 0.85 <= accuracy <= 0.90


def test_errors_are_never_larger_than_one_day() -> None:
    """The whole model is only trustworthy to +/- a day; assert that literally."""
    histogram = validate()["error_histogram"]
    assert set(histogram) <= {-1, 0, 1}


# -- build_provisional_table -------------------------------------------------


def test_default_table_covers_a_century() -> None:
    """The no-argument call answers the 'give me the next 100 years' request."""
    table = build_provisional_table()
    assert min(table) == VERIFIED_MAX_BS_YEAR + 1
    assert max(table) == VERIFIED_MAX_BS_YEAR + 100
    assert len(table) == 100


def test_every_predicted_year_is_internally_valid() -> None:
    """Each predicted year has twelve months totalling 365 or 366 days."""
    for year, lengths in build_provisional_table(through_year=2183).items():
        assert len(lengths) == MONTHS_IN_YEAR, year
        assert all(29 <= n <= 32 for n in lengths), year
        assert sum(lengths) in (365, 366), (year, sum(lengths))


def test_table_is_contiguous_and_starts_after_the_verified_range() -> None:
    """Provisional years tile straight onto the verified ones, no gap or overlap."""
    table = build_provisional_table(through_year=2100)
    assert sorted(table) == list(range(VERIFIED_MAX_BS_YEAR + 1, 2101))


def test_build_table_before_the_range_is_rejected() -> None:
    """Asking for a table that does not extend the range is an error, not empty."""
    with pytest.raises(ValueError, match="not past the verified range"):
        build_provisional_table(through_year=VERIFIED_MAX_BS_YEAR)


def test_predicted_month_days_shape() -> None:
    """A single predicted year has the shape of a real one."""
    lengths = predicted_month_days(2090)
    assert len(lengths) == MONTHS_IN_YEAR
    assert sum(lengths) in (365, 366)


def test_predicted_month_days_before_anchor_is_rejected() -> None:
    """The model cannot walk earlier than its anchor year."""
    with pytest.raises(ValueError, match="anchored"):
        predicted_month_days(1900)


# -- install_provisional validation (safe: rejects before mutating) ----------


def test_install_rejects_non_contiguous_years() -> None:
    """A gap between the verified range and the new data is refused."""
    with pytest.raises(ValueError, match="contiguous"):
        install_provisional({VERIFIED_MAX_BS_YEAR + 5: (30,) * 12})


def test_install_rejects_wrong_month_count() -> None:
    """A year without twelve months is refused."""
    with pytest.raises(ValueError, match="month lengths"):
        install_provisional({VERIFIED_MAX_BS_YEAR + 1: (30, 30, 30)})


def test_install_rejects_impossible_year_total() -> None:
    """A year that does not total 365/366 days is refused -- the 2096-BS trap."""
    with pytest.raises(ValueError, match="not a possible year"):
        install_provisional({VERIFIED_MAX_BS_YEAR + 1: (30,) * 12})  # 360 days


def test_install_rejects_out_of_bounds_month_length() -> None:
    """A month length outside 29..32 is refused."""
    bad = (33,) + (30,) * 11
    with pytest.raises(ValueError, match="29..32"):
        install_provisional({VERIFIED_MAX_BS_YEAR + 1: bad})


# -- activation paths (subprocess: they mutate global calendar state) --------


def _run(script: str, **env_extra: str) -> str:
    """Run a Python snippet in a clean subprocess and return its stdout."""
    import os

    env = {**os.environ, **env_extra}
    result = subprocess.run(
        [sys.executable, "-c", textwrap.dedent(script)],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


def test_env_var_activates_provisional_at_import() -> None:
    """Setting the env var makes the package accept flagged provisional dates."""
    out = _run(
        """
        import warnings
        import django_bikram as b
        from django_bikram import BSDate, ProvisionalDateWarning
        assert b.MAX_BS_YEAR == 2150, b.MAX_BS_YEAR
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            d = BSDate(2100, 1, 1)
            ad = d.to_ad()
        assert d.is_verified is False
        assert BSDate.from_ad(ad) == d
        assert any(issubclass(w.category, ProvisionalDateWarning) for w in caught)
        assert BSDate(2081, 1, 1).is_verified is True
        print("ok")
        """,
        DJANGO_BIKRAM_PROVISIONAL_THROUGH_YEAR="2150",
    )
    assert out.strip() == "ok"


def test_runtime_install_keeps_every_cached_view_consistent() -> None:
    """A startup install() call refreshes convert, date and the top-level echoes."""
    out = _run(
        """
        import django_bikram as b
        from django_bikram import BSDate
        from django_bikram import calendar_data as cd, convert
        from django_bikram import date as datemod
        from django_bikram.predict import build_provisional_table
        cd.install_provisional(build_provisional_table(through_year=2120))
        # every module's echo of the bound agrees -- no stale alias
        assert b.MAX_BS_YEAR == cd.MAX_BS_YEAR == convert.MAX_BS_YEAR == 2120
        assert datemod.MAX_BS_YEAR == 2120
        assert BSDate.max.year == 2120
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            assert BSDate.from_ad(BSDate(2115, 6, 10).to_ad()) == BSDate(2115, 6, 10)
        print("ok")
        """,
    )
    assert out.strip() == "ok"


def test_default_import_has_no_provisional_years() -> None:
    """Without the opt-in, the package stays strictly verified-only."""
    out = _run(
        """
        import django_bikram as b
        from django_bikram import BSDate, DateOutOfRange
        assert b.MAX_BS_YEAR == b.VERIFIED_MAX_BS_YEAR == 2083
        try:
            BSDate(2100, 1, 1)
        except DateOutOfRange:
            print("ok")
        """,
    )
    assert out.strip() == "ok"

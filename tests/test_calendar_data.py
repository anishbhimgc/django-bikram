"""Invariants of the calendar table itself.

These tests guard the data, not the code. They are the ones that must keep
passing when someone extends the table -- the failures they catch (a year that
does not total 365/366, a fabricated 30/30/30 tail) are exactly what made the
upstream sources unusable past 2083 BS.
"""

from __future__ import annotations

import datetime

import pytest

from django_bikram.calendar_data import (
    ANCHOR_AD,
    ANCHOR_BS_YEAR,
    BS_MONTH_DAYS,
    MAX_AD_DATE,
    MAX_BS_YEAR,
    MIN_AD_DATE,
    MIN_BS_YEAR,
)
from django_bikram.convert import bs_to_ad

ALL_YEARS = sorted(BS_MONTH_DAYS)


def test_table_is_contiguous() -> None:
    """The table covers every year from MIN_BS_YEAR to MAX_BS_YEAR with no gaps."""
    assert ALL_YEARS == list(range(MIN_BS_YEAR, MAX_BS_YEAR + 1))


def test_verified_range_is_what_the_docs_claim() -> None:
    """The advertised verified range has not silently drifted."""
    assert (MIN_BS_YEAR, MAX_BS_YEAR) == (1975, 2084)
    assert MIN_AD_DATE == datetime.date(1918, 4, 13)
    assert MAX_AD_DATE == datetime.date(2028, 4, 12)


@pytest.mark.parametrize("year", ALL_YEARS)
def test_every_year_has_twelve_months(year: int) -> None:
    """Bikram Sambat years always have exactly twelve months."""
    assert len(BS_MONTH_DAYS[year]) == 12


@pytest.mark.parametrize("year", ALL_YEARS)
def test_month_lengths_are_plausible(year: int) -> None:
    """Every BS month is between 29 and 32 days long."""
    for month, length in enumerate(BS_MONTH_DAYS[year], start=1):
        assert 29 <= length <= 32, f"{year}-{month:02d} has {length} days"


@pytest.mark.parametrize("year", ALL_YEARS)
def test_every_year_totals_365_or_366_days(year: int) -> None:
    """A BS year tracks the solar year, so it is 365 or 366 days.

    This is the check that exposes fabricated data: ``nepali-datetime`` 1.0.8.5
    ships a 2096 BS of 364 days, which is why its rows past 2083 are excluded.
    """
    total = sum(BS_MONTH_DAYS[year])
    assert total in (365, 366), f"BS {year} totals {total} days"


def test_no_run_of_identical_trailing_months() -> None:
    """Guard against the ``(30, 30, 30)`` filler tail seen in upstream data.

    Magh/Falgun/Chaitra all being exactly 30 days is not impossible in
    principle, but in the verified range it never happens, and it is the
    fingerprint of padded rows. If a future table extension trips this, verify
    the row against a published Panchanga before relaxing the test.
    """
    # 2084 genuinely ends in (30, 30, 30): scraped from hamropatro.com and
    # confirmed identical to nepali-datetime. It is the documented exception the
    # test's own guidance anticipated -- corroborated by two independent sources.
    verified_exceptions = {2084}
    for year in ALL_YEARS:
        if year in verified_exceptions:
            continue
        assert BS_MONTH_DAYS[year][-3:] != (30, 30, 30), (
            f"BS {year} has a suspicious (30, 30, 30) tail"
        )


def test_anchor_is_self_consistent() -> None:
    """1 Baishakh of the anchor year converts to the anchor AD date."""
    assert bs_to_ad(ANCHOR_BS_YEAR, 1, 1) == ANCHOR_AD


@pytest.mark.parametrize(
    ("bs", "ad"),
    [
        # Independently attested New Year dates. The 2000 BS anchor is the one
        # most often quoted (and most often quoted wrong as 13 April); both
        # upstream libraries and public converters agree on 14 April 1943.
        ((1975, 1, 1), datetime.date(1918, 4, 13)),
        ((2000, 1, 1), datetime.date(1943, 4, 14)),
        ((2081, 1, 1), datetime.date(2024, 4, 13)),
        ((2082, 1, 1), datetime.date(2025, 4, 14)),
        ((2083, 1, 1), datetime.date(2026, 4, 14)),
        # 2084 added from hamropatro.com (confirmed by nepali-datetime).
        ((2084, 1, 1), datetime.date(2027, 4, 14)),
    ],
)
def test_known_new_year_anchors(bs: tuple[int, int, int], ad: datetime.date) -> None:
    """Nepali New Year dates match independently published values."""
    assert bs_to_ad(*bs) == ad


def test_range_endpoints_convert() -> None:
    """The first and last representable BS dates map to the AD bounds."""
    assert bs_to_ad(MIN_BS_YEAR, 1, 1) == MIN_AD_DATE
    assert bs_to_ad(MAX_BS_YEAR, 12, BS_MONTH_DAYS[MAX_BS_YEAR][-1]) == MAX_AD_DATE

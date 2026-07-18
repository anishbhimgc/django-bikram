"""Conversion correctness, checked exhaustively rather than by sampling.

The verified range is only ~40k days, so there is no reason to spot-check:
every single date in the range is round-tripped and weekday-checked here.
"""

from __future__ import annotations

import datetime

import pytest

from django_bikram.calendar_data import (
    BS_MONTH_DAYS,
    MAX_AD_DATE,
    MAX_BS_YEAR,
    MIN_AD_DATE,
    MIN_BS_YEAR,
)
from django_bikram.convert import ad_to_bs, bs_to_ad, check_bs_date, days_in_month, days_in_year
from django_bikram.exceptions import DateOutOfRange, InvalidBSDate


def _all_bs_dates() -> list[tuple[int, int, int]]:
    """Enumerate every Bikram Sambat date in the verified range.

    Returns:
        Every ``(year, month, day)`` triple the table can represent.
    """
    return [
        (year, month, day)
        for year in range(MIN_BS_YEAR, MAX_BS_YEAR + 1)
        for month, length in enumerate(BS_MONTH_DAYS[year], start=1)
        for day in range(1, length + 1)
    ]


ALL_DATES = _all_bs_dates()


def test_the_range_is_the_size_we_think_it_is() -> None:
    """Sanity-check the exhaustive fixture before relying on it."""
    assert len(ALL_DATES) == (MAX_AD_DATE - MIN_AD_DATE).days + 1
    assert len(ALL_DATES) == 40178  # 1975-2084 BS (39813 + 365 for 2084)


def test_bs_to_ad_is_a_bijection_over_the_whole_range() -> None:
    """Every BS date maps to a distinct, consecutive AD date, and back.

    Walking the calendar in order and asserting each AD date is exactly one day
    after the previous proves three things at once: the mapping round-trips, it
    is strictly monotonic, and the table has no gaps or overlaps -- an off-by-one
    in any month length would break the chain.
    """
    expected_ad = MIN_AD_DATE
    for year, month, day in ALL_DATES:
        ad = bs_to_ad(year, month, day)
        assert ad == expected_ad, f"BS {year}-{month:02d}-{day:02d} drifted"
        assert ad_to_bs(ad) == (year, month, day)
        expected_ad += datetime.timedelta(days=1)
    assert expected_ad - datetime.timedelta(days=1) == MAX_AD_DATE


def test_ad_to_bs_round_trips_for_every_ad_date() -> None:
    """``bs_to_ad(ad_to_bs(d)) == d`` for every AD date in range."""
    ad = MIN_AD_DATE
    while ad <= MAX_AD_DATE:
        assert bs_to_ad(*ad_to_bs(ad)) == ad
        ad += datetime.timedelta(days=1)


def test_weekday_advances_by_exactly_one_each_day() -> None:
    """Consecutive BS days advance the AD weekday by exactly one.

    Weekday continuity is independent of the month lengths being *right*, but
    it catches any place where the day-offset arithmetic skips or repeats a
    day -- the failure mode that a naive month-boundary loop produces.
    """
    previous = bs_to_ad(*ALL_DATES[0]).weekday()
    for year, month, day in ALL_DATES[1:]:
        current = bs_to_ad(year, month, day).weekday()
        assert current == (previous + 1) % 7, (
            f"weekday discontinuity at BS {year}-{month:02d}-{day:02d}"
        )
        previous = current


def test_ad_to_bs_accepts_datetime() -> None:
    """A datetime is accepted and its date component used."""
    assert ad_to_bs(datetime.datetime(2024, 4, 13, 23, 59)) == (2081, 1, 1)


@pytest.mark.parametrize(
    "value",
    [
        MIN_AD_DATE - datetime.timedelta(days=1),
        MAX_AD_DATE + datetime.timedelta(days=1),
        datetime.date(1800, 1, 1),
        datetime.date(2100, 1, 1),
    ],
)
def test_ad_to_bs_rejects_out_of_range(value: datetime.date) -> None:
    """AD dates outside the verified range raise, rather than extrapolate."""
    with pytest.raises(DateOutOfRange):
        ad_to_bs(value)


def test_ad_to_bs_rejects_non_dates() -> None:
    """A non-date input raises InvalidBSDate, not TypeError."""
    with pytest.raises(InvalidBSDate):
        ad_to_bs("2024-04-13")  # type: ignore[arg-type]


@pytest.mark.parametrize("year", [MIN_BS_YEAR - 1, MAX_BS_YEAR + 1, 1, 3000])
def test_bs_to_ad_rejects_years_outside_the_table(year: int) -> None:
    """BS years the table does not cover raise DateOutOfRange."""
    with pytest.raises(DateOutOfRange):
        bs_to_ad(year, 1, 1)


@pytest.mark.parametrize("month", [0, 13, -1, 100])
def test_bs_to_ad_rejects_bad_months(month: int) -> None:
    """Month numbers outside 1..12 raise InvalidBSDate."""
    with pytest.raises(InvalidBSDate):
        bs_to_ad(2081, month, 1)


@pytest.mark.parametrize("day", [0, -1, 33])
def test_bs_to_ad_rejects_bad_days(day: int) -> None:
    """Day numbers outside the month's length raise InvalidBSDate."""
    with pytest.raises(InvalidBSDate):
        bs_to_ad(2081, 1, day)


def test_day_32_is_valid_only_in_32_day_months() -> None:
    """Day 32 exists in some BS months and not others; the table decides."""
    # 2081 Jestha (month 2) has 32 days; 2081 Baishakh (month 1) has 31.
    assert days_in_month(2081, 2) == 32
    assert days_in_month(2081, 1) == 31
    check_bs_date(2081, 2, 32)
    with pytest.raises(InvalidBSDate, match="day 32 is out of range"):
        check_bs_date(2081, 1, 32)


def test_days_in_year_matches_the_table() -> None:
    """days_in_year agrees with summing the month lengths."""
    for year in range(MIN_BS_YEAR, MAX_BS_YEAR + 1):
        assert days_in_year(year) == sum(BS_MONTH_DAYS[year])


def test_booleans_are_not_accepted_as_components() -> None:
    """``True`` is an int in Python, but it is not a month."""
    with pytest.raises(InvalidBSDate):
        check_bs_date(2081, True, 1)  # type: ignore[arg-type]

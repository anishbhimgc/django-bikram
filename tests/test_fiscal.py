"""Nepali fiscal year and quarter arithmetic.

The rule under test is that the fiscal year runs 1 Shrawan to the last day of
Ashadh and is named for the year it starts in. Everything else -- quarters,
bounds, the ORM helpers -- is derived from that, so the tests here lean on
exhaustive day-by-day checks rather than on hand-picked examples.
"""

from __future__ import annotations

import datetime

import pytest

from django_bikram import BSDate
from django_bikram.calendar_data import VERIFIED_MAX_BS_YEAR, VERIFIED_MIN_BS_YEAR
from django_bikram.exceptions import DateOutOfRange, InvalidBSDate
from django_bikram.fiscal import (
    FISCAL_START_MONTH,
    fiscal_quarter,
    fiscal_quarter_bounds,
    fiscal_year,
    fiscal_year_bounds,
    fiscal_year_label,
)


def test_fiscal_year_starts_in_shrawan() -> None:
    """1 Shrawan opens a new fiscal year; the day before closes the old one."""
    assert FISCAL_START_MONTH == 4
    assert fiscal_year(BSDate(2081, 4, 1)) == 2081
    assert fiscal_year(BSDate(2081, 3, 31)) == 2080


def test_fiscal_year_spans_two_bs_years() -> None:
    """The months after Chaitra belong to the fiscal year that opened earlier."""
    assert fiscal_year(BSDate(2081, 12, 30)) == 2081
    assert fiscal_year(BSDate(2082, 1, 1)) == 2081
    assert fiscal_year(BSDate(2082, 3, 31)) == 2081
    assert fiscal_year(BSDate(2082, 4, 1)) == 2082


def test_fiscal_year_label_uses_two_digit_ending_year() -> None:
    """The label is written the way Nepali documents write it."""
    assert fiscal_year_label(BSDate(2081, 4, 1)) == "2081/82"
    assert fiscal_year_label(BSDate(2081, 3, 31)) == "2080/81"
    # A century rollover still pads to two digits rather than emitting "2099/0".
    assert fiscal_year_label(BSDate(2000, 4, 1)) == "2000/01"


@pytest.mark.parametrize(
    ("month", "quarter"),
    [(4, 1), (5, 1), (6, 1), (7, 2), (8, 2), (9, 2),
     (10, 3), (11, 3), (12, 3), (1, 4), (2, 4), (3, 4)],
)
def test_fiscal_quarter_per_month(month: int, quarter: int) -> None:
    """Quarters are the fiscal year cut into four three-month blocks."""
    assert fiscal_quarter(BSDate(2081, month, 1)) == quarter


def test_bsdate_exposes_the_same_answers() -> None:
    """The BSDate properties are the module functions, not a second rule."""
    d = BSDate(2082, 1, 1)
    assert (d.fiscal_year, d.fiscal_year_label, d.fiscal_quarter) == (
        2081,
        "2081/82",
        4,
    )


# --- bounds ------------------------------------------------------------


def test_fiscal_year_bounds_are_half_open() -> None:
    """The end bound is 1 Shrawan of the next year, not its last day."""
    start, end = fiscal_year_bounds(2081)
    assert start == BSDate(2081, 4, 1).to_ad()
    assert end == BSDate(2082, 4, 1).to_ad()


def test_consecutive_fiscal_years_tile_exactly() -> None:
    """Adjacent fiscal years meet with no gap and no overlap."""
    for year in range(VERIFIED_MIN_BS_YEAR, VERIFIED_MAX_BS_YEAR - 1):
        assert fiscal_year_bounds(year)[1] == fiscal_year_bounds(year + 1)[0]


def test_quarters_tile_their_fiscal_year() -> None:
    """The four quarters partition the fiscal year exactly."""
    year_start, year_end = fiscal_year_bounds(2081)
    quarters = [fiscal_quarter_bounds(2081, q) for q in (1, 2, 3, 4)]
    assert quarters[0][0] == year_start
    assert quarters[-1][1] == year_end
    for earlier, later in zip(quarters[:-1], quarters[1:], strict=True):
        assert earlier[1] == later[0]


def test_every_day_of_a_fiscal_year_agrees_with_its_bounds() -> None:
    """Exhaustive check: classification and bounds cannot disagree.

    Walks all 365-odd days of FY 2081/82 and asserts each one is classified into
    the fiscal year and quarter whose bounds actually contain it. This is what
    catches an off-by-one at a quarter edge, where month lengths differ.
    """
    start, end = fiscal_year_bounds(2081)
    day = start
    while day < end:
        bs = BSDate.from_ad(day)
        assert bs.fiscal_year == 2081
        low, high = fiscal_quarter_bounds(2081, bs.fiscal_quarter)
        assert low <= day < high
        day += datetime.timedelta(days=1)


def test_fiscal_quarter_bounds_rejects_a_bad_quarter() -> None:
    """A quarter outside 1..4 is a caller error, not a silent wrap."""
    for bad in (0, 5, -1):
        with pytest.raises(InvalidBSDate, match="quarter must be in 1..4"):
            fiscal_quarter_bounds(2081, bad)
    with pytest.raises(InvalidBSDate, match="must be an int"):
        fiscal_quarter_bounds(2081, True)


def test_fiscal_year_needs_both_bs_years_in_range() -> None:
    """The last verified BS year has no complete fiscal year after it.

    A fiscal year reaches into the following BS year, so it runs out one year
    before the calendar table does. Failing loudly beats returning a bound
    derived from data that is not there.
    """
    with pytest.raises(DateOutOfRange):
        fiscal_year_bounds(VERIFIED_MAX_BS_YEAR)
    # The year before is fine -- it ends exactly at the table's edge.
    assert fiscal_year_bounds(VERIFIED_MAX_BS_YEAR - 1)[1] == BSDate(
        VERIFIED_MAX_BS_YEAR, FISCAL_START_MONTH, 1
    ).to_ad()

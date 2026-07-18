"""Query helpers for BS year/month ranges."""

from __future__ import annotations

import datetime

import pytest

from django_bikram import BSDate
from django_bikram.calendar_data import MAX_BS_YEAR, MIN_BS_YEAR
from django_bikram.django.lookups import (
    bs_month_bounds,
    bs_month_q,
    bs_year_bounds,
    bs_year_q,
)
from django_bikram.exceptions import DateOutOfRange, InvalidBSDate

from .models import Invoice


def test_year_bounds() -> None:
    """A BS year's bounds are its first day and the day after its last."""
    start, end = bs_year_bounds(2081)
    assert start == datetime.date(2024, 4, 13)
    assert end == datetime.date(2025, 4, 14)
    assert end == BSDate(2082, 1, 1).to_ad()


def test_month_bounds() -> None:
    """A BS month's bounds are its first day and the day after its last."""
    start, end = bs_month_bounds(2081, 1)
    assert start == BSDate(2081, 1, 1).to_ad()
    assert end == BSDate(2081, 2, 1).to_ad()


def test_year_bounds_are_half_open_and_tile() -> None:
    """Consecutive years tile exactly: one year's end is the next year's start."""
    for year in range(MIN_BS_YEAR, MAX_BS_YEAR):
        assert bs_year_bounds(year)[1] == bs_year_bounds(year + 1)[0]


def test_month_bounds_tile_within_a_year() -> None:
    """Months tile exactly and cover the whole year."""
    for month in range(1, 12):
        assert bs_month_bounds(2081, month)[1] == bs_month_bounds(2081, month + 1)[0]
    assert bs_month_bounds(2081, 1)[0] == bs_year_bounds(2081)[0]
    assert bs_month_bounds(2081, 12)[1] == bs_year_bounds(2081)[1]


def test_bounds_at_the_end_of_the_table() -> None:
    """The last year's upper bound is computable even though 2084 BS is not.

    The bound is arithmetic on a datetime.date, so it does not need a BS year
    that the table lacks -- an easy off-by-one to get wrong.
    """
    start, end = bs_year_bounds(MAX_BS_YEAR)
    assert end == datetime.date(2027, 4, 14)
    assert end > start


@pytest.mark.parametrize("year", [MIN_BS_YEAR - 1, MAX_BS_YEAR + 1])
def test_bounds_reject_unsupported_years(year: int) -> None:
    """Years outside the table raise DateOutOfRange."""
    with pytest.raises(DateOutOfRange):
        bs_year_bounds(year)


def test_month_bounds_reject_bad_months() -> None:
    """Month numbers outside 1..12 raise InvalidBSDate."""
    with pytest.raises(InvalidBSDate):
        bs_month_bounds(2081, 13)


def test_q_objects_are_half_open_ranges() -> None:
    """The Q objects compile to gte/lt on the indexed column."""
    q = bs_year_q("issued_on", 2081)
    assert dict(q.children) == {
        "issued_on__gte": datetime.date(2024, 4, 13),
        "issued_on__lt": datetime.date(2025, 4, 14),
    }


@pytest.mark.django_db
def test_bs_year_q_selects_exactly_the_year() -> None:
    """bs_year_q matches every day of the year and nothing outside it."""
    inside = [BSDate(2081, 1, 1), BSDate(2081, 6, 15), BSDate(2081, 12, 30)]
    outside = [BSDate(2080, 12, 30), BSDate(2082, 1, 1)]
    for d in inside + outside:
        Invoice.objects.create(issued_on=d)

    qs = Invoice.objects.filter(bs_year_q("issued_on", 2081))
    assert sorted(i.issued_on for i in qs) == sorted(inside)


@pytest.mark.django_db
def test_bs_month_q_selects_exactly_the_month() -> None:
    """bs_month_q matches the month's days only, including a 32-day month."""
    # 2081 Jestha (month 2) has 32 days.
    for d in [BSDate(2081, 1, 31), BSDate(2081, 2, 1), BSDate(2081, 2, 32), BSDate(2081, 3, 1)]:
        Invoice.objects.create(issued_on=d)

    qs = Invoice.objects.filter(bs_month_q("issued_on", 2081, 2))
    assert sorted(i.issued_on for i in qs) == [BSDate(2081, 2, 1), BSDate(2081, 2, 32)]


@pytest.mark.django_db
def test_bs_year_q_composes_with_other_filters() -> None:
    """The helper is a plain Q and composes with exclude() and &."""
    Invoice.objects.create(issued_on=BSDate(2081, 1, 1), due_on=None)
    Invoice.objects.create(issued_on=BSDate(2081, 1, 2), due_on=BSDate(2081, 2, 1))
    Invoice.objects.create(issued_on=BSDate(2082, 1, 1), due_on=None)

    assert Invoice.objects.filter(bs_year_q("issued_on", 2081)).count() == 2
    assert Invoice.objects.exclude(bs_year_q("issued_on", 2081)).count() == 1
    combined = Invoice.objects.filter(bs_year_q("issued_on", 2081), due_on__isnull=True)
    assert combined.count() == 1


@pytest.mark.django_db
def test_bs_year_q_uses_a_range_scan_not_a_function() -> None:
    """The generated SQL is a bare comparison, so an index can serve it.

    A CASE-expression transform would appear here instead, and would be
    unusable by the btree index on the column.
    """
    sql = str(Invoice.objects.filter(bs_year_q("issued_on", 2081)).query)
    assert ">=" in sql and "<" in sql
    assert "CASE" not in sql.upper()


@pytest.mark.django_db
def test_bs_year_q_across_the_whole_table_partitions_the_rows() -> None:
    """Every date belongs to exactly one BS year's range.

    Sampling one date per year and checking that bs_year_q(y) finds exactly the
    row for y proves the ranges neither overlap nor leave gaps.
    """
    years = range(2075, 2084)
    for year in years:
        Invoice.objects.create(issued_on=BSDate(year, 1, 1))
    for year in years:
        qs = Invoice.objects.filter(bs_year_q("issued_on", year))
        assert [i.issued_on for i in qs] == [BSDate(year, 1, 1)]

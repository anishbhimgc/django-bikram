"""Index-friendly helpers for querying by Bikram Sambat year and month.

Why there is no ``__bs_year`` lookup
------------------------------------

The obvious feature request is ``Invoice.objects.filter(issued_on__bs_year=2081)``.
It is not implemented here, on purpose.

The column holds a Gregorian ``date``. To evaluate a BS year in SQL the
database would need the BS calendar table, which it does not have. There are
three ways to give it one, and none is worth shipping:

1. **Inline the table into the query.** A ``CASE WHEN issued_on BETWEEN … THEN
   2081 …`` expression with one branch per BS year. Correct, but the expression
   is opaque to the planner: it cannot use the btree index on ``issued_on``, so
   every query degrades to a sequential scan plus 109 comparisons per row. It
   would look convenient and quietly make tables slow -- the exact trade this
   package exists to avoid.
2. **Add a stored generated column** (plus an index, plus a migration, plus a
   backfill, plus a rebuild every time the calendar table is extended). That is
   a schema decision belonging to the application, not something a field type
   should impose.
3. **Rewrite equality into a range**, the way Django's own ``YearExact`` lookup
   does. This works for ``__bs_year=2081`` but not for ``__bs_year__gt=2081``
   or for ``__bs_year`` in ``values()``, ``annotate()``, ``order_by()`` or
   aggregation -- so the transform would be correct in some positions and
   wrong or slow in others. A lookup that is only sometimes safe is worse than
   no lookup.

The honest alternative is a half-open range on the indexed column, which is
what a BS year *is*: a contiguous span of AD dates. The helpers below build
those ranges, so the query stays a plain indexed range scan::

    from django_bikram.django.lookups import bs_year_q, bs_month_q

    Invoice.objects.filter(bs_year_q("issued_on", 2081))
    Invoice.objects.filter(bs_month_q("issued_on", 2081, 1))

Both compile to ``issued_on >= %s AND issued_on < %s`` -- one index range scan,
no per-row work, and it composes with ``Q`` objects, ``exclude()``, ``select
_related`` and everything else as normal.

Grouping by BS year in the database (the ``TruncYear`` equivalent) has the same
problem and the same answer: aggregate per range, or annotate in Python.
"""

from __future__ import annotations

import datetime

from django.db.models import Q

from ..convert import bs_to_ad, days_in_month, days_in_year
from ..fiscal import fiscal_quarter_bounds, fiscal_year_bounds

__all__ = [
    "bs_year_bounds",
    "bs_month_bounds",
    "bs_year_q",
    "bs_month_q",
    "bs_fiscal_year_q",
    "bs_fiscal_quarter_q",
]


def bs_year_bounds(year: int) -> tuple[datetime.date, datetime.date]:
    """Return the half-open Gregorian range covering a Bikram Sambat year.

    Args:
        year: The Bikram Sambat year.

    Returns:
        A ``(start, end)`` pair of :class:`datetime.date`, where ``start`` is
        1 Baishakh of ``year`` and ``end`` is the day **after** its last day.
        The range is half-open -- ``start <= d < end`` -- so adjacent years
        tile without overlapping and without leap-day special cases.

    Raises:
        DateOutOfRange: If the year, or the day after it, is outside the
            verified calendar range.

    Example:
        >>> bs_year_bounds(2081)
        (datetime.date(2024, 4, 13), datetime.date(2025, 4, 14))
    """
    start = bs_to_ad(year, 1, 1)
    end = start + datetime.timedelta(days=days_in_year(year))
    return start, end


def bs_month_bounds(year: int, month: int) -> tuple[datetime.date, datetime.date]:
    """Return the half-open Gregorian range covering a Bikram Sambat month.

    Args:
        year: The Bikram Sambat year.
        month: The month number, 1 through 12.

    Returns:
        A ``(start, end)`` pair of :class:`datetime.date`, half-open as in
        :func:`bs_year_bounds`.

    Raises:
        DateOutOfRange: If the month is outside the verified calendar range.
        InvalidBSDate: If ``month`` is not in 1..12.

    Example:
        >>> bs_month_bounds(2081, 1)
        (datetime.date(2024, 4, 13), datetime.date(2024, 5, 14))
    """
    start = bs_to_ad(year, month, 1)
    end = start + datetime.timedelta(days=days_in_month(year, month))
    return start, end


def bs_year_q(field: str, year: int) -> Q:
    """Build a ``Q`` matching rows whose date falls in a Bikram Sambat year.

    The result is a half-open range on the indexed column, so it plans as a
    single index range scan.

    Args:
        field: The field name (or lookup path, e.g. ``"invoice__issued_on"``).
        year: The Bikram Sambat year to match.

    Returns:
        A :class:`~django.db.models.Q` object.

    Raises:
        DateOutOfRange: If the year is outside the verified calendar range.

    Example:
        >>> q = bs_year_q("issued_on", 2081)
        >>> dict(q.children) == {
        ...     "issued_on__gte": datetime.date(2024, 4, 13),
        ...     "issued_on__lt": datetime.date(2025, 4, 14),
        ... }
        True
    """
    start, end = bs_year_bounds(year)
    return Q(**{f"{field}__gte": start, f"{field}__lt": end})


def bs_month_q(field: str, year: int, month: int) -> Q:
    """Build a ``Q`` matching rows whose date falls in a Bikram Sambat month.

    Args:
        field: The field name (or lookup path).
        year: The Bikram Sambat year.
        month: The month number, 1 through 12.

    Returns:
        A :class:`~django.db.models.Q` object.

    Raises:
        DateOutOfRange: If the month is outside the verified calendar range.
        InvalidBSDate: If ``month`` is not in 1..12.

    Example:
        >>> Invoice.objects.filter(bs_month_q("issued_on", 2081, 1))  # doctest: +SKIP
    """
    start, end = bs_month_bounds(year, month)
    return Q(**{f"{field}__gte": start, f"{field}__lt": end})


def bs_fiscal_year_q(field: str, start_year: int) -> Q:
    """Build a ``Q`` matching rows inside a Nepali fiscal year.

    Nepal's fiscal year runs 1 Shrawan to the last of Ashadh, so it spans two BS
    years -- which is exactly why it needs a helper: no combination of the
    built-in lookups expresses it, and it is a single contiguous range of AD
    dates. See :mod:`django_bikram.fiscal`.

    Args:
        field: The field name (or lookup path).
        start_year: The BS year the fiscal year starts in -- 2081 for FY
            2081/82.

    Returns:
        A :class:`~django.db.models.Q` object compiling to one index range scan.

    Raises:
        DateOutOfRange: If either end of the fiscal year is outside the verified
            calendar range.

    Example:
        >>> q = bs_fiscal_year_q("issued_on", 2081)
        >>> dict(q.children) == {
        ...     "issued_on__gte": datetime.date(2024, 7, 16),
        ...     "issued_on__lt": datetime.date(2025, 7, 17),
        ... }
        True
    """
    start, end = fiscal_year_bounds(start_year)
    return Q(**{f"{field}__gte": start, f"{field}__lt": end})


def bs_fiscal_quarter_q(field: str, start_year: int, quarter: int) -> Q:
    """Build a ``Q`` matching rows inside one quarter of a Nepali fiscal year.

    Args:
        field: The field name (or lookup path).
        start_year: The BS year the fiscal year starts in.
        quarter: The quarter number, 1 through 4.

    Returns:
        A :class:`~django.db.models.Q` object compiling to one index range scan.

    Raises:
        InvalidBSDate: If ``quarter`` is not in 1..4.
        DateOutOfRange: If the quarter is outside the verified calendar range.

    Example:
        >>> q = bs_fiscal_quarter_q("issued_on", 2081, 1)
        >>> dict(q.children) == {
        ...     "issued_on__gte": datetime.date(2024, 7, 16),
        ...     "issued_on__lt": datetime.date(2024, 10, 17),
        ... }
        True
    """
    start, end = fiscal_quarter_bounds(start_year, quarter)
    return Q(**{f"{field}__gte": start, f"{field}__lt": end})

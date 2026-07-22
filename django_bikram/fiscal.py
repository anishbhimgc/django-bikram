"""Nepali fiscal year and quarter arithmetic.

Nepal's fiscal year (आर्थिक वर्ष) runs **1 Shrawan through the last day of
Ashadh** -- month 4 of one Bikram Sambat year to month 3 of the next. It is
named for the year it *starts* in, written with the ending year's last two
digits: the year beginning 1 Shrawan 2081 is **FY 2081/82**.

Everything here derives from that one rule, so there is no second calendar table
to keep in step with :mod:`django_bikram.calendar_data`.

Why this is not a "just add 3 months" helper
--------------------------------------------
The fiscal year is a contiguous span of days, and the only correct way to select
it from a database is a half-open range over the indexed column -- exactly as for
a BS year. :func:`fiscal_year_bounds` returns those Gregorian bounds;
:func:`django_bikram.django.lookups.bs_fiscal_year_q` wraps them in a ``Q``.
Deriving a fiscal year *per row* in SQL would need the BS calendar table inlined
into the query, with the same sequential-scan cost documented in
:mod:`django_bikram.django.lookups`.

Quarters follow the Nepali government's convention, which is simply the fiscal
year cut into four three-month blocks:

======  ==========================================  ==============
Q1      Shrawan, Bhadra, Ashwin (months 4-6)        first quarter
Q2      Kartik, Mangsir, Poush (months 7-9)         second quarter
Q3      Magh, Falgun, Chaitra (months 10-12)        third quarter
Q4      Baishakh, Jestha, Ashadh (months 1-3)       fourth quarter
======  ==========================================  ==============

Note that Q4 is the *earlier* part of the BS year: Baishakh 2082 belongs to
FY 2081/82, not FY 2082/83.
"""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

from .calendar_data import MONTHS_IN_YEAR
from .convert import bs_to_ad
from .exceptions import InvalidBSDate

if TYPE_CHECKING:
    from .date import BSDate

__all__ = [
    "FISCAL_START_MONTH",
    "fiscal_year",
    "fiscal_year_label",
    "fiscal_quarter",
    "fiscal_year_bounds",
    "fiscal_quarter_bounds",
]

#: The BS month a fiscal year starts in: 4, Shrawan.
FISCAL_START_MONTH = 4

#: Months per fiscal quarter.
_MONTHS_PER_QUARTER = 3


def fiscal_year(value: BSDate) -> int:
    """Return the Bikram Sambat year the date's fiscal year **starts** in.

    A fiscal year is named for its starting year, so every date from
    1 Shrawan 2081 to the last day of Ashadh 2082 returns ``2081``.

    Args:
        value: The date to classify.

    Returns:
        The starting BS year of the fiscal year containing ``value``.

    Example:
        >>> from django_bikram import BSDate
        >>> fiscal_year(BSDate(2081, 4, 1))    # 1 Shrawan: the year opens
        2081
        >>> fiscal_year(BSDate(2081, 3, 31))   # Ashadh: still the year before
        2080
        >>> fiscal_year(BSDate(2082, 3, 15))   # Ashadh again, one year on
        2081
    """
    return value.year if value.month >= FISCAL_START_MONTH else value.year - 1


def fiscal_year_label(value: BSDate) -> str:
    """Return the conventional ``2081/82`` label for the date's fiscal year.

    Args:
        value: The date to classify.

    Returns:
        The fiscal year written the way Nepali documents write it: the starting
        year in full, then the ending year's last two digits.

    Example:
        >>> from django_bikram import BSDate
        >>> fiscal_year_label(BSDate(2081, 4, 1))
        '2081/82'
        >>> fiscal_year_label(BSDate(2081, 3, 31))
        '2080/81'
    """
    start = fiscal_year(value)
    return f"{start}/{(start + 1) % 100:02d}"


def fiscal_quarter(value: BSDate) -> int:
    """Return which quarter of its fiscal year the date falls in, 1 through 4.

    Q1 opens the fiscal year in Shrawan; Q4 closes it in Ashadh. Because the
    fiscal year straddles two BS years, Q4 months (Baishakh to Ashadh) carry a
    *higher* BS year than the Q1 months of the same fiscal year.

    Args:
        value: The date to classify.

    Returns:
        The quarter number, 1 through 4.

    Example:
        >>> from django_bikram import BSDate
        >>> fiscal_quarter(BSDate(2081, 4, 1))    # Shrawan
        1
        >>> fiscal_quarter(BSDate(2081, 10, 1))   # Magh
        3
        >>> fiscal_quarter(BSDate(2082, 1, 1))    # Baishakh, closing FY 2081/82
        4
    """
    months_in = (value.month - FISCAL_START_MONTH) % MONTHS_IN_YEAR
    return months_in // _MONTHS_PER_QUARTER + 1


def fiscal_year_bounds(start_year: int) -> tuple[datetime.date, datetime.date]:
    """Return the half-open Gregorian range covering a Nepali fiscal year.

    The range is half-open -- ``start <= d < end`` -- so consecutive fiscal
    years tile exactly, with no overlap and no month-length special cases. This
    is the form that keeps a database index in play; see
    :mod:`django_bikram.django.lookups`.

    Args:
        start_year: The BS year the fiscal year starts in -- 2081 for FY
            2081/82.

    Returns:
        A ``(start, end)`` pair of :class:`datetime.date`, where ``start`` is
        1 Shrawan of ``start_year`` and ``end`` is the day **after** the last of
        Ashadh in ``start_year + 1``.

    Raises:
        DateOutOfRange: If either end of the fiscal year is outside the verified
            calendar range. A fiscal year spans two BS years, so it needs both.

    Example:
        >>> fiscal_year_bounds(2081)
        (datetime.date(2024, 7, 16), datetime.date(2025, 7, 17))
    """
    start = bs_to_ad(start_year, FISCAL_START_MONTH, 1)
    # The day after the fiscal year ends is 1 Shrawan of the following year, so
    # the exclusive bound needs no month-length lookup of its own.
    end = bs_to_ad(start_year + 1, FISCAL_START_MONTH, 1)
    return start, end


def fiscal_quarter_bounds(
    start_year: int, quarter: int
) -> tuple[datetime.date, datetime.date]:
    """Return the half-open Gregorian range covering one fiscal quarter.

    Args:
        start_year: The BS year the fiscal year starts in -- 2081 for FY
            2081/82.
        quarter: The quarter number, 1 through 4.

    Returns:
        A ``(start, end)`` pair of :class:`datetime.date`, half-open as in
        :func:`fiscal_year_bounds`.

    Raises:
        InvalidBSDate: If ``quarter`` is not in 1..4.
        DateOutOfRange: If the quarter is outside the verified calendar range.

    Example:
        >>> fiscal_quarter_bounds(2081, 1)
        (datetime.date(2024, 7, 16), datetime.date(2024, 10, 17))
        >>> fiscal_quarter_bounds(2081, 4)   # Baishakh-Ashadh, in BS 2082
        (datetime.date(2025, 4, 14), datetime.date(2025, 7, 17))
    """
    if not isinstance(quarter, int) or isinstance(quarter, bool):
        raise InvalidBSDate(f"quarter must be an int, got {type(quarter).__name__!r}")
    if not 1 <= quarter <= 4:
        raise InvalidBSDate(f"quarter must be in 1..4, got {quarter}")

    def _month_start(offset: int) -> datetime.date:
        """Return 1st of the BS month ``offset`` months into the fiscal year."""
        absolute = FISCAL_START_MONTH - 1 + offset
        year = start_year + absolute // MONTHS_IN_YEAR
        return bs_to_ad(year, absolute % MONTHS_IN_YEAR + 1, 1)

    first_month = (quarter - 1) * _MONTHS_PER_QUARTER
    return _month_start(first_month), _month_start(first_month + _MONTHS_PER_QUARTER)

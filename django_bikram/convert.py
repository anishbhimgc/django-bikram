"""Bidirectional conversion between Bikram Sambat and Gregorian dates.

Both directions are day-offset arithmetic from the single anchor defined in
:mod:`django_bikram.calendar_data`: a BS date is turned into "days since the anchor",
which the Gregorian side already knows how to handle via
:class:`datetime.timedelta`.

Cost
----
A cumulative day count per year is built once at import (109 additions) and
cached in :data:`_YEAR_START_OFFSET`. That makes conversion cheap and, more
importantly, independent of how far the date is from the anchor:

* :func:`bs_to_ad` -- ``O(months_in_year)``, i.e. at most 12 additions.
* :func:`ad_to_bs` -- ``O(log years)`` to locate the year by binary search,
  then at most 12 additions to locate the month.

Neither walks day by day, so a date in 2083 BS costs the same as one in 1975.
"""

from __future__ import annotations

import datetime
import warnings
from bisect import bisect_right

from .calendar_data import (
    ANCHOR_AD,
    BS_MONTH_DAYS,
    MAX_AD_DATE,
    MAX_BS_YEAR,
    MIN_AD_DATE,
    MIN_BS_YEAR,
    MONTHS_IN_YEAR,
    VERIFIED_MAX_BS_YEAR,
    is_verified_year,
)
from .exceptions import DateOutOfRange, InvalidBSDate, ProvisionalDateWarning

__all__ = ["bs_to_ad", "ad_to_bs", "days_in_month", "days_in_year", "check_bs_date"]


def _warn_if_provisional(year: int, *, stacklevel: int) -> None:
    """Emit :class:`ProvisionalDateWarning` for a non-verified year.

    Verified years pass silently. The warning fires from ``stacklevel`` frames
    up so it points at the caller's code, and -- under the default warning
    filter -- shows once per call site rather than on every conversion.

    Args:
        year: The BS year being used.
        stacklevel: Frames to skip so the warning is attributed to user code.
    """
    if not is_verified_year(year):
        warnings.warn(
            f"BS year {year} is provisional: its month lengths are computed, not "
            f"verified against published sources, and may differ from the "
            f"official calendar by a day (verified through {VERIFIED_MAX_BS_YEAR} "
            f"BS). Use BSDate.is_verified to check.",
            ProvisionalDateWarning,
            stacklevel=stacklevel + 1,
        )


def _build_year_offsets() -> tuple[list[int], list[int]]:
    """Precompute the anchor-relative day offset at which each BS year starts.

    Returns:
        A ``(years, offsets)`` pair of parallel lists, both ascending, where
        ``offsets[i]`` is the number of days from :data:`ANCHOR_AD` to
        1 Baishakh of ``years[i]``. ``offsets`` is strictly increasing, which
        is what makes the binary search in :func:`ad_to_bs` valid.
    """
    years: list[int] = []
    offsets: list[int] = []
    running = 0
    for year in range(MIN_BS_YEAR, MAX_BS_YEAR + 1):
        years.append(year)
        offsets.append(running)
        running += sum(BS_MONTH_DAYS[year])
    return years, offsets


_YEARS, _YEAR_START_OFFSET = _build_year_offsets()

#: Total number of days covered by the working table.
_TOTAL_DAYS = _YEAR_START_OFFSET[-1] + sum(BS_MONTH_DAYS[MAX_BS_YEAR])


def _reload_from_calendar_data() -> None:
    """Rebuild cached offsets after the working table gained provisional years.

    Called by :func:`django_bikram.calendar_data.install_provisional`. The
    ``BS_MONTH_DAYS`` mapping is mutated in place upstream, so this module's
    reference already sees the new years; only the derived caches and the
    ``MAX_*`` echoes used in error messages need refreshing.
    """
    global _YEARS, _YEAR_START_OFFSET, _TOTAL_DAYS, MAX_BS_YEAR, MAX_AD_DATE
    from . import calendar_data as cd

    MAX_BS_YEAR = cd.MAX_BS_YEAR
    MAX_AD_DATE = cd.MAX_AD_DATE
    _YEARS, _YEAR_START_OFFSET = _build_year_offsets()
    _TOTAL_DAYS = _YEAR_START_OFFSET[-1] + sum(cd.BS_MONTH_DAYS[cd.MAX_BS_YEAR])


def days_in_month(year: int, month: int) -> int:
    """Return the length in days of a Bikram Sambat month.

    Args:
        year: Bikram Sambat year, within the verified range.
        month: Month number, 1 (Baishakh) through 12 (Chaitra).

    Returns:
        The number of days in that month, between 29 and 32.

    Raises:
        DateOutOfRange: If ``year`` is outside the verified calendar range.
        InvalidBSDate: If ``month`` is not in 1..12.

    Example:
        >>> days_in_month(2081, 1)
        31
    """
    if not isinstance(year, int) or isinstance(year, bool):
        raise InvalidBSDate(f"year must be an int, got {type(year).__name__!r}")
    if year not in BS_MONTH_DAYS:
        raise DateOutOfRange(
            f"BS year {year} is outside the verified range "
            f"{MIN_BS_YEAR}..{MAX_BS_YEAR}. See django_bikram.calendar_data for why "
            f"this package refuses to extrapolate."
        )
    if not isinstance(month, int) or isinstance(month, bool):
        raise InvalidBSDate(f"month must be an int, got {type(month).__name__!r}")
    if not 1 <= month <= MONTHS_IN_YEAR:
        raise InvalidBSDate(f"month must be in 1..{MONTHS_IN_YEAR}, got {month}")
    return BS_MONTH_DAYS[year][month - 1]


def days_in_year(year: int) -> int:
    """Return the total number of days in a Bikram Sambat year.

    Args:
        year: Bikram Sambat year, within the verified range.

    Returns:
        365 or 366.

    Raises:
        DateOutOfRange: If ``year`` is outside the verified calendar range.

    Example:
        >>> days_in_year(2081)
        366
    """
    if year not in BS_MONTH_DAYS:
        raise DateOutOfRange(
            f"BS year {year} is outside the verified range "
            f"{MIN_BS_YEAR}..{MAX_BS_YEAR}."
        )
    return sum(BS_MONTH_DAYS[year])


def check_bs_date(year: int, month: int, day: int) -> None:
    """Validate a Bikram Sambat year/month/day triple.

    Args:
        year: Bikram Sambat year.
        month: Month number, 1 through 12.
        day: Day of month, 1 through the length of that specific month.

    Raises:
        DateOutOfRange: If ``year`` is outside the verified calendar range.
        InvalidBSDate: If any component is not an ``int``, or if the day does
            not exist in the given month -- e.g. day 32 of a 31-day month.

    Example:
        >>> check_bs_date(2081, 1, 31)
        >>> check_bs_date(2081, 1, 32)  # doctest: +ELLIPSIS
        Traceback (most recent call last):
            ...
        django_bikram.exceptions.InvalidBSDate: day 32 is out of range for 2081-01, ...
    """
    length = days_in_month(year, month)  # validates year and month
    if not isinstance(day, int) or isinstance(day, bool):
        raise InvalidBSDate(f"day must be an int, got {type(day).__name__!r}")
    if not 1 <= day <= length:
        raise InvalidBSDate(
            f"day {day} is out of range for {year:04d}-{month:02d}, which has "
            f"{length} days"
        )
    # Only warn once the date is known to be well-formed, so a bad provisional
    # date reports the real error rather than a warning about the year.
    _warn_if_provisional(year, stacklevel=2)


def bs_to_ad(year: int, month: int, day: int) -> datetime.date:
    """Convert a Bikram Sambat date to its Gregorian equivalent.

    Args:
        year: Bikram Sambat year, within the verified range.
        month: Month number, 1 (Baishakh) through 12 (Chaitra).
        day: Day of month.

    Returns:
        The corresponding :class:`datetime.date` in the Gregorian calendar.

    Raises:
        DateOutOfRange: If the year is outside the verified calendar range.
        InvalidBSDate: If the date does not exist.

    Example:
        >>> bs_to_ad(2081, 1, 1)
        datetime.date(2024, 4, 13)
    """
    check_bs_date(year, month, day)
    offset = _YEAR_START_OFFSET[year - MIN_BS_YEAR]
    offset += sum(BS_MONTH_DAYS[year][: month - 1])
    offset += day - 1
    return ANCHOR_AD + datetime.timedelta(days=offset)


def ad_to_bs(value: datetime.date) -> tuple[int, int, int]:
    """Convert a Gregorian date to its Bikram Sambat equivalent.

    Args:
        value: A :class:`datetime.date`. A :class:`datetime.datetime` is
            accepted and its date component used.

    Returns:
        A ``(year, month, day)`` tuple of Bikram Sambat components.

    Raises:
        DateOutOfRange: If the date falls outside the verified calendar range.
        InvalidBSDate: If ``value`` is not a date.

    Example:
        >>> ad_to_bs(datetime.date(2024, 4, 13))
        (2081, 1, 1)
    """
    if isinstance(value, datetime.datetime):
        value = value.date()
    if not isinstance(value, datetime.date):
        raise InvalidBSDate(
            f"expected a datetime.date, got {type(value).__name__!r}"
        )
    delta = (value - ANCHOR_AD).days
    if not 0 <= delta < _TOTAL_DAYS:
        raise DateOutOfRange(
            f"{value.isoformat()} is outside the verified range "
            f"{MIN_AD_DATE.isoformat()}..{MAX_AD_DATE.isoformat()} "
            f"(BS {MIN_BS_YEAR}..{MAX_BS_YEAR})."
        )

    # bisect_right gives the index of the first year starting after `delta`;
    # the year containing `delta` is therefore the one before it. Offsets are
    # strictly increasing, so this is exact.
    index = bisect_right(_YEAR_START_OFFSET, delta) - 1
    year = _YEARS[index]
    remainder = delta - _YEAR_START_OFFSET[index]
    _warn_if_provisional(year, stacklevel=2)

    for month_index, length in enumerate(BS_MONTH_DAYS[year]):
        if remainder < length:
            return year, month_index + 1, remainder + 1
        remainder -= length

    # Unreachable: `remainder` is less than the year's total length by
    # construction, so the loop always returns.
    raise AssertionError(  # pragma: no cover
        f"calendar table inconsistent for BS year {year}"
    )

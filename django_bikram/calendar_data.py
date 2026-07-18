"""Bikram Sambat calendar data: year -> month lengths, plus the AD anchor.

This module is the entire correctness surface of the package. Every conversion
is arithmetic over :data:`BS_MONTH_DAYS` from a single anchor, so an error here
is an error everywhere.

Provenance
----------
The month-length table was **not** authored by hand. It was extracted and
cross-verified from two independently maintained, MIT-licensed sources:

1. ``nepali-datetime`` 1.0.8.5 -- ``nepali_datetime/data/calendar_bs.csv``
2. ``bikram-sambat`` 0.2.0 -- ``bikram_sambat/data/calendar_data.py``

Both ultimately derive from the Nepali Panchanga (the official almanac
published by the Nepal Panchanga Nirnayak Samiti). Month lengths are decided
astronomically -- by the moment the sun crosses into each zodiac sign -- so
they cannot be computed from a rule and must come from published tables.

Verified range: **1975-01-01 BS through 2084-12-30 BS**
(1918-04-13 AD through 2028-04-12 AD).

For 1975-2083 (109 years) the two sources above agree on all 1,308 month
lengths, every year totals 365 or 366 days, every month is 29-32 days, and the
derived anchors reproduce independently attested dates (see ``ANCHOR_AD``).

**2084** was added later (2026-07) from a different independent pair: scraped
from hamropatro.com and found identical to ``nepali-datetime`` for all twelve
months. Those two disagree with ``bikram-sambat`` on 2084, so Hamro Patro breaks
the tie; 2084 chains exactly onto 2083 (1 Baishakh 2084 = 2027-04-14). It is the
first year with a ``(30, 30, 30)`` tail -- corroborated by both sources, but
worth re-confirming against the official Panchanga once it publishes.

Why the range stops at 2084 BS
------------------------------
It stops where the evidence stops, not where the sources stop. 2084 itself was
confirmed against Hamro Patro (see above); from 2085 on there is no such check:

* ``nepali-datetime`` carries rows through 2100 BS, but from 2085 BS onward
  they are visibly synthetic: 14 of its remaining years end in the tail
  ``(30, 30, 30)``, and **2096 BS sums to 364 days** -- an impossible year.
* ``bikram-sambat`` carries rows from 1901 to 2199 BS, but outside 1975-2084
  it has no corroborating source here.
* The two tables diverge from 2085 BS onward and never re-converge.

Extrapolated data would be silently wrong rather than loudly absent, so by
default dates outside the verified range raise
:class:`~django_bikram.exceptions.DateOutOfRange`.

Two tiers: verified and provisional
-----------------------------------
The data is split so that "attested" and "computed" never blur together:

* :data:`VERIFIED_BS_MONTH_DAYS` -- the two-source table above, the default and
  the correctness core.
* :data:`PROVISIONAL_BS_MONTH_DAYS` -- **empty by default**. A place for
  *computed* years produced by :mod:`django_bikram.predict`, for projects that
  must keep working past the verified horizon and can accept that a predicted
  month length is right about seven times in eight (see that module's
  ``validate()``). Opt in by setting the :data:`PROVISIONAL_ENV_VAR` environment
  variable, or by calling :func:`install_provisional` at startup.

:data:`BS_MONTH_DAYS` is the merged working table the conversion code runs over.
:func:`is_verified_year` and :attr:`django_bikram.date.BSDate.is_verified` report
which tier a date came from, and using a provisional date raises
:class:`~django_bikram.exceptions.ProvisionalDateWarning`.

Extending the *verified* table
------------------------------
When the Panchanga Nirnayak Samiti publishes further years, append the rows to
:data:`VERIFIED_BS_MONTH_DAYS` and raise :data:`VERIFIED_MAX_BS_YEAR`.
Corroborate each new year against at least two independent sources and check
that it totals 365 or 366 days; ``tests/test_calendar_data.py`` enforces the
invariants. Moving a year from predicted to verified is the goal; the predictor
is a stopgap, never a substitute.
"""

from __future__ import annotations

import datetime
import os

__all__ = [
    "BS_MONTH_DAYS",
    "VERIFIED_BS_MONTH_DAYS",
    "PROVISIONAL_BS_MONTH_DAYS",
    "MIN_BS_YEAR",
    "MAX_BS_YEAR",
    "VERIFIED_MIN_BS_YEAR",
    "VERIFIED_MAX_BS_YEAR",
    "ANCHOR_BS_YEAR",
    "ANCHOR_AD",
    "MIN_AD_DATE",
    "MAX_AD_DATE",
    "VERIFIED_MAX_AD_DATE",
    "MONTHS_IN_YEAR",
    "is_verified_year",
    "install_provisional",
    "PROVISIONAL_ENV_VAR",
]

#: Environment variable that opts in to provisional (predicted) years at import.
#: Set it to the BS year through which to extend, e.g.
#: ``DJANGO_BIKRAM_PROVISIONAL_THROUGH_YEAR=2183``. Read once, at import.
PROVISIONAL_ENV_VAR = "DJANGO_BIKRAM_PROVISIONAL_THROUGH_YEAR"

#: Number of months in a Bikram Sambat year.
MONTHS_IN_YEAR = 12

#: First Bikram Sambat year *verified* against two independent sources.
VERIFIED_MIN_BS_YEAR = 1975

#: Last Bikram Sambat year *verified* against two independent sources. Beyond
#: this the calendar can only be *predicted*, not attested; such years live in
#: :data:`PROVISIONAL_BS_MONTH_DAYS` and are flagged on use.
VERIFIED_MAX_BS_YEAR = 2084

#: The BS year whose 1 Baishakh is pinned to :data:`ANCHOR_AD`.
ANCHOR_BS_YEAR = 1975

#: The Gregorian date of 1 Baishakh :data:`ANCHOR_BS_YEAR` BS.
#:
#: Independently corroborated downstream anchors (asserted in the test suite):
#:
#: * 1 Baishakh 2000 BS == 1943-04-14 AD
#: * 1 Baishakh 2081 BS == 2024-04-13 AD
#: * 1 Baishakh 2082 BS == 2025-04-14 AD
ANCHOR_AD = datetime.date(1918, 4, 13)

#: Verified month lengths: maps a BS year to its twelve month lengths, Baishakh
#: (index 0) to Chaitra. The trailing comment on each row is the year's total
#: length in days. This is the correctness core -- every row is attested by two
#: independent sources (see the module docstring).
VERIFIED_BS_MONTH_DAYS: dict[int, tuple[int, ...]] = {
    1975: (31, 31, 32, 32, 31, 30, 30, 29, 30, 29, 30, 30),  # 365
    1976: (31, 32, 31, 32, 31, 30, 30, 30, 29, 29, 30, 31),  # 366
    1977: (30, 32, 31, 32, 31, 30, 30, 30, 29, 30, 29, 31),  # 365
    1978: (31, 31, 32, 31, 31, 31, 30, 29, 30, 29, 30, 30),  # 365
    1979: (31, 31, 32, 32, 31, 30, 30, 29, 30, 29, 30, 30),  # 365
    1980: (31, 32, 31, 32, 31, 30, 30, 30, 29, 29, 30, 31),  # 366
    1981: (31, 31, 31, 32, 31, 31, 29, 30, 30, 29, 30, 30),  # 365
    1982: (31, 31, 32, 31, 31, 31, 30, 29, 30, 29, 30, 30),  # 365
    1983: (31, 31, 32, 32, 31, 30, 30, 29, 30, 29, 30, 30),  # 365
    1984: (31, 32, 31, 32, 31, 30, 30, 30, 29, 29, 30, 31),  # 366
    1985: (31, 31, 31, 32, 31, 31, 29, 30, 30, 29, 30, 30),  # 365
    1986: (31, 31, 32, 31, 31, 31, 30, 29, 30, 29, 30, 30),  # 365
    1987: (31, 32, 31, 32, 31, 30, 30, 29, 30, 29, 30, 30),  # 365
    1988: (31, 32, 31, 32, 31, 30, 30, 30, 29, 29, 30, 31),  # 366
    1989: (31, 31, 31, 32, 31, 31, 29, 30, 30, 29, 30, 30),  # 365
    1990: (31, 31, 32, 31, 31, 31, 30, 29, 30, 29, 30, 30),  # 365
    1991: (31, 32, 31, 32, 31, 30, 30, 30, 29, 29, 30, 30),  # 365
    1992: (31, 32, 31, 32, 31, 30, 30, 30, 29, 30, 29, 31),  # 366
    1993: (31, 31, 32, 31, 31, 31, 30, 29, 30, 29, 30, 30),  # 365
    1994: (31, 31, 32, 31, 31, 31, 30, 29, 30, 29, 30, 30),  # 365
    1995: (31, 32, 31, 32, 31, 30, 30, 30, 29, 29, 30, 30),  # 365
    1996: (31, 32, 31, 32, 31, 30, 30, 30, 29, 30, 29, 31),  # 366
    1997: (31, 31, 32, 31, 31, 31, 30, 29, 30, 29, 30, 30),  # 365
    1998: (31, 31, 32, 31, 31, 31, 30, 29, 30, 29, 30, 30),  # 365
    1999: (31, 32, 31, 32, 31, 30, 30, 30, 29, 29, 30, 31),  # 366
    2000: (30, 32, 31, 32, 31, 30, 30, 30, 29, 30, 29, 31),  # 365
    2001: (31, 31, 32, 31, 31, 31, 30, 29, 30, 29, 30, 30),  # 365
    2002: (31, 31, 32, 32, 31, 30, 30, 29, 30, 29, 30, 30),  # 365
    2003: (31, 32, 31, 32, 31, 30, 30, 30, 29, 29, 30, 31),  # 366
    2004: (30, 32, 31, 32, 31, 30, 30, 30, 29, 30, 29, 31),  # 365
    2005: (31, 31, 32, 31, 31, 31, 30, 29, 30, 29, 30, 30),  # 365
    2006: (31, 31, 32, 32, 31, 30, 30, 29, 30, 29, 30, 30),  # 365
    2007: (31, 32, 31, 32, 31, 30, 30, 30, 29, 29, 30, 31),  # 366
    2008: (31, 31, 31, 32, 31, 31, 29, 30, 30, 29, 29, 31),  # 365
    2009: (31, 31, 32, 31, 31, 31, 30, 29, 30, 29, 30, 30),  # 365
    2010: (31, 31, 32, 32, 31, 30, 30, 29, 30, 29, 30, 30),  # 365
    2011: (31, 32, 31, 32, 31, 30, 30, 30, 29, 29, 30, 31),  # 366
    2012: (31, 31, 31, 32, 31, 31, 29, 30, 30, 29, 30, 30),  # 365
    2013: (31, 31, 32, 31, 31, 31, 30, 29, 30, 29, 30, 30),  # 365
    2014: (31, 31, 32, 32, 31, 30, 30, 29, 30, 29, 30, 30),  # 365
    2015: (31, 32, 31, 32, 31, 30, 30, 30, 29, 29, 30, 31),  # 366
    2016: (31, 31, 31, 32, 31, 31, 29, 30, 30, 29, 30, 30),  # 365
    2017: (31, 31, 32, 31, 31, 31, 30, 29, 30, 29, 30, 30),  # 365
    2018: (31, 32, 31, 32, 31, 30, 30, 29, 30, 29, 30, 30),  # 365
    2019: (31, 32, 31, 32, 31, 30, 30, 30, 29, 30, 29, 31),  # 366
    2020: (31, 31, 31, 32, 31, 31, 30, 29, 30, 29, 30, 30),  # 365
    2021: (31, 31, 32, 31, 31, 31, 30, 29, 30, 29, 30, 30),  # 365
    2022: (31, 32, 31, 32, 31, 30, 30, 30, 29, 29, 30, 30),  # 365
    2023: (31, 32, 31, 32, 31, 30, 30, 30, 29, 30, 29, 31),  # 366
    2024: (31, 31, 31, 32, 31, 31, 30, 29, 30, 29, 30, 30),  # 365
    2025: (31, 31, 32, 31, 31, 31, 30, 29, 30, 29, 30, 30),  # 365
    2026: (31, 32, 31, 32, 31, 30, 30, 30, 29, 29, 30, 31),  # 366
    2027: (30, 32, 31, 32, 31, 30, 30, 30, 29, 30, 29, 31),  # 365
    2028: (31, 31, 32, 31, 31, 31, 30, 29, 30, 29, 30, 30),  # 365
    2029: (31, 31, 32, 31, 32, 30, 30, 29, 30, 29, 30, 30),  # 365
    2030: (31, 32, 31, 32, 31, 30, 30, 30, 29, 29, 30, 31),  # 366
    2031: (30, 32, 31, 32, 31, 30, 30, 30, 29, 30, 29, 31),  # 365
    2032: (31, 31, 32, 31, 31, 31, 30, 29, 30, 29, 30, 30),  # 365
    2033: (31, 31, 32, 32, 31, 30, 30, 29, 30, 29, 30, 30),  # 365
    2034: (31, 32, 31, 32, 31, 30, 30, 30, 29, 29, 30, 31),  # 366
    2035: (30, 32, 31, 32, 31, 31, 29, 30, 30, 29, 29, 31),  # 365
    2036: (31, 31, 32, 31, 31, 31, 30, 29, 30, 29, 30, 30),  # 365
    2037: (31, 31, 32, 32, 31, 30, 30, 29, 30, 29, 30, 30),  # 365
    2038: (31, 32, 31, 32, 31, 30, 30, 30, 29, 29, 30, 31),  # 366
    2039: (31, 31, 31, 32, 31, 31, 29, 30, 30, 29, 30, 30),  # 365
    2040: (31, 31, 32, 31, 31, 31, 30, 29, 30, 29, 30, 30),  # 365
    2041: (31, 31, 32, 32, 31, 30, 30, 29, 30, 29, 30, 30),  # 365
    2042: (31, 32, 31, 32, 31, 30, 30, 30, 29, 29, 30, 31),  # 366
    2043: (31, 31, 31, 32, 31, 31, 29, 30, 30, 29, 30, 30),  # 365
    2044: (31, 31, 32, 31, 31, 31, 30, 29, 30, 29, 30, 30),  # 365
    2045: (31, 32, 31, 32, 31, 30, 30, 29, 30, 29, 30, 30),  # 365
    2046: (31, 32, 31, 32, 31, 30, 30, 30, 29, 29, 30, 31),  # 366
    2047: (31, 31, 31, 32, 31, 31, 30, 29, 30, 29, 30, 30),  # 365
    2048: (31, 31, 32, 31, 31, 31, 30, 29, 30, 29, 30, 30),  # 365
    2049: (31, 32, 31, 32, 31, 30, 30, 30, 29, 29, 30, 30),  # 365
    2050: (31, 32, 31, 32, 31, 30, 30, 30, 29, 30, 29, 31),  # 366
    2051: (31, 31, 31, 32, 31, 31, 30, 29, 30, 29, 30, 30),  # 365
    2052: (31, 31, 32, 31, 31, 31, 30, 29, 30, 29, 30, 30),  # 365
    2053: (31, 32, 31, 32, 31, 30, 30, 30, 29, 29, 30, 30),  # 365
    2054: (31, 32, 31, 32, 31, 30, 30, 30, 29, 30, 29, 31),  # 366
    2055: (31, 31, 32, 31, 31, 31, 30, 29, 30, 29, 30, 30),  # 365
    2056: (31, 31, 32, 31, 32, 30, 30, 29, 30, 29, 30, 30),  # 365
    2057: (31, 32, 31, 32, 31, 30, 30, 30, 29, 29, 30, 31),  # 366
    2058: (30, 32, 31, 32, 31, 30, 30, 30, 29, 30, 29, 31),  # 365
    2059: (31, 31, 32, 31, 31, 31, 30, 29, 30, 29, 30, 30),  # 365
    2060: (31, 31, 32, 32, 31, 30, 30, 29, 30, 29, 30, 30),  # 365
    2061: (31, 32, 31, 32, 31, 30, 30, 30, 29, 29, 30, 31),  # 366
    2062: (31, 31, 31, 32, 31, 31, 29, 30, 29, 30, 29, 31),  # 365
    2063: (31, 31, 32, 31, 31, 31, 30, 29, 30, 29, 30, 30),  # 365
    2064: (31, 31, 32, 32, 31, 30, 30, 29, 30, 29, 30, 30),  # 365
    2065: (31, 32, 31, 32, 31, 30, 30, 30, 29, 29, 30, 31),  # 366
    2066: (31, 31, 31, 32, 31, 31, 29, 30, 30, 29, 29, 31),  # 365
    2067: (31, 31, 32, 31, 31, 31, 30, 29, 30, 29, 30, 30),  # 365
    2068: (31, 31, 32, 32, 31, 30, 30, 29, 30, 29, 30, 30),  # 365
    2069: (31, 32, 31, 32, 31, 30, 30, 30, 29, 29, 30, 31),  # 366
    2070: (31, 31, 31, 32, 31, 31, 29, 30, 30, 29, 30, 30),  # 365
    2071: (31, 31, 32, 31, 31, 31, 30, 29, 30, 29, 30, 30),  # 365
    2072: (31, 32, 31, 32, 31, 30, 30, 29, 30, 29, 30, 30),  # 365
    2073: (31, 32, 31, 32, 31, 30, 30, 30, 29, 29, 30, 31),  # 366
    2074: (31, 31, 31, 32, 31, 31, 30, 29, 30, 29, 30, 30),  # 365
    2075: (31, 31, 32, 31, 31, 31, 30, 29, 30, 29, 30, 30),  # 365
    2076: (31, 32, 31, 32, 31, 30, 30, 30, 29, 29, 30, 30),  # 365
    2077: (31, 32, 31, 32, 31, 30, 30, 30, 29, 30, 29, 31),  # 366
    2078: (31, 31, 31, 32, 31, 31, 30, 29, 30, 29, 30, 30),  # 365
    2079: (31, 31, 32, 31, 31, 31, 30, 29, 30, 29, 30, 30),  # 365
    2080: (31, 32, 31, 32, 31, 30, 30, 30, 29, 29, 30, 30),  # 365
    2081: (31, 32, 31, 32, 31, 30, 30, 30, 29, 30, 29, 31),  # 366
    2082: (31, 31, 32, 31, 31, 31, 30, 29, 30, 29, 30, 30),  # 365
    2083: (31, 31, 32, 31, 31, 31, 30, 29, 30, 29, 30, 30),  # 365
    # 2084 added 2026-07: scraped from hamropatro.com and found identical to
    # nepali-datetime for all 12 months. Those two are independent sources, and
    # they disagree with bikram-sambat here (366 days) -- so Hamro Patro breaks
    # the tie. It chains exactly onto 2083 (1 Baishakh 2084 = 2027-04-14). This
    # is the first year with a (30, 30, 30) tail; unusual, but corroborated by
    # both sources. Re-confirm against the official Panchanga once it publishes.
    2084: (31, 31, 32, 31, 31, 30, 30, 30, 29, 30, 30, 30),  # 365
}

#: Provisional (computed) month lengths for years beyond the verified range.
#:
#: **Empty by default** -- the package ships no unverified data. It may be
#: populated from :mod:`django_bikram.predict`, whose output is *astronomically
#: predicted*, not attested. Each provisional year must stay contiguous with the
#: verified range and total 365 or 366 days. Using a provisional date is allowed
#: but raises :class:`~django_bikram.exceptions.ProvisionalDateWarning`, because
#: a predicted month length can differ from the eventual official one by a day.
PROVISIONAL_BS_MONTH_DAYS: dict[int, tuple[int, ...]] = {}

#: The full working table: verified data, extended by any provisional data. All
#: conversion arithmetic runs over this merged view, so provisional dates
#: convert exactly like verified ones -- they are just flagged on the way.
BS_MONTH_DAYS: dict[int, tuple[int, ...]] = {
    **VERIFIED_BS_MONTH_DAYS,
    **PROVISIONAL_BS_MONTH_DAYS,
}

#: First BS year in the working table.
MIN_BS_YEAR = min(BS_MONTH_DAYS)

#: Last BS year in the working table. Equals :data:`VERIFIED_MAX_BS_YEAR` until
#: provisional data extends it.
MAX_BS_YEAR = max(BS_MONTH_DAYS)


def is_verified_year(year: int) -> bool:
    """Return whether a BS year is verified rather than provisional.

    Args:
        year: A Bikram Sambat year.

    Returns:
        ``True`` if ``year`` lies in the two-source verified range,
        ``False`` if it is covered only by provisional (computed) data.

    Example:
        >>> is_verified_year(2081)
        True
        >>> is_verified_year(2200)
        False
    """
    return VERIFIED_MIN_BS_YEAR <= year <= VERIFIED_MAX_BS_YEAR


def _last_ad_date(last_bs_year: int) -> datetime.date:
    """Return the Gregorian date of the final day of ``last_bs_year`` BS.

    Args:
        last_bs_year: A BS year present in :data:`BS_MONTH_DAYS`.

    Returns:
        The Gregorian date of that year's 30th/31st/32nd of Chaitra.
    """
    days = sum(sum(BS_MONTH_DAYS[y]) for y in range(MIN_BS_YEAR, last_bs_year + 1))
    return ANCHOR_AD + datetime.timedelta(days=days - 1)


#: Earliest representable Gregorian date (1 Baishakh of :data:`MIN_BS_YEAR`).
MIN_AD_DATE = ANCHOR_AD

#: Latest Gregorian date covered by the *verified* range (last day of Chaitra
#: 2084 BS = 2028-04-12). Fixed regardless of any provisional extension.
VERIFIED_MAX_AD_DATE = _last_ad_date(VERIFIED_MAX_BS_YEAR)

#: Latest representable Gregorian date across the working table. Equals
#: :data:`VERIFIED_MAX_AD_DATE` until provisional data extends the range.
MAX_AD_DATE = _last_ad_date(MAX_BS_YEAR)


def install_provisional(table: dict[int, tuple[int, ...]]) -> None:
    """Merge predicted years into the working calendar table.

    This is the one supported way to make the package accept dates past the
    verified range. It appends ``table`` -- typically from
    :func:`django_bikram.predict.build_provisional_table` -- to
    :data:`PROVISIONAL_BS_MONTH_DAYS`, rebuilds the merged
    :data:`BS_MONTH_DAYS`, extends :data:`MAX_BS_YEAR` / :data:`MAX_AD_DATE`, and
    refreshes the caches in :mod:`~django_bikram.convert` and the
    :attr:`~django_bikram.date.BSDate.max` bound.

    **Run it once, at startup, before the first date operation.** The easiest way
    is not to call it at all but to set the :data:`PROVISIONAL_ENV_VAR`
    environment variable, which triggers exactly this at import -- the point at
    which it is unambiguously safe. Installed years remain flagged: constructing
    or converting one raises
    :class:`~django_bikram.exceptions.ProvisionalDateWarning`, and
    :func:`is_verified_year` reports ``False`` for it.

    Args:
        table: A mapping of BS year to twelve month lengths, contiguous with the
            current end of the table (first key must be ``MAX_BS_YEAR + 1``).

    Raises:
        ValueError: If the years are not contiguous, a year lacks twelve months,
            a month length is not an ``int`` in 29..32, or a year does not total
            365 or 366 days. Bad predicted data fails loudly rather than
            silently corrupting every conversion.

    Example:
        >>> from django_bikram.predict import build_provisional_table
        >>> install_provisional(build_provisional_table(MAX_BS_YEAR + 5))
        ... # doctest: +SKIP
    """
    if not table:
        return
    expected = max(BS_MONTH_DAYS) + 1
    for year in sorted(table):
        lengths = table[year]
        if year != expected:
            raise ValueError(
                f"provisional years must be contiguous with the table; expected "
                f"{expected} BS next, got {year}"
            )
        if len(lengths) != MONTHS_IN_YEAR:
            raise ValueError(
                f"BS {year}: expected {MONTHS_IN_YEAR} month lengths, got "
                f"{len(lengths)}"
            )
        if not all(isinstance(n, int) and 29 <= n <= 32 for n in lengths):
            raise ValueError(f"BS {year}: month lengths must be ints in 29..32")
        if sum(lengths) not in (365, 366):
            raise ValueError(
                f"BS {year}: totals {sum(lengths)} days, which is not a possible "
                f"year (must be 365 or 366)"
            )
        expected = year + 1

    global MAX_BS_YEAR, MAX_AD_DATE
    PROVISIONAL_BS_MONTH_DAYS.update({y: tuple(v) for y, v in table.items()})
    BS_MONTH_DAYS.clear()
    BS_MONTH_DAYS.update(VERIFIED_BS_MONTH_DAYS)
    BS_MONTH_DAYS.update(PROVISIONAL_BS_MONTH_DAYS)
    MAX_BS_YEAR = max(BS_MONTH_DAYS)
    MAX_AD_DATE = _last_ad_date(MAX_BS_YEAR)

    # Refresh any consumer modules that cached derived values at import. At
    # env-triggered import time none are loaded yet (this module is imported
    # first), so these are no-ops; at a startup call they keep everything in sync.
    import sys

    for name in ("convert", "date", "formatting"):
        module = sys.modules.get(f"{__package__}.{name}")
        if module is not None:
            module._reload_from_calendar_data()
    package = sys.modules.get(__package__ or "")
    if package is not None:
        # Update the top-level re-exports in place (module globals, not a class).
        vars(package)["MAX_BS_YEAR"] = MAX_BS_YEAR
        vars(package)["MAX_AD_DATE"] = MAX_AD_DATE


def _activate_provisional_from_env() -> None:
    """Populate provisional years at import if :data:`PROVISIONAL_ENV_VAR` is set.

    Reads the environment once. An unset or empty variable leaves the package in
    its strict, verified-only default. A malformed value fails loudly rather
    than silently disabling the feature the operator asked for.

    Raises:
        ValueError: If the variable is set but not an integer BS year.
    """
    raw = os.environ.get(PROVISIONAL_ENV_VAR, "").strip()
    if not raw:
        return
    try:
        through_year = int(raw)
    except ValueError:
        raise ValueError(
            f"{PROVISIONAL_ENV_VAR} must be an integer BS year, got {raw!r}"
        ) from None
    from .predict import build_provisional_table

    install_provisional(build_provisional_table(through_year))


_activate_provisional_from_env()

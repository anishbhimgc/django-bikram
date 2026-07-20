"""Bikram Sambat (Nepali) dates for Python, with first-class Django support.

The public surface is small on purpose::

    >>> from django_bikram import BSDate
    >>> BSDate(2081, 1, 1).to_ad()
    datetime.date(2024, 4, 13)
    >>> BSDate.from_ad(datetime.date(2024, 4, 13))
    BSDate(2081, 1, 1)

Django integration lives in :mod:`django_bikram.django` and is imported separately so
that this package stays usable without Django installed.
"""

from __future__ import annotations

from .calendar_data import (
    MAX_AD_DATE,
    MAX_BS_YEAR,
    MIN_AD_DATE,
    MIN_BS_YEAR,
    VERIFIED_MAX_AD_DATE,
    VERIFIED_MAX_BS_YEAR,
    VERIFIED_MIN_BS_YEAR,
    is_verified_year,
)
from .convert import ad_to_bs, bs_to_ad, days_in_month, days_in_year
from .date import BSDate
from .exceptions import (
    BikramError,
    DateOutOfRange,
    InvalidBSDate,
    ProvisionalDateWarning,
)
from .formatting import format_bs, parse_bs, to_ascii_digits, to_devanagari

__version__ = "0.2.0"

__all__ = [
    "BSDate",
    "BikramError",
    "InvalidBSDate",
    "DateOutOfRange",
    "ProvisionalDateWarning",
    "ad_to_bs",
    "bs_to_ad",
    "days_in_month",
    "days_in_year",
    "is_verified_year",
    "format_bs",
    "parse_bs",
    "to_devanagari",
    "to_ascii_digits",
    "MIN_BS_YEAR",
    "MAX_BS_YEAR",
    "VERIFIED_MIN_BS_YEAR",
    "VERIFIED_MAX_BS_YEAR",
    "MIN_AD_DATE",
    "MAX_AD_DATE",
    "VERIFIED_MAX_AD_DATE",
    "__version__",
]

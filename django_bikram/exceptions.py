"""Exception hierarchy for :mod:`django_bikram`.

The hierarchy is deliberately shallow::

    BikramError
    └── InvalidBSDate  (also a ValueError)
        └── DateOutOfRange

:class:`InvalidBSDate` subclasses :exc:`ValueError` as well as
:class:`BikramError`. That is not an accident: callers who already write
``except ValueError`` around date parsing -- and every Django/DRF ``to_python``
in the wild does -- keep working, while callers who want to catch exactly this
package's failures can say ``except BikramError``.
"""

from __future__ import annotations

__all__ = [
    "BikramError",
    "InvalidBSDate",
    "DateOutOfRange",
    "ProvisionalDateWarning",
]


class BikramError(Exception):
    """Base class for every exception raised by :mod:`django_bikram`."""


class InvalidBSDate(BikramError, ValueError):
    """A Bikram Sambat date is malformed or does not exist.

    Raised for field values outside their natural bounds (month 13, day 0) and
    for days that do not exist in the specific month being addressed -- for
    example day 32 of a 31-day Baishakh. Because month lengths vary year to
    year, the second case can only be decided against the calendar table.
    """


class DateOutOfRange(InvalidBSDate):
    """A date is well-formed but lies outside the supported calendar range.

    Bikram Sambat month lengths are set astronomically and published year by
    year; they cannot be extrapolated from a rule. Rather than guess, the
    package refuses dates it has neither verified nor provisional data for. See
    :mod:`django_bikram.calendar_data` for the ranges and how to extend them.
    """


class ProvisionalDateWarning(UserWarning):
    """A date falls in the provisional (computed, unverified) calendar range.

    The verified range (two independent sources) ends at
    :data:`~django_bikram.calendar_data.VERIFIED_MAX_BS_YEAR` BS. Beyond it the
    month lengths are *astronomically predicted* rather than attested, and a
    prediction can differ from the eventually-published official value by a day.

    Such dates are allowed -- so planning past the verified horizon keeps
    working -- but their use raises this warning so the uncertainty is never
    silent. It is a :class:`UserWarning`, so the standard machinery applies::

        import warnings
        from django_bikram import ProvisionalDateWarning

        # silence entirely:
        warnings.filterwarnings("ignore", category=ProvisionalDateWarning)
        # or make it fatal, restoring the strict "verified only" behaviour:
        warnings.filterwarnings("error", category=ProvisionalDateWarning)

    :attr:`~django_bikram.date.BSDate.is_verified` reports the same distinction
    without raising anything.
    """

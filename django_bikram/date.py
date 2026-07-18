"""The :class:`BSDate` value type.

:class:`BSDate` is to Bikram Sambat what :class:`datetime.date` is to the
Gregorian calendar, and it deliberately mirrors that API: same constructor
shape, same ``weekday()`` convention, same ``timedelta`` arithmetic. Code that
already knows :mod:`datetime` should not have to learn much.
"""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Any, overload

from .calendar_data import MAX_BS_YEAR, MIN_BS_YEAR, is_verified_year
from .convert import ad_to_bs, bs_to_ad, check_bs_date, days_in_month, days_in_year
from .exceptions import InvalidBSDate

if TYPE_CHECKING:
    from typing import Literal

__all__ = ["NEPAL_TZ", "BSDate"]

#: Nepal Standard Time, UTC+05:45.
#:
#: A fixed offset rather than a ``ZoneInfo("Asia/Kathmandu")`` lookup, so the core
#: package keeps its only dependency as the standard library — no ``tzdata`` wheel
#: on Windows, no IANA database at import. Nepal has been +05:45 since 1986 and
#: observes no DST, so the fixed offset is not an approximation; it is the whole
#: rule.
#:
#: The 45 is the point. A 15-minute-offset zone is exactly where naive-vs-aware
#: bugs stop cancelling out and start producing an off-by-one **day**.
NEPAL_TZ = datetime.timezone(datetime.timedelta(hours=5, minutes=45), "NPT")


class BSDate:
    """An immutable, hashable, totally ordered Bikram Sambat date.

    A ``BSDate`` is a value: it is validated once at construction against the
    calendar table, then never changes. Every instance corresponds to exactly
    one :class:`datetime.date`, and that correspondence is a bijection over the
    verified range -- which is what makes ``from_ad(to_ad(d)) == d`` hold.

    Implemented with ``__slots__`` rather than a frozen dataclass so that the
    constructor can validate and normalise before the instance exists, and so
    instances stay small (three ints, no ``__dict__``).

    Ordering is chronological. Because BS year/month/day are ascending
    positional components, comparing the ``(year, month, day)`` tuple is
    equivalent to comparing the underlying Gregorian dates, so ordering needs
    no conversion.

    Attributes:
        year: Bikram Sambat year.
        month: Month number, 1 (Baishakh) through 12 (Chaitra).
        day: Day of the month.

    Example:
        >>> d = BSDate(2081, 1, 1)
        >>> d.to_ad()
        datetime.date(2024, 4, 13)
        >>> d + datetime.timedelta(days=31)
        BSDate(2081, 2, 1)
    """

    __slots__ = ("_year", "_month", "_day")

    # Declared so the type checker knows the slot members and their types; the
    # values are set through object.__setattr__ in __init__ (see below), because
    # our own __setattr__ refuses ordinary assignment.
    _year: int
    _month: int
    _day: int

    #: Earliest representable date, mirroring :attr:`datetime.date.min`.
    min: BSDate
    #: Latest representable date, mirroring :attr:`datetime.date.max`.
    max: BSDate
    #: Smallest possible difference between two dates.
    resolution = datetime.timedelta(days=1)

    def __init__(self, year: int, month: int, day: int) -> None:
        """Construct and validate a Bikram Sambat date.

        Args:
            year: Bikram Sambat year, within the verified range.
            month: Month number, 1 through 12.
            day: Day of month, 1 through the length of that month.

        Raises:
            InvalidBSDate: If the date does not exist.
            DateOutOfRange: If the year is outside the verified range.
        """
        check_bs_date(year, month, day)
        object.__setattr__(self, "_year", year)
        object.__setattr__(self, "_month", month)
        object.__setattr__(self, "_day", day)

    # -- immutability ----------------------------------------------------

    def __setattr__(self, name: str, value: Any) -> None:
        """Reject attribute assignment; ``BSDate`` is immutable."""
        raise AttributeError(
            f"{type(self).__name__} is immutable; use .replace() to derive a "
            f"new value"
        )

    def __delattr__(self, name: str) -> None:
        """Reject attribute deletion; ``BSDate`` is immutable."""
        raise AttributeError(f"{type(self).__name__} is immutable")

    def __reduce__(self) -> tuple[Any, tuple[int, int, int]]:
        """Support pickle and copy by rebuilding through the constructor.

        The default protocol for a ``__slots__`` class restores state with
        ``setattr``, which :meth:`__setattr__` refuses. Reconstructing from the
        constructor sidesteps that and re-validates on the way in, so an
        unpickled date cannot smuggle in a value the constructor would reject.

        Returns:
            A ``(callable, args)`` pair as required by :mod:`pickle`.
        """
        return (type(self), (self._year, self._month, self._day))

    # -- components ------------------------------------------------------

    @property
    def year(self) -> int:
        """The Bikram Sambat year."""
        return self._year

    @property
    def month(self) -> int:
        """The month number, 1 (Baishakh) through 12 (Chaitra)."""
        return self._month

    @property
    def day(self) -> int:
        """The day of the month."""
        return self._day

    # -- constructors ----------------------------------------------------

    @classmethod
    def from_ad(cls, value: datetime.date) -> BSDate:
        """Build a :class:`BSDate` from a Gregorian date.

        Args:
            value: A :class:`datetime.date`. A :class:`datetime.datetime` is
                accepted and its date component used.

        Returns:
            The equivalent Bikram Sambat date.

        Raises:
            DateOutOfRange: If the date is outside the verified range.

        Example:
            >>> BSDate.from_ad(datetime.date(2024, 4, 13))
            BSDate(2081, 1, 1)
        """
        return cls(*ad_to_bs(value))

    @classmethod
    def today(cls, tz: datetime.tzinfo | None = None) -> BSDate:
        """Return today's date in Bikram Sambat.

        Defaults to **Nepal**, not the system timezone. A Bikram Sambat date is a
        Nepali civil date, so "today" means today in Kathmandu — and the two
        disagree for 5h45m of every day on the UTC container this will actually
        run on. At 18:30 UTC it is already 00:15 tomorrow in Nepal, so
        ``datetime.date.today()`` reports yesterday for a quarter of every day.
        Near a BS month boundary that lands the date in the wrong month, which is
        the wrong bucket for every monthly and fiscal rollup built on it.

        Django's own ``DateField.pre_save`` has this same wart. Inheriting it in a
        library whose entire purpose is Nepali dates would be the wrong default:
        the caller who wants process-local time can pass a tz and say so.

        Args:
            tz: The timezone whose "today" is meant. Defaults to :data:`NEPAL_TZ`.

        Returns:
            Today as a :class:`BSDate`.

        Raises:
            DateOutOfRange: If the current date is outside the verified range.
                This is a real possibility once the table lapses; see
                :mod:`django_bikram.calendar_data`.
        """
        return cls.from_ad(datetime.datetime.now(tz or NEPAL_TZ).date())

    @classmethod
    def fromisoformat(cls, value: str) -> BSDate:
        """Parse a ``YYYY-MM-DD`` Bikram Sambat date string.

        The digits are interpreted as Bikram Sambat components, not Gregorian.

        Args:
            value: A date string such as ``"2081-01-01"``.

        Returns:
            The parsed date.

        Raises:
            InvalidBSDate: If the string is not a valid ISO-shaped BS date.

        Example:
            >>> BSDate.fromisoformat("2081-01-01")
            BSDate(2081, 1, 1)
        """
        if not isinstance(value, str):
            raise InvalidBSDate(
                f"fromisoformat expects a str, got {type(value).__name__!r}"
            )
        parts = value.split("-")
        # isdecimal(), not isdigit(): isdigit() also accepts the 128 Unicode
        # characters int() refuses — superscripts, circled digits — so the guard
        # passes and int() then raises a bare ValueError, which is not an
        # InvalidBSDate and escapes every handler downstream as a 500. isdecimal()
        # is an exact guard for int(), and still accepts Devanagari and fullwidth.
        if len(parts) != 3 or not all(p.isdecimal() for p in parts):
            raise InvalidBSDate(f"invalid isoformat string: {value!r}")
        year, month, day = (int(p) for p in parts)
        return cls(year, month, day)

    @classmethod
    def strptime(
        cls,
        value: str,
        fmt: str,
        *,
        lang: Literal["en", "ne"] = "en",
        numerals: Literal["ascii", "devanagari", "auto"] = "auto",
    ) -> BSDate:
        """Parse a string into a :class:`BSDate` using a strftime-style format.

        Args:
            value: The string to parse.
            fmt: A format string; see :mod:`django_bikram.formatting` for directives.
            lang: Language for month and weekday names, ``"en"`` or ``"ne"``.
            numerals: Numeral system of the digits. ``"auto"`` accepts either
                ASCII or Devanagari.

        Returns:
            The parsed date.

        Raises:
            InvalidBSDate: If the string does not match, or names a date that
                does not exist.

        Example:
            >>> BSDate.strptime("2081-01-01", "%Y-%m-%d")
            BSDate(2081, 1, 1)
        """
        from .formatting import parse_bs  # late import: avoids a cycle

        return cls(*parse_bs(value, fmt, lang=lang, numerals=numerals))

    # -- conversion ------------------------------------------------------

    def to_ad(self) -> datetime.date:
        """Return the Gregorian equivalent of this date.

        Returns:
            The corresponding :class:`datetime.date`.

        Example:
            >>> BSDate(2081, 1, 1).to_ad()
            datetime.date(2024, 4, 13)
        """
        return bs_to_ad(self._year, self._month, self._day)

    def replace(
        self,
        year: int | None = None,
        month: int | None = None,
        day: int | None = None,
    ) -> BSDate:
        """Return a copy of this date with the given components replaced.

        Args:
            year: New year, or ``None`` to keep the current one.
            month: New month, or ``None`` to keep the current one.
            day: New day, or ``None`` to keep the current one.

        Returns:
            A new :class:`BSDate`.

        Raises:
            InvalidBSDate: If the result does not exist. Note that month
                lengths vary by year, so replacing only the year can fail --
                ``BSDate(2081, 2, 32).replace(year=2082)`` has no 32nd Jestha
                to land on.

        Example:
            >>> BSDate(2081, 1, 1).replace(month=2)
            BSDate(2081, 2, 1)
        """
        return type(self)(
            self._year if year is None else year,
            self._month if month is None else month,
            self._day if day is None else day,
        )

    # -- calendar queries ------------------------------------------------

    def weekday(self) -> int:
        """Return the day of the week, Monday == 0 ... Sunday == 6.

        This follows the :meth:`datetime.date.weekday` convention so the two
        types stay interchangeable. For the Nepali convention, where the week
        starts on Sunday, use :meth:`nepali_weekday`.

        Returns:
            The weekday index, 0 through 6.
        """
        return self.to_ad().weekday()

    def isoweekday(self) -> int:
        """Return the day of the week, Monday == 1 ... Sunday == 7.

        Returns:
            The ISO weekday number, 1 through 7.
        """
        return self.to_ad().isoweekday()

    def nepali_weekday(self) -> int:
        """Return the day of the week Nepali-style, Sunday == 0 ... Saturday == 6.

        The Nepali week begins on Sunday (Aaitabar), so this is the index that
        matches a printed Nepali calendar's columns.

        Returns:
            The weekday index, 0 (Aaitabar) through 6 (Sanibar).
        """
        return (self.to_ad().weekday() + 1) % 7

    def timetuple(self) -> Any:
        """Return the Gregorian ``time.struct_time``, for interop.

        Returns:
            The :meth:`datetime.date.timetuple` of the Gregorian equivalent.
        """
        return self.to_ad().timetuple()

    def toordinal(self) -> int:
        """Return the proleptic Gregorian ordinal of this date.

        Returns:
            The same ordinal as ``self.to_ad().toordinal()``.
        """
        return self.to_ad().toordinal()

    @property
    def days_in_month(self) -> int:
        """The number of days in this date's month, 29 through 32."""
        return days_in_month(self._year, self._month)

    @property
    def days_in_year(self) -> int:
        """The number of days in this date's year, 365 or 366."""
        return days_in_year(self._year)

    @property
    def is_verified(self) -> bool:
        """Whether this date's year is verified rather than provisional.

        ``True`` for the two-source verified range; ``False`` for a date in the
        provisional (computed) range, whose month lengths may differ from the
        eventual official calendar by a day. Constructing or converting a
        provisional date also raises
        :class:`~django_bikram.exceptions.ProvisionalDateWarning`; this property
        is the quiet way to make the same check.
        """
        return is_verified_year(self._year)

    # -- formatting ------------------------------------------------------

    def isoformat(self) -> str:
        """Return the date as a ``YYYY-MM-DD`` Bikram Sambat string.

        The components are Bikram Sambat, not Gregorian; the shape is ISO-like
        for sortability and round-tripping, not an ISO 8601 claim.

        Returns:
            A string such as ``"2081-01-01"``.
        """
        return f"{self._year:04d}-{self._month:02d}-{self._day:02d}"

    def strftime(
        self,
        fmt: str,
        *,
        lang: Literal["en", "ne"] = "en",
        numerals: Literal["ascii", "devanagari"] = "ascii",
    ) -> str:
        """Format this date using a strftime-style format string.

        Args:
            fmt: A format string; see :mod:`django_bikram.formatting` for directives.
            lang: Language for month and weekday names, ``"en"`` or ``"ne"``.
            numerals: Numeral system for digits, ``"ascii"`` or
                ``"devanagari"``.

        Returns:
            The formatted date.

        Example:
            >>> BSDate(2081, 1, 1).strftime("%d %B %Y")
            '01 Baishakh 2081'
        """
        from .formatting import format_bs  # late import: avoids a cycle

        return format_bs(self, fmt, lang=lang, numerals=numerals)

    def __str__(self) -> str:
        """Return the ISO-shaped representation."""
        return self.isoformat()

    def __repr__(self) -> str:
        """Return an eval-able representation."""
        return f"{type(self).__name__}({self._year}, {self._month}, {self._day})"

    def __format__(self, spec: str) -> str:
        """Format via :meth:`strftime` when a spec is given.

        Args:
            spec: A strftime format string, or empty for :meth:`isoformat`.

        Returns:
            The formatted date.
        """
        return self.strftime(spec) if spec else self.isoformat()

    # -- comparison ------------------------------------------------------

    def _key(self) -> tuple[int, int, int]:
        """Return the ordering key."""
        return (self._year, self._month, self._day)

    def __eq__(self, other: object) -> bool:
        """Compare for equality with another :class:`BSDate`.

        A ``BSDate`` never compares equal to a :class:`datetime.date`, even one
        denoting the same day. They are different types with different
        semantics, and silently equating them would make dict keys and set
        membership ambiguous. Convert explicitly.
        """
        if isinstance(other, BSDate):
            return self._key() == other._key()
        return NotImplemented

    def __hash__(self) -> int:
        """Hash on the ``(year, month, day)`` key."""
        return hash((BSDate, self._key()))

    def __lt__(self, other: BSDate) -> bool:
        """Return whether this date precedes ``other``."""
        if isinstance(other, BSDate):
            return self._key() < other._key()
        return NotImplemented

    def __le__(self, other: BSDate) -> bool:
        """Return whether this date precedes or equals ``other``."""
        if isinstance(other, BSDate):
            return self._key() <= other._key()
        return NotImplemented

    def __gt__(self, other: BSDate) -> bool:
        """Return whether this date follows ``other``."""
        if isinstance(other, BSDate):
            return self._key() > other._key()
        return NotImplemented

    def __ge__(self, other: BSDate) -> bool:
        """Return whether this date follows or equals ``other``."""
        if isinstance(other, BSDate):
            return self._key() >= other._key()
        return NotImplemented

    # -- arithmetic ------------------------------------------------------

    def __add__(self, other: datetime.timedelta) -> BSDate:
        """Add a :class:`datetime.timedelta`, returning a new date.

        Only the whole-day component participates; a ``timedelta`` with a
        sub-day remainder is rejected rather than silently truncated, because
        truncation direction is a coin flip callers should not have to guess.

        Args:
            other: A whole-day timedelta.

        Returns:
            The shifted date.

        Raises:
            InvalidBSDate: If ``other`` is not a whole number of days.
            DateOutOfRange: If the result leaves the verified range.
        """
        if not isinstance(other, datetime.timedelta):
            return NotImplemented
        if other % datetime.timedelta(days=1):
            raise InvalidBSDate(
                f"can only add whole days to a {type(self).__name__}, got "
                f"{other!r}"
            )
        return type(self).from_ad(self.to_ad() + other)

    __radd__ = __add__

    @overload
    def __sub__(self, other: BSDate) -> datetime.timedelta: ...

    @overload
    def __sub__(self, other: datetime.timedelta) -> BSDate: ...

    def __sub__(
        self, other: BSDate | datetime.timedelta
    ) -> BSDate | datetime.timedelta:
        """Subtract a timedelta (giving a date) or a date (giving a timedelta).

        Args:
            other: A :class:`BSDate` or a whole-day
                :class:`datetime.timedelta`.

        Returns:
            A :class:`datetime.timedelta` if ``other`` is a :class:`BSDate`,
            otherwise the shifted :class:`BSDate`.

        Raises:
            InvalidBSDate: If ``other`` is a non-whole-day timedelta.
            DateOutOfRange: If the result leaves the verified range.

        Example:
            >>> BSDate(2081, 1, 2) - BSDate(2081, 1, 1)
            datetime.timedelta(days=1)
        """
        if isinstance(other, BSDate):
            return self.to_ad() - other.to_ad()
        if isinstance(other, datetime.timedelta):
            return self.__add__(-other)
        return NotImplemented


BSDate.min = BSDate(MIN_BS_YEAR, 1, 1)
BSDate.max = BSDate(MAX_BS_YEAR, 12, days_in_month(MAX_BS_YEAR, 12))


def _reload_from_calendar_data() -> None:
    """Refresh :attr:`BSDate.max` after provisional years extended the table.

    Called by :func:`django_bikram.calendar_data.install_provisional`. The new
    maximum is itself a provisional date, so the (expected) warning from
    constructing it is suppressed here -- installing the table is not the same
    as a caller reaching into the provisional range.
    """
    import warnings

    from . import calendar_data as cd

    global MAX_BS_YEAR
    MAX_BS_YEAR = cd.MAX_BS_YEAR
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        BSDate.max = BSDate(cd.MAX_BS_YEAR, 12, days_in_month(cd.MAX_BS_YEAR, 12))

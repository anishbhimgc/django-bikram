"""Behaviour of the BSDate value type."""

from __future__ import annotations

import copy
import datetime
import pickle

import pytest

import django_bikram.date
from django_bikram import BSDate
from django_bikram.date import NEPAL_TZ
from django_bikram.exceptions import BikramError, DateOutOfRange, InvalidBSDate


def test_components_are_exposed() -> None:
    """year/month/day read back what was constructed."""
    d = BSDate(2081, 2, 32)
    assert (d.year, d.month, d.day) == (2081, 2, 32)


def test_is_immutable() -> None:
    """Attribute assignment and deletion are rejected."""
    d = BSDate(2081, 1, 1)
    with pytest.raises(AttributeError):
        d.year = 2082  # type: ignore[misc]
    with pytest.raises(AttributeError):
        del d.year  # type: ignore[attr-defined]


def test_has_no_dict() -> None:
    """__slots__ is in force, so instances carry no __dict__."""
    assert not hasattr(BSDate(2081, 1, 1), "__dict__")


def test_is_hashable_and_usable_in_sets_and_dicts() -> None:
    """Equal dates hash equally and collapse in a set."""
    a, b = BSDate(2081, 1, 1), BSDate(2081, 1, 1)
    assert hash(a) == hash(b)
    assert len({a, b}) == 1
    assert {a: "x"}[b] == "x"


def test_total_ordering() -> None:
    """Dates order chronologically across month and year boundaries."""
    dates = [BSDate(2081, 1, 1), BSDate(2081, 1, 2), BSDate(2081, 2, 1), BSDate(2082, 1, 1)]
    assert sorted(reversed(dates)) == dates
    assert dates[0] < dates[1] <= dates[1] < dates[2] < dates[3]
    assert dates[3] > dates[0] and dates[0] >= BSDate(2081, 1, 1)


def test_ordering_matches_gregorian_ordering() -> None:
    """Comparing BS components agrees with comparing the AD equivalents."""
    a, b = BSDate(2081, 12, 30), BSDate(2082, 1, 1)
    assert (a < b) == (a.to_ad() < b.to_ad())


def test_does_not_compare_equal_to_datetime_date() -> None:
    """A BSDate is never equal to a datetime.date, even for the same day."""
    d = BSDate(2081, 1, 1)
    assert d != datetime.date(2024, 4, 13)
    assert d != "2081-01-01"
    assert d != 42


def test_comparison_with_other_types_raises() -> None:
    """Ordering against a foreign type is a TypeError, as with datetime."""
    with pytest.raises(TypeError):
        BSDate(2081, 1, 1) < datetime.date(2024, 4, 13)  # type: ignore[operator]


def test_round_trip_via_ad() -> None:
    """from_ad(to_ad(d)) is the identity."""
    d = BSDate(2081, 5, 15)
    assert BSDate.from_ad(d.to_ad()) == d


def test_from_ad_accepts_datetime() -> None:
    """A datetime is accepted and truncated to its date."""
    assert BSDate.from_ad(datetime.datetime(2024, 4, 13, 12, 0)) == BSDate(2081, 1, 1)


def test_today_is_nepal_local_not_process_local(monkeypatch: pytest.MonkeyPatch) -> None:
    """today() reports Nepal's day even when the process runs in UTC.

    18:30 UTC is already 00:15 the next day in Kathmandu (+05:45), so a UTC
    container must still report the Nepali day — this instant also crosses a BS
    month boundary (Ashadh -> Shrawan), so getting it wrong buckets a whole
    month's rollups a month early.

    The previous test here asserted
    ``BSDate.today() == BSDate.from_ad(datetime.date.today())``, which was the
    implementation restated: it could not fail, and did not, while today() was
    wrong for 5h45m of every day.
    """
    instant = datetime.datetime(2026, 7, 17, 18, 30, tzinfo=datetime.timezone.utc)

    class _Frozen(datetime.datetime):
        @classmethod
        def now(cls, tz: datetime.tzinfo | None = None) -> datetime.datetime:
            return instant.astimezone(tz)

    monkeypatch.setattr(django_bikram.date.datetime, "datetime", _Frozen)

    assert BSDate.today() == BSDate(2083, 4, 2)  # Nepal's day, not UTC's 2083-04-01


def test_today_accepts_an_explicit_timezone(monkeypatch: pytest.MonkeyPatch) -> None:
    """A caller who wants another zone's today can ask for it."""
    instant = datetime.datetime(2026, 7, 17, 18, 30, tzinfo=datetime.timezone.utc)

    class _Frozen(datetime.datetime):
        @classmethod
        def now(cls, tz: datetime.tzinfo | None = None) -> datetime.datetime:
            return instant.astimezone(tz)

    monkeypatch.setattr(django_bikram.date.datetime, "datetime", _Frozen)

    assert BSDate.today(datetime.timezone.utc) == BSDate(2083, 4, 1)
    assert BSDate.today(NEPAL_TZ) == BSDate(2083, 4, 2)


def test_min_and_max_are_the_table_bounds() -> None:
    """min/max sit exactly at the edges of the verified range."""
    assert BSDate.min == BSDate(1975, 1, 1)
    assert BSDate.max == BSDate(2083, 12, 30)
    assert BSDate.resolution == datetime.timedelta(days=1)


@pytest.mark.parametrize(
    ("args", "exc"),
    [
        ((2081, 1, 32), InvalidBSDate),
        ((2081, 13, 1), InvalidBSDate),
        ((2081, 0, 1), InvalidBSDate),
        ((2081, 1, 0), InvalidBSDate),
        ((1974, 1, 1), DateOutOfRange),
        ((2084, 1, 1), DateOutOfRange),
    ],
)
def test_invalid_dates_raise_specific_errors(args: tuple[int, int, int], exc: type) -> None:
    """Bad dates raise InvalidBSDate/DateOutOfRange, never a bare ValueError."""
    with pytest.raises(exc):
        BSDate(*args)


def test_exceptions_are_catchable_both_ways() -> None:
    """InvalidBSDate is both a BikramError and a ValueError."""
    with pytest.raises(BikramError):
        BSDate(2081, 1, 32)
    with pytest.raises(ValueError):
        BSDate(2081, 1, 32)
    assert issubclass(DateOutOfRange, InvalidBSDate)


def test_replace() -> None:
    """replace() derives a new value, leaving the original untouched."""
    d = BSDate(2081, 1, 1)
    assert d.replace(month=2) == BSDate(2081, 2, 1)
    assert d.replace(year=2082, day=5) == BSDate(2082, 1, 5)
    assert d == BSDate(2081, 1, 1)


def test_replace_validates_against_the_target_year() -> None:
    """Replacing the year can invalidate the day, because months vary.

    2081 Jestha has 32 days but 2082 Jestha has 31, so this must fail rather
    than silently clamp.
    """
    d = BSDate(2081, 2, 32)
    with pytest.raises(InvalidBSDate):
        d.replace(year=2082)


def test_arithmetic_with_timedelta() -> None:
    """Adding and subtracting whole-day timedeltas shifts the date."""
    d = BSDate(2081, 1, 1)
    assert d + datetime.timedelta(days=31) == BSDate(2081, 2, 1)
    assert d + datetime.timedelta(days=1) - datetime.timedelta(days=1) == d
    assert datetime.timedelta(days=1) + d == BSDate(2081, 1, 2)


def test_difference_of_two_dates_is_a_timedelta() -> None:
    """BSDate - BSDate yields a timedelta, matching datetime.date."""
    assert BSDate(2081, 2, 1) - BSDate(2081, 1, 1) == datetime.timedelta(days=31)
    assert BSDate(2081, 1, 1) - BSDate(2081, 2, 1) == datetime.timedelta(days=-31)


def test_arithmetic_rejects_sub_day_timedeltas() -> None:
    """A partial-day timedelta is rejected rather than silently truncated."""
    with pytest.raises(InvalidBSDate):
        BSDate(2081, 1, 1) + datetime.timedelta(hours=5)


def test_arithmetic_out_of_range_raises() -> None:
    """Arithmetic that leaves the verified range raises DateOutOfRange."""
    with pytest.raises(DateOutOfRange):
        BSDate.max + datetime.timedelta(days=1)
    with pytest.raises(DateOutOfRange):
        BSDate.min - datetime.timedelta(days=1)


def test_arithmetic_with_unsupported_type() -> None:
    """Adding a non-timedelta is a TypeError."""
    with pytest.raises(TypeError):
        BSDate(2081, 1, 1) + 1  # type: ignore[operator]


def test_weekday_conventions() -> None:
    """weekday/isoweekday follow datetime; nepali_weekday starts on Sunday."""
    # 1 Baishakh 2081 BS == 13 April 2024, a Saturday.
    d = BSDate(2081, 1, 1)
    assert d.to_ad().weekday() == 5
    assert d.weekday() == 5
    assert d.isoweekday() == 6
    assert d.nepali_weekday() == 6


def test_nepali_weekday_sunday_is_zero() -> None:
    """Sunday maps to 0 in the Nepali convention."""
    # 14 April 2024 was a Sunday == 2 Baishakh 2081.
    d = BSDate(2081, 1, 2)
    assert d.to_ad().weekday() == 6
    assert d.nepali_weekday() == 0


def test_isoformat_and_str() -> None:
    """isoformat renders zero-padded BS components."""
    assert BSDate(2081, 1, 1).isoformat() == "2081-01-01"
    assert str(BSDate(2081, 1, 1)) == "2081-01-01"


def test_repr_round_trips() -> None:
    """repr is eval-able back into an equal value."""
    d = BSDate(2081, 5, 15)
    assert repr(d) == "BSDate(2081, 5, 15)"
    assert eval(repr(d)) == d  # noqa: S307


def test_fromisoformat() -> None:
    """fromisoformat parses BS components, not Gregorian ones."""
    assert BSDate.fromisoformat("2081-01-01") == BSDate(2081, 1, 1)


@pytest.mark.parametrize("value", ["", "2081", "2081-01", "not-a-date", "2081-01-32", "2081/01/01"])
def test_fromisoformat_rejects_junk(value: str) -> None:
    """Malformed ISO strings raise InvalidBSDate."""
    with pytest.raises(InvalidBSDate):
        BSDate.fromisoformat(value)


@pytest.mark.parametrize("value", ["²⁰⁸¹-01-01", "①-01-01", "2081-²-01", "2081-01-⑴"])
def test_fromisoformat_rejects_non_decimal_digits(value: str) -> None:
    """Non-decimal "digits" raise InvalidBSDate, not a bare ValueError.

    ``str.isdigit()`` is True for 128 characters ``int()`` refuses — superscripts,
    circled digits, Ethiopic numerals. Guarding with isdigit() let them through to
    ``int()``, which raised a bare ValueError: not an InvalidBSDate, so it escaped
    every ``except InvalidBSDate`` in the Django layer and surfaced as a 500 from
    ``full_clean()`` — the one call whose entire job is turning bad input into a
    ValidationError. ``isdecimal()`` is an exact guard for ``int()``.
    """
    with pytest.raises(InvalidBSDate):
        BSDate.fromisoformat(value)


@pytest.mark.parametrize("value", ["२०८१-०१-०१", "２０８１-01-01"])
def test_fromisoformat_still_accepts_devanagari_and_fullwidth(value: str) -> None:
    """The isdecimal() guard must not cost us the numerals users actually type.

    Devanagari is the point of this library; fullwidth is free. Both are
    isdecimal() and int()-able, so tightening isdigit() -> isdecimal() loses
    neither.
    """
    assert BSDate.fromisoformat(value) == BSDate(2081, 1, 1)


def test_fromisoformat_rejects_non_string() -> None:
    """A non-string raises InvalidBSDate rather than AttributeError."""
    with pytest.raises(InvalidBSDate):
        BSDate.fromisoformat(2081)  # type: ignore[arg-type]


def test_format_protocol() -> None:
    """__format__ delegates to strftime, or isoformat when spec is empty."""
    d = BSDate(2081, 1, 1)
    assert f"{d}" == "2081-01-01"
    assert f"{d:%d %B %Y}" == "01 Baishakh 2081"


def test_strptime_classmethod() -> None:
    """BSDate.strptime parses via the formatting module."""
    assert BSDate.strptime("01 Baishakh 2081", "%d %B %Y") == BSDate(2081, 1, 1)


def test_days_in_month_and_year_properties() -> None:
    """The convenience properties read from the table."""
    assert BSDate(2081, 2, 1).days_in_month == 32
    assert BSDate(2081, 1, 1).days_in_year == 366


def test_toordinal_and_timetuple_match_gregorian() -> None:
    """Interop helpers delegate to the Gregorian equivalent."""
    d = BSDate(2081, 1, 1)
    assert d.toordinal() == datetime.date(2024, 4, 13).toordinal()
    assert d.timetuple() == datetime.date(2024, 4, 13).timetuple()


def test_pickle_round_trip() -> None:
    """Instances survive pickling despite __slots__."""
    d = BSDate(2081, 5, 15)
    assert pickle.loads(pickle.dumps(d)) == d


def test_copy_round_trip() -> None:
    """copy and deepcopy return equal values."""
    d = BSDate(2081, 5, 15)
    assert copy.copy(d) == d
    assert copy.deepcopy(d) == d

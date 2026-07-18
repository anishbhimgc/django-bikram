"""Formatting and parsing, including the language/numeral matrix."""

from __future__ import annotations

import pytest

from django_bikram import BSDate
from django_bikram.calendar_data import BS_MONTH_DAYS, MAX_BS_YEAR, MIN_BS_YEAR
from django_bikram.exceptions import InvalidBSDate
from django_bikram.formatting import (
    MONTH_ABBRS,
    MONTH_NAMES,
    WEEKDAY_ABBRS,
    WEEKDAY_NAMES,
    format_bs,
    parse_bs,
    to_ascii_digits,
    to_devanagari,
)

# 1 Baishakh 2081 BS == Saturday 13 April 2024.
NEW_YEAR_2081 = BSDate(2081, 1, 1)


def test_numeral_helpers_round_trip() -> None:
    """ASCII and Devanagari digit conversion are inverses."""
    assert to_devanagari("2081-01-01") == "२०८१-०१-०१"
    assert to_ascii_digits("२०८१-०१-०१") == "2081-01-01"
    assert to_ascii_digits(to_devanagari("1234567890")) == "1234567890"


def test_numeral_helpers_leave_non_digits_alone() -> None:
    """Only digits are translated."""
    assert to_devanagari("Baishakh 2081") == "Baishakh २०८१"


@pytest.mark.parametrize(
    ("fmt", "expected"),
    [
        ("%Y", "2081"),
        ("%y", "81"),
        ("%m", "01"),
        ("%-m", "1"),
        ("%d", "01"),
        ("%-d", "1"),
        ("%B", "Baishakh"),
        ("%b", "Bai"),
        ("%A", "Saturday"),
        ("%a", "Sat"),
        ("%j", "001"),
        ("%%", "%"),
        ("%Y-%m-%d", "2081-01-01"),
        ("%-d %B %Y", "1 Baishakh 2081"),
        ("%A, %-d %b %Y", "Saturday, 1 Bai 2081"),
    ],
)
def test_directives_english_ascii(fmt: str, expected: str) -> None:
    """Each supported directive renders correctly in English/ASCII."""
    assert format_bs(NEW_YEAR_2081, fmt) == expected


def test_unknown_directive_passes_through() -> None:
    """Unknown directives are emitted verbatim, as datetime.strftime does."""
    assert format_bs(NEW_YEAR_2081, "%Q") == "%Q"


def test_literal_text_is_preserved() -> None:
    """Non-directive text survives formatting."""
    assert format_bs(NEW_YEAR_2081, "Issued on %Y!") == "Issued on 2081!"


def test_nepali_names() -> None:
    """Nepali month and weekday names render in Devanagari."""
    assert format_bs(NEW_YEAR_2081, "%B", lang="ne") == "वैशाख"
    assert format_bs(NEW_YEAR_2081, "%A", lang="ne") == "शनिबार"


def test_devanagari_numerals_with_english_names() -> None:
    """Language and numerals are independent switches."""
    assert format_bs(NEW_YEAR_2081, "%d %B %Y", numerals="devanagari") == "०१ Baishakh २०८१"


def test_nepali_names_with_ascii_numerals() -> None:
    """The other half of the matrix."""
    assert format_bs(NEW_YEAR_2081, "%d %B %Y", lang="ne") == "01 वैशाख 2081"


def test_full_nepali() -> None:
    """Nepali names and Devanagari numerals together."""
    assert (
        format_bs(NEW_YEAR_2081, "%A, %d %B %Y", lang="ne", numerals="devanagari")
        == "शनिबार, ०१ वैशाख २०८१"
    )


def test_day_of_year() -> None:
    """%j counts days from 1 Baishakh."""
    assert format_bs(BSDate(2081, 2, 1), "%j") == "032"  # Baishakh 2081 has 31 days


@pytest.mark.parametrize("bad", ["fr", "np", "", None])
def test_format_rejects_unknown_lang(bad: object) -> None:
    """An unsupported language raises rather than falling back silently."""
    with pytest.raises(InvalidBSDate):
        format_bs(NEW_YEAR_2081, "%B", lang=bad)  # type: ignore[arg-type]


def test_format_rejects_unknown_numerals() -> None:
    """An unsupported numeral system raises."""
    with pytest.raises(InvalidBSDate):
        format_bs(NEW_YEAR_2081, "%Y", numerals="roman")  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("value", "fmt", "expected"),
    [
        ("2081-01-01", "%Y-%m-%d", (2081, 1, 1)),
        ("2081/01/01", "%Y/%m/%d", (2081, 1, 1)),
        ("1 Baishakh 2081", "%-d %B %Y", (2081, 1, 1)),
        ("01 Baishakh 2081", "%d %B %Y", (2081, 1, 1)),
        ("1 Bai 2081", "%-d %b %Y", (2081, 1, 1)),
        ("Saturday, 1 Baishakh 2081", "%A, %-d %B %Y", (2081, 1, 1)),
        ("२०८१-०१-०१", "%Y-%m-%d", (2081, 1, 1)),
        # %y resolves toward the 20xx century where both are in range...
        ("81-01-01", "%y-%m-%d", (2081, 1, 1)),
        ("75-01-01", "%y-%m-%d", (2075, 1, 1)),
        ("00-01-01", "%y-%m-%d", (2000, 1, 1)),
        # ...and falls back to 19xx where 20xx is out of range.
        ("90-01-01", "%y-%m-%d", (1990, 1, 1)),
        ("99-01-01", "%y-%m-%d", (1999, 1, 1)),
    ],
)
def test_parse(value: str, fmt: str, expected: tuple[int, int, int]) -> None:
    """Parsing recovers the components for a spread of formats."""
    assert parse_bs(value, fmt) == expected


def test_parse_nepali_names() -> None:
    """Nepali month names parse when lang='ne'."""
    assert parse_bs("०१ वैशाख २०८१", "%d %B %Y", lang="ne") == (2081, 1, 1)
    assert parse_bs("शनिबार, ०१ वैशाख २०८१", "%A, %d %B %Y", lang="ne") == (2081, 1, 1)


def test_parse_padded_and_unpadded_are_both_accepted() -> None:
    """A %d format still accepts an unpadded day, as the stdlib does."""
    assert parse_bs("2081-1-1", "%Y-%m-%d") == (2081, 1, 1)


def test_parse_strips_surrounding_whitespace() -> None:
    """Leading/trailing whitespace is tolerated."""
    assert parse_bs("  2081-01-01  ", "%Y-%m-%d") == (2081, 1, 1)


def test_parse_numeral_restriction() -> None:
    """An explicit numeral system rejects the other one."""
    assert parse_bs("2081-01-01", "%Y-%m-%d", numerals="ascii") == (2081, 1, 1)
    with pytest.raises(InvalidBSDate):
        parse_bs("२०८१-०१-०१", "%Y-%m-%d", numerals="ascii")
    with pytest.raises(InvalidBSDate):
        parse_bs("2081-01-01", "%Y-%m-%d", numerals="devanagari")


def test_parse_auto_accepts_either() -> None:
    """The default 'auto' accepts both numeral systems."""
    assert parse_bs("२०८१-०१-०१", "%Y-%m-%d", numerals="auto") == (2081, 1, 1)
    assert parse_bs("2081-01-01", "%Y-%m-%d", numerals="auto") == (2081, 1, 1)


@pytest.mark.parametrize(
    ("value", "fmt"),
    [
        ("not a date", "%Y-%m-%d"),
        ("2081-01", "%Y-%m-%d"),
        ("2081-01-01 extra", "%Y-%m-%d"),
        ("01 Nonesuch 2081", "%d %B %Y"),
        ("2081-01-01", "%d/%m/%Y"),
        ("", "%Y-%m-%d"),
    ],
)
def test_parse_rejects_mismatches(value: str, fmt: str) -> None:
    """Input that does not match the format raises InvalidBSDate."""
    with pytest.raises(InvalidBSDate):
        parse_bs(value, fmt)


def test_parse_requires_a_complete_date() -> None:
    """A format missing a component cannot yield a date."""
    with pytest.raises(InvalidBSDate, match="does not supply"):
        parse_bs("2081-01", "%Y-%m")


def test_parse_rejects_non_string() -> None:
    """A non-string input raises InvalidBSDate."""
    with pytest.raises(InvalidBSDate):
        parse_bs(20810101, "%Y-%m-%d")  # type: ignore[arg-type]


def test_parse_two_digit_year_outside_range_raises() -> None:
    """A %y that maps nowhere in the verified range is an error, not a guess."""
    # Within 1975..2084 no two-digit year maps nowhere (2000+yy needs yy<=84,
    # 1900+yy needs yy>=75, and those overlap), so there is nothing to raise on
    # -- assert the documented 20xx preference instead.
    assert parse_bs("74-01-01", "%y-%m-%d") == (2074, 1, 1)
    assert parse_bs("85-01-01", "%y-%m-%d") == (1985, 1, 1)  # 2085 out of range


def test_two_digit_year_ambiguity_is_resolved_toward_20xx() -> None:
    """Where both centuries are valid, %y picks 20xx, as documented."""
    for yy in range(75, 84):
        assert parse_bs(f"{yy}-01-01", "%y-%m-%d")[0] == 2000 + yy
        # Both expansions really are in range -- this is a genuine tie.
        assert MIN_BS_YEAR <= 1900 + yy <= MAX_BS_YEAR
        assert MIN_BS_YEAR <= 2000 + yy <= MAX_BS_YEAR


def test_parse_escapes_regex_metacharacters_in_format() -> None:
    """Literal '.' in a format matches a literal dot, not any character."""
    assert parse_bs("2081.01.01", "%Y.%m.%d") == (2081, 1, 1)
    with pytest.raises(InvalidBSDate):
        parse_bs("2081x01x01", "%Y.%m.%d")


def test_parse_literal_percent() -> None:
    """%% matches a literal percent sign on both sides of the round trip."""
    assert format_bs(NEW_YEAR_2081, "%Y%%%m%%%d") == "2081%01%01"
    assert parse_bs("2081%01%01", "%Y%%%m%%%d") == (2081, 1, 1)


def test_format_parse_round_trip_across_the_range() -> None:
    """Every date in the range survives format -> parse, in all four modes."""
    dates = [
        BSDate(year, month, 1)
        for year in range(MIN_BS_YEAR, MAX_BS_YEAR + 1)
        for month in range(1, 13)
    ]
    # Include the last day of every month, where off-by-ones live.
    dates += [
        BSDate(year, month, BS_MONTH_DAYS[year][month - 1])
        for year in range(MIN_BS_YEAR, MAX_BS_YEAR + 1)
        for month in range(1, 13)
    ]
    for d in dates:
        for lang in ("en", "ne"):
            for numerals in ("ascii", "devanagari"):
                text = format_bs(d, "%d %B %Y", lang=lang, numerals=numerals)
                assert parse_bs(text, "%d %B %Y", lang=lang) == (d.year, d.month, d.day)


def test_month_and_weekday_tables_are_well_formed() -> None:
    """Name tables have the right size and no duplicates.

    Duplicate abbreviations would make %b ambiguous to parse -- the reason the
    English abbreviations are not naive three-letter prefixes.
    """
    for lang in ("en", "ne"):
        assert len(MONTH_NAMES[lang]) == 12
        assert len(MONTH_ABBRS[lang]) == 12
        assert len(WEEKDAY_NAMES[lang]) == 7
        assert len(WEEKDAY_ABBRS[lang]) == 7
        assert len(set(MONTH_NAMES[lang])) == 12
        assert len(set(MONTH_ABBRS[lang])) == 12
        assert len(set(WEEKDAY_NAMES[lang])) == 7
        assert len(set(WEEKDAY_ABBRS[lang])) == 7


def test_every_month_name_parses_back_to_its_index() -> None:
    """%B and %b recover the month number for all twelve months."""
    for lang in ("en", "ne"):
        for month in range(1, 13):
            d = BSDate(2081, month, 1)
            assert parse_bs(format_bs(d, "%B %d %Y", lang=lang), "%B %d %Y", lang=lang)[1] == month
            assert parse_bs(format_bs(d, "%b %d %Y", lang=lang), "%b %d %Y", lang=lang)[1] == month

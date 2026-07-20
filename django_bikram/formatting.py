"""strftime-style formatting and parsing for Bikram Sambat dates.

Two axes vary independently, and conflating them is the usual mistake:

* **Language** (``lang``) picks the words -- month and weekday names, in
  English romanisation or Nepali Devanagari.
* **Numerals** (``numerals``) picks the digits -- ASCII ``2081`` or
  Devanagari ``२०८१``.

They are separate because real Nepali documents mix them freely: an English
form may still want Devanagari numerals, and a Nepali UI may want ASCII digits
for a machine-readable field.

Supported directives
--------------------

=========  ===================================================================
``%Y``     Year, zero-padded to four digits (``2081``)
``%y``     Year without century, zero-padded to two digits (``81``). Ambiguous
           on input -- see :func:`_resolve_two_digit_year`; prefer ``%Y``.
``%m``     Month, zero-padded to two digits (``01``)
``%-m``    Month, no padding (``1``)
``%d``     Day, zero-padded to two digits (``01``)
``%-d``    Day, no padding (``1``)
``%B``     Full month name (``Baishakh`` / ``वैशाख``)
``%b``     Abbreviated month name (``Bai`` / ``वैश``)
``%A``     Full weekday name (``Saturday`` / ``शनिबार``)
``%a``     Abbreviated weekday name (``Sat`` / ``शनि``)
``%j``     Day of year, zero-padded to three digits (``001``)
``%%``     A literal ``%``
=========  ===================================================================

Anything else is emitted verbatim, matching :meth:`datetime.date.strftime`'s
forgiving behaviour for unknown directives.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Literal

from .calendar_data import (
    BS_MONTH_DAYS,
    VERIFIED_MAX_BS_YEAR,
    VERIFIED_MIN_BS_YEAR,
)
from .exceptions import InvalidBSDate

if TYPE_CHECKING:
    from .date import BSDate

__all__ = [
    "format_bs",
    "parse_bs",
    "to_devanagari",
    "to_ascii_digits",
    "MONTH_NAMES",
    "MONTH_ABBRS",
    "WEEKDAY_NAMES",
    "WEEKDAY_ABBRS",
    "DEVANAGARI_DIGITS",
]

#: Devanagari digits zero through nine, indexed by value.
DEVANAGARI_DIGITS = "०१२३४५६७८९"

_ASCII_TO_DEV = {ord(str(i)): DEVANAGARI_DIGITS[i] for i in range(10)}
_DEV_TO_ASCII = {ord(DEVANAGARI_DIGITS[i]): str(i) for i in range(10)}

#: Full month names, indexed by ``month - 1``, keyed by language.
MONTH_NAMES: dict[str, tuple[str, ...]] = {
    "en": (
        "Baishakh", "Jestha", "Ashadh", "Shrawan", "Bhadra", "Ashwin",
        "Kartik", "Mangsir", "Poush", "Magh", "Falgun", "Chaitra",
    ),
    "ne": (
        "वैशाख", "जेठ", "असार", "साउन", "भदौ", "असोज",
        "कात्तिक", "मंसिर", "पुस", "माघ", "फागुन", "चैत",
    ),
}

#: Abbreviated month names, indexed by ``month - 1``, keyed by language.
#:
#: The English abbreviations avoid the usual Ashadh/Ashwin collision (both
#: would be "Ash"), which would make ``%b`` ambiguous to parse.
MONTH_ABBRS: dict[str, tuple[str, ...]] = {
    "en": (
        "Bai", "Jes", "Asa", "Shr", "Bha", "Asw",
        "Kar", "Man", "Pou", "Mag", "Fal", "Cha",
    ),
    "ne": (
        "वैश", "जेठ", "असा", "साउ", "भदौ", "असो",
        "कात्", "मंसि", "पुस", "माघ", "फागु", "चैत",
    ),
}

#: Full weekday names, indexed Sunday == 0 (the Nepali week's first day).
WEEKDAY_NAMES: dict[str, tuple[str, ...]] = {
    "en": (
        "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
        "Saturday",
    ),
    "ne": (
        "आइतबार", "सोमबार", "मङ्गलबार", "बुधबार", "बिहीबार", "शुक्रबार",
        "शनिबार",
    ),
}

#: Abbreviated weekday names, indexed Sunday == 0.
WEEKDAY_ABBRS: dict[str, tuple[str, ...]] = {
    "en": ("Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"),
    "ne": ("आइत", "सोम", "मङ्गल", "बुध", "बिही", "शुक्र", "शनि"),
}

_LANGS = ("en", "ne")
_NUMERALS = ("ascii", "devanagari")


# Matches a directive: '%', an optional '-' padding suppressor, then a letter
# or a literal '%'.
_DIRECTIVE_RE = re.compile(r"%(-?)([A-Za-z%])")


def to_devanagari(value: str) -> str:
    """Convert ASCII digits in a string to Devanagari digits.

    Non-digit characters pass through untouched.

    Args:
        value: Any string.

    Returns:
        The string with ``0-9`` replaced by ``०-९``.

    Example:
        >>> to_devanagari("2081-01-01")
        '२०८१-०१-०१'
    """
    return value.translate(_ASCII_TO_DEV)


def to_ascii_digits(value: str) -> str:
    """Convert Devanagari digits in a string to ASCII digits.

    Non-digit characters pass through untouched.

    Args:
        value: Any string.

    Returns:
        The string with ``०-९`` replaced by ``0-9``.

    Example:
        >>> to_ascii_digits("२०८१")
        '2081'
    """
    return value.translate(_DEV_TO_ASCII)


def _check_lang(lang: str) -> None:
    """Validate a language code.

    Args:
        lang: The language code to check.

    Raises:
        InvalidBSDate: If ``lang`` is unsupported.
    """
    if lang not in _LANGS:
        raise InvalidBSDate(f"lang must be one of {_LANGS}, got {lang!r}")


def _day_of_year(year: int, month: int, day: int) -> int:
    """Return the 1-based day of the Bikram Sambat year.

    Args:
        year: Bikram Sambat year.
        month: Month number, 1 through 12.
        day: Day of month.

    Returns:
        The ordinal day within the year.
    """
    return sum(BS_MONTH_DAYS[year][: month - 1]) + day


def format_bs(
    value: BSDate,
    fmt: str,
    *,
    lang: Literal["en", "ne"] = "en",
    numerals: Literal["ascii", "devanagari"] = "ascii",
) -> str:
    """Format a Bikram Sambat date with a strftime-style format string.

    Args:
        value: The date to format.
        fmt: A format string; see the module docstring for directives.
        lang: Language for month and weekday names, ``"en"`` or ``"ne"``.
        numerals: Numeral system for digits, ``"ascii"`` or ``"devanagari"``.

    Returns:
        The formatted string.

    Raises:
        InvalidBSDate: If ``lang`` or ``numerals`` is unsupported.

    Example:
        >>> from django_bikram import BSDate
        >>> format_bs(BSDate(2081, 1, 1), "%d %B %Y")
        '01 Baishakh 2081'
        >>> format_bs(BSDate(2081, 1, 1), "%d %B %Y", lang="ne",
        ...           numerals="devanagari")
        '०१ वैशाख २०८१'
    """
    _check_lang(lang)
    if numerals not in _NUMERALS:
        raise InvalidBSDate(f"numerals must be one of {_NUMERALS}, got {numerals!r}")

    weekday = value.nepali_weekday()

    def render(match: re.Match[str]) -> str:
        """Render one directive."""
        dash, code = match.group(1), match.group(2)
        pad = not dash
        if code == "%":
            return "%"
        if code == "Y":
            return f"{value.year:04d}"
        if code == "y":
            return f"{value.year % 100:02d}"
        if code == "m":
            return f"{value.month:02d}" if pad else str(value.month)
        if code == "d":
            return f"{value.day:02d}" if pad else str(value.day)
        if code == "j":
            return f"{_day_of_year(value.year, value.month, value.day):03d}"
        if code == "B":
            return MONTH_NAMES[lang][value.month - 1]
        if code == "b":
            return MONTH_ABBRS[lang][value.month - 1]
        if code == "A":
            return WEEKDAY_NAMES[lang][weekday]
        if code == "a":
            return WEEKDAY_ABBRS[lang][weekday]
        # Unknown directive: emit verbatim, as datetime.strftime does.
        return match.group(0)

    out = _DIRECTIVE_RE.sub(render, fmt)
    return to_devanagari(out) if numerals == "devanagari" else out


# Regex fragments per directive. Names are captured so the parser can pick
# them out of the match by group name.
_DIGIT_CLASS = r"[0-9०-९]"

# Upper bound on the length of a string parse_bs() will attempt to match. No real
# formatted BS date — even one with a full weekday and month name in Devanagari —
# approaches this, so it rejects nothing legitimate. It exists as defence in depth:
# it caps the input the regex sees, so a pathological *format* string (many
# adjacent numeric directives) cannot be driven into slow backtracking by a long
# value. Format strings are trusted developer input (as in datetime.strptime), so
# this is belt-and-braces, not a load-bearing control.
_MAX_PARSE_INPUT = 256


def _name_alternation(names: tuple[str, ...]) -> str:
    """Build a regex alternation over names, longest first.

    Sorting by descending length stops a short name from shadowing a longer one
    that starts with it (e.g. ``जेठ`` vs a hypothetical ``जेठको``).

    Args:
        names: The candidate names.

    Returns:
        A regex alternation fragment.
    """
    return "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True))


def _resolve_two_digit_year(value: int) -> int:
    """Expand a two-digit Bikram Sambat year to four digits.

    ``%y`` is inherently ambiguous here: the verified range spans 109 years, so
    values 75-83 match both 19xx and 20xx (1975 and 2075 are both real). The
    tie is broken toward the **20xx** century, because 19xx BS ended in 1943 AD
    and essentially no live data uses it.

    The preference only applies when it can: 85-99 resolve to 19xx, since 2085+
    is outside the verified range. Values that land nowhere raise instead of
    guessing.

    Resolution is pinned to the **verified** range, not the working range, so
    installing provisional years never silently changes what a two-digit year
    means.

    Prefer ``%Y`` in any format you control. This exists for parsing input you
    do not.

    Args:
        value: A two-digit year, 0 through 99.

    Returns:
        The four-digit Bikram Sambat year.

    Raises:
        InvalidBSDate: If neither expansion falls in the verified range.
    """
    for century in (2000, 1900):
        candidate = century + value
        if VERIFIED_MIN_BS_YEAR <= candidate <= VERIFIED_MAX_BS_YEAR:
            return candidate
    raise InvalidBSDate(
        f"two-digit year {value:02d} does not map into the verified range "
        f"{VERIFIED_MIN_BS_YEAR}..{VERIFIED_MAX_BS_YEAR}; use %Y instead"
    )


def parse_bs(
    value: str,
    fmt: str,
    *,
    lang: Literal["en", "ne"] = "en",
    numerals: Literal["ascii", "devanagari", "auto"] = "auto",
) -> tuple[int, int, int]:
    """Parse a string into Bikram Sambat date components.

    Weekday directives (``%A``, ``%a``) are matched but not checked against the
    parsed date, mirroring :func:`datetime.datetime.strptime`.

    The format string ``fmt`` is trusted developer input, exactly as it is for
    :func:`datetime.datetime.strptime`; do not build it from untrusted data. A
    deliberately pathological format (many adjacent numeric directives) could make
    the underlying regex backtrack slowly. The ``value`` being parsed is untrusted
    and safe: it is length-bounded before matching.

    Args:
        value: The string to parse.
        fmt: A format string; see the module docstring for directives.
        lang: Language for month and weekday names, ``"en"`` or ``"ne"``.
        numerals: Numeral system of the digits. ``"auto"`` accepts ASCII or
            Devanagari, including a mix.

    Returns:
        A ``(year, month, day)`` tuple. The components are validated as a real
        date by :class:`~django_bikram.date.BSDate`, not here.

    Raises:
        InvalidBSDate: If the string does not match the format, if a required
            component is missing, or if a month name is unrecognised.

    Example:
        >>> parse_bs("01 Baishakh 2081", "%d %B %Y")
        (2081, 1, 1)
        >>> parse_bs("२०८१-०१-०१", "%Y-%m-%d")
        (2081, 1, 1)
    """
    _check_lang(lang)
    if numerals not in (*_NUMERALS, "auto"):
        raise InvalidBSDate(
            f"numerals must be one of {(*_NUMERALS, 'auto')}, got {numerals!r}"
        )
    if not isinstance(value, str):
        raise InvalidBSDate(f"expected a str to parse, got {type(value).__name__!r}")
    if len(value) > _MAX_PARSE_INPUT:
        raise InvalidBSDate(
            f"value is too long to be a date: {len(value)} characters "
            f"(maximum {_MAX_PARSE_INPUT})"
        )

    if numerals == "devanagari":
        digit = r"[०-९]"
    elif numerals == "ascii":
        digit = r"[0-9]"
    else:
        digit = _DIGIT_CLASS

    seen: list[str] = []

    def build(match: re.Match[str]) -> str:
        """Translate one directive into a regex fragment."""
        # group(1) is the optional '-' padding flag; it affects only how a value
        # is *rendered*, never what input matches, so the parser ignores it.
        code = match.group(2)
        if code == "%":
            return re.escape("%")
        if code in {"Y", "y", "m", "d", "j"}:
            widths = {"Y": 4, "y": 2, "m": 2, "d": 2, "j": 3}
            # %Y is fixed at four digits so it cannot swallow the digits of an
            # adjacent field (e.g. "20810101" for "%Y%m%d"). Every other numeric
            # directive accepts 1..width digits so both "1" and "01" parse; the
            # '-' padding flag only affects *formatting*, not what input matches,
            # which is why it does not appear here.
            frag = f"{digit}{{4}}" if code == "Y" else f"{digit}{{1,{widths[code]}}}"
            name = f"g{len(seen)}_{code}"
            seen.append(code)
            return f"(?P<{name}>{frag})"
        if code in {"B", "b", "A", "a"}:
            table = {
                "B": MONTH_NAMES,
                "b": MONTH_ABBRS,
                "A": WEEKDAY_NAMES,
                "a": WEEKDAY_ABBRS,
            }[code][lang]
            name = f"g{len(seen)}_{code}"
            seen.append(code)
            return f"(?P<{name}>{_name_alternation(table)})"
        return re.escape(match.group(0))

    # Escape the literal parts of the format, then substitute directives. We
    # escape first so that regex metacharacters in the literal text (like '.')
    # cannot leak through, and re-find directives in the escaped text.
    escaped = re.escape(fmt)
    # re.escape mangles '%' in older versions and '-' as '\-'; normalise the
    # directive shape back so _DIRECTIVE_RE can find them.
    escaped = escaped.replace("\\%", "%").replace("%\\-", "%-")
    pattern = _DIRECTIVE_RE.sub(build, escaped)

    match = re.fullmatch(pattern, value.strip(), re.UNICODE)
    if match is None:
        raise InvalidBSDate(
            f"{value!r} does not match format {fmt!r}"
            + (f" (lang={lang!r})" if lang != "en" else "")
        )

    year: int | None = None
    month: int | None = None
    day: int | None = None

    for name, text in match.groupdict().items():
        if text is None:  # pragma: no cover - all groups are required
            continue
        code = name.rsplit("_", 1)[1]
        if code in {"Y", "y", "m", "d", "j"}:
            number = int(to_ascii_digits(text))
            if code == "Y":
                year = number
            elif code == "y":
                year = _resolve_two_digit_year(number)
            elif code == "m":
                month = number
            elif code == "d":
                day = number
            # %j is matched but not used to derive the date; %Y/%m/%d win.
        elif code == "B":
            month = MONTH_NAMES[lang].index(text) + 1
        elif code == "b":
            month = MONTH_ABBRS[lang].index(text) + 1
        # %A / %a are matched and discarded, as the stdlib does.

    missing = [
        label
        for label, component in (("year", year), ("month", month), ("day", day))
        if component is None
    ]
    if missing:
        raise InvalidBSDate(
            f"format {fmt!r} does not supply {', '.join(missing)}; a complete "
            f"date needs a year, a month and a day"
        )

    assert year is not None and month is not None and day is not None
    return year, month, day

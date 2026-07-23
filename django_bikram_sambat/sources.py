"""Optional external data sources for the provisional calendar range.

An **alternative** to the astronomical predictor in :mod:`django_bikram_sambat.predict`
for years past the verified range.

`bikram-sambat <https://pypi.org/project/bikram-sambat/>`_ (MIT) is a separately
maintained Nepali date library whose table covers 1901-2199 BS. Its 1975-2083
rows match this package's verified table exactly; **past 2083 they are that
project's own computed values** -- a single, unverified source. It is no more
authoritative than the built-in predictor: the two disagree on every year past
2083, and neither is the official Panchanga. This adapter exists only so you can
*choose* which best-guess to install; both produce tables you feed to
:func:`django_bikram_sambat.calendar_data.install_provisional`.

Requires the optional dependency::

    pip install "django-bikram-sambat[bikram-sambat]"

Nothing here is imported by default, so the dependency stays opt-in.

Bringing your own data
----------------------
:func:`month_lengths_from_csv` reads a table you produced yourself -- from a
published Panchanga, a scrape, an internal dataset -- and derives month lengths
from it, using nothing but the standard library. This package never fetches
anything: a date library that makes network calls turns every request cycle into
a place your application can fail, and a parser that silently breaks yields
plausible wrong dates, which is the one outcome this package exists to prevent.
Gather the data out-of-band; hand the file to this function.

That also makes the *verification* step reproducible. Every year in the verified
table had to agree across two independent sources; this is how you check a third
one against it before proposing a year for promotion.
"""

from __future__ import annotations

import csv
import datetime
import os
from collections import defaultdict

from .calendar_data import MONTHS_IN_YEAR, VERIFIED_MAX_BS_YEAR

__all__ = ["bikram_sambat_table", "month_lengths_from_csv"]


def bikram_sambat_table(
    through_year: int = VERIFIED_MAX_BS_YEAR + 100,
) -> dict[int, tuple[int, ...]]:
    """Return `bikram-sambat`'s month lengths for years past the verified range.

    The result is shaped like
    :data:`~django_bikram_sambat.calendar_data.VERIFIED_BS_MONTH_DAYS` and covers
    ``VERIFIED_MAX_BS_YEAR + 1`` through ``through_year``, ready to hand to
    :func:`~django_bikram_sambat.calendar_data.install_provisional`.

    **This is unverified, single-source data** (see the module docstring). Treat
    it exactly like a prediction: fine for planning and display, never for a date
    where a one-day error matters. Installed years are flagged the same way the
    predictor's are -- ``is_verified`` is ``False`` and use raises
    :class:`~django_bikram_sambat.exceptions.ProvisionalDateWarning`.

    Args:
        through_year: The last BS year to include. Defaults to a century past
            the verified range.

    Returns:
        A mapping of BS year to twelve month lengths, contiguous from
        ``VERIFIED_MAX_BS_YEAR + 1``.

    Raises:
        ImportError: If the optional ``bikram-sambat`` package is not installed.
        ValueError: If ``through_year`` does not extend the range, or if
            ``bikram-sambat`` lacks a requested year or returns a malformed one.

    Example:
        >>> from django_bikram_sambat.calendar_data import install_provisional
        >>> install_provisional(bikram_sambat_table(2150))  # doctest: +SKIP
    """
    first = VERIFIED_MAX_BS_YEAR + 1
    if through_year < first:
        raise ValueError(
            f"through_year {through_year} is not past the verified range; the "
            f"provisional table starts at {first} BS"
        )
    try:
        from bikram_sambat.calendar import YEAR_MONTH_DAYS_BS
    except ImportError as exc:  # pragma: no cover - depends on the environment
        raise ImportError(
            "bikram_sambat_table() needs the optional 'bikram-sambat' package. "
            'Install it with: pip install "django-bikram-sambat[bikram-sambat]"'
        ) from exc

    table: dict[int, tuple[int, ...]] = {}
    for year in range(first, through_year + 1):
        if year not in YEAR_MONTH_DAYS_BS:
            raise ValueError(
                f"bikram-sambat has no data for BS {year} (its range ends "
                f"earlier); lower through_year"
            )
        row = tuple(int(n) for n in YEAR_MONTH_DAYS_BS[year])
        if len(row) != MONTHS_IN_YEAR or sum(row) not in (365, 366):
            raise ValueError(
                f"bikram-sambat returned a malformed year for BS {year}: {row}"
            )
        table[year] = row
    return table


def _parse_bs_components(row: dict[str, str], line: int) -> tuple[int, int, int]:
    """Pull the Bikram Sambat year/month/day out of one CSV row.

    Accepts either separate ``bs_year``/``bs_month``/``bs_day`` columns or a
    single ``bs_date`` of the form ``YYYY-M-D``, so a file does not have to be
    reshaped before it can be read.

    Args:
        row: The parsed CSV row.
        line: The 1-based line number, used in error messages.

    Returns:
        A ``(year, month, day)`` triple.

    Raises:
        ValueError: If neither form is present or the values are not integers.
    """
    if row.get("bs_year") and row.get("bs_month") and row.get("bs_day"):
        parts = (row["bs_year"], row["bs_month"], row["bs_day"])
    elif row.get("bs_date"):
        parts = tuple(row["bs_date"].split("-"))  # type: ignore[assignment]
        if len(parts) != 3:
            raise ValueError(f"line {line}: bs_date {row['bs_date']!r} is not YYYY-M-D")
    else:
        raise ValueError(
            f"line {line}: need either bs_year/bs_month/bs_day or bs_date columns"
        )
    try:
        return int(parts[0]), int(parts[1]), int(parts[2])
    except ValueError:
        raise ValueError(
            f"line {line}: non-integer Bikram Sambat date {parts!r}"
        ) from None


def month_lengths_from_csv(
    path: str | os.PathLike[str],
    *,
    from_year: int | None = None,
    through_year: int | None = None,
) -> dict[int, tuple[int, ...]]:
    """Derive Bikram Sambat month lengths from a CSV of BS dates.

    The file must have one row per day, with a ``bs_date`` column (``YYYY-M-D``)
    or separate ``bs_year``/``bs_month``/``bs_day`` columns, plus an ``ad_date``
    column in ISO format. Extra columns are ignored, so the output of a scraper
    that also captures panchang or festivals can be passed through unchanged.

    Only **complete** years are returned: a year is included when it has twelve
    months, each numbered day present from 1 with no gaps, and a total of 365 or
    366 days. A partially scraped year is dropped rather than reported short,
    because a short month is indistinguishable from a missing row.

    The Gregorian column is not merely along for the ride -- it is checked. Every
    consecutive pair of Bikram Sambat days must advance the AD date by exactly
    one, across the whole ordered file. That is what catches a truncated fetch,
    a duplicated page or a silently mis-parsed row, none of which the BS side
    alone would reveal.

    Args:
        path: The CSV file to read.
        from_year: Ignore years before this one. Defaults to no lower bound.
        through_year: Ignore years after this one. Defaults to no upper bound.

    Returns:
        A mapping of BS year to its twelve month lengths, ready to compare
        against :data:`~django_bikram_sambat.calendar_data.VERIFIED_BS_MONTH_DAYS`
        or, once sliced to a contiguous run past the verified range, to hand to
        :func:`~django_bikram_sambat.calendar_data.install_provisional`.

    Raises:
        ValueError: If the file is empty, lacks the required columns, contains a
            malformed date, or if the Gregorian dates do not advance by exactly
            one day per Bikram Sambat day.

    Example:
        >>> table = month_lengths_from_csv("hamropatro.csv")   # doctest: +SKIP
        >>> table[2085]                                         # doctest: +SKIP
        (31, 31, 32, 31, 31, 31, 30, 29, 30, 29, 30, 30)
    """
    ad_by_bs: dict[tuple[int, int, int], datetime.date] = {}
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"{path}: file is empty")
        for line, row in enumerate(reader, start=2):
            year, month, day = _parse_bs_components(row, line)
            raw = (row.get("ad_date") or "").strip()
            if not raw:
                raise ValueError(f"line {line}: missing ad_date")
            try:
                ad = datetime.date.fromisoformat(raw)
            except ValueError:
                raise ValueError(f"line {line}: ad_date {raw!r} is not ISO") from None
            ad_by_bs[(year, month, day)] = ad

    if not ad_by_bs:
        raise ValueError(f"{path}: no rows")

    # One day of Bikram Sambat is one day of Gregorian. Anything else means the
    # file is incomplete or misparsed, whatever the BS columns claim.
    ordered = sorted(ad_by_bs.items())
    for (earlier, prev_ad), (later, next_ad) in zip(ordered, ordered[1:], strict=False):
        if (next_ad - prev_ad).days != 1:
            raise ValueError(
                f"BS {earlier} -> {later} moves the Gregorian date from "
                f"{prev_ad} to {next_ad}, a gap of {(next_ad - prev_ad).days} "
                f"days; the file is incomplete or misparsed"
            )

    days_seen: dict[int, dict[int, set[int]]] = defaultdict(lambda: defaultdict(set))
    for year, month, day in ad_by_bs:
        days_seen[year][month].add(day)

    table: dict[int, tuple[int, ...]] = {}
    for year in sorted(days_seen):
        if from_year is not None and year < from_year:
            continue
        if through_year is not None and year > through_year:
            continue
        months = days_seen[year]
        if set(months) != set(range(1, MONTHS_IN_YEAR + 1)):
            continue  # incomplete year
        lengths = []
        for month in range(1, MONTHS_IN_YEAR + 1):
            days = months[month]
            if days != set(range(1, max(days) + 1)):
                break  # a gap mid-month: treat the year as incomplete
            lengths.append(max(days))
        else:
            if sum(lengths) in (365, 366):
                table[year] = tuple(lengths)
    return table

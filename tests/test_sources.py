"""Tests for the optional bikram-sambat provisional data adapter.

These require the optional ``bikram-sambat`` package, which the ``[dev]`` extra
installs. Activation mutates process-global calendar state, so that path runs in
a clean subprocess.
"""

from __future__ import annotations

import datetime
import subprocess
import sys
import textwrap

import pytest

from django_bikram_sambat.calendar_data import MONTHS_IN_YEAR, VERIFIED_MAX_BS_YEAR
from django_bikram_sambat.predict import predicted_month_days
from django_bikram_sambat.sources import bikram_sambat_table


def test_table_covers_the_requested_span() -> None:
    """The table is contiguous from just past the verified range."""
    table = bikram_sambat_table(through_year=2100)
    assert min(table) == VERIFIED_MAX_BS_YEAR + 1
    assert max(table) == 2100


def test_every_year_is_structurally_valid() -> None:
    """Each row has twelve months totalling 365 or 366 days."""
    for year, lengths in bikram_sambat_table(through_year=2150).items():
        assert len(lengths) == MONTHS_IN_YEAR, year
        assert sum(lengths) in (365, 366), (year, sum(lengths))


def test_extraction_matches_the_source_exactly() -> None:
    """What we return is exactly what bikram-sambat holds -- no transformation."""
    from bikram_sambat.calendar import YEAR_MONTH_DAYS_BS

    table = bikram_sambat_table(through_year=2090)
    for year, lengths in table.items():
        assert lengths == tuple(int(n) for n in YEAR_MONTH_DAYS_BS[year])


def test_before_the_range_is_rejected() -> None:
    """Asking for a table that does not extend the range is an error."""
    with pytest.raises(ValueError, match="not past the verified range"):
        bikram_sambat_table(through_year=VERIFIED_MAX_BS_YEAR)


def test_it_is_a_genuinely_independent_guess() -> None:
    """bikram-sambat and the built-in predictor disagree past the verified range.

    This is the whole point of offering both: they are two independent
    unverified sources, and neither is authoritative. If they ever fully agreed,
    that agreement would itself be worth promoting to verified.
    """
    disagreements = sum(
        1
        for year, lengths in bikram_sambat_table(through_year=2100).items()
        if lengths != predicted_month_days(year)
    )
    assert disagreements > 0


def _run(script: str) -> str:
    """Run a snippet in a clean subprocess and return stdout."""
    result = subprocess.run(
        [sys.executable, "-c", textwrap.dedent(script)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


def test_installs_as_an_alternative_provisional_source() -> None:
    """The table feeds install_provisional() and its dates are flagged."""
    out = _run(
        """
        import warnings
        import django_bikram_sambat as b
        from django_bikram_sambat import BSDate, ProvisionalDateWarning
        from django_bikram_sambat.calendar_data import install_provisional
        from django_bikram_sambat.sources import bikram_sambat_table
        install_provisional(bikram_sambat_table(through_year=2100))
        assert b.MAX_BS_YEAR == 2100, b.MAX_BS_YEAR
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            d = BSDate(2090, 1, 1)
            ad = d.to_ad()
        assert d.is_verified is False
        assert BSDate.from_ad(ad) == d
        assert any(issubclass(w.category, ProvisionalDateWarning) for w in caught)
        print("ok")
        """
    )
    assert out.strip() == "ok"


# --- month_lengths_from_csv ---------------------------------------------


def _calendar_csv(tmp_path, years, *, minimal=False, drop=()):
    """Write the package's own verified calendar out in scraper CSV shape."""
    import csv

    from django_bikram_sambat import BSDate
    from django_bikram_sambat.calendar_data import VERIFIED_BS_MONTH_DAYS

    path = tmp_path / ("minimal.csv" if minimal else "full.csv")
    columns = (
        ["bs_date", "ad_date"]
        if minimal
        else ["bs_year", "bs_month", "bs_day", "ad_date", "weekday"]
    )
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, columns)
        writer.writeheader()
        for year in years:
            for month, length in enumerate(VERIFIED_BS_MONTH_DAYS[year], 1):
                for day in range(1, length + 1):
                    if (year, month, day) in drop:
                        continue
                    ad = BSDate(year, month, day).to_ad()
                    row = {
                        "bs_year": year, "bs_month": month, "bs_day": day,
                        "bs_date": f"{year}-{month}-{day}",
                        "ad_date": ad.isoformat(), "weekday": ad.strftime("%A"),
                    }
                    writer.writerow({k: row[k] for k in columns})
    return path


def test_csv_round_trips_the_verified_table(tmp_path) -> None:
    """Derived month lengths must equal the table they were generated from.

    The strongest available check: emit the whole verified calendar as a CSV,
    read it back, and require an exact match. Any off-by-one in the derivation
    shows up immediately.
    """
    from django_bikram_sambat.calendar_data import VERIFIED_BS_MONTH_DAYS
    from django_bikram_sambat.sources import month_lengths_from_csv

    years = sorted(VERIFIED_BS_MONTH_DAYS)
    path = _calendar_csv(tmp_path, years)
    assert month_lengths_from_csv(path) == VERIFIED_BS_MONTH_DAYS


def test_csv_accepts_the_minimal_two_column_shape(tmp_path) -> None:
    """A bs_date/ad_date pair is enough; the split columns are optional."""
    from django_bikram_sambat.calendar_data import VERIFIED_BS_MONTH_DAYS
    from django_bikram_sambat.sources import month_lengths_from_csv

    years = [2081, 2082, 2083]
    path = _calendar_csv(tmp_path, years, minimal=True)
    expected = {y: VERIFIED_BS_MONTH_DAYS[y] for y in years}
    assert month_lengths_from_csv(path) == expected


def test_csv_year_bounds(tmp_path) -> None:
    """from_year/through_year slice without re-reading the file differently."""
    from django_bikram_sambat.sources import month_lengths_from_csv

    path = _calendar_csv(tmp_path, [2080, 2081, 2082, 2083])
    got = month_lengths_from_csv(path, from_year=2081, through_year=2082)
    assert sorted(got) == [2081, 2082]


def test_csv_rejects_a_gap_in_the_gregorian_sequence(tmp_path) -> None:
    """A missing row is invisible in the BS columns but not in the AD ones.

    Dropping one day leaves the surrounding BS numbering looking plausible --
    the month simply appears one day shorter. Only the Gregorian side reveals
    it, which is why that check exists.
    """
    from django_bikram_sambat.sources import month_lengths_from_csv

    path = _calendar_csv(tmp_path, [2081], drop={(2081, 5, 10)})
    with pytest.raises(ValueError, match="incomplete or misparsed"):
        month_lengths_from_csv(path)


def test_csv_drops_an_incomplete_year_rather_than_reporting_it_short(
    tmp_path,
) -> None:
    """A half-scraped year must not look like a real 6-month year."""
    import csv

    from django_bikram_sambat import BSDate
    from django_bikram_sambat.sources import month_lengths_from_csv

    path = tmp_path / "partial.csv"
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, ["bs_date", "ad_date"])
        writer.writeheader()
        day = BSDate(2081, 1, 1)
        for _ in range(120):  # four months in, then stop
            writer.writerow(
                {"bs_date": f"{day.year}-{day.month}-{day.day}",
                 "ad_date": day.to_ad().isoformat()}
            )
            day = day + datetime.timedelta(days=1)
    assert month_lengths_from_csv(path) == {}


@pytest.mark.parametrize(
    ("rows", "match"),
    [
        ("bs_date,ad_date\n2081-1-1,nonsense\n", "is not ISO"),
        ("bs_date,ad_date\n2081-1-1,\n", "missing ad_date"),
        ("bs_date,ad_date\n2081-x-1,2024-04-13\n", "non-integer"),
        ("bs_date,ad_date\n2081-1,2024-04-13\n", "not YYYY-M-D"),
        ("weekday,ad_date\nSunday,2024-04-13\n", "bs_year/bs_month/bs_day or bs_date"),
        ("bs_date,ad_date\n", "no rows"),
    ],
)
def test_csv_rejects_malformed_input(tmp_path, rows: str, match: str) -> None:
    """Bad input fails loudly with the offending line, never silently."""
    from django_bikram_sambat.sources import month_lengths_from_csv

    path = tmp_path / "bad.csv"
    path.write_text(rows, encoding="utf-8")
    with pytest.raises(ValueError, match=match):
        month_lengths_from_csv(path)


def test_csv_output_feeds_install_provisional(tmp_path) -> None:
    """The derived table is the shape install_provisional() accepts.

    Uses predicted years so the test needs no network and no scrape, but the
    path is identical for a real file: derive, slice to a contiguous run past
    the verified range, install.
    """
    from django_bikram_sambat.calendar_data import MONTHS_IN_YEAR, VERIFIED_MAX_BS_YEAR
    from django_bikram_sambat.sources import month_lengths_from_csv

    path = _calendar_csv(tmp_path, [2081, 2082])
    table = month_lengths_from_csv(path)
    for lengths in table.values():
        assert len(lengths) == MONTHS_IN_YEAR
        assert sum(lengths) in (365, 366)
    assert all(isinstance(n, int) for lengths in table.values() for n in lengths)
    assert max(table) <= VERIFIED_MAX_BS_YEAR

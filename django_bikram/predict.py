"""Astronomical *prediction* of Bikram Sambat month lengths -- **provisional**.

Read this before using anything here.
=====================================

The verified table (:mod:`django_bikram.calendar_data`) stops at
:data:`~django_bikram.calendar_data.VERIFIED_MAX_BS_YEAR` BS because that is
where two independent published sources still agree. Beyond it, month lengths
are *not published yet* -- the Panchanga Nirnayak Samiti sets them
astronomically and releases them roughly a year ahead. This module fills that
gap by **computing** them, so a project can keep working past the verified
horizon. What it returns is a prediction, not a fact.

How good is the prediction?
---------------------------
Measured against the 110 verified years (1975-2084 BS), a self-check anyone can
re-run via :func:`validate`:

* **~87% of months** get the exact right length;
* **the rest are wrong by exactly one day** -- never more;
* only about **53% of years** come out completely correct.

That residual is not a bug to be tuned away. The Bikram Sambat month boundary is
the instant the true sun (by Surya-Siddhanta reckoning) crosses into the next
sidereal sign, assigned to a civil day by a traditional rule, and the official
committee occasionally applies manual corrections. An independent computation
using the same Surya-Siddhanta model still lands one day to either side of the
official value about one month in eight. Modern-astronomy models (Meeus + a
Lahiri ayanamsa) do *worse* here -- ~73% -- precisely because the calendar is
not defined by modern astronomy.

What this means for you
-----------------------
* **Never treat a predicted date as authoritative.** A due date, a legal
  deadline, an invoice date past the verified range can be off by a day.
* **Do use it for planning and display** where a one-day slip is tolerable, and
  replace it with verified rows the moment the Samiti publishes them.
* Predicted years are **not installed into the calendar automatically**. Every
  BS date this package produces stays verified unless you opt in by hand -- see
  :func:`build_provisional_table` and the ``PROVISIONAL_BS_MONTH_DAYS`` note in
  :mod:`django_bikram.calendar_data`. When a predicted year *is* installed, using
  it raises :class:`~django_bikram.exceptions.ProvisionalDateWarning`.

The model
---------
Surya-Siddhanta mean solar longitude with the classical manda (equation of
centre) correction, crossed against the twelve sidereal signs, with the sign
ingress assigned to a Nepal civil day by a fixed near-midnight threshold. The
two free constants (:data:`_AYANAMSA_FIT` and :data:`_DAY_THRESHOLD_HOURS`) were
fit to the verified range; they are documented, not magic, and re-fitting them
cannot push past the ~87% ceiling above.
"""

from __future__ import annotations

import datetime
import math

from .calendar_data import (
    ANCHOR_AD,
    MONTHS_IN_YEAR,
    VERIFIED_BS_MONTH_DAYS,
    VERIFIED_MAX_BS_YEAR,
    VERIFIED_MIN_BS_YEAR,
)

__all__ = [
    "predicted_month_days",
    "build_provisional_table",
    "validate",
]

# -- Surya-Siddhanta constants ------------------------------------------------
# Ratios that define the mean solar motion (a Mahayuga is 4,320,000 years).
_CIVIL_DAYS_PER_MAHAYUGA = 1_577_917_828.0
_SUN_REVOLUTIONS_PER_MAHAYUGA = 4_320_000.0
#: Julian Day of the Kali Yuga epoch (mean sunrise at Ujjain), the zero of the
#: ahargana day-count from which mean longitude is reckoned.
_KALI_EPOCH_JD = 588_465.5
#: Sun's mandocca (apogee) longitude in degrees. Its motion over a single
#: century is a few thousandths of a degree, negligible here, so it is fixed.
_SUN_APOGEE_DEG = 77.25
#: Circumference of the sun's manda epicycle in degrees; sets the amplitude of
#: the equation of centre (max correction ~2.23 deg).
_SUN_EPICYCLE_DEG = 14.0

# -- constants fit to the verified range (see module docstring) ---------------
#: Constant longitude offset (deg) folded into the ayanamsa, fit so the computed
#: ingresses best reproduce 1975-2083 BS.
_AYANAMSA_FIT = 0.18
#: Hours after Nepal midnight before which a sign ingress still counts toward
#: the day that is ending. Fit to the verified range; ~40 minutes.
_DAY_THRESHOLD_HOURS = 0.67
#: Nepal Standard Time offset as a fraction of a day (UTC+05:45).
_NPT_DAY_FRACTION = (5 * 60 + 45) / (24 * 60)


def _julian_day(date: datetime.date) -> float:
    """Return the Julian Day number at 00:00 UT of ``date``.

    Args:
        date: A proleptic-Gregorian date.

    Returns:
        The Julian Day at midnight UT.
    """
    year, month, day = date.year, date.month, date.day
    if month <= 2:
        year -= 1
        month += 12
    a = year // 100
    b = 2 - a + a // 4
    return (
        math.floor(365.25 * (year + 4716))
        + math.floor(30.6001 * (month + 1))
        + day
        + b
        - 1524.5
    )


def _sidereal_sun_longitude(jd: float) -> float:
    """Return the Surya-Siddhanta true sidereal solar longitude in degrees.

    Args:
        jd: Julian Day (UT).

    Returns:
        The sun's true longitude, 0 through 360 degrees, measured from the
        sidereal Aries point.
    """
    ahargana = jd - _KALI_EPOCH_JD
    mean = (
        ahargana
        * _SUN_REVOLUTIONS_PER_MAHAYUGA
        / _CIVIL_DAYS_PER_MAHAYUGA
        * 360.0
    ) % 360.0
    anomaly = math.radians(mean - _SUN_APOGEE_DEG)
    equation = math.degrees(
        math.asin((_SUN_EPICYCLE_DEG / 360.0) * math.sin(anomaly))
    )
    return (mean - equation + _AYANAMSA_FIT) % 360.0


def _ingress_jd(sign_index: int, guess_jd: float) -> float:
    """Return the UT Julian Day the sun enters sidereal sign ``sign_index``.

    Args:
        sign_index: Which 30-degree ingress; longitude target is
            ``(sign_index * 30) mod 360``.
        guess_jd: A Julian Day within ~20 days of the crossing, used to seed
            the bisection.

    Returns:
        The Julian Day of the ingress.
    """
    target = (sign_index * 30) % 360

    def offset(jd: float) -> float:
        diff = (_sidereal_sun_longitude(jd) - target) % 360
        return diff - 360 if diff > 180 else diff

    low, high = guess_jd - 20.0, guess_jd + 20.0
    f_low = offset(low)
    for _ in range(60):  # 40-day bracket to <1e-16 days: comfortably exact
        mid = (low + high) / 2
        f_mid = offset(mid)
        if f_low * f_mid <= 0:
            high = mid
        else:
            low, f_low = mid, f_mid
    return (low + high) / 2


def _month_start_ordinals(month_count: int) -> list[int]:
    """Return civil-day ordinals (from the anchor) of successive month starts.

    Ordinal 0 is 1 Baishakh of :data:`~django_bikram.calendar_data.ANCHOR_AD`'s
    year. Each entry is the whole-day offset from the anchor at which a solar
    month begins, so consecutive differences are month lengths.

    Args:
        month_count: How many month starts to compute (one more than the number
            of months you want lengths for).

    Returns:
        A strictly increasing list of integer day ordinals, length
        ``month_count``.
    """
    anchor_jd = _julian_day(ANCHOR_AD)
    starts: list[int] = []
    for k in range(month_count):
        ingress = _ingress_jd(k, anchor_jd + k * 30.436_8)
        local = ingress + _NPT_DAY_FRACTION
        civil = math.floor(local + 0.5)  # civil day number (midnight-based)
        hours_after_midnight = (local + 0.5 - civil) * 24.0
        if hours_after_midnight >= _DAY_THRESHOLD_HOURS:
            civil += 1
        starts.append(civil - int(anchor_jd))
    return starts


def _year_lengths(first_bs_year: int, year_count: int) -> dict[int, tuple[int, ...]]:
    """Compute predicted month lengths for a run of consecutive BS years.

    Args:
        first_bs_year: The BS year the run starts at. Must be
            :data:`~django_bikram.calendar_data.VERIFIED_MIN_BS_YEAR` or later,
            since the ingress walk is anchored there.
        year_count: How many consecutive years to compute.

    Returns:
        A mapping of BS year to its twelve predicted month lengths.
    """
    skip_years = first_bs_year - VERIFIED_MIN_BS_YEAR
    months = (skip_years + year_count) * MONTHS_IN_YEAR
    starts = _month_start_ordinals(months + 1)
    table: dict[int, tuple[int, ...]] = {}
    for offset in range(year_count):
        base = (skip_years + offset) * MONTHS_IN_YEAR
        lengths = tuple(
            starts[base + m + 1] - starts[base + m] for m in range(MONTHS_IN_YEAR)
        )
        table[first_bs_year + offset] = lengths
    return table


def predicted_month_days(bs_year: int) -> tuple[int, ...]:
    """Return the twelve *predicted* month lengths for a Bikram Sambat year.

    The result is a prediction (see the module docstring): about one month in
    eight is a day out. For years within the verified range this still returns
    the *computed* value, which is the honest thing to expose from a predictor;
    use :data:`~django_bikram.calendar_data.VERIFIED_BS_MONTH_DAYS` for the
    attested lengths.

    Args:
        bs_year: A Bikram Sambat year at or after
            :data:`~django_bikram.calendar_data.VERIFIED_MIN_BS_YEAR`.

    Returns:
        Twelve month lengths, Baishakh (index 0) through Chaitra.

    Raises:
        ValueError: If ``bs_year`` precedes the anchor year, which the model
            cannot walk back before.

    Example:
        >>> lengths = predicted_month_days(2090)
        >>> len(lengths), sum(lengths) in (365, 366)
        (12, True)
    """
    if bs_year < VERIFIED_MIN_BS_YEAR:
        raise ValueError(
            f"predictions are anchored at {VERIFIED_MIN_BS_YEAR} BS and cannot "
            f"run backwards to {bs_year}"
        )
    return _year_lengths(bs_year, 1)[bs_year]


def build_provisional_table(
    through_year: int = VERIFIED_MAX_BS_YEAR + 100,
) -> dict[int, tuple[int, ...]]:
    """Predict month lengths for every year past the verified range.

    This is the "give me the next hundred years" entry point. It returns a table
    shaped exactly like :data:`~django_bikram.calendar_data.VERIFIED_BS_MONTH_DAYS`,
    covering ``VERIFIED_MAX_BS_YEAR + 1`` through ``through_year`` inclusive, so
    it can be dropped straight into
    :data:`~django_bikram.calendar_data.PROVISIONAL_BS_MONTH_DAYS`.

    Every row it returns is a prediction. Each is internally consistent (twelve
    months totalling 365 or 366 days), but individual month lengths carry the
    one-day uncertainty documented for this module.

    Args:
        through_year: The last BS year to predict. Defaults to a century past
            the verified range.

    Returns:
        A mapping of BS year to twelve predicted month lengths, contiguous from
        ``VERIFIED_MAX_BS_YEAR + 1``.

    Raises:
        ValueError: If ``through_year`` is not past the verified range.

    Example:
        >>> table = build_provisional_table(through_year=2183)
        >>> min(table), max(table)
        (2085, 2183)
        >>> all(sum(v) in (365, 366) and len(v) == 12 for v in table.values())
        True
    """
    first = VERIFIED_MAX_BS_YEAR + 1
    if through_year < first:
        raise ValueError(
            f"through_year {through_year} is not past the verified range; the "
            f"provisional table starts at {first} BS"
        )
    return _year_lengths(first, through_year - first + 1)


def validate() -> dict[str, object]:
    """Re-derive the predictor's accuracy against the verified years.

    Runs the model over the whole verified range and compares it, month by
    month, to :data:`~django_bikram.calendar_data.VERIFIED_BS_MONTH_DAYS`. This
    is the number to trust -- and to re-run if the constants ever change -- not
    a claim in a docstring.

    Returns:
        A report with keys ``months_total``, ``months_exact``,
        ``month_accuracy`` (0-1), ``years_total``, ``years_exact``,
        ``max_error_days`` (the largest absolute month-length error, which
        should be 1), and ``error_histogram`` (signed error -> count).

    Example:
        >>> report = validate()
        >>> report["max_error_days"]
        1
        >>> report["month_accuracy"] > 0.85
        True
    """
    predicted = _year_lengths(
        VERIFIED_MIN_BS_YEAR, VERIFIED_MAX_BS_YEAR - VERIFIED_MIN_BS_YEAR + 1
    )
    months_total = months_exact = years_exact = 0
    max_error = 0
    histogram: dict[int, int] = {}
    for year in range(VERIFIED_MIN_BS_YEAR, VERIFIED_MAX_BS_YEAR + 1):
        truth = VERIFIED_BS_MONTH_DAYS[year]
        guess = predicted[year]
        if guess == truth:
            years_exact += 1
        for got, want in zip(guess, truth, strict=True):
            months_total += 1
            error = got - want
            histogram[error] = histogram.get(error, 0) + 1
            max_error = max(max_error, abs(error))
            if error == 0:
                months_exact += 1
    return {
        "months_total": months_total,
        "months_exact": months_exact,
        "month_accuracy": months_exact / months_total,
        "years_total": VERIFIED_MAX_BS_YEAR - VERIFIED_MIN_BS_YEAR + 1,
        "years_exact": years_exact,
        "max_error_days": max_error,
        "error_histogram": dict(sorted(histogram.items())),
    }

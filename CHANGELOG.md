# Changelog

All notable changes to this project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Verified 2084 BS.** The verified range now runs 1975–2084 BS
  (through 12 April 2028), up from 2083. 2084 was cross-checked between
  hamropatro.com and `nepali-datetime` (identical for all twelve months;
  `bikram-sambat` is the lone outlier and chains one day short). This pushes the
  `DateOutOfRange` horizon — and `BSDate.today()`'s expiry — out by a full year.

- `django_bikram.sources.bikram_sambat_table()` — reads the MIT-licensed
  `bikram-sambat` table as an *alternative* provisional source past the verified
  range, for callers who prefer it to the built-in predictor. Opt-in extra:
  `pip install django-bikram[bikram-sambat]`. Still single-source and unverified.
- Django 6.0 support: tested in CI and added to the classifiers.

### Fixed

- `mypy` now passes on the whole package under Django 6.0 without stubs (typed
  the form widget's context; marked the DRF field's always-raising paths
  terminal). Added an English `docs/quickstart.md` alongside the Nepali one.

## [0.1.0] - 2026-07-18

Initial release.

### Added

- `BSDate`: an immutable, hashable, totally ordered Bikram Sambat date with a
  `datetime.date`-shaped API — `weekday()`, `isoformat()`, `replace()`,
  `timedelta` arithmetic, and `BSDate - BSDate -> timedelta`.
- AD ↔ BS conversion (`django_bikram.convert`) via day-offset arithmetic from a
  single anchor. `O(log years)` per conversion; never walks day by day.
- Verified calendar data for **1975–2083 BS** (1918-04-13 – 2027-04-13 AD),
  cross-checked between two independent MIT-licensed sources. Dates outside the
  range raise `DateOutOfRange` rather than being extrapolated.
- Two-tier calendar data: `VERIFIED_BS_MONTH_DAYS` (two-source attested) versus
  an opt-in `PROVISIONAL_BS_MONTH_DAYS` (computed). `is_verified_year()` and
  `BSDate.is_verified` report which tier a date belongs to.
- `django_bikram.predict`: a Surya-Siddhanta month-length predictor for years
  past the verified range. `validate()` backtests it against the 109 verified
  years (~87% of months exact, remainder ±1 day, 58/109 years fully correct);
  `build_provisional_table()` returns the predicted table. Enable predicted
  years with the `DJANGO_BIKRAM_PROVISIONAL_THROUGH_YEAR` environment variable
  or `install_provisional()`; using one raises `ProvisionalDateWarning`.
  Predictions are never presented as verified.
- `django_bikram.formatting`: strftime-style formatting and parsing with
  independent language (English/Nepali) and numeral (ASCII/Devanagari) switches.
  Directives: `%Y %y %m %-m %d %-d %B %b %A %a %j %%`.
- `django_bikram.django.fields.BSDateField`: a `models.DateField` subclass that
  stores a native Gregorian `date` and exposes a `BSDate`, preserving indexes,
  range queries, ordering, aggregation and DB-side date functions.
- `django_bikram.django.forms`: `BSDateField` form field and `BSDateInput` widget.
- `django_bikram.django.drf`: DRF serializer field, import-guarded as an optional
  extra, plus `register_serializer_field()` for `ModelSerializer`.
- `django_bikram.django.lookups`: `bs_year_q` / `bs_month_q` / `bs_year_bounds` /
  `bs_month_bounds` — index-friendly half-open range helpers.
- Migration serializer for `BSDate`, so `default=BSDate(...)` works.
- `py.typed`: the package ships inline type information and passes `mypy --strict`.
- Bilingual documentation: English and Nepali README plus a Nepali quickstart.

### Deliberately not included

- `__bs_year` / `__bs_month` query transforms. See the README section
  "Why there is no `__bs_year` lookup" — the range helpers are exact and use
  the index; a transform would not.
- Bikram Sambat time/datetime types. The calendar defines days, not clocks;
  use an ordinary `DateTimeField` for instants.

# Changelog

All notable changes to this project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- `BSDate.fromisoformat()` now accepts only ASCII and Devanagari digits, matching
  `strptime()`/`parse_bs()`. Previously fullwidth digits (`"２０８１-01-01"`) parsed
  through `fromisoformat` but were rejected by the other parse paths — the two
  entry points now agree on the numeral systems this package speaks.

### Security

- `parse_bs()`/`strptime()` now length-bound the value before matching, as defence
  in depth: a pathological format string (many adjacent numeric directives) can no
  longer be driven into slow regex backtracking by a long value. Format strings
  remain trusted developer input, as with `datetime.strptime`.

## [0.2.0] - 2026-07-19

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

- **`BSDateField.bulk_update()` and `update(field=F(...))`** no longer crash:
  `get_db_prep_save` now passes resolved query expressions through instead of
  routing them into `to_python`.
- **`auto_now` / `auto_now_add` under `USE_TZ=False`** no longer crash;
  `pre_save` falls back to the plain local date where `localdate()` would raise.
- **`import django_bikram` under `-W error`** with the provisional env var set no
  longer crashes (the `BSDate.max` sentinel no longer emits a warning at import),
  and copying/pickling a provisional `BSDate` no longer re-emits it.
- `%y` two-digit-year parsing is pinned to the *verified* range, so installing
  provisional years never silently changes what it resolves to.
- `days_in_year()` rejects non-`int` years like `days_in_month()` does; the
  provisional env var rejects an implausibly large (typo'd) year instead of
  hanging import.
- `mypy` now passes on the whole package under Django 6.0 without stubs (typed
  the form widget's context; marked the DRF field's always-raising paths
  terminal). Added an English `docs/quickstart.md` alongside the Nepali one.

### Packaging

- Modernized metadata: `License-Expression: MIT` (PEP 639), dropped the untested
  Django 5.0/5.1 classifiers, absolute README links (render on PyPI), SHA-pinned
  GitHub Actions with Dependabot, and a concurrency guard on the publish job.

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

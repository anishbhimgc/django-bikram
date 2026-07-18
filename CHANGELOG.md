# Changelog

All notable changes to this project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- **Import package renamed `bikram` → `django_bikram`** (the distribution stays
  `django-bikram`). The old top-level `bikram` name collided with an unrelated
  existing PyPI package; `django_bikram` matches the distribution and collides
  with nothing. Update imports: `from django_bikram import BSDate`.

### Added

- **Two-tier calendar data.** `VERIFIED_BS_MONTH_DAYS` (1975–2083, two-source
  attested) is now separate from an opt-in `PROVISIONAL_BS_MONTH_DAYS`
  (computed). `is_verified_year()` and `BSDate.is_verified` report which tier a
  date belongs to; `VERIFIED_MAX_BS_YEAR` / `VERIFIED_MAX_AD_DATE` expose the
  attested bound independently of any extension.
- **`django_bikram.predict`** — a Surya-Siddhanta month-length predictor for
  years past the verified range. `validate()` backtests it against the 109
  verified years (≈87% of months exact, remainder ±1 day, 58/109 years fully
  correct); `build_provisional_table(through_year)` returns the predicted table.
  Predictions are never presented as verified.
- **Provisional activation.** Set `DJANGO_BIKRAM_PROVISIONAL_THROUGH_YEAR` (read
  at import) or call `calendar_data.install_provisional()` at startup to accept
  flagged dates past 2083. Each such date raises the new
  `ProvisionalDateWarning`; `warnings` filters silence or harden it.

### Fixed

- `BSDate`'s `__slots__` members are now annotated, so the core passes
  `mypy --strict`. `mypy django_bikram/` is clean across the whole package.
- Corrected a broken `check_bs_date` doctest and removed a dead branch in the
  format-string parser. `mypy` and `ruff` are now part of the `[dev]` extra and
  the documented dev workflow.

## [0.1.0] - 2026-07-15

Initial release.

### Added

- `BSDate`: an immutable, hashable, totally ordered Bikram Sambat date with a
  `datetime.date`-shaped API — `weekday()`, `isoformat()`, `replace()`,
  `timedelta` arithmetic, and `BSDate - BSDate -> timedelta`.
- AD ↔ BS conversion (`django_bikram.convert`) via day-offset arithmetic from a single
  anchor. `O(log years)` per conversion; never walks day by day.
- Verified calendar data for **1975–2083 BS** (1918-04-13 – 2027-04-13 AD),
  cross-checked between two independent MIT-licensed sources. Dates outside the
  range raise `DateOutOfRange` rather than being extrapolated.
- `django_bikram.formatting`: strftime-style formatting and parsing with independent
  language (English/Nepali) and numeral (ASCII/Devanagari) switches.
  Directives: `%Y %y %m %-m %d %-d %B %b %A %a %j %%`.
- `django_bikram.django.fields.BSDateField`: a `models.DateField` subclass that stores
  a native Gregorian `date` and exposes a `BSDate`, preserving indexes, range
  queries, ordering, aggregation and DB-side date functions.
- `django_bikram.django.forms`: `BSDateField` form field and `BSDateInput` widget.
- `django_bikram.django.drf`: DRF serializer field, import-guarded as an optional
  extra, plus `register_serializer_field()` for `ModelSerializer`.
- `django_bikram.django.lookups`: `bs_year_q` / `bs_month_q` / `bs_year_bounds` /
  `bs_month_bounds` — index-friendly half-open range helpers.
- Migration serializer for `BSDate`, so `default=BSDate(...)` works.
- `py.typed`: the package ships inline type information.

### Deliberately not included

- `__bs_year` / `__bs_month` query transforms. See the README section
  "Why there is no `__bs_year` lookup" — the range helpers are exact and use
  the index; a transform would not.
- Bikram Sambat time/datetime types. The calendar defines days, not clocks;
  use an ordinary `DateTimeField` for instants.

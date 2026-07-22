# Changelog

All notable changes to this project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.0] - 2026-07-22

### Added

- **`django_bikram.fiscal`** — Nepali fiscal year (1 Shrawan to the last of
  Ashadh) and quarter arithmetic. `fiscal_year()`, `fiscal_year_label()`
  (`'2081/82'`), `fiscal_quarter()`, and half-open `fiscal_year_bounds()` /
  `fiscal_quarter_bounds()`, plus `BSDate.fiscal_year`,
  `.fiscal_year_label` and `.fiscal_quarter`. Derived entirely from the one
  start-month rule, so there is no second calendar table to keep in step.
- **`bs_fiscal_year_q()` / `bs_fiscal_quarter_q()`** in
  `django_bikram.django.lookups` — index-friendly `Q` helpers, matching the
  existing `bs_year_q` / `bs_month_q`. A fiscal year spans two BS years, so no
  combination of built-in lookups expresses it.
- **`BSDatePickerInput`** — a bundled Bikram Sambat calendar widget: 13 kB of
  vanilla JavaScript, no npm, no build step, no CDN, no new dependency. The
  calendar table is compiled into the asset as a 1.3 kB string
  (`encode_verified_calendar()`), so the browser does real BS arithmetic instead
  of round-tripping to the server; a test asserts the shipped copy still equals
  the Python table. Verified against Python for all 40,178 dates in the range,
  both directions. Progressive enhancement — the field is still a text input,
  and every value is re-validated server-side.
- **`BSDateFieldListFilter`** in `django_bikram.django.admin` — an admin
  `list_filter` whose periods are Bikram Sambat. Django resolves `BSDateField`
  through `isinstance(f, models.DateField)` to its own Gregorian filter, whose
  buckets carry no calendar in their labels: "This month" selects the *Gregorian*
  month, which spans two BS months and, in mid-July, two fiscal years. The
  replacement offers Today, Past 7 days, This month, This year and This fiscal
  year, each still a single index range scan, and omits any bucket that would
  reach past the verified table rather than approximating it. Opt in per field,
  or globally with `register_list_filter()`. `date_hierarchy` remains Gregorian
  and is now documented as such — it is built by a template tag with no registry
  to hook.
- `django_bikram.apps.DjangoBikramConfig` — add `"django_bikram"` to
  `INSTALLED_APPS` to make the picker's static assets discoverable by
  `collectstatic`. Needed for the picker only; nothing else in the package
  requires app registration, and registering it has no other effect.
- **`docs/migrating.md`** — step-by-step migration from
  `django-nepali-datetime-field` (no data migration needed; the storage is
  already compatible), from `django-npdt` (`CharField` → `BSDateField`, with a
  batched backfill), and from hand-rolled string or three-integer storage.

### Fixed

- **The Django admin no longer renders a Gregorian date picker on a
  `BSDateField`.** `django.contrib.admin` maps `models.DateField` to
  `AdminDateWidget` by walking the field's MRO, so `BSDateField` inherited it —
  along with the `vDateField` class that `calendar.js` and
  `DateTimeShortcuts.js` bind to. That gave the field a Gregorian calendar popup
  and a "Today" button writing the Gregorian date, which read back as Bikram
  Sambat: `2026-07-22` → 2026 BS → 1969 AD. `formfield()` now swaps that widget
  for `BSDateInput`. Widgets you choose yourself are untouched.
- **`serializers.serialize("json"|"python", ...)` no longer emits Gregorian
  digits** for an in-memory instance that was assigned a raw `datetime.date`.
  Those serializers pass a value through untouched when Django's
  `is_protected_type()` is true — which it is for `datetime.date` — so
  `value_to_string()` was never consulted and the AD digits reached the fixture,
  where `loaddata` read them back as Bikram Sambat: a silent 57-year error.
  `BSDateField.value_from_object()` now normalises the date first. `dumpdata` was
  never affected (it loads from the database, so the value is already a
  `BSDate`), nor was the XML serializer.
- `model_to_dict()` — and therefore `ModelForm` initial data — normalises an
  assigned `datetime.date` the same way, instead of rendering the Gregorian
  digits into a Bikram Sambat field.
- **A form field no longer overwrites a language set on its widget.**
  `BSDateField(widget=BSDateInput(lang="ne"))` was silently reset to the field's
  default `"en"`, making the explicit argument useless. The widget now records
  which settings were passed to it, and the field fills in only the rest.
- **A form can now parse what it just rendered.** A widget set to `lang="ne"`
  emits `०१ वैशाख २०८१`, which a field left at the default `"en"` rejected as
  invalid. The field now adopts a language set on its widget (and the field
  still wins if both were set). Likewise a widget `format` outside
  `DEFAULT_INPUT_FORMATS` is now accepted on input — unless you passed
  `input_formats` yourself, which remains an exact statement of what is
  accepted.
- **`ProvisionalDateWarning` is attributed to the caller, so it is no longer
  silenced after the first use.** A fixed `stacklevel` pointed every such warning
  at `django_bikram/date.py`; because `warnings` deduplicates on the *attributed*
  module and line, the second module in a program to touch provisional data got
  no warning at all and silently used unverified dates. The stacklevel is now
  computed by walking out to the first frame outside the package, which is
  correct for every entry point (`BSDate()`, `bs_to_ad()`, `ad_to_bs()`,
  `check_bs_date()`) — their depths differ, so no constant could have worked.
- **The DRF field parses its own output.** `BSDateField(format="%d.%m.%Y")`
  emitted `01.01.2081` and then rejected it, so a client POSTing back a record it
  had just fetched failed validation on the API's own output. The render format
  is now always accepted on input, unless you pass `input_formats` explicitly.
- `BSDate.fromisoformat()` now accepts only ASCII and Devanagari digits, matching
  `strptime()`/`parse_bs()`. Previously fullwidth digits (`"２０８１-01-01"`) parsed
  through `fromisoformat` but were rejected by the other parse paths — the two
  entry points now agree on the numeral systems this package speaks.

### Documentation

- **`TruncMonth` / `TruncYear`** are now documented as the one database-side date
  function whose result does not announce its calendar. They truncate the stored
  *Gregorian* value and the result converts back to a `BSDate` that is not a BS
  period start — `TruncMonth` over 1 Baishakh 2081 yields `BSDate(2080, 12, 19)`.
  A correct AD truncation and a meaningless BS bucket. Both READMEs now say so,
  the values are pinned by a test, and the range helpers are named as the way to
  group by Bikram Sambat periods. No behaviour changed.

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

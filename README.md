# django-bikram

[![CI](https://github.com/anishbhimgc/django-bikram/actions/workflows/ci.yml/badge.svg)](https://github.com/anishbhimgc/django-bikram/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/django-bikram)](https://pypi.org/project/django-bikram/)
[![Python versions](https://img.shields.io/pypi/pyversions/django-bikram)](https://pypi.org/project/django-bikram/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![Types: mypy strict](https://img.shields.io/badge/types-mypy%20strict-blue)](https://mypy-lang.org/)
[![Lint: ruff](https://img.shields.io/badge/lint-ruff-261230)](https://github.com/astral-sh/ruff)

Bikram Sambat (Nepali) dates for Python, with first-class Django and DRF
integration.

> **New here?** Start with the **[Quickstart](docs/quickstart.md)**.
>
> 🇳🇵 नेपालीमा: [README.ne.md](README.ne.md) · [छिटो सुरु गर्ने मार्गदर्शन](docs/quickstart.ne.md)

```python
from django_bikram import BSDate

BSDate(2081, 1, 1).to_ad()              # datetime.date(2024, 4, 13)
BSDate.from_ad(datetime.date(2024, 4, 13))  # BSDate(2081, 1, 1)
BSDate.today().strftime("%d %B %Y", lang="ne", numerals="devanagari")
```

```python
from django.db import models
from django_bikram.django import BSDateField

class Invoice(models.Model):
    issued_on = BSDateField()           # a real DATE column underneath

Invoice.objects.filter(issued_on__gte=BSDate(2081, 1, 1))  # uses the index
```

---

## Read this before you publish or depend on this package

Two things are deliberately not glossed over.

### 1. The *verified* range ends at 2083 BS (13 April 2027)

The Bikram Sambat calendar's month lengths are set **astronomically** — by the
moment the sun crosses into each zodiac sign — and published year by year in
the Nepali Panchanga. This package ships the years it could **verify against two
independent sources**: **1975–2083 BS (1918-04-13 – 2027-04-13 AD)**. By default,
dates outside that range raise `DateOutOfRange` rather than guessing.

They *can* be approximated by computation — but not exactly, and that gap is the
whole point. A Surya-Siddhanta model of the sun (the same reckoning the official
calendar uses) reproduces the verified 109 years to only **~87% of months, the
rest off by exactly one day, and just 58 of 109 years fully correct** (re-run it
yourself: `python -c "from django_bikram.predict import validate; print(validate())"`).
The residual is the traditional day-boundary rule plus the committee's occasional
manual corrections — real, and not tunable away. So computed years are shipped as
a clearly-marked **provisional** tier, never as fact.

If 2027 is too close for you (it is, for anything long-lived), you have two
honest options — see [Living past 2083](#living-past-2083).

### 2. Distribution name vs. import name

You **install** `django-bikram` but you **import** `django_bikram`:

```bash
pip install django-bikram
```
```python
from django_bikram import BSDate
```

This is deliberate. An earlier revision used a top-level `bikram` import
package, but PyPI already hosts a **different** project literally named
[`bikram`](https://pypi.org/project/bikram/) (v2.1.4, "Utilities to work with
Bikram/Vikram Samwat dates") which installs its own top-level `bikram/`
directory. Two packages claiming the same import name means installing both
silently overwrites one, with no warning from pip. The import package is
therefore `django_bikram`, which matches the distribution name and collides with
nothing.

Before you upload, still **re-check the distribution name is free** — a `GET`
to `https://pypi.org/pypi/django-bikram/json` returning 404 means it is
available; names get taken.

---

## Installation

```bash
pip install django-bikram          # core + Django integration
pip install django-bikram[drf]     # also pulls in djangorestframework
```

Requires Python 3.10+. Django is only needed for `django_bikram.django`; the core
`BSDate` type has **no dependencies at all**.

---

## The design decision that matters

**`BSDateField` stores a native `date` (Gregorian/AD) in the database and
exposes a `BSDate` in Python.** Conversion happens at the boundary, and only
there.

Most Nepali date libraries store BS as a string (`"2081-01-01"`) or as three
integer columns. Both throw away everything the database is for:

| | native `date` (this package) | BS string | y/m/d integers |
|---|---|---|---|
| btree index on ranges | ✅ | ❌ equality/prefix only | ⚠️ composite, no range seek |
| `__gte` / `__lt` / `__range` | ✅ plain comparison | ❌ wrong across month lengths | ⚠️ OR-of-ANDs |
| `ORDER BY` | ✅ | ❌ | ⚠️ 3-column sort |
| `Min` / `Max` / aggregates | ✅ | ❌ | ❌ |
| `TruncMonth`, `ExtractYear`, date_trunc | ✅ | ❌ | ❌ |
| readable from psql / BI tools | ✅ | ⚠️ | ❌ |

A BS string does not sort chronologically in a way the database understands,
and no index can fix that. Because `BSDateField` subclasses
`models.DateField`, every lookup Django already ships keeps working — there is
nothing to reimplement.

### The one consequence to know

`__year`, `__month` and `__day` are **inherited from `DateField` and operate on
the stored Gregorian value**, because that is genuinely what the column holds:

```python
Invoice.objects.filter(issued_on__year=2024)   # AD year — 1 Baishakh 2081 matches
Invoice.objects.filter(issued_on__year=2081)   # matches nothing
```

This is documented, tested, and intentional. For BS years, read on.

---

## Querying by BS year or month

There is **no `__bs_year` lookup**, on purpose.

The database has no BS calendar table, so evaluating a BS year in SQL requires
either inlining a 109-branch `CASE` expression (correct, but opaque to the
planner — every query becomes a sequential scan, quietly making your tables
slow), or a stored generated column (a schema decision that belongs to your
application, not to a field type). A third option — rewriting equality into a
range, as Django's own `YearExact` does — works for `__bs_year=2081` but not
for `__bs_year__gt`, `values()`, `annotate()` or `order_by()`, which would make
the transform correct in some positions and wrong in others.

A lookup that is only sometimes safe is worse than no lookup. So the package
ships helpers instead — a BS year *is* a contiguous span of AD dates, and
saying so directly keeps the index in play:

```python
from django_bikram.django.lookups import bs_year_q, bs_month_q, bs_year_bounds

Invoice.objects.filter(bs_year_q("issued_on", 2081))
Invoice.objects.filter(bs_month_q("issued_on", 2081, 1))
Invoice.objects.filter(bs_year_q("issued_on", 2081), status="paid")
Invoice.objects.exclude(bs_year_q("issued_on", 2081))

bs_year_bounds(2081)   # (date(2024, 4, 13), date(2025, 4, 14)) — half-open
```

These compile to `issued_on >= %s AND issued_on < %s`: one index range scan, no
per-row work.

---

## `BSDate`

Immutable (`__slots__`), hashable, totally ordered, and shaped like
`datetime.date` so there is little new to learn.

```python
d = BSDate(2081, 1, 1)

d.year, d.month, d.day        # 2081, 1, 1
d.to_ad()                     # datetime.date(2024, 4, 13)
d.weekday()                   # 5 — Monday==0, like datetime
d.nepali_weekday()            # 6 — Sunday==0, like a printed Nepali calendar
d.isoformat()                 # '2081-01-01'  (BS components)
d.replace(month=2)            # BSDate(2081, 2, 1)
d.days_in_month               # 31  (months run 29–32 days)

d + datetime.timedelta(days=31)     # BSDate(2081, 2, 1)
BSDate(2081, 2, 1) - d              # datetime.timedelta(days=31)

BSDate.today()
BSDate.from_ad(datetime.date(2024, 4, 13))
BSDate.fromisoformat("2081-01-01")
BSDate.strptime("01 Baishakh 2081", "%d %B %Y")
```

A few deliberate choices:

- **`BSDate != datetime.date`, always**, even for the same day. Silently
  equating them would make dict keys and set membership ambiguous. Convert
  explicitly.
- **Sub-day timedeltas are rejected**, not truncated — the rounding direction
  is a coin flip callers shouldn't have to guess.
- **`replace(year=...)` can raise.** 2081 Jestha has 32 days; 2082 Jestha has
  31. There is no 32nd to land on, so it fails instead of clamping.

### Errors

```
BikramError
└── InvalidBSDate      (also a ValueError)
    └── DateOutOfRange
```

`InvalidBSDate` subclasses `ValueError` so existing `except ValueError` blocks
keep working, while `except BikramError` catches exactly this package.

```python
BSDate(2081, 1, 32)   # InvalidBSDate: day 32 is out of range for 2081-01, which has 31 days
BSDate(2090, 1, 1)    # DateOutOfRange: BS year 2090 is outside the verified range 1975..2083
```

---

## Formatting

Language and numerals are **independent** switches, because real Nepali
documents mix them freely.

```python
d.strftime("%d %B %Y")                                    # '01 Baishakh 2081'
d.strftime("%d %B %Y", lang="ne")                         # '01 वैशाख 2081'
d.strftime("%d %B %Y", numerals="devanagari")             # '०१ Baishakh २०८१'
d.strftime("%A, %d %B %Y", lang="ne", numerals="devanagari")  # 'शनिबार, ०१ वैशाख २०८१'
```

| Directive | Meaning |
|---|---|
| `%Y` `%y` | Year (4-digit / 2-digit) |
| `%m` `%-m` | Month, padded / unpadded |
| `%d` `%-d` | Day, padded / unpadded |
| `%B` `%b` | Month name, full / abbreviated |
| `%A` `%a` | Weekday name, full / abbreviated |
| `%j` | Day of year |
| `%%` | Literal `%` |

Parsing accepts either numeral system by default (`numerals="auto"`):

```python
from django_bikram import parse_bs
parse_bs("२०८१-०१-०१", "%Y-%m-%d")        # (2081, 1, 1)
parse_bs("०१ वैशाख २०८१", "%d %B %Y", lang="ne")
```

`%y` is ambiguous on input — the range spans 109 years, so `75`–`83` match both
19xx and 20xx. It resolves toward 20xx and is documented as such. Prefer `%Y`.

---

## Django integration

### Model field

```python
from django_bikram.django import BSDateField

class Invoice(models.Model):
    issued_on  = BSDateField(db_index=True)
    due_on     = BSDateField(null=True, blank=True)
    created_on = BSDateField(auto_now_add=True)   # yields a BSDate
```

Assignment accepts, with fixed meanings:

| Input | Read as |
|---|---|
| `BSDate(2081, 1, 1)` | itself |
| `datetime.date(2024, 4, 13)` | **Gregorian**, converted |
| `"2081-01-01"` | **Bikram Sambat** |

The asymmetry is deliberate: a `datetime.date` is unambiguously Gregorian,
while a string in this field's context is the BS value a user typed. `dumpdata`
emits BS strings, and `loaddata` reads them back.

`default=BSDate(2081, 1, 1)` works — a migration serializer is registered.

### Forms

```python
from django_bikram.django.forms import BSDateField, BSDateInput

class InvoiceForm(forms.ModelForm):
    class Meta:
        model, fields = Invoice, ["issued_on"]
        widgets = {"issued_on": BSDateInput(format="%d %B %Y", lang="ne",
                                            numerals="devanagari")}
```

The widget is a plain text input, not `<input type="date">` — the browser's
native picker only speaks Gregorian and would rewrite the value. It emits a
`data-bs-date="2081-01-01"` attribute for JS date pickers to hook.

### DRF

```python
from django_bikram.django.drf import BSDateField

class InvoiceSerializer(serializers.ModelSerializer):
    issued_on = BSDateField()
    class Meta:
        model, fields = Invoice, ["id", "issued_on"]
```

⚠️ **If you use `ModelSerializer` without declaring the field explicitly**, DRF
resolves `BSDateField` to its own `DateField` (since it subclasses
`models.DateField`) and emits **Gregorian** dates — plausible-looking output in
the wrong calendar. Close that trap once at startup:

```python
class MyAppConfig(AppConfig):
    def ready(self):
        from django_bikram.django.drf import register_serializer_field
        register_serializer_field()
```

It isn't done on import, because mutating a third-party class as an import side
effect makes test suites order-dependent.

---

## Calendar data: provenance and verified range

**Where the table came from.** It was not authored by hand or generated. It was
extracted and cross-verified from two independently maintained, MIT-licensed
sources:

1. [`nepali-datetime`](https://pypi.org/project/nepali-datetime/) 1.0.8.5 —
   `nepali_datetime/data/calendar_bs.csv`
2. [`bikram-sambat`](https://pypi.org/project/bikram-sambat/) 0.2.0 —
   `bikram_sambat/data/calendar_data.py`

Both ultimately derive from the Nepali Panchanga. Month lengths are facts, not
authorship; the implementations here are original.

**Verified range: 1975–2083 BS (1918-04-13 – 2027-04-13 AD).** Across those 109
years the two sources agree on **all 1,308 month lengths**, and:

- every year totals 365 or 366 days;
- every month is 29–32 days;
- all 39,813 dates round-trip (`from_ad(to_ad(d)) == d`);
- consecutive BS days advance the AD weekday by exactly one, with no gaps;
- derived anchors match independently published values:
  - 1 Baishakh **1975** BS = 13 April 1918
  - 1 Baishakh **2000** BS = **14 April 1943**
  - 1 Baishakh **2081** BS = 13 April 2024
  - 1 Baishakh **2082** BS = 14 April 2025

> Note on the 2000 BS anchor: it is often quoted as *13* April 1943. That is
> off by one. Both upstream libraries, and public converters, place it at **14
> April 1943**, and the whole 1975–2083 chain is self-consistent only with that
> value.

**Why it stops at 2083** — it stops where the evidence stops, not where the
sources stop:

- `nepali-datetime` carries rows to 2100 BS, but from 2084 they are visibly
  synthetic: 14 of its 17 remaining years end in the tail `(30, 30, 30)`, and
  **2096 BS sums to 364 days**, which is not a possible year.
- `bikram-sambat` carries 1901–2199 BS, but outside 1975–2083 nothing here
  corroborates it.
- The two diverge from 2084 onward and never re-converge.

Data below 1975 BS (available from `bikram-sambat` alone) is excluded for the
same reason: single-source and unverified.

---

## Living past 2083

2027 is close. Two honest ways forward, and one that is not on offer.

### Not on offer: a "100-year table" of verified dates

There isn't one — anywhere. Nobody has authoritative month lengths for
2084 BS onward, because the Panchanga committee sets them astronomically and
publishes roughly a year ahead. Every file that claims a century of BS dates is
either computed (a prediction) or filler (the `nepali-datetime` rows past 2083
include a **364-day year**). This package will not pretend otherwise.

### Option A — extend the verified table as data is published

When the Samiti publishes further years:

1. Append the rows to `VERIFIED_BS_MONTH_DAYS` in
   `django_bikram/calendar_data.py` and raise `VERIFIED_MAX_BS_YEAR`.
2. Corroborate each new year against **at least two independent sources**.
3. Run the suite — `tests/test_calendar_data.py` enforces the 365/366 total,
   the 29–32 month bound, and the anti-filler tail check;
   `tests/test_convert.py` re-verifies round-trips and weekday continuity.

This is the real fix. The provisional tier is a bridge to it, not a replacement.

### Option B — enable computed (provisional) years now

If you need dates past 2027 today and can accept that a predicted month length
is right about **seven times in eight** (±1 day otherwise), opt in:

```bash
# import-time, framework-agnostic — the safe way
export DJANGO_BIKRAM_PROVISIONAL_THROUGH_YEAR=2183
```

Now `BSDate(2100, 1, 1)` works instead of raising. Every such date is **flagged**:

```python
BSDate(2100, 1, 1).is_verified          # False
# constructing or converting it raises ProvisionalDateWarning (once, by default)
```

Prefer to generate the numbers yourself, or wire them in from your own startup
code? The predictor is a plain module:

```python
from django_bikram.predict import build_provisional_table, validate

validate()                       # the honest backtest: ~87% of months, ±1 day
table = build_provisional_table(through_year=2183)   # {2084: (...), ... 2183: (...)}

from django_bikram.calendar_data import install_provisional
install_provisional(table)       # call once at startup, before the first date op
```

The model is Surya-Siddhanta solar longitude crossed against the sidereal signs,
with two constants fit to the verified range. It is documented in
`django_bikram/predict.py`, caveats and all. **Do not use provisional dates where
a one-day error matters** (due dates, legal deadlines); do use them for planning
and display, and replace them with verified rows the moment they publish.

To silence or harden the warning globally:

```python
import warnings
from django_bikram import ProvisionalDateWarning
warnings.filterwarnings("ignore", category=ProvisionalDateWarning)  # quiet
warnings.filterwarnings("error",  category=ProvisionalDateWarning)  # strict again
```

---

## Development

```bash
pip install -e ".[dev]"
pytest
ruff check django_bikram/
mypy django_bikram/
```

---

## Deliberately out of scope

- **BS time/datetime types.** The calendar defines days, not clocks. Use a
  normal `DateTimeField` for instants.
- **`__bs_year` / `__bs_month` transforms.** See above.
- **Fiscal-year helpers, holiday calendars, Panchanga tithi.** Different
  problems with different data sources.

## License

MIT. See [LICENSE](LICENSE).

# django-bikram-sambat

[![CI](https://github.com/anishbhimgc/django-bikram-sambat/actions/workflows/ci.yml/badge.svg)](https://github.com/anishbhimgc/django-bikram-sambat/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/django-bikram-sambat)](https://pypi.org/project/django-bikram-sambat/)
[![Python versions](https://img.shields.io/pypi/pyversions/django-bikram-sambat)](https://pypi.org/project/django-bikram-sambat/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](https://github.com/anishbhimgc/django-bikram-sambat/blob/main/LICENSE)
[![Types: mypy strict](https://img.shields.io/badge/types-mypy%20strict-blue)](https://mypy-lang.org/)
[![Lint: ruff](https://img.shields.io/badge/lint-ruff-261230)](https://github.com/astral-sh/ruff)

Bikram Sambat (Nepali) dates for Python, with first-class Django and DRF
integration.

> **New here?** Start with the **[Quickstart](https://github.com/anishbhimgc/django-bikram-sambat/blob/main/docs/quickstart.md)**.
>
> 🇳🇵 नेपालीमा: [README.ne.md](https://github.com/anishbhimgc/django-bikram-sambat/blob/main/README.ne.md) · [छिटो सुरु गर्ने मार्गदर्शन](https://github.com/anishbhimgc/django-bikram-sambat/blob/main/docs/quickstart.ne.md)

```python
from django_bikram_sambat import BSDate

BSDate(2081, 1, 1).to_ad()              # datetime.date(2024, 4, 13)
BSDate.from_ad(datetime.date(2024, 4, 13))  # BSDate(2081, 1, 1)
BSDate.today().strftime("%d %B %Y", lang="ne", numerals="devanagari")
```

```python
from django.db import models
from django_bikram_sambat.django import BSDateField

class Invoice(models.Model):
    issued_on = BSDateField()           # a real DATE column underneath

Invoice.objects.filter(issued_on__gte=BSDate(2081, 1, 1))  # uses the index
```

---

## Read this before you depend on this package

One thing is deliberately not glossed over.

### The *verified* range ends at 2084 BS (12 April 2028)

The Bikram Sambat calendar's month lengths are set **astronomically** — by the
moment the sun crosses into each zodiac sign — and published year by year in
the Nepali Panchanga. This package ships the years it could **verify against two
independent sources**: **1975–2084 BS (1918-04-13 – 2028-04-12 AD)**. By default,
dates outside that range raise `DateOutOfRange` rather than guessing.

They *can* be approximated by computation — but not exactly, and that gap is the
whole point. A Surya-Siddhanta model of the sun (the same reckoning the official
calendar uses) reproduces the verified years to only **~87% of months, the
rest off by exactly one day, and just 58 of 110 years fully correct** (re-run it
yourself: `python -c "from django_bikram_sambat.predict import validate; print(validate())"`).
The residual is the traditional day-boundary rule plus the committee's occasional
manual corrections — real, and not tunable away. So computed years are shipped as
a clearly-marked **provisional** tier, never as fact.

If April 2028 is too close for you (it is, for anything long-lived), you have
two honest options — see [Living past 2084](#living-past-2084).

---

## Installation

```bash
pip install django-bikram-sambat          # core + Django integration
pip install django-bikram-sambat[drf]     # also pulls in djangorestframework
```

Requires Python 3.10+. Django is only needed for `django_bikram_sambat.django`; the core
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
| `TruncMonth`, `ExtractYear`, date_trunc | ✅ *(on the AD value — see below)* | ❌ | ❌ |
| readable from psql / BI tools | ✅ | ⚠️ | ❌ |

A BS string does not sort chronologically in a way the database understands,
and no index can fix that. Because `BSDateField` subclasses
`models.DateField`, every lookup Django already ships keeps working — there is
nothing to reimplement.

### The one consequence to know

Every database-side date operation is **inherited from `DateField` and works on
the stored Gregorian value**, because that is genuinely what the column holds.

```python
Invoice.objects.filter(issued_on__year=2024)   # AD year — 1 Baishakh 2081 matches
Invoice.objects.filter(issued_on__year=2081)   # matches nothing
```

`ExtractYear` is the same story and says so out loud — it returns `2024`, a
plain integer nobody will mistake for a BS year.

**`TruncMonth` and `TruncYear` are the one case that does not announce itself,
so it is worth stating plainly.** They truncate to the start of the *AD* month
or year, which falls in the middle of a BS one; the result then converts back
through this field and arrives as a `BSDate` that is not a BS period start:

```python
Invoice.objects.annotate(m=TruncMonth("issued_on"))   # 1 Baishakh 2081 →
                                                      # BSDate(2080, 12, 19)
Invoice.objects.annotate(y=TruncYear("issued_on"))    # → BSDate(2080, 9, 16)
```

That is a correct AD truncation and a meaningless BS bucket. To group by Bikram
Sambat periods, aggregate per range with the helpers below, or bucket in Python:

```python
start, end = bs_month_bounds(2081, 1)
Invoice.objects.filter(issued_on__gte=start, issued_on__lt=end).aggregate(Sum("total"))
```

All of this is documented, tested, and intentional. For BS years, read on.

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
from django_bikram_sambat.django.lookups import bs_year_q, bs_month_q, bs_year_bounds

Invoice.objects.filter(bs_year_q("issued_on", 2081))
Invoice.objects.filter(bs_month_q("issued_on", 2081, 1))
Invoice.objects.filter(bs_year_q("issued_on", 2081), status="paid")
Invoice.objects.exclude(bs_year_q("issued_on", 2081))

bs_year_bounds(2081)   # (date(2024, 4, 13), date(2025, 4, 14)) — half-open
```

These compile to `issued_on >= %s AND issued_on < %s`: one index range scan, no
per-row work.

---

## Fiscal year

Nepal's fiscal year (आर्थिक वर्ष) runs **1 Shrawan to the last day of Ashadh**,
and is named for the year it starts in: **FY 2081/82**.

```python
d = BSDate(2082, 1, 1)          # Baishakh — the *closing* quarter of FY 2081/82

d.fiscal_year                   # 2081
d.fiscal_year_label             # '2081/82'
d.fiscal_quarter                # 4
```

Because a fiscal year spans two BS years, no combination of built-in lookups
expresses it — so it gets the same half-open range treatment as a BS year:

```python
from django_bikram_sambat.django.lookups import bs_fiscal_year_q, bs_fiscal_quarter_q
from django_bikram_sambat.fiscal import fiscal_year_bounds

Invoice.objects.filter(bs_fiscal_year_q("issued_on", 2081))
Invoice.objects.filter(bs_fiscal_quarter_q("issued_on", 2081, 1))

fiscal_year_bounds(2081)   # (date(2024, 7, 16), date(2025, 7, 17)) — half-open
```

Quarters are the fiscal year cut into three-month blocks: Q1 Shrawan–Ashwin,
Q2 Kartik–Poush, Q3 Magh–Chaitra, Q4 Baishakh–Ashadh. **Q4 carries the higher BS
year** — Baishakh 2082 belongs to FY 2081/82, not FY 2082/83. That is the part
everyone gets wrong, so it is checked day by day in the test suite.

Note that `fiscal_year_bounds(2084)` raises: a fiscal year reaches into the next
BS year, so it runs out one year before the calendar table does.

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
BSDate(2090, 1, 1)    # DateOutOfRange: BS year 2090 is outside the verified range 1975..2084
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
from django_bikram_sambat import parse_bs
parse_bs("२०८१-०१-०१", "%Y-%m-%d")        # (2081, 1, 1)
parse_bs("०१ वैशाख २०८१", "%d %B %Y", lang="ne")
```

`%y` is ambiguous on input — the range spans 109 years, so `75`–`83` match both
19xx and 20xx. It resolves toward 20xx and is documented as such. Prefer `%Y`.

---

## Django integration

### Model field

```python
from django_bikram_sambat.django import BSDateField

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
from django_bikram_sambat.django.forms import BSDateField, BSDateInput

class InvoiceForm(forms.ModelForm):
    class Meta:
        model, fields = Invoice, ["issued_on"]
        widgets = {"issued_on": BSDateInput(format="%d %B %Y", lang="ne",
                                            numerals="devanagari")}
```

The widget is a plain text input, not `<input type="date">` — the browser's
native picker only speaks Gregorian and would rewrite the value. It emits a
`data-bs-date="2081-01-01"` attribute for JS date pickers to hook.

In the **Django admin**, `BSDateField` would otherwise inherit `AdminDateWidget`
(admin maps `models.DateField` to it by walking the MRO), whose `vDateField`
class binds Django's *Gregorian* calendar popup and a "Today" button writing the
Gregorian date. `formfield()` swaps that widget out. Widgets you choose yourself
are left alone.

### Admin list filters

The same MRO lookup gives `BSDateField` Django's Gregorian `DateFieldListFilter`.
**Do not use it on this field — every bucket returns zero rows.**

A list filter round-trips its bounds through the query string, so they come back
as ISO strings, and a string in this field's context is a *Bikram Sambat* value
(that is the documented contract). The Gregorian bound `2026-07-17` is therefore
re-read as 2026-07-17 **BS** — 1969 AD — and matches nothing. "Today" on a row
saved today returns nothing, on every supported Django version. The labels are
wrong too: "This month" means the *Gregorian* month, which spans two BS months
and, in mid-July, two fiscal years.

Use the BS-aware filter instead. It offers *Today*, *Past 7 days*, *This month*,
*This year* and *This fiscal year*, each a half-open range on the indexed column,
and it parses its own bounds back as Gregorian so the buckets actually select:

```python
from django_bikram_sambat.django.admin import BSDateFieldListFilter

class InvoiceAdmin(admin.ModelAdmin):
    list_filter = [("issued_on", BSDateFieldListFilter)]
```

Or make it the default for every `BSDateField` in the project:

```python
class MyAppConfig(AppConfig):
    def ready(self):
        from django_bikram_sambat.django.admin import register_list_filter
        register_list_filter()
```

⚠️ **`date_hierarchy` is not covered.** It is rendered by a Django template tag
that builds `__year`/`__month`/`__day` directly, with no registry to hook — so it
drills down by **AD**, showing a 1 Baishakh 2081 record under "2024". Prefer the
filter above.

### Date picker

```python
# settings.py — required for the picker only; the rest of the package
# needs no app registration.
INSTALLED_APPS = [..., "django_bikram_sambat"]
```

```python
from django_bikram_sambat.django import BSDatePickerInput

widgets = {"issued_on": BSDatePickerInput(lang="ne", numerals="devanagari")}
```

A Bikram Sambat calendar in 13 kB of vanilla JavaScript (4 kB gzipped), plus
2.8 kB of CSS — **no npm, no build
step, no CDN, and no new dependency**. The verified calendar is compiled into the
asset as a 1.3 kB string, so the browser does real BS arithmetic rather than
asking the server on every click; a test asserts that copy still equals the
Python table, and the two agree on all 40,178 dates in the range.

It is progressive enhancement: the field is the same text input underneath, so it
works with JavaScript off, and every value the picker writes is re-validated
server-side exactly like typed input. Needs `django.contrib.staticfiles` and
`{{ form.media }}` in your template; inside the admin both are already handled.

### DRF

```python
from django_bikram_sambat.django.drf import BSDateField

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
        from django_bikram_sambat.django.drf import register_serializer_field
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

**Core verified range: 1975–2083 BS (1918-04-13 – 2027-04-13 AD).** Across those
109 years the two sources agree on **all 1,308 month lengths**, and:

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

**2084 BS was added later (July 2026)** from a different independent pair:
scraped from hamropatro.com and found identical to `nepali-datetime` for all
twelve months (those two disagree with `bikram-sambat` there, so Hamro Patro
breaks the tie). It chains exactly onto 2083 and extends the verified range to
**12 April 2028**. It is the first year with a `(30, 30, 30)` tail — corroborated
by both sources, but worth re-confirming against the official Panchanga.

**Why it stops at 2084** — it stops where the evidence stops, not where the
sources stop:

- `nepali-datetime` carries rows to 2100 BS, but from 2085 they are visibly
  synthetic: 14 of its 17 remaining years end in the tail `(30, 30, 30)`, and
  **2096 BS sums to 364 days**, which is not a possible year. (2084 itself
  checked out against Hamro Patro; 2085 onward has no such corroboration.)
- `bikram-sambat` carries 1901–2199 BS, but outside 1975–2084 nothing here
  corroborates it.
- The two diverge from 2084 onward and never re-converge.

Data below 1975 BS (available from `bikram-sambat` alone) is excluded for the
same reason: single-source and unverified.

---

## Living past 2084

April 2028 is the current edge. Two honest ways forward, and one that is not on
offer.

### Not on offer: a "100-year table" of verified dates

There isn't one — anywhere. Nobody has authoritative month lengths for
2085 BS onward, because the Panchanga committee sets them astronomically and
publishes roughly a year ahead. Every file that claims a century of BS dates is
either computed (a prediction) or filler (the `nepali-datetime` rows past 2084
include a **364-day year**). This package will not pretend otherwise.

### Option A — extend the verified table as data is published

When the Samiti publishes further years:

1. Append the rows to `VERIFIED_BS_MONTH_DAYS` in
   `django_bikram_sambat/calendar_data.py` and raise `VERIFIED_MAX_BS_YEAR`.
2. Corroborate each new year against **at least two independent sources**.
3. Run the suite — `tests/test_calendar_data.py` enforces the 365/366 total,
   the 29–32 month bound, and the anti-filler tail check;
   `tests/test_convert.py` re-verifies round-trips and weekday continuity.

This is the real fix. The provisional tier is a bridge to it, not a replacement.

**Turning a source into a table.** Step 2 needs a second opinion in a comparable
shape. `month_lengths_from_csv()` derives month lengths from any per-day CSV —
a published Panchanga you transcribed, an internal dataset, a scrape — using
only the standard library:

```python
from django_bikram_sambat.sources import month_lengths_from_csv
from django_bikram_sambat.calendar_data import VERIFIED_BS_MONTH_DAYS

table = month_lengths_from_csv("calendar.csv")     # {2085: (31, 31, 32, ...), ...}

# Where the file overlaps the verified range, it must agree exactly.
for year, lengths in table.items():
    known = VERIFIED_BS_MONTH_DAYS.get(year)
    if known and known != lengths:
        print(f"{year}: source says {lengths}, table says {known}")
```

The file needs a `bs_date` column (or `bs_year`/`bs_month`/`bs_day`) and an ISO
`ad_date`; extra columns are ignored. Only complete years are returned, and the
Gregorian column is checked — every consecutive BS day must advance the AD date
by exactly one, which is what catches a truncated fetch or a mis-parsed row that
the BS numbering alone would hide.

**This package never fetches anything.** Gather the data out of band and hand
over the file. A date library that makes network calls turns every request cycle
into somewhere your application can fail, and an HTML parser that breaks quietly
produces plausible wrong dates — the one outcome this package exists to prevent.

Past the verified range the same function feeds
[Option B](#option-b--enable-computed-provisional-years-now): slice the result to
a contiguous run starting at 2085 and pass it to `install_provisional()`. It
stays flagged provisional, because one source is one source.

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
from django_bikram_sambat.predict import build_provisional_table, validate

validate()                       # the honest backtest: ~87% of months, ±1 day
table = build_provisional_table(through_year=2183)   # {2084: (...), ... 2183: (...)}

from django_bikram_sambat.calendar_data import install_provisional
install_provisional(table)       # call once at startup, before the first date op
```

The model is Surya-Siddhanta solar longitude crossed against the sidereal signs,
with two constants fit to the verified range. It is documented in
`django_bikram_sambat/predict.py`, caveats and all. **Do not use provisional dates where
a one-day error matters** (due dates, legal deadlines); do use them for planning
and display, and replace them with verified rows the moment they publish.

**A second source, if you prefer it.** `bikram-sambat` (MIT) ships its own table
to 2199 BS. Install `django-bikram-sambat[bikram-sambat]` and use it in place of the
predictor:

```python
from django_bikram_sambat.sources import bikram_sambat_table
from django_bikram_sambat.calendar_data import install_provisional
install_provisional(bikram_sambat_table(through_year=2150))
```

Be clear-eyed: this is still **one unverified source**, no more authoritative
than the predictor — they disagree on every year past 2084, and neither is the
official Panchanga. It is offered only so you can choose which best-guess to run.

To silence or harden the warning globally:

```python
import warnings
from django_bikram_sambat import ProvisionalDateWarning
warnings.filterwarnings("ignore", category=ProvisionalDateWarning)  # quiet
warnings.filterwarnings("error",  category=ProvisionalDateWarning)  # strict again
```

---

## Development

```bash
pip install -e ".[dev]"
pytest
ruff check django_bikram_sambat/
mypy django_bikram_sambat/
```

---

## Migrating from another package

Coming from `django-nepali-datetime-field`, `django-npdt`, or hand-rolled
string/integer storage? See **[docs/migrating.md](https://github.com/anishbhimgc/django-bikram-sambat/blob/main/docs/migrating.md)**.

If you are on `django-nepali-datetime-field` the storage is already compatible —
it is a field swap with **no data migration**.

---

## Deliberately out of scope

- **BS time/datetime types.** The calendar defines days, not clocks. Use a
  normal `DateTimeField` for instants.
- **`__bs_year` / `__bs_month` transforms.** See above.
- **Holiday calendars and Panchanga tithi.** Different problems with different
  data sources, and neither is derivable from month lengths.

## License

MIT. See [LICENSE](https://github.com/anishbhimgc/django-bikram-sambat/blob/main/LICENSE).

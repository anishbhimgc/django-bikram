# Quickstart

A practical, step-by-step guide to using `django-bikram`. For the full reference,
see the [README](../README.md). नेपालीमा: [quickstart.ne.md](quickstart.ne.md).

> This library ships **only verified dates: 1975–2084 BS** (up to 12 April 2028).
> Dates outside that range raise `DateOutOfRange` by default — this is
> intentional (it never guesses). See [step 8](#step-8--dates-past-2084).

---

## Step 1 — Install

```bash
pip install django-bikram          # core + Django
pip install django-bikram[drf]     # also Django REST Framework
```

Python 3.10+ is required. The core `BSDate` type has **no dependencies** — Django
is only needed for `django_bikram.django`.

---

## Step 2 — Your first date and conversion

`BSDate` behaves like the standard library's `datetime.date`, so there is little
new to learn.

```python
from django_bikram import BSDate
import datetime

d = BSDate(2081, 1, 1)

d.to_ad()                                    # datetime.date(2024, 4, 13)
BSDate.from_ad(datetime.date(2024, 4, 13))   # BSDate(2081, 1, 1)
BSDate.today()                               # today, in Nepal time

d.year, d.month, d.day                       # (2081, 1, 1)
d.days_in_month                              # 31  (this month's length)
d.weekday()                                  # 5  (Mon=0, like datetime)
d.nepali_weekday()                           # 6  (Sun=0, like a printed patro)
```

> **Why does `today()` use Nepal time?** Servers usually run in UTC. Nepal is
> UTC+5:45, so `datetime.date.today()` reports *yesterday* for part of every day
> — which near a month boundary lands you in the wrong month. `BSDate.today()`
> defaults to Nepal, and you can pass a `tz` if you want something else.

---

## Step 3 — Displaying dates (Nepali & Devanagari)

Language and numerals are **independent** switches, because real Nepali documents
mix them freely.

```python
d = BSDate(2081, 1, 1)

d.strftime("%d %B %Y")                                       # '01 Baishakh 2081'
d.strftime("%d %B %Y", lang="ne")                            # '01 वैशाख 2081'
d.strftime("%d %B %Y", numerals="devanagari")                # '०१ Baishakh २०८१'
d.strftime("%A, %d %B %Y", lang="ne", numerals="devanagari") # 'शनिबार, ०१ वैशाख २०८१'
```

Directives: `%Y %y %m %-m %d %-d %B %b %A %a %j %%`.

---

## Step 4 — Parsing user input

```python
from django_bikram import parse_bs, BSDate

# ASCII or Devanagari digits both work (numerals="auto" by default)
parse_bs("२०८१-०१-०१", "%Y-%m-%d")            # (2081, 1, 1)
parse_bs("01 वैशाख 2081", "%d %B %Y", lang="ne")

# straight to a BSDate
BSDate.strptime("2081-01-01", "%Y-%m-%d")     # BSDate(2081, 1, 1)
BSDate.fromisoformat("2081-01-01")            # BSDate(2081, 1, 1)
```

---

## Step 5 — Using it in a Django model

```python
from django.db import models
from django_bikram.django import BSDateField

class Invoice(models.Model):
    issued_on  = BSDateField(db_index=True)
    due_on     = BSDateField(null=True, blank=True)
    created_on = BSDateField(auto_now_add=True)
```

The database stores a **real `DATE` column** (Gregorian), but Python gives you a
`BSDate`. That is the whole design: every index, range query, ordering and
aggregation keeps working because underneath it is an ordinary date.

```python
# Range queries — plain comparisons, uses the index
Invoice.objects.filter(issued_on__gte=BSDate(2081, 1, 1))
Invoice.objects.filter(issued_on__range=(BSDate(2081, 1, 1), BSDate(2081, 12, 30)))

# Aggregation and ordering
from django.db.models import Max
Invoice.objects.aggregate(Max("issued_on"))
Invoice.objects.order_by("-issued_on")
```

---

## Step 6 — Querying by BS year or month

There is **no `__bs_year` lookup** (the README explains why). Use the helpers
instead — they build index-friendly half-open ranges:

```python
from django_bikram.django.lookups import bs_year_q, bs_month_q

Invoice.objects.filter(bs_year_q("issued_on", 2081))          # all of 2081 BS
Invoice.objects.filter(bs_month_q("issued_on", 2081, 1))      # Baishakh 2081
Invoice.objects.filter(bs_year_q("issued_on", 2081), status="paid")
Invoice.objects.exclude(bs_year_q("issued_on", 2081))
```

> ⚠️ **Gotcha:** `issued_on__year=2081` matches **nothing** — the stored value is
> Gregorian, so `__year` filters on the *AD* year. Always use the helpers above
> for BS years.

---

## Step 7 — DRF (if you use it)

```python
from rest_framework import serializers
from django_bikram.django.drf import BSDateField

class InvoiceSerializer(serializers.ModelSerializer):
    issued_on = BSDateField()          # declare it explicitly
    class Meta:
        model, fields = Invoice, ["id", "issued_on"]
```

**Important:** if you leave the field out of a `ModelSerializer`, DRF resolves it
to its own `DateField` and emits **Gregorian** dates — plausible-looking output
in the wrong calendar. Close that trap once at startup:

```python
# apps.py
from django.apps import AppConfig

class MyAppConfig(AppConfig):
    name = "myapp"
    def ready(self):
        from django_bikram.django.drf import register_serializer_field
        register_serializer_field()
```

---

## Step 8 — Dates past 2084

```python
BSDate(2081, 1, 32)   # InvalidBSDate — 2081-01 only has 31 days
BSDate(2100, 1, 1)    # DateOutOfRange — outside the verified range (1975..2084)
```

The calendar is verified through **2084 BS (12 April 2028)**. Past that, month
lengths are not yet officially published, so by default the library refuses them.

If you need dates beyond 2028 and can accept that a *predicted* month length is
right about seven times in eight (±1 day otherwise), opt in:

```bash
export DJANGO_BIKRAM_PROVISIONAL_THROUGH_YEAR=2183
```

Now `BSDate(2100, 1, 1)` works but is flagged (`is_verified == False`, and using
it raises `ProvisionalDateWarning`). **Never use predicted dates where a one-day
error matters** — see the README's ["Living past 2084"](../README.md#living-past-2084).

---

## Handling errors

```python
from django_bikram import BikramError, InvalidBSDate, DateOutOfRange

try:
    d = BSDate(year, month, day)
except DateOutOfRange:
    ...   # well-formed but outside the supported range
except InvalidBSDate:
    ...   # the date does not exist (e.g. the 32nd of a 31-day month)
except BikramError:
    ...   # anything else this package raises
```

`InvalidBSDate` also subclasses `ValueError`, so existing `except ValueError`
blocks keep working.

---

## Where next

- Full reference and design rationale: [README.md](../README.md)
- नेपाली: [README.ne.md](../README.ne.md)

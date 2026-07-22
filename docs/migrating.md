# Migrating to django-bikram

This guide covers moving from the three Bikram Sambat field packages already on
PyPI. Each section states what changes on disk, what changes in your code, and
the data migration to run.

Read [Before you start](#before-you-start) first regardless of which one you are
coming from.

---

## Before you start

**Check the verified range covers your data.** django-bikram refuses dates
outside **1975–2084 BS** rather than extrapolating them, and the migrations below
will raise `DateOutOfRange` on a row it cannot represent. That is deliberate —
such a row was already wrong — but you want to find out before the migration, not
during it:

```python
from django_bikram import MIN_AD_DATE, VERIFIED_MAX_AD_DATE

Invoice.objects.exclude(
    issued_on__range=(MIN_AD_DATE, VERIFIED_MAX_AD_DATE)
).count()          # for packages storing a native date

# for packages storing a BS string
Invoice.objects.exclude(issued_on__regex=r"^(19[7-9]\d|20[0-8]\d)-").count()
```

If that count is not zero, decide what those rows should be before continuing.
See [Living past 2084](../README.md#living-past-2084) if they are genuinely
future-dated.

**Take a backup.** The `CharField` migration below rewrites a column in place.

---

## From `django-nepali-datetime-field`

**The easy case — the storage is already right.** That package also stores a
native `DATE` column holding the Gregorian value, so **your data does not move
and no data migration is needed.** Only the Python type changes: you get a
`BSDate` back instead of a `nepali_datetime.date`.

### 1. Swap the field

```diff
-from nepali_datetime_field.models import NepaliDateField
+from django_bikram.django import BSDateField

 class Invoice(models.Model):
-    issued_on = NepaliDateField()
+    issued_on = BSDateField()
```

`makemigrations` will emit an `AlterField`. It is a no-op at the database level —
both fields are `DateField` subclasses with the same `db_type` — so it applies
instantly even on a large table.

### 2. Update the value type at the edges

| `nepali_datetime.date` | `django_bikram.BSDate` |
|---|---|
| `nepali_datetime.date(2081, 1, 1)` | `BSDate(2081, 1, 1)` |
| `d.to_datetime_date()` | `d.to_ad()` |
| `nepali_datetime.date.from_datetime_date(g)` | `BSDate.from_ad(g)` |
| `nepali_datetime.date.today()` | `BSDate.today()` — defaults to **Nepal**, not the server timezone |
| `d.strftime("%Y-%m-%d")` | same, plus `lang=` and `numerals=` |

### 3. Things that now work

These were broken in the package you are leaving, so check whether you had
workarounds to remove:

- **`auto_now` / `auto_now_add`.** These raised
  `TypeError: expected string or bytes-like object` on every save. They work
  here, and return a `BSDate`.
- **Assigning a `datetime.date`.** Also a `TypeError` there. Here it is read as
  Gregorian and converted — so `date(2024, 4, 13)` and `BSDate(2081, 1, 1)` are
  interchangeable in queries.
- **Dates past 2084 BS.** Its calendar table runs to 2100 BS, but those years are
  unverified and one of them — **2096 BS — sums to 364 days**, which is not a
  possible year. If you have rows in that region they were silently shifted. See
  [Calendar data](../README.md#calendar-data-provenance-and-verified-range).

---

## From `django-npdt`

This one stores Bikram Sambat as a `CharField(max_length=10)`, so the column
must be rewritten. Budget a real migration.

### 1. Add the new column alongside the old one

Keep both while you migrate, so a failed run costs nothing:

```python
class Invoice(models.Model):
    issued_on = NepaliDateField()                      # the old CharField
    issued_on_bs = BSDateField(null=True, blank=True)  # the new one
```

```bash
python manage.py makemigrations && python manage.py migrate
```

### 2. Backfill

```python
# invoices/migrations/00XX_backfill_issued_on.py
from django.db import migrations
from django_bikram import BSDate


def forwards(apps, schema_editor):
    Invoice = apps.get_model("invoices", "Invoice")
    updates = []
    for row in Invoice.objects.exclude(issued_on="").iterator(chunk_size=2000):
        # The old column holds a BS string; BSDate validates it really exists,
        # which a regex-only CharField never did.
        updates.append(Invoice(pk=row.pk, issued_on_bs=BSDate.fromisoformat(row.issued_on)))
        if len(updates) >= 2000:
            Invoice.objects.bulk_update(updates, ["issued_on_bs"])
            updates.clear()
    Invoice.objects.bulk_update(updates, ["issued_on_bs"])


def backwards(apps, schema_editor):
    Invoice = apps.get_model("invoices", "Invoice")
    for row in Invoice.objects.exclude(issued_on_bs=None).iterator(chunk_size=2000):
        row.issued_on = row.issued_on_bs.isoformat()
        row.save(update_fields=["issued_on"])


class Migration(migrations.Migration):
    dependencies = [("invoices", "00XX_add_issued_on_bs")]
    operations = [migrations.RunPython(forwards, backwards)]
```

Expect `InvalidBSDate` on rows the old field accepted but that are not real
dates — `django-npdt` validates only the `\d{4}-\d{2}-\d{2}` *shape*, so
`2081-01-32` (Baishakh 2081 has 31 days) could be stored. Fix those rows rather
than skipping them; they were always wrong.

### 3. Drop the old column, rename the new one

```python
operations = [
    migrations.RemoveField("invoice", "issued_on"),
    migrations.RenameField("invoice", "issued_on_bs", "issued_on"),
    migrations.AlterField("invoice", "issued_on", BSDateField()),  # drop null=True
]
```

### 4. What changes in your code

The old field handed back a `str` subclass, so comparisons were **lexicographic**
and ordering only worked by accident of the ISO shape. After migrating:

```python
# before: string comparison, no index range scan, wrong across month lengths
Invoice.objects.filter(issued_on__gte="2081-01-01")

# after: a real date comparison on an indexed column
Invoice.objects.filter(issued_on__gte=BSDate(2081, 1, 1))
```

`.fiscal_year` and `.fiscal_quarter` have direct equivalents — see
[`django_bikram.fiscal`](../django_bikram/fiscal.py):

```python
d.fiscal_year          # 2081
d.fiscal_year_label    # '2081/82'
d.fiscal_quarter       # 1

from django_bikram.django.lookups import bs_fiscal_year_q
Invoice.objects.filter(bs_fiscal_year_q("issued_on", 2081))   # uses the index
```

The old `fiscal_year` returned `None` silently whenever the underlying parse
failed. This one raises.

### 5. The date picker

`django-npdt` ships a JS picker. So does this package, without the
`npdatetime` C-extension dependency:

```python
from django_bikram.django import BSDatePickerInput

widgets = {"issued_on": BSDatePickerInput(lang="ne", numerals="devanagari")}
```

See [Date picker](../README.md#date-picker).

---

## From raw `nepali-datetime` with a `CharField` or three integers

If you rolled your own storage, the shape of the work is the same as the
`django-npdt` path above: add a `BSDateField`, backfill, swap. Two notes:

- **From three integer columns** (`year`, `month`, `day`), build the value with
  `BSDate(row.year, row.month, row.day)`. Rows that fail validation are rows
  where the three columns never described a real date.
- **From a Gregorian `DateField`** you were converting in application code,
  there is nothing to backfill at all — change the field class and delete the
  conversion helpers. The column already holds exactly what `BSDateField` wants.

---

## Verifying the migration

Run this after any of the paths above:

```python
from django_bikram import BSDate

# 1. Every row round-trips.
for row in Invoice.objects.iterator(chunk_size=2000):
    assert BSDate.from_ad(row.issued_on.to_ad()) == row.issued_on

# 2. Ordering matches what the database thinks.
in_python = sorted(Invoice.objects.values_list("issued_on", flat=True))
in_sql = list(Invoice.objects.order_by("issued_on").values_list("issued_on", flat=True))
assert in_python == in_sql

# 3. Spot-check a known anchor against a printed calendar.
assert BSDate(2081, 1, 1).to_ad().isoformat() == "2024-04-13"
```

The second check is the one that catches a bad `CharField` migration: string
ordering and date ordering agree on ISO-shaped data right up until they don't.

---

## Getting help

Open an issue at
<https://github.com/anishbhimgc/django-bikram/issues> with the package you are
migrating from and the error. Migration problems are a documentation bug as much
as a code one.

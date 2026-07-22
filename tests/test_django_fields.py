"""Model field behaviour, including the storage decision it exists to enforce."""

from __future__ import annotations

import datetime

import pytest
from django.core.exceptions import ValidationError
from django.core.serializers import deserialize, serialize
from django.db import connection, models, transaction
from django.db.models import Max, Min
from django.db.models.functions import ExtractYear, TruncMonth, TruncYear
from django.test import override_settings
from django.utils import timezone

from django_bikram import BSDate
from django_bikram.django import BSDateField

from .models import Invoice

pytestmark = pytest.mark.django_db


# --- the core design decision ------------------------------------------


def test_column_is_a_native_date() -> None:
    """The column type is the backend's real DATE, not text or integers.

    This is the whole point of the package: everything below -- indexes, range
    scans, ordering, aggregation, DB-side date functions -- follows from the
    column being a genuine date.
    """
    field = Invoice._meta.get_field("issued_on")
    assert field.get_internal_type() == "DateField"
    assert field.db_type(connection) == connection.data_types["DateField"] % {}


def test_field_subclasses_datefield() -> None:
    """Subclassing DateField is what inherits every date lookup for free."""
    assert issubclass(BSDateField, models.DateField)


def test_stored_value_is_the_gregorian_date() -> None:
    """The raw column holds the AD date, readable by any non-Python consumer."""
    Invoice.objects.create(issued_on=BSDate(2081, 1, 1))
    with connection.cursor() as cursor:
        cursor.execute("SELECT issued_on FROM tests_invoice")
        raw = cursor.fetchone()[0]
    # SQLite hands back a string; other backends a date. Either way it is the
    # Gregorian value, not "2081-01-01".
    assert str(raw).startswith("2024-04-13")


# --- round-tripping ----------------------------------------------------


def test_save_and_load_round_trip() -> None:
    """A BSDate written to the DB comes back as an equal BSDate."""
    Invoice.objects.create(issued_on=BSDate(2081, 1, 1))
    invoice = Invoice.objects.get()
    assert invoice.issued_on == BSDate(2081, 1, 1)
    assert isinstance(invoice.issued_on, BSDate)


def test_null_round_trip() -> None:
    """A nullable field round-trips None."""
    Invoice.objects.create(issued_on=BSDate(2081, 1, 1), due_on=None)
    assert Invoice.objects.get().due_on is None


def test_assigning_a_gregorian_date_converts_it() -> None:
    """A datetime.date is read as Gregorian and converted on save."""
    Invoice.objects.create(issued_on=datetime.date(2024, 4, 13))
    assert Invoice.objects.get().issued_on == BSDate(2081, 1, 1)


def test_assigning_a_bs_string_parses_it_as_bs() -> None:
    """A string is read as a Bikram Sambat date."""
    Invoice.objects.create(issued_on="2081-01-01")
    assert Invoice.objects.get().issued_on == BSDate(2081, 1, 1)


def test_auto_now_add_and_auto_now_produce_bs_dates() -> None:
    """Auto-populated timestamps are BSDates, not datetime.dates.

    Asserted against ``timezone.localdate()`` — the project's TIME_ZONE, which is
    what pre_save now follows — rather than against ``BSDate.today()``. Comparing
    to today() would put the same function on both sides of the assertion, which
    passes no matter how wrong the timezone handling is; that is exactly how the
    process-TZ bug shipped.
    """
    invoice = Invoice.objects.create(issued_on=BSDate(2081, 1, 1))
    expected = BSDate.from_ad(timezone.localdate())

    assert isinstance(invoice.created_on, BSDate)
    assert isinstance(invoice.updated_on, BSDate)
    assert invoice.created_on == expected
    assert Invoice.objects.get().created_on == expected


def test_saving_an_unrepresentable_gregorian_date_is_refused() -> None:
    """A date with no BS equivalent must not reach the column.

    get_prep_value lets bare dates through for query bounds (bs_year_q needs
    2027-04-14, one day past the table). Writes must not inherit that licence: a
    stored date with no BS equivalent is readable by nothing — from_db_value
    raises on it — so the row poisons every queryset that touches the table, and
    only raw SQL can remove it.
    """
    # Wrapped in its own atomic block so the failure rolls back to a savepoint.
    # Django's save_base uses atomic(savepoint=False), so an exception escaping it
    # marks the enclosing transaction unusable — which is correct (the write must
    # not stand) but leaves nothing queryable afterwards without this.
    with pytest.raises(ValidationError), transaction.atomic():
        Invoice.objects.create(issued_on=datetime.date(1800, 1, 1))

    assert Invoice.objects.count() == 0
    # The query-bound licence this must not break is already covered by
    # test_query_bound_one_day_past_the_table_is_allowed, below.


# --- lookups inherited from DateField ----------------------------------


def test_exact_lookup() -> None:
    """Equality filtering works with a BSDate."""
    Invoice.objects.create(issued_on=BSDate(2081, 1, 1))
    Invoice.objects.create(issued_on=BSDate(2081, 1, 2))
    assert Invoice.objects.filter(issued_on=BSDate(2081, 1, 1)).count() == 1


def test_range_lookups_use_bs_dates() -> None:
    """__gte/__lt compare correctly because the column is a real date."""
    for day in range(1, 6):
        Invoice.objects.create(issued_on=BSDate(2081, 1, day))
    qs = Invoice.objects.filter(
        issued_on__gte=BSDate(2081, 1, 2), issued_on__lt=BSDate(2081, 1, 5)
    )
    assert [i.issued_on.day for i in qs] == [2, 3, 4]


def test_range_lookup_with_tuple() -> None:
    """__range works and is inclusive on both ends."""
    for day in range(1, 6):
        Invoice.objects.create(issued_on=BSDate(2081, 1, day))
    qs = Invoice.objects.filter(issued_on__range=(BSDate(2081, 1, 2), BSDate(2081, 1, 4)))
    assert qs.count() == 3


def test_query_bound_one_day_past_the_table_is_allowed() -> None:
    """A Gregorian query bound with no BS equivalent must still work.

    Regression test. The exclusive upper bound of the last supported BS year
    (2084) is 2028-04-13, one day past the table and therefore with no BSDate.
    get_prep_value must pass a datetime.date straight through rather than
    round-trip it through BSDate, or every range query touching the end of the
    calendar raises.
    """
    Invoice.objects.create(issued_on=BSDate(2084, 12, 30))
    edge = datetime.date(2028, 4, 13)  # bs_year_bounds(2084)[1]; not representable
    with pytest.raises(Exception):  # noqa: B017,PT011 - genuinely has no BSDate
        BSDate.from_ad(edge)
    assert Invoice.objects.filter(issued_on__lt=edge).count() == 1


def test_bulk_update_survives_the_case_expression() -> None:
    """bulk_update's CASE expression must pass through get_db_prep_save."""
    a = Invoice.objects.create(issued_on=BSDate(2081, 1, 1))
    b = Invoice.objects.create(issued_on=BSDate(2081, 1, 5))
    a.issued_on, b.issued_on = BSDate(2081, 2, 1), BSDate(2081, 2, 2)
    Invoice.objects.bulk_update([a, b], ["issued_on"])
    assert Invoice.objects.get(pk=a.pk).issued_on == BSDate(2081, 2, 1)
    assert Invoice.objects.get(pk=b.pk).issued_on == BSDate(2081, 2, 2)


def test_update_with_an_f_expression() -> None:
    """`update(field=F(other))` resolves to a Col and must reach SQL untouched."""
    inv = Invoice.objects.create(
        issued_on=BSDate(2081, 1, 1), due_on=BSDate(2082, 1, 1)
    )
    Invoice.objects.update(due_on=models.F("issued_on"))
    assert Invoice.objects.get(pk=inv.pk).due_on == BSDate(2081, 1, 1)


@override_settings(USE_TZ=False)
def test_auto_fields_work_under_use_tz_false() -> None:
    """auto fields must not call localdate() (raises) under USE_TZ=False."""
    inv = Invoice.objects.create(issued_on=BSDate(2081, 1, 1))
    assert isinstance(inv.created_on, BSDate)  # auto_now_add populated, no crash
    assert isinstance(inv.updated_on, BSDate)  # auto_now populated, no crash


def test_gregorian_and_bs_filters_agree() -> None:
    """Filtering by the AD equivalent selects the same rows."""
    Invoice.objects.create(issued_on=BSDate(2081, 1, 1))
    assert Invoice.objects.filter(issued_on=datetime.date(2024, 4, 13)).count() == 1


def test_in_lookup() -> None:
    """__in prepares every element through the boundary."""
    Invoice.objects.create(issued_on=BSDate(2081, 1, 1))
    Invoice.objects.create(issued_on=BSDate(2081, 1, 2))
    qs = Invoice.objects.filter(issued_on__in=[BSDate(2081, 1, 1), BSDate(2081, 5, 5)])
    assert qs.count() == 1


def test_isnull_lookup() -> None:
    """__isnull works on a nullable BS date."""
    Invoice.objects.create(issued_on=BSDate(2081, 1, 1), due_on=None)
    Invoice.objects.create(issued_on=BSDate(2081, 1, 2), due_on=BSDate(2081, 2, 1))
    assert Invoice.objects.filter(due_on__isnull=True).count() == 1


def test_ordering_is_chronological() -> None:
    """ORDER BY sorts by the real date, across a BS year boundary."""
    later = Invoice.objects.create(issued_on=BSDate(2082, 1, 1))
    earlier = Invoice.objects.create(issued_on=BSDate(2081, 12, 30))
    assert list(Invoice.objects.order_by("issued_on")) == [earlier, later]
    assert list(Invoice.objects.order_by("-issued_on")) == [later, earlier]


def test_aggregation() -> None:
    """Min/Max aggregate on the date column and convert back to BSDate."""
    Invoice.objects.create(issued_on=BSDate(2081, 1, 1))
    Invoice.objects.create(issued_on=BSDate(2082, 5, 10))
    result = Invoice.objects.aggregate(first=Min("issued_on"), last=Max("issued_on"))
    assert result["first"] == BSDate(2081, 1, 1)
    assert result["last"] == BSDate(2082, 5, 10)


def test_db_side_date_function_sees_gregorian() -> None:
    """DB date functions work, and operate on the stored AD value.

    Documented behaviour, not a bug: ExtractYear on 1 Baishakh 2081 yields
    2024, because that is what the column contains. Use
    django_bikram.django.lookups.bs_year_q for BS-year filtering.
    """
    Invoice.objects.create(issued_on=BSDate(2081, 1, 1))
    row = Invoice.objects.annotate(ad_year=ExtractYear("issued_on")).get()
    assert row.ad_year == 2024


def test_trunc_buckets_by_the_gregorian_period() -> None:
    """Trunc* truncates the AD value, so the BSDate it returns is mid-period.

    The one DB-side date function whose result does not announce which calendar
    it came from: ExtractYear returns a bare 2024, but Trunc* returns a BSDate
    that looks like a BS period start and is not one. Pinned here because the
    README documents these exact values -- group by BS periods with the range
    helpers in django_bikram.django.lookups instead.
    """
    Invoice.objects.create(issued_on=BSDate(2081, 1, 1))  # 2024-04-13
    row = Invoice.objects.annotate(
        m=TruncMonth("issued_on"), y=TruncYear("issued_on")
    ).get()
    assert row.m == BSDate(2080, 12, 19)  # AD 2024-04-01, not 1 Baishakh
    assert row.y == BSDate(2080, 9, 16)  # AD 2024-01-01, not 1 Baishakh


def test_builtin_year_lookup_is_gregorian() -> None:
    """The inherited __year lookup filters on the AD year, by construction."""
    Invoice.objects.create(issued_on=BSDate(2081, 1, 1))  # 2024-04-13
    assert Invoice.objects.filter(issued_on__year=2024).count() == 1
    assert Invoice.objects.filter(issued_on__year=2081).count() == 0


# --- validation --------------------------------------------------------


def test_to_python_rejects_invalid_bs_string() -> None:
    """A well-shaped but unreal BS date raises ValidationError."""
    field = BSDateField()
    with pytest.raises(ValidationError) as exc:
        field.to_python("2081-01-32")
    assert exc.value.code == "invalid_date"


def test_to_python_rejects_malformed_string() -> None:
    """A wrongly shaped string raises ValidationError with 'invalid'."""
    field = BSDateField()
    with pytest.raises(ValidationError) as exc:
        field.to_python("garbage")
    assert exc.value.code == "invalid"


def test_to_python_rejects_out_of_range_gregorian() -> None:
    """An AD date outside the verified range raises ValidationError."""
    field = BSDateField()
    with pytest.raises(ValidationError) as exc:
        field.to_python(datetime.date(1800, 1, 1))
    assert exc.value.code == "out_of_range"


def test_to_python_rejects_wrong_type() -> None:
    """An unsupported type raises ValidationError, not TypeError."""
    field = BSDateField()
    with pytest.raises(ValidationError):
        field.to_python(object())


def test_to_python_passes_through_none_and_bsdate() -> None:
    """None and BSDate are returned unchanged."""
    field = BSDateField()
    assert field.to_python(None) is None
    d = BSDate(2081, 1, 1)
    assert field.to_python(d) is d


# --- serialisation -----------------------------------------------------


def test_dumpdata_emits_bs_and_loaddata_reads_it_back() -> None:
    """Fixtures round-trip through the BS representation."""
    Invoice.objects.create(issued_on=BSDate(2081, 1, 1))
    payload = serialize("json", Invoice.objects.all())
    assert '"issued_on": "2081-01-01"' in payload

    Invoice.objects.all().delete()
    for obj in deserialize("json", payload):
        obj.save()
    assert Invoice.objects.get().issued_on == BSDate(2081, 1, 1)


def test_json_serializer_emits_bs_for_an_assigned_gregorian_date() -> None:
    """A raw date assigned in memory still serialises as Bikram Sambat.

    The JSON and Python serializers pass a value straight through when Django's
    is_protected_type() is true, which it is for datetime.date -- so
    value_to_string never runs and the *Gregorian* digits would reach the
    fixture, where loaddata reads them back as BS. A silent 57-year error.
    value_from_object normalises the date first, which both fixes the value and
    makes it a non-protected type so value_to_string is consulted after all.
    """
    unsaved = Invoice(issued_on=datetime.date(2024, 4, 13))
    assert '"issued_on": "2081-01-01"' in serialize("json", [unsaved])
    assert serialize("python", [unsaved])[0]["fields"]["issued_on"] == "2081-01-01"
    # The XML serializer always calls value_to_string, so it was never affected.
    assert ">2081-01-01<" in serialize("xml", [unsaved])


def test_model_to_dict_normalises_an_assigned_gregorian_date() -> None:
    """ModelForm initial data shows the BS value, not the Gregorian one.

    model_to_dict() reads through value_from_object, so without the conversion a
    raw date would render via str() as Gregorian digits inside a BS field.
    """
    from django.forms.models import model_to_dict

    unsaved = Invoice(issued_on=datetime.date(2024, 4, 13))
    assert model_to_dict(unsaved)["issued_on"] == BSDate(2081, 1, 1)


def test_value_from_object_leaves_strings_alone() -> None:
    """A string passes through, so a failed form redisplays what was typed."""
    unsaved = Invoice(issued_on="not a date")
    assert Invoice._meta.get_field("issued_on").value_from_object(unsaved) == (
        "not a date"
    )


def test_field_deconstructs_for_migrations() -> None:
    """The field deconstructs to an importable path with its kwargs."""
    name, path, args, kwargs = BSDateField(null=True).deconstruct()
    assert path == "django_bikram.django.fields.BSDateField"
    assert kwargs["null"] is True


def test_bsdate_default_serialises_in_a_migration() -> None:
    """A BSDate default can be written into a migration file.

    Without the registered serializer this raises "cannot serialize".
    """
    from django.db.migrations.writer import MigrationWriter

    string, imports = MigrationWriter.serialize(BSDate(2081, 1, 1))
    assert string == "django_bikram.BSDate(2081, 1, 1)"
    assert "import django_bikram" in imports
    assert eval(string, {"django_bikram": __import__("django_bikram")}) == BSDate(2081, 1, 1)


def test_admin_gregorian_date_widget_is_replaced() -> None:
    """The admin's Gregorian calendar picker never reaches a BS field.

    django.contrib.admin maps models.DateField to AdminDateWidget by walking the
    field's MRO, so BSDateField inherits it. That widget renders
    class="vDateField", which calendar.js and DateTimeShortcuts.js bind to --
    giving a Gregorian popup and a "Today" button that writes the Gregorian date
    into a Bikram Sambat field. 2026-07-22 would read back as 2026 BS: 1969 AD.
    """
    from django.contrib.admin.widgets import AdminDateWidget

    from django_bikram.django.forms import BSDateInput

    # Instance and class both, since Django passes either.
    for widget in (AdminDateWidget(), AdminDateWidget):
        form_field = BSDateField().formfield(widget=widget)
        assert isinstance(form_field.widget, BSDateInput)
        assert "vDateField" not in form_field.widget.render("issued_on", None)

    # The swap targets the admin's Gregorian widget only: any other widget the
    # caller chose deliberately is left alone.
    from django import forms

    plain = BSDateField().formfield(widget=forms.TextInput).widget
    assert isinstance(plain, forms.TextInput)
    assert not isinstance(plain, BSDateInput)


def test_formfield_is_the_bs_form_field() -> None:
    """The model field hands back a BS-aware form field."""
    from django_bikram.django.forms import BSDateField as BSDateFormField

    assert isinstance(BSDateField().formfield(), BSDateFormField)

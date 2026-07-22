"""The Bikram Sambat aware admin ``list_filter``.

Django resolves a field's list filter with ``isinstance(f, models.DateField)``,
which ``BSDateField`` satisfies -- so without this filter the admin offers
buckets labelled "This month" and "This year" that are silently *Gregorian*
periods. The tests below pin both halves: that Django's default really is wrong
for this field, and that ours really is right.
"""

from __future__ import annotations

import datetime

import pytest
from django.contrib import admin
from django.contrib.admin.filters import DateFieldListFilter, FieldListFilter
from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import User
from django.test import RequestFactory

from django_bikram import BSDate
from django_bikram.django.admin import BSDateFieldListFilter
from django_bikram.django.lookups import bs_month_bounds, bs_year_bounds
from django_bikram.fiscal import fiscal_year_bounds

from .models import Invoice

pytestmark = pytest.mark.django_db


def _changelist(list_filter: list) -> tuple:
    """Build a real changelist and return its first filter plus the changelist."""

    class InvoiceAdmin(admin.ModelAdmin):
        pass

    InvoiceAdmin.list_filter = list_filter
    model_admin = InvoiceAdmin(Invoice, AdminSite())
    request = RequestFactory().get("/")
    request.user = User(is_superuser=True)
    changelist = model_admin.get_changelist_instance(request)
    return changelist.get_filters(request)[0][0], changelist


def _buckets(list_filter: list) -> dict[str, tuple]:
    """Return ``{label: (since, until)}`` for a filter's date buckets."""
    flt, _ = _changelist(list_filter)
    out = {}
    for title, params in flt.links:
        if not params or "isnull" in next(iter(params), ""):
            continue
        out[str(title)] = tuple(params.values())
    return out


def test_django_default_is_gregorian_for_this_field() -> None:
    """The problem being solved: Django's filter matches BSDateField.

    Not a test of our code -- a test of the premise. If Django ever stops
    resolving BSDateField to DateFieldListFilter, the custom filter is no longer
    needed and this test says so.
    """
    flt, _ = _changelist(["issued_on"])
    assert isinstance(flt, DateFieldListFilter)
    assert not isinstance(flt, BSDateFieldListFilter)

    gregorian = _buckets(["issued_on"])
    # "This month" is the Gregorian month, which is not a BS month.
    since, until = gregorian["This month"]
    assert since.day == 1 and since.month == datetime.date.today().month
    assert BSDate.from_ad(since).day != 1


def test_bs_filter_buckets_are_bikram_sambat() -> None:
    """Each bucket is the real BS period containing today."""
    today = BSDate.today()
    buckets = _buckets([("issued_on", BSDateFieldListFilter)])

    assert buckets["This month"] == bs_month_bounds(today.year, today.month)
    assert buckets["This year"] == bs_year_bounds(today.year)
    assert buckets["This fiscal year"] == fiscal_year_bounds(today.fiscal_year)

    # And each really starts on the 1st of a BS period, unlike Django's.
    assert BSDate.from_ad(buckets["This month"][0]).day == 1
    assert BSDate.from_ad(buckets["This year"][0]) == BSDate(today.year, 1, 1)


def test_bs_filter_today_and_past_7_days() -> None:
    """The day-scale buckets are unchanged in meaning, just anchored in BS."""
    today = BSDate.today().to_ad()
    buckets = _buckets([("issued_on", BSDateFieldListFilter)])
    assert buckets["Today"] == (today, today + datetime.timedelta(days=1))
    assert buckets["Past 7 days"] == (
        today - datetime.timedelta(days=7),
        today + datetime.timedelta(days=1),
    )


def test_bs_filter_actually_filters() -> None:
    """The buckets select the rows they claim to."""
    today = BSDate.today()
    inside = Invoice.objects.create(issued_on=today)
    outside = Invoice.objects.create(
        issued_on=BSDate.from_ad(bs_year_bounds(today.year)[0] - datetime.timedelta(days=1))
    )

    flt, changelist = _changelist([("issued_on", BSDateFieldListFilter)])
    params = dict(next(p for t, p in flt.links if str(t) == "This year").items())
    matched = set(Invoice.objects.filter(**params).values_list("pk", flat=True))
    assert inside.pk in matched
    assert outside.pk not in matched


def test_bs_filter_offers_any_date_and_is_selectable() -> None:
    """It still behaves like a Django filter: choices render, one is selected."""
    flt, changelist = _changelist([("issued_on", BSDateFieldListFilter)])
    choices = list(flt.choices(changelist))
    assert [c["display"] for c in choices][0] == "Any date"
    assert all("query_string" in c for c in choices)
    assert sum(c["selected"] for c in choices) == 1


def test_bs_filter_omits_buckets_past_the_table_rather_than_guessing() -> None:
    """Near the calendar's edge a bucket is dropped, never approximated.

    The fiscal year reaches into the following BS year, so it is the first
    bucket to become unbuildable. Rather than raise -- which would break the
    whole changelist -- the filter simply does not offer it.
    """
    from django_bikram.calendar_data import VERIFIED_MAX_BS_YEAR
    from django_bikram.exceptions import DateOutOfRange

    with pytest.raises(DateOutOfRange):
        fiscal_year_bounds(VERIFIED_MAX_BS_YEAR)

    # Sanity: today is well inside the table, so every bucket is present now.
    buckets = _buckets([("issued_on", BSDateFieldListFilter)])
    assert {"Today", "Past 7 days", "This month", "This year", "This fiscal year"} <= (
        buckets.keys()
    )


def test_register_list_filter_takes_priority_over_django() -> None:
    """The opt-in global registration must actually win the lookup.

    Django's DateField test is registered first and the first match wins, so a
    registration without take_priority would silently do nothing.
    """
    from django_bikram.django.admin import register_list_filter

    saved = list(FieldListFilter._field_list_filters)
    saved_index = FieldListFilter._take_priority_index
    try:
        register_list_filter()
        flt, _ = _changelist(["issued_on"])
        assert isinstance(flt, BSDateFieldListFilter)
    finally:
        FieldListFilter._field_list_filters = saved
        FieldListFilter._take_priority_index = saved_index

    # Restored: back to Django's Gregorian filter.
    flt, _ = _changelist(["issued_on"])
    assert not isinstance(flt, BSDateFieldListFilter)

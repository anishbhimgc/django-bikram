"""Form field and widget behaviour."""

from __future__ import annotations

import datetime

import pytest
from django import forms
from django.core.exceptions import ValidationError

from django_bikram import BSDate
from django_bikram.django.forms import BSDateField, BSDateInput

from .models import Invoice


class InvoiceForm(forms.ModelForm):
    """A ModelForm over the BS date fields."""

    class Meta:
        """Form metadata."""

        model = Invoice
        fields = ["issued_on", "due_on"]


def test_clean_iso_input() -> None:
    """ISO-shaped BS input cleans to a BSDate."""
    assert BSDateField().clean("2081-01-01") == BSDate(2081, 1, 1)


@pytest.mark.parametrize(
    "value",
    ["2081-01-01", "2081/01/01", "01-01-2081", "01/01/2081", "01 Baishakh 2081", "1 Bai 2081"],
)
def test_default_input_formats(value: str) -> None:
    """Each default input format is accepted."""
    assert BSDateField().clean(value) == BSDate(2081, 1, 1)


def test_clean_devanagari_input() -> None:
    """Devanagari numerals are accepted by default."""
    assert BSDateField().clean("२०८१-०१-०१") == BSDate(2081, 1, 1)


def test_clean_nepali_month_name() -> None:
    """Nepali month names parse when the field is configured for Nepali."""
    field = BSDateField(lang="ne")
    assert field.clean("०१ वैशाख २०८१") == BSDate(2081, 1, 1)


def test_clean_passes_through_bsdate_and_date() -> None:
    """Non-string values are coerced consistently with the model field."""
    field = BSDateField()
    assert field.clean(BSDate(2081, 1, 1)) == BSDate(2081, 1, 1)
    assert field.clean(datetime.date(2024, 4, 13)) == BSDate(2081, 1, 1)


def test_custom_input_formats() -> None:
    """input_formats overrides the defaults."""
    field = BSDateField(input_formats=["%d.%m.%Y"])
    assert field.clean("01.01.2081") == BSDate(2081, 1, 1)
    with pytest.raises(ValidationError):
        field.clean("2081-01-01")


def test_invalid_input_raises() -> None:
    """Unparseable input raises with the 'invalid' code."""
    with pytest.raises(ValidationError) as exc:
        BSDateField().clean("not a date")
    assert exc.value.code == "invalid"


def test_unreal_date_raises() -> None:
    """A well-shaped but unreal BS date is rejected."""
    with pytest.raises(ValidationError):
        BSDateField().clean("2081-01-32")


def test_out_of_range_gets_its_own_message() -> None:
    """A supported shape with an unsupported year says so specifically.

    "2090-01-01 is outside the supported range" is a far more actionable
    message than "enter a valid date", and the distinction is the difference
    between a user typo and a package limitation.
    """
    with pytest.raises(ValidationError) as exc:
        BSDateField().clean("2090-01-01")
    assert exc.value.code == "out_of_range"


def test_required_and_empty() -> None:
    """Empty input honours required/optional."""
    with pytest.raises(ValidationError):
        BSDateField(required=True).clean("")
    assert BSDateField(required=False).clean("") is None


def test_has_changed() -> None:
    """has_changed compares cleaned values, not raw strings."""
    field = BSDateField()
    assert not field.has_changed(BSDate(2081, 1, 1), "2081-01-01")
    # Same date, different input format -- not a change.
    assert not field.has_changed(BSDate(2081, 1, 1), "01 Baishakh 2081")
    assert field.has_changed(BSDate(2081, 1, 1), "2081-01-02")
    assert field.has_changed(BSDate(2081, 1, 1), "garbage")


def test_widget_renders_bs() -> None:
    """The widget renders the BS value, not the Gregorian one."""
    html = BSDateInput().render("issued_on", BSDate(2081, 1, 1))
    assert 'value="2081-01-01"' in html
    assert "2024" not in html


def test_widget_renders_devanagari() -> None:
    """The widget honours lang and numerals."""
    widget = BSDateInput(format="%d %B %Y", lang="ne", numerals="devanagari")
    assert "०१ वैशाख २०८१" in widget.render("issued_on", BSDate(2081, 1, 1))


def test_widget_exposes_data_attribute_for_js_pickers() -> None:
    """A machine-readable ISO value is available for JS date pickers."""
    html = BSDateInput(format="%d %B %Y").render("issued_on", BSDate(2081, 1, 1))
    assert 'data-bs-date="2081-01-01"' in html


def test_widget_renders_empty() -> None:
    """A None value renders an empty input."""
    assert "value=" not in BSDateInput().render("issued_on", None)


def test_modelform_valid() -> None:
    """A ModelForm accepts BS input and saves the AD value."""
    form = InvoiceForm(data={"issued_on": "2081-01-01", "due_on": "2081-02-15"})
    assert form.is_valid(), form.errors
    assert form.cleaned_data["issued_on"] == BSDate(2081, 1, 1)


def test_modelform_invalid() -> None:
    """A ModelForm surfaces field errors for bad BS input."""
    form = InvoiceForm(data={"issued_on": "2081-01-32"})
    assert not form.is_valid()
    assert "issued_on" in form.errors


@pytest.mark.django_db
def test_modelform_save_round_trip() -> None:
    """Saving through a ModelForm stores and reloads the right date."""
    form = InvoiceForm(data={"issued_on": "2081-01-01"})
    assert form.is_valid(), form.errors
    invoice = form.save()
    invoice.refresh_from_db()
    assert invoice.issued_on == BSDate(2081, 1, 1)
    assert invoice.issued_on.to_ad() == datetime.date(2024, 4, 13)


@pytest.mark.django_db
def test_modelform_initial_renders_bs() -> None:
    """Editing an existing row shows the BS date in the input."""
    invoice = Invoice.objects.create(issued_on=BSDate(2081, 1, 1))
    form = InvoiceForm(instance=invoice)
    assert 'value="2081-01-01"' in form.as_p()


def test_invalid_input_is_redisplayed_verbatim() -> None:
    """A failed submission shows the user what they actually typed."""
    form = InvoiceForm(data={"issued_on": "whatever the user typed"})
    assert not form.is_valid()
    assert "whatever the user typed" in form.as_p()

"""DRF serializer field behaviour.

Skipped in full when djangorestframework is not installed, since it is an
optional extra.
"""

from __future__ import annotations

import datetime

import pytest

from django_bikram import BSDate

from .models import Invoice

rest_framework = pytest.importorskip("rest_framework", reason="DRF is an optional extra")

from rest_framework import serializers  # noqa: E402

from django_bikram.django.drf import BSDateField, register_serializer_field  # noqa: E402


class InvoiceSerializer(serializers.ModelSerializer):
    """Serializer with an explicitly declared BS date field."""

    issued_on = BSDateField()

    class Meta:
        """Serializer metadata."""

        model = Invoice
        fields = ["id", "issued_on"]


def test_to_representation() -> None:
    """A BSDate renders as an ISO-shaped BS string."""
    assert BSDateField().to_representation(BSDate(2081, 1, 1)) == "2081-01-01"


def test_to_representation_converts_gregorian() -> None:
    """A datetime.date is read as Gregorian and rendered as BS."""
    assert BSDateField().to_representation(datetime.date(2024, 4, 13)) == "2081-01-01"


def test_to_representation_none() -> None:
    """None renders as None."""
    assert BSDateField().to_representation(None) is None


def test_to_representation_custom_format() -> None:
    """format/lang/numerals control the output."""
    field = BSDateField(format="%d %B %Y", lang="ne", numerals="devanagari")
    assert field.to_representation(BSDate(2081, 1, 1)) == "०१ वैशाख २०८१"


def test_to_internal_value() -> None:
    """An ISO-shaped BS string parses to a BSDate."""
    assert BSDateField().to_internal_value("2081-01-01") == BSDate(2081, 1, 1)


def test_to_internal_value_devanagari() -> None:
    """Devanagari numerals are accepted by default."""
    assert BSDateField().to_internal_value("२०८१-०१-०१") == BSDate(2081, 1, 1)


def test_to_internal_value_accepts_dates() -> None:
    """BSDate and datetime.date inputs are coerced."""
    field = BSDateField()
    assert field.to_internal_value(BSDate(2081, 1, 1)) == BSDate(2081, 1, 1)
    assert field.to_internal_value(datetime.date(2024, 4, 13)) == BSDate(2081, 1, 1)


def test_to_internal_value_invalid() -> None:
    """Unparseable input raises a DRF ValidationError."""
    with pytest.raises(serializers.ValidationError):
        BSDateField().to_internal_value("not a date")


def test_to_internal_value_unreal_date() -> None:
    """A well-shaped but unreal BS date is rejected."""
    with pytest.raises(serializers.ValidationError):
        BSDateField().to_internal_value("2081-01-32")


def test_to_internal_value_out_of_range_message() -> None:
    """An unsupported year gets the specific out-of-range message."""
    with pytest.raises(serializers.ValidationError) as exc:
        BSDateField().to_internal_value("2090-01-01")
    assert "outside the supported" in str(exc.value)


def test_to_internal_value_wrong_type() -> None:
    """A non-string, non-date input is a validation error, not a crash."""
    with pytest.raises(serializers.ValidationError):
        BSDateField().to_internal_value(12345)


@pytest.mark.django_db
def test_serializer_round_trip() -> None:
    """A ModelSerializer reads and writes BS dates."""
    invoice = Invoice.objects.create(issued_on=BSDate(2081, 1, 1))
    assert InvoiceSerializer(invoice).data["issued_on"] == "2081-01-01"

    serializer = InvoiceSerializer(data={"issued_on": "2082-05-10"})
    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["issued_on"] == BSDate(2082, 5, 10)


@pytest.mark.django_db
def test_serializer_save_stores_gregorian() -> None:
    """Saving through DRF stores the AD date in the column."""
    serializer = InvoiceSerializer(data={"issued_on": "2081-01-01"})
    assert serializer.is_valid(), serializer.errors
    invoice = serializer.save()
    invoice.refresh_from_db()
    assert invoice.issued_on.to_ad() == datetime.date(2024, 4, 13)


def test_serializer_reports_errors() -> None:
    """Invalid input surfaces as a field error."""
    serializer = InvoiceSerializer(data={"issued_on": "2081-01-32"})
    assert not serializer.is_valid()
    assert "issued_on" in serializer.errors


def test_modelserializer_without_registration_uses_drf_datefield() -> None:
    """Auto-built fields are Gregorian until register_serializer_field() runs.

    This is the trap the registration helper exists to close: DRF resolves our
    model field to its own DateField (because it subclasses DateField) and
    emits the AD date, which looks plausible and is the wrong calendar.
    """

    class AutoSerializer(serializers.ModelSerializer):
        class Meta:
            model = Invoice
            fields = ["issued_on"]

    mapping = serializers.ModelSerializer.serializer_field_mapping
    from django_bikram.django.fields import BSDateField as BSDateModelField

    assert mapping.get(BSDateModelField) is None
    assert isinstance(AutoSerializer().fields["issued_on"], serializers.DateField)


def test_register_serializer_field_fixes_modelserializer() -> None:
    """After registration, ModelSerializer builds the BS field automatically."""
    from django_bikram.django.fields import BSDateField as BSDateModelField

    mapping = serializers.ModelSerializer.serializer_field_mapping
    original = mapping.copy()
    try:
        register_serializer_field()

        class AutoSerializer(serializers.ModelSerializer):
            class Meta:
                model = Invoice
                fields = ["issued_on"]

        field = AutoSerializer().fields["issued_on"]
        assert isinstance(field, BSDateField)
        assert mapping[BSDateModelField] is BSDateField
    finally:
        # Restore, so this test cannot leak into the one above via ordering.
        serializers.ModelSerializer.serializer_field_mapping = original


def test_field_parses_its_own_output_for_any_format() -> None:
    """A client must be able to POST back a value the API just returned.

    With format="%d.%m.%Y" the field emitted "01.01.2081" and then rejected it,
    so round-tripping a fetched record failed validation on the API's own
    output. The render format is now always accepted on input.
    """
    date = BSDate(2081, 1, 1)
    for kwargs in (
        {},
        {"format": "%d %B %Y"},
        {"format": "%d.%m.%Y"},
        {"format": "%Y/%m/%d"},
        {"format": "%d %B %Y", "lang": "ne", "numerals": "devanagari"},
    ):
        field = BSDateField(**kwargs)
        rendered = field.to_representation(date)
        assert field.to_internal_value(rendered) == date, kwargs


def test_explicit_input_formats_are_not_widened() -> None:
    """Passing input_formats states exactly what is accepted, and nothing else."""
    field = BSDateField(format="%d.%m.%Y", input_formats=["%Y-%m-%d"])
    assert field.input_formats == ("%Y-%m-%d",)
    assert field.to_internal_value("2081-01-01") == BSDate(2081, 1, 1)
    with pytest.raises(serializers.ValidationError):
        field.to_internal_value("01.01.2081")

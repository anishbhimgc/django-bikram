"""Django REST Framework serializer field for Bikram Sambat dates.

DRF is an optional dependency. Importing this module without it installed
raises :exc:`ImportError` with an actionable message rather than a bare
``ModuleNotFoundError`` from somewhere deep in the import graph::

    pip install django-bikram[drf]

Nothing else in :mod:`django_bikram` imports this module, so the dependency stays
opt-in.
"""

from __future__ import annotations

import datetime
from collections.abc import Sequence
from typing import Any, Literal

try:
    from rest_framework import serializers
except ImportError as exc:  # pragma: no cover - depends on the environment
    raise ImportError(
        "django_bikram.django.drf requires djangorestframework, which is an optional "
        "dependency of django-bikram. Install it with: "
        "pip install django-bikram[drf]"
    ) from exc

from ..date import BSDate
from ..exceptions import DateOutOfRange, InvalidBSDate
from ..formatting import format_bs, parse_bs
from .fields import BSDateField as BSDateModelField
from .forms import DEFAULT_INPUT_FORMATS

__all__ = ["BSDateField", "register_serializer_field"]


class BSDateField(serializers.Field):
    """Serialise a :class:`~django_bikram.date.BSDate` to and from a string.

    By default the representation is the Bikram Sambat ``YYYY-MM-DD`` string,
    which sorts, round-trips, and is what a Nepali client expects to display.

    Example:
        >>> class InvoiceSerializer(serializers.ModelSerializer):
        ...     issued_on = BSDateField()

    To emit Devanagari for a human-facing endpoint::

        issued_on = BSDateField(format="%d %B %Y", lang="ne",
                                numerals="devanagari")

    Note that a non-ISO ``format`` is still accepted on input only if a
    matching entry exists in ``input_formats``; the two are configured
    independently, as in DRF's own ``DateField``.
    """

    default_error_messages = {
        "invalid": (
            "Date has wrong format. Expected a Bikram Sambat date in one of: "
            "{formats}."
        ),
        "out_of_range": (
            "Date is outside the supported Bikram Sambat calendar range "
            "({min_year}-{max_year} BS)."
        ),
        "datatype": "Expected a string but got {input_type}.",
    }

    def __init__(
        self,
        *,
        format: str = "%Y-%m-%d",  # noqa: A002 - matches DRF's parameter name
        input_formats: Sequence[str] | None = None,
        lang: Literal["en", "ne"] = "en",
        numerals: Literal["ascii", "devanagari"] = "ascii",
        input_numerals: Literal["ascii", "devanagari", "auto"] = "auto",
        **kwargs: Any,
    ) -> None:
        """Configure the field.

        Args:
            format: strftime-style format for output.
            input_formats: Formats accepted on input; defaults to
                :data:`django_bikram.django.forms.DEFAULT_INPUT_FORMATS`.
            lang: Language for month and weekday names, in both directions.
            numerals: Numeral system for output digits.
            input_numerals: Numeral system accepted on input. ``"auto"``
                accepts both.
            **kwargs: Passed to :class:`rest_framework.serializers.Field`.
        """
        self.format = format
        self.input_formats = tuple(input_formats or DEFAULT_INPUT_FORMATS)
        self.lang = lang
        self.numerals = numerals
        self.input_numerals = input_numerals
        super().__init__(**kwargs)

    def to_representation(self, value: Any) -> str | None:
        """Render a value for output.

        Args:
            value: A :class:`BSDate`, a :class:`datetime.date` (read as
                Gregorian), or ``None``.

        Returns:
            The formatted string, or ``None``.
        """
        if value in (None, ""):
            return None
        if isinstance(value, datetime.datetime):
            value = value.date()
        # A BSDate is not a datetime.date, so this branch only catches genuine
        # Gregorian dates; a BSDate falls straight through to format_bs.
        if isinstance(value, datetime.date):
            value = BSDate.from_ad(value)
        return format_bs(value, self.format, lang=self.lang, numerals=self.numerals)

    def to_internal_value(self, data: Any) -> BSDate:
        """Parse incoming data into a :class:`BSDate`.

        Args:
            data: A string, :class:`datetime.date`, or :class:`BSDate`.

        Returns:
            The parsed date.

        Raises:
            rest_framework.exceptions.ValidationError: If the value is not a
                parseable Bikram Sambat date in the supported range.
        """
        if isinstance(data, BSDate):
            return data
        if isinstance(data, datetime.datetime):
            data = data.date()
        if isinstance(data, datetime.date):
            try:
                return BSDate.from_ad(data)
            except DateOutOfRange:
                self._fail_out_of_range()
        if not isinstance(data, str):
            self.fail("datatype", input_type=type(data).__name__)

        text = data.strip()
        out_of_range = False
        for fmt in self.input_formats:
            try:
                return BSDate(
                    *parse_bs(text, fmt, lang=self.lang, numerals=self.input_numerals)
                )
            except DateOutOfRange:
                out_of_range = True
            except InvalidBSDate:
                continue
        if out_of_range:
            self._fail_out_of_range()
        self.fail("invalid", formats=", ".join(self.input_formats))

    def _fail_out_of_range(self) -> None:
        """Raise the out-of-range validation error.

        Raises:
            rest_framework.exceptions.ValidationError: Always.
        """
        from ..calendar_data import MAX_BS_YEAR, MIN_BS_YEAR

        self.fail("out_of_range", min_year=MIN_BS_YEAR, max_year=MAX_BS_YEAR)


def register_serializer_field() -> None:
    """Map :class:`~django_bikram.django.fields.BSDateField` in ``ModelSerializer``.

    ``ModelSerializer`` builds fields by looking the model field's class up in
    ``serializer_field_mapping``. Because our model field subclasses
    :class:`~django.db.models.DateField`, DRF would otherwise resolve it to
    ``serializers.DateField`` and emit **Gregorian** dates -- correct-looking
    output that is silently the wrong calendar.

    Call this once at startup (an ``AppConfig.ready()`` is the natural place)
    to make every ``ModelSerializer`` handle the field correctly by default::

        class MyAppConfig(AppConfig):
            def ready(self):
                from django_bikram.django.drf import register_serializer_field
                register_serializer_field()

    It is not called on import: mutating a third-party class as a side effect
    of importing a module is the kind of action-at-a-distance that makes test
    suites order-dependent. Declaring the field explicitly on a serializer
    works without it.
    """
    serializers.ModelSerializer.serializer_field_mapping[BSDateModelField] = BSDateField

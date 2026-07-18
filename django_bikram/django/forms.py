"""Form field and widget for Bikram Sambat dates."""

from __future__ import annotations

import datetime
from collections.abc import Sequence
from typing import Any, Literal

from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from ..date import BSDate
from ..exceptions import DateOutOfRange, InvalidBSDate
from ..formatting import format_bs, parse_bs

__all__ = ["BSDateField", "BSDateInput", "DEFAULT_INPUT_FORMATS"]

#: Formats tried in order when parsing user input.
#:
#: ISO-shaped input comes first because it is what the widget renders, so the
#: common case -- a round-tripped value -- matches on the first attempt.
DEFAULT_INPUT_FORMATS: tuple[str, ...] = (
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%Y.%m.%d",
    "%d-%m-%Y",
    "%d/%m/%Y",
    "%d %B %Y",
    "%d %b %Y",
    "%B %d, %Y",
)


class BSDateInput(forms.TextInput):
    """A text input that renders a :class:`BSDate` in Bikram Sambat.

    Deliberately a plain text input rather than ``<input type="date">``: the
    browser's native date picker only speaks Gregorian and would rewrite the
    value. Pair it with a Nepali date-picker JS library if you want a calendar
    UI -- the ``data-bs-date`` attribute is there for exactly that.
    """

    def __init__(
        self,
        attrs: dict[str, Any] | None = None,
        *,
        format: str = "%Y-%m-%d",
        lang: Literal["en", "ne"] = "en",
        numerals: Literal["ascii", "devanagari"] = "ascii",
    ) -> None:
        """Configure the widget.

        Args:
            attrs: Extra HTML attributes.
            format: strftime-style format used to render the value.
            lang: Language for month and weekday names.
            numerals: Numeral system for rendered digits.
        """
        self.format = format
        self.lang = lang
        self.numerals = numerals
        super().__init__(attrs)

    def format_value(self, value: Any) -> str | None:
        """Render the value for display.

        Args:
            value: A :class:`BSDate`, a string, or ``None``.

        Returns:
            The rendered string, or ``None`` for an empty value.
        """
        if value is None or value == "":
            return None
        if isinstance(value, BSDate):
            return format_bs(
                value, self.format, lang=self.lang, numerals=self.numerals
            )
        return str(value)

    def get_context(
        self, name: str, value: Any, attrs: dict[str, Any] | None
    ) -> dict[str, Any]:
        """Add a ``data-bs-date`` hook for JS date pickers.

        Args:
            name: The field name.
            value: The field value.
            attrs: HTML attributes.

        Returns:
            The template context.
        """
        context = super().get_context(name, value, attrs)
        if isinstance(value, BSDate):
            context["widget"]["attrs"]["data-bs-date"] = value.isoformat()
        return context


class BSDateField(forms.Field):
    """A form field that cleans user input into a :class:`BSDate`.

    Example:
        >>> field = BSDateField()
        >>> field.clean("2081-01-01")
        BSDate(2081, 1, 1)
    """

    widget = BSDateInput
    default_error_messages = {
        "invalid": _("Enter a valid Bikram Sambat date."),
        "out_of_range": _(
            "That date is outside the supported Bikram Sambat calendar range."
        ),
    }

    def __init__(
        self,
        *,
        input_formats: Sequence[str] | None = None,
        lang: Literal["en", "ne"] = "en",
        numerals: Literal["ascii", "devanagari", "auto"] = "auto",
        **kwargs: Any,
    ) -> None:
        """Configure the field.

        Args:
            input_formats: Formats to try when parsing; defaults to
                :data:`DEFAULT_INPUT_FORMATS`.
            lang: Language for month names in input and output.
            numerals: Numeral system accepted on input. ``"auto"`` accepts
                both ASCII and Devanagari.
            **kwargs: Passed to :class:`django.forms.Field`.
        """
        self.input_formats = tuple(input_formats or DEFAULT_INPUT_FORMATS)
        self.lang = lang
        self.numerals = numerals
        super().__init__(**kwargs)
        # Keep the widget's language in step with the field's unless the
        # caller configured the widget explicitly. Bind through a local because
        # Django replaces the ``widget`` class attribute with an instance during
        # ``super().__init__`` -- a swap a stub-less checker cannot see.
        widget: Any = self.widget
        if isinstance(widget, BSDateInput):
            widget.lang = lang
            if numerals != "auto":
                widget.numerals = numerals

    def to_python(self, value: Any) -> BSDate | None:
        """Parse user input into a :class:`BSDate`.

        Args:
            value: Raw input: a :class:`BSDate`, :class:`datetime.date`,
                string, or empty value.

        Returns:
            The parsed date, or ``None`` when empty.

        Raises:
            ValidationError: If the input matches no accepted format, or names
                a date outside the verified calendar range.
        """
        if value in self.empty_values:
            return None
        if isinstance(value, BSDate):
            return value
        if isinstance(value, datetime.datetime):
            value = value.date()
        if isinstance(value, datetime.date):
            try:
                return BSDate.from_ad(value)
            except DateOutOfRange as exc:
                raise ValidationError(
                    self.error_messages["out_of_range"], code="out_of_range"
                ) from exc

        text = str(value).strip()
        out_of_range = False
        for fmt in self.input_formats:
            try:
                return BSDate(
                    *parse_bs(text, fmt, lang=self.lang, numerals=self.numerals)
                )
            except DateOutOfRange:
                # Shape matched but the year is unsupported -- a strictly more
                # useful message than "invalid", so remember it and keep
                # trying the remaining formats.
                out_of_range = True
            except InvalidBSDate:
                continue
        if out_of_range:
            raise ValidationError(
                self.error_messages["out_of_range"], code="out_of_range"
            )
        raise ValidationError(self.error_messages["invalid"], code="invalid")

    def prepare_value(self, value: Any) -> Any:
        """Prepare a value for rendering, leaving invalid input untouched.

        Args:
            value: The current value.

        Returns:
            The value for the widget; raw strings pass through so that a failed
            submission redisplays what the user actually typed.
        """
        return value

    def has_changed(self, initial: Any, data: Any) -> bool:
        """Report whether submitted data differs from the initial value.

        Args:
            initial: The initial value.
            data: The submitted value.

        Returns:
            ``True`` if the cleaned values differ.
        """
        if self.disabled:
            return False
        try:
            initial_date = self.to_python(initial)
            data_date = self.to_python(data)
        except ValidationError:
            return True
        return initial_date != data_date

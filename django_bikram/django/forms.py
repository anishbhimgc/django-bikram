"""Form field and widget for Bikram Sambat dates."""

from __future__ import annotations

import datetime
from collections.abc import Sequence
from typing import Any, Literal

from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from ..calendar_data import VERIFIED_BS_MONTH_DAYS
from ..date import BSDate
from ..exceptions import DateOutOfRange, InvalidBSDate
from ..formatting import format_bs, parse_bs

__all__ = [
    "BSDateField",
    "BSDateInput",
    "BSDatePickerInput",
    "DEFAULT_INPUT_FORMATS",
    "encode_verified_calendar",
]

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
        format: str | None = None,
        lang: Literal["en", "ne"] | None = None,
        numerals: Literal["ascii", "devanagari"] | None = None,
    ) -> None:
        """Configure the widget.

        ``lang`` and ``numerals`` default to ``None`` rather than to their
        values so the widget can tell "caller said English" from "caller said
        nothing". :class:`BSDateField` propagates its own settings into the
        widget, and must not overwrite a choice made here -- see
        :meth:`BSDateField.__init__`.

        Args:
            attrs: Extra HTML attributes.
            format: strftime-style format used to render the value.
            lang: Language for month and weekday names. Defaults to ``"en"``.
            numerals: Numeral system for rendered digits. Defaults to
                ``"ascii"``.
        """
        self.format = "%Y-%m-%d" if format is None else format
        self.lang: Literal["en", "ne"] = "en" if lang is None else lang
        self.numerals: Literal["ascii", "devanagari"] = (
            "ascii" if numerals is None else numerals
        )
        #: Which settings were chosen here rather than left to default, so a
        #: containing field knows what it may propagate into and what it must
        #: adopt. See :meth:`BSDateField.__init__`.
        self.lang_was_set = lang is not None
        self.numerals_was_set = numerals is not None
        self.format_was_set = format is not None
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
        context: dict[str, Any] = super().get_context(name, value, attrs)
        if isinstance(value, BSDate):
            context["widget"]["attrs"]["data-bs-date"] = value.isoformat()
        return context


def encode_verified_calendar() -> str:
    """Encode the verified month-length table as one compact ASCII string.

    Twelve characters per year, starting at
    :data:`~django_bikram.calendar_data.VERIFIED_MIN_BS_YEAR`, each holding
    ``days - 29``. Month lengths are always 29 to 32, so every month fits in a
    single digit ``0``-``3`` and the whole 110-year calendar costs ~1.3 kB --
    small enough for the browser to do real Bikram Sambat arithmetic rather than
    round-trip to the server for every click.

    :class:`BSDatePickerInput` ships this in a static file; a test asserts the
    shipped copy still equals this function's output, so the JavaScript calendar
    cannot silently drift from the Python one.

    Returns:
        The encoded table.

    Example:
        >>> encoded = encode_verified_calendar()
        >>> len(encoded) % 12
        0
        >>> int(encoded[0]) + 29        # Baishakh 1975 BS
        31
    """
    return "".join(
        str(days - 29)
        for year in sorted(VERIFIED_BS_MONTH_DAYS)
        for days in VERIFIED_BS_MONTH_DAYS[year]
    )


class BSDatePickerInput(BSDateInput):
    """A :class:`BSDateInput` with a dependency-free Bikram Sambat calendar.

    The plain :class:`BSDateInput` deliberately ships no calendar: the browser's
    native picker speaks only Gregorian, and pulling in a third-party JS date
    library would hand this package a supply chain it does not otherwise have.
    This widget closes that gap without either compromise -- the calendar is
    13 kB of vanilla JavaScript (4 kB gzipped) with no build step, no npm, and
    no CDN.

    It is progressive enhancement: the field is the same text input underneath,
    so it still works with JavaScript disabled, and every value the picker
    writes is re-validated server-side by :class:`BSDateField` exactly as typed
    input is.

    Example:
        >>> class InvoiceForm(forms.ModelForm):
        ...     class Meta:
        ...         model, fields = Invoice, ["issued_on"]
        ...         widgets = {"issued_on": BSDatePickerInput(lang="ne",
        ...                                                   numerals="devanagari")}
        ...     # doctest: +SKIP

    Requires ``django.contrib.staticfiles`` (which the admin already requires)
    and ``{{ form.media }}`` in the template. Inside the admin both are handled
    for you.
    """

    class Media:
        """Static assets for the picker, deduplicated by Django's ``Media``."""

        css = {"all": ("django_bikram/bs-datepicker.css",)}
        js = ("django_bikram/bs-datepicker.js",)

    def get_context(
        self, name: str, value: Any, attrs: dict[str, Any] | None
    ) -> dict[str, Any]:
        """Add the hooks the picker JavaScript binds to.

        The script reads its configuration off the element rather than from a
        global, so several fields on one page can use different languages and
        numeral systems.

        Args:
            name: The field name.
            value: The field value.
            attrs: HTML attributes.

        Returns:
            The template context.
        """
        context: dict[str, Any] = super().get_context(name, value, attrs)
        widget_attrs = context["widget"]["attrs"]
        existing = widget_attrs.get("class", "")
        widget_attrs["class"] = f"{existing} bs-datepicker".strip()
        widget_attrs["data-bs-lang"] = self.lang
        widget_attrs["data-bs-numerals"] = self.numerals
        widget_attrs["data-bs-format"] = self.format
        widget_attrs.setdefault("autocomplete", "off")
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
        lang: Literal["en", "ne"] | None = None,
        numerals: Literal["ascii", "devanagari", "auto"] = "auto",
        **kwargs: Any,
    ) -> None:
        """Configure the field.

        ``lang`` defaults to ``None`` rather than ``"en"`` so the field can tell
        "caller said English" from "caller said nothing", which is what lets the
        field and its widget agree; see below.

        Args:
            input_formats: Formats to try when parsing; defaults to
                :data:`DEFAULT_INPUT_FORMATS`.
            lang: Language for month names in input and output. Defaults to the
                widget's language if one was set there, otherwise ``"en"``.
            numerals: Numeral system accepted on input. ``"auto"`` accepts
                both ASCII and Devanagari.
            **kwargs: Passed to :class:`django.forms.Field`.
        """
        self.input_formats = tuple(input_formats or DEFAULT_INPUT_FORMATS)
        self.numerals = numerals
        super().__init__(**kwargs)

        # Field and widget must end up on the *same* language, or the form
        # cannot parse what it just rendered: a widget set to "ne" emits
        # "०१ वैशाख २०८१", which a field left at "en" rejects as invalid --
        # a form that fails to round-trip its own output.
        #
        # So whichever side was set explicitly wins, and the other adopts it.
        # The field wins if both were set. Bind the widget through a local
        # because Django replaces the ``widget`` class attribute with an
        # instance during ``super().__init__`` -- a swap a stub-less checker
        # cannot see.
        widget: Any = self.widget
        widget_is_ours = isinstance(widget, BSDateInput)
        if lang is not None:
            self.lang: Literal["en", "ne"] = lang
        elif widget_is_ours and widget.lang_was_set:
            self.lang = widget.lang
        else:
            self.lang = "en"

        if widget_is_ours:
            if not widget.lang_was_set:
                widget.lang = self.lang
            if numerals != "auto" and not widget.numerals_was_set:
                widget.numerals = numerals
            # Same round-trip guarantee for the format: a widget rendering
            # "%d %B %Y" must be parseable even when the caller did not think to
            # add that format to input_formats. Only when *both* were left to us
            # -- an explicit input_formats is an exact statement of what the
            # field accepts, and widening it would be overriding the caller.
            # Appended, not prepended, so the default order still decides
            # ambiguous cases.
            if (
                input_formats is None
                and widget.format_was_set
                and widget.format not in self.input_formats
            ):
                self.input_formats = (*self.input_formats, widget.format)

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

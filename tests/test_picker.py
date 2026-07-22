"""The bundled date picker widget and the calendar data it ships to the browser.

The picker does Bikram Sambat arithmetic in JavaScript, which means the calendar
table exists in two languages. The load-bearing test here is
:func:`test_shipped_calendar_matches_python`: it asserts the copy compiled into
the static file still equals the Python table, so extending the calendar without
regenerating the asset fails loudly instead of shipping a browser that disagrees
with the server.
"""

from __future__ import annotations

import re
from pathlib import Path

from django_bikram import BSDate
from django_bikram.calendar_data import VERIFIED_BS_MONTH_DAYS, VERIFIED_MIN_BS_YEAR
from django_bikram.django.forms import (
    BSDateField,
    BSDateInput,
    BSDatePickerInput,
    encode_verified_calendar,
)

STATIC = Path(__file__).resolve().parent.parent / "django_bikram" / "static"
PICKER_JS = STATIC / "django_bikram" / "bs-datepicker.js"
PICKER_CSS = STATIC / "django_bikram" / "bs-datepicker.css"


# --- the encoded calendar ----------------------------------------------


def test_encoding_round_trips_the_table() -> None:
    """Twelve digits per year, each holding days - 29."""
    encoded = encode_verified_calendar()
    assert len(encoded) == len(VERIFIED_BS_MONTH_DAYS) * 12
    for index, year in enumerate(sorted(VERIFIED_BS_MONTH_DAYS)):
        chunk = encoded[index * 12 : (index + 1) * 12]
        decoded = tuple(int(c) + 29 for c in chunk)
        assert decoded == VERIFIED_BS_MONTH_DAYS[year]


def test_shipped_calendar_matches_python() -> None:
    """The static file's calendar must equal the Python table.

    If this fails, the calendar was extended without regenerating
    django_bikram/static/django_bikram/bs-datepicker.js -- the browser would
    disagree with the server about month lengths, which is the one bug this
    package cannot tolerate. Rebuild the MONTHS literal from
    encode_verified_calendar().
    """
    source = PICKER_JS.read_text(encoding="utf-8")
    match = re.search(r'var MONTHS = "([0-3]+)";', source)
    assert match is not None, "MONTHS literal not found in the shipped picker"
    assert match.group(1) == encode_verified_calendar()

    min_year = re.search(r"var MIN_YEAR = (\d+);", source)
    assert min_year is not None
    assert int(min_year.group(1)) == VERIFIED_MIN_BS_YEAR


def test_shipped_assets_are_self_contained() -> None:
    """No CDN, no npm, no external fetch: the whole point of bundling it."""
    for asset in (PICKER_JS, PICKER_CSS):
        text = asset.read_text(encoding="utf-8")
        assert "http://" not in text
        assert "https://" not in text.replace("https://github.com", "")
        assert "import " not in text
        assert "require(" not in text


# --- the widget --------------------------------------------------------


def test_panel_escapes_clipping_ancestors() -> None:
    """The panel must be position:fixed, or Django admin hides it entirely.

    An absolutely-positioned popover is clipped by any ancestor with
    overflow != visible. Django admin's `.form-row` sets `overflow: hidden`, so
    in 0.3.0 the calendar rendered correctly -- 31 day buttons, 274x315px, not
    hidden -- and was invisible anyway, in the one place the widget matters
    most. Only a real browser caught it; nothing here can, so this pins the
    property that fixes it.
    """
    css = PICKER_CSS.read_text(encoding="utf-8")
    # Match the rule itself, anchored at line start -- ".bs-dp-panel" also
    # appears in the file's header comment.
    rule = re.search(r"^\.bs-dp-panel\s*\{(.*?)^\}", css, re.S | re.M)
    assert rule is not None, "no .bs-dp-panel rule found"
    assert "position: fixed" in rule.group(1)
    assert "position: absolute" not in rule.group(1)


def test_panel_is_positioned_from_javascript() -> None:
    """position:fixed means CSS cannot place the panel; JS must, and must re-place.

    Its size depends on the month (5 or 6 week rows), and it has to stay
    attached to its input when an ancestor scrolls.
    """
    js = PICKER_JS.read_text(encoding="utf-8")
    assert "function place()" in js
    assert "getBoundingClientRect" in js
    # Re-placed on open, after every re-render, and while scrolling or resizing.
    assert js.count("place();") >= 2
    assert 'addEventListener("scroll", place, true)' in js
    assert 'removeEventListener("scroll", place, true)' in js


def test_picker_declares_its_media() -> None:
    """Django's Media handles deduplication across many fields on a page."""
    media = str(BSDatePickerInput().media)
    assert "django_bikram/bs-datepicker.js" in media
    assert "django_bikram/bs-datepicker.css" in media


def test_picker_renders_its_hooks() -> None:
    """The script reads configuration off the element, not from a global."""
    html = BSDatePickerInput(lang="ne", numerals="devanagari").render(
        "issued_on", BSDate(2081, 1, 1)
    )
    assert 'class="bs-datepicker"' in html
    assert 'data-bs-lang="ne"' in html
    assert 'data-bs-numerals="devanagari"' in html
    assert 'data-bs-format="%Y-%m-%d"' in html
    # The ISO hook from BSDateInput survives, so JS never re-parses the display
    # text to learn which date is selected.
    assert 'data-bs-date="2081-01-01"' in html
    assert "autocomplete" in html


def test_picker_keeps_a_caller_supplied_class() -> None:
    """Adding our hook must not clobber styling the caller asked for."""
    html = BSDatePickerInput(attrs={"class": "form-control"}).render("d", None)
    assert "form-control" in html
    assert "bs-datepicker" in html


def test_picker_is_still_a_text_input() -> None:
    """Progressive enhancement: it works with JavaScript switched off."""
    html = BSDatePickerInput().render("d", BSDate(2081, 1, 1))
    assert 'type="text"' in html
    assert "2081-01-01" in html


def test_picker_inherits_bs_date_input() -> None:
    """It is a BSDateInput, so the model field's admin swap accepts it too."""
    assert issubclass(BSDatePickerInput, BSDateInput)


# --- widget language propagation ---------------------------------------


def test_field_propagates_its_language_to_a_default_widget() -> None:
    """A widget the caller did not configure follows the field."""
    field = BSDateField(lang="ne", numerals="devanagari")
    assert field.widget.lang == "ne"
    assert field.widget.numerals == "devanagari"


def test_field_does_not_clobber_an_explicit_widget_language() -> None:
    """BSDateInput(lang="ne") used to be silently reset to the field's "en"."""
    field = BSDateField(widget=BSDateInput(lang="ne", numerals="devanagari"))
    assert field.widget.lang == "ne"
    assert field.widget.numerals == "devanagari"

    # And the field still wins where the widget stayed at its default.
    mixed = BSDateField(lang="ne", widget=BSDateInput(numerals="devanagari"))
    assert mixed.widget.lang == "ne"
    assert mixed.widget.numerals == "devanagari"


def test_field_adopts_an_explicit_widget_language() -> None:
    """The field must be able to parse what its own widget renders.

    A widget set to "ne" emits "०१ वैशाख २०८१". A field left at the default "en"
    rejected that as invalid -- a form that could not round-trip its own output.
    """
    field = BSDateField(widget=BSDateInput(lang="ne"))
    assert field.lang == "ne"
    assert field.clean("०१ वैशाख २०८१") == BSDate(2081, 1, 1)


def test_field_wins_when_both_set_a_language() -> None:
    """Contradictory settings resolve to the field."""
    field = BSDateField(lang="en", widget=BSDateInput(lang="ne"))
    assert field.lang == "en"
    assert field.widget.lang == "ne"


def test_field_accepts_its_widget_format_on_input() -> None:
    """A widget format outside DEFAULT_INPUT_FORMATS still round-trips."""
    field = BSDateField(widget=BSDateInput(format="%d.%m.%Y"))
    assert "%d.%m.%Y" in field.input_formats
    assert field.clean("01.01.2081") == BSDate(2081, 1, 1)


def test_picker_round_trips_through_a_form() -> None:
    """End to end: what the picker writes is what the field accepts back."""
    widget = BSDatePickerInput(lang="ne", numerals="devanagari", format="%d %B %Y")
    field = BSDateField(widget=widget)
    rendered = widget.format_value(BSDate(2081, 1, 1))
    assert rendered == "०१ वैशाख २०८१"
    assert field.clean(rendered) == BSDate(2081, 1, 1)


def test_app_config_is_importable() -> None:
    """The picker's static assets are only discoverable via an installed app."""
    from django_bikram.apps import DjangoBikramConfig

    assert DjangoBikramConfig.name == "django_bikram"

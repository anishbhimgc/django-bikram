"""Django integration for :mod:`django_bikram`.

Model and form fields are re-exported here for convenience::

    from django_bikram.django import BSDateField

:mod:`django_bikram.django.drf` is **not** re-exported: it imports Django REST
Framework, which is an optional extra, so importing it must stay an explicit
choice rather than a side effect of touching this package.
"""

from __future__ import annotations

from .fields import BSDateField
from .forms import BSDateField as BSDateFormField
from .forms import BSDateInput, BSDatePickerInput
from .lookups import (
    bs_fiscal_quarter_q,
    bs_fiscal_year_q,
    bs_month_bounds,
    bs_month_q,
    bs_year_bounds,
    bs_year_q,
)

__all__ = [
    "BSDateField",
    "BSDateFormField",
    "BSDateInput",
    "BSDatePickerInput",
    "bs_year_bounds",
    "bs_month_bounds",
    "bs_year_q",
    "bs_month_q",
    "bs_fiscal_year_q",
    "bs_fiscal_quarter_q",
]

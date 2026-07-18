"""Django model field for Bikram Sambat dates.

The whole design rests on one decision, stated here because everything else
follows from it:

**The column is a native ``date`` holding the Gregorian (AD) value; Python sees
a** :class:`~django_bikram.date.BSDate` **. Conversion happens only at the boundary.**

The alternative -- storing ``"2081-01-01"`` as text, or splitting into
``year``/``month``/``day`` integer columns -- looks simpler for about a day and
then quietly costs you everything the database is for:

* **Indexes.** A btree on a real ``date`` answers ranges; a btree on a BS text
  column only answers equality and prefix, because BS text does not sort
  chronologically across the varying month lengths. Split integer columns need
  a composite index and still cannot express "between these two dates" in one
  seek.
* **Range queries.** ``__gte`` / ``__lt`` / ``__range`` are ordinary
  comparisons on a ``date``. On split columns they become an OR-of-ANDs across
  three columns that no planner enjoys.
* **Aggregation and ordering.** ``Min``, ``Max``, ``ORDER BY`` and window
  functions work because ``date`` has a total order in SQL.
* **DB-side date functions.** ``TruncMonth``, ``ExtractYear``, date_trunc, age
  arithmetic -- all of it stays available.
* **Interoperability.** Reports, BI tools, ``psql``, and any non-Python
  consumer see a normal date column.

Because :class:`BSDateField` subclasses :class:`~django.db.models.DateField`,
every lookup Django already implements for dates keeps working, and values are
converted through :meth:`BSDateField.get_prep_value` on the way down.

The one thing to know is that the built-in ``__year`` / ``__month`` / ``__day``
lookups operate on the **stored Gregorian** value, because that is genuinely
what the column contains. See :mod:`django_bikram.django.lookups` for the BS-year
equivalent and why it is a helper rather than a lookup.
"""

from __future__ import annotations

import datetime
from typing import Any

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from ..date import BSDate
from ..exceptions import InvalidBSDate

__all__ = ["BSDateField"]


class BSDateField(models.DateField):
    """A date field that stores Gregorian dates and exposes :class:`BSDate`.

    Use it exactly like :class:`~django.db.models.DateField`::

        class Invoice(models.Model):
            issued_on = BSDateField()

        Invoice.objects.filter(issued_on__gte=BSDate(2081, 1, 1))
        Invoice.objects.filter(issued_on__range=(bs_start, bs_end))
        Invoice.objects.aggregate(Max("issued_on"))

    Assignment accepts several types, each with a fixed meaning:

    * :class:`~django_bikram.date.BSDate` -- used as-is.
    * :class:`datetime.date` -- read as a **Gregorian** date and converted.
      This is what makes ``date(2024, 4, 13)`` and ``BSDate(2081, 1, 1)``
      interchangeable in queries.
    * :class:`str` -- read as a **Bikram Sambat** ``YYYY-MM-DD`` string, so
      that ``dumpdata``/``loaddata`` and form input round-trip.

    The asymmetry is deliberate: a ``datetime.date`` is unambiguously
    Gregorian, while a bare string in this field's context is unambiguously
    the BS value the user typed.
    """

    description = _("Bikram Sambat date (stored as a Gregorian date)")

    default_error_messages = {
        "invalid": _(
            "“%(value)s” value has an invalid date format. It must be in "
            "YYYY-MM-DD (Bikram Sambat) format."
        ),
        "invalid_date": _(
            "“%(value)s” value has the correct format (YYYY-MM-DD) but it is "
            "an invalid Bikram Sambat date."
        ),
        "out_of_range": _(
            "“%(value)s” is outside the verified Bikram Sambat calendar range."
        ),
    }

    def from_db_value(
        self,
        value: BSDate | datetime.date | None,
        expression: Any,
        connection: Any,
    ) -> BSDate | None:
        """Convert a Gregorian date loaded from the database into a BS date.

        Args:
            value: The raw column value, a :class:`datetime.date` or ``None``.
            expression: The originating query expression (unused).
            connection: The database connection (unused).

        Returns:
            The equivalent :class:`BSDate`, or ``None``.

        Raises:
            ValidationError: If the stored date falls outside the verified
                calendar range, which can only happen if rows were written by
                something other than this field.
        """
        if value is None:
            return None
        if isinstance(value, BSDate):  # pragma: no cover - defensive
            return value
        try:
            return BSDate.from_ad(value)
        except InvalidBSDate as exc:
            raise ValidationError(
                self.error_messages["out_of_range"],
                code="out_of_range",
                params={"value": value},
            ) from exc

    def to_python(self, value: Any) -> BSDate | None:
        """Coerce a value into a :class:`BSDate`.

        Args:
            value: A :class:`BSDate`, :class:`datetime.date`,
                :class:`datetime.datetime`, ``YYYY-MM-DD`` Bikram Sambat
                string, or ``None``.

        Returns:
            The coerced :class:`BSDate`, or ``None``.

        Raises:
            ValidationError: If the value cannot be interpreted as a valid
                Bikram Sambat date.
        """
        if value is None or isinstance(value, BSDate):
            return value
        if isinstance(value, datetime.datetime):
            value = value.date()
        if isinstance(value, datetime.date):
            try:
                return BSDate.from_ad(value)
            except InvalidBSDate as exc:
                raise ValidationError(
                    self.error_messages["out_of_range"],
                    code="out_of_range",
                    params={"value": value},
                ) from exc
        if isinstance(value, str):
            try:
                return BSDate.fromisoformat(value)
            except InvalidBSDate as exc:
                # Distinguish "wrong shape" from "right shape, unreal date" so
                # the error tells the user which mistake they made.
                parts = value.split("-")
                # isdecimal(), matching BSDate.fromisoformat's guard: isdigit()
                # accepts characters int() rejects, so the two would disagree
                # about what "right shape" means.
                shaped = len(parts) == 3 and all(p.isdecimal() for p in parts)
                code = "invalid_date" if shaped else "invalid"
                raise ValidationError(
                    self.error_messages[code],
                    code=code,
                    params={"value": value},
                ) from exc
        raise ValidationError(
            self.error_messages["invalid"],
            code="invalid",
            params={"value": value},
        )

    def get_prep_value(self, value: Any) -> datetime.date | None:
        """Convert a Python value into the Gregorian date the column stores.

        This is the boundary. Everything below it is ordinary Gregorian
        ``date`` handling, which is why indexes and range queries work.

        A :class:`datetime.date` is passed through **unconverted and
        unvalidated**: it is already the Gregorian value the column wants, so
        round-tripping it through :class:`BSDate` would add nothing but a range
        check. That check would actively break correct queries -- the exclusive
        upper bound of the last supported BS year is 2027-04-14, one day past
        the table, so ``bs_year_q(field, 2083)`` legitimately needs to send a
        date that has no BS equivalent. Validation belongs in
        :meth:`to_python` (and therefore ``full_clean``), which is also where
        :class:`~django.db.models.DateField` puts it.

        Args:
            value: A :class:`BSDate`, :class:`datetime.date`, Bikram Sambat
                ``YYYY-MM-DD`` string, or ``None``.

        Returns:
            The Gregorian :class:`datetime.date` to send to the database, or
            ``None``.
        """
        # Deliberately skips DateField.get_prep_value, whose contract is to
        # return a datetime.date from to_python -- ours returns a BSDate.
        value = models.Field.get_prep_value(self, value)
        if value is None:
            return None
        if isinstance(value, BSDate):
            return value.to_ad()
        if isinstance(value, datetime.datetime):
            return value.date()
        if isinstance(value, datetime.date):
            return value
        prepared = self.to_python(value)
        return None if prepared is None else prepared.to_ad()

    def get_db_prep_save(self, value: Any, connection: Any) -> Any:
        """Range-check on the way to storage, unlike a query bound.

        :meth:`get_prep_value` deliberately lets a bare :class:`datetime.date`
        through unvalidated so that a bound one day past the table keeps working
        -- ``bs_year_q(field, 2083)`` needs 2027-04-14, which has no BS
        equivalent. That licence is correct for a **query** and wrong for a
        **write**: a stored date with no BS equivalent is readable by nothing.
        :meth:`from_db_value` raises on it, so the row poisons not just itself but
        every queryset that touches the table, and only raw SQL can remove it.

        Django splits the two for exactly this reason -- ``get_db_prep_save`` is
        the saves-only path -- so the check goes here and the query bound is
        untouched.

        Args:
            value: The value being saved.
            connection: The database connection.

        Returns:
            The Gregorian date to store, or ``None``.

        Raises:
            ValidationError: If the value has no Bikram Sambat equivalent.
        """
        prepared = self.get_prep_value(value)
        if prepared is not None:
            try:
                BSDate.from_ad(prepared)  # range check only; the result is discarded
            except InvalidBSDate as exc:
                raise ValidationError(
                    self.error_messages["out_of_range"],
                    code="out_of_range",
                    params={"value": prepared},
                ) from exc
        return super().get_db_prep_save(prepared, connection)

    def pre_save(self, model_instance: models.Model, add: bool) -> Any:
        """Apply ``auto_now`` / ``auto_now_add``, keeping the value a BS date.

        Args:
            model_instance: The instance being saved.
            add: Whether this is an insert.

        Returns:
            The value to persist: a :class:`BSDate` when auto-populated,
            otherwise whatever the attribute holds.
        """
        if self.auto_now or (self.auto_now_add and add):
            # timezone.localdate(), not BSDate.today(): inside Django the stamp
            # must follow the project's TIME_ZONE, not the zone the container
            # happens to run in, and not this library's Nepal default either — a
            # project that sets TIME_ZONE is stating which day it means.
            value = BSDate.from_ad(timezone.localdate())
            setattr(model_instance, self.attname, value)
            return value
        return super(models.DateField, self).pre_save(model_instance, add)

    def value_to_string(self, obj: models.Model) -> str:
        """Serialise the field for ``dumpdata``.

        Args:
            obj: The model instance.

        Returns:
            The Bikram Sambat ``YYYY-MM-DD`` string, or ``""`` for ``None``.
            Emitting BS (not AD) keeps fixtures human-meaningful and makes
            ``loaddata`` symmetric with :meth:`to_python`.
        """
        # Coerced through to_python, not serialised straight off the attribute.
        # value_from_object is a bare getattr, so on an instance that was assigned
        # a raw datetime.date and not yet reloaded, .isoformat() emits the
        # **Gregorian** digits — which to_python then reads back as Bikram Sambat.
        # A silent 57-year error, and an asymmetric round-trip in the one method
        # whose whole job is the round-trip.
        value = self.to_python(self.value_from_object(obj))
        return "" if value is None else value.isoformat()

    def formfield(self, **kwargs: Any) -> Any:
        """Return the default form field for this model field.

        Args:
            **kwargs: Overrides passed to the form field.

        Returns:
            A :class:`~django_bikram.django.forms.BSDateField` form field.
        """
        from .forms import BSDateField as BSDateFormField

        defaults: dict[str, Any] = {"form_class": BSDateFormField}
        defaults.update(kwargs)
        # Skip DateField.formfield, which would force a DateField form class.
        return super(models.DateField, self).formfield(**defaults)


def _register_migration_serializer() -> None:
    """Teach Django's migration writer how to serialise a :class:`BSDate`.

    Without this, ``default=BSDate(2081, 1, 1)`` on a field would crash
    ``makemigrations`` with "cannot serialize". Registration happens on import
    of this module, which is exactly when it is needed -- a migration that
    references the field imports it.
    """
    try:
        from django.db.migrations.serializer import BaseSerializer
        from django.db.migrations.writer import MigrationWriter
    except ImportError:  # pragma: no cover - Django internals moved
        return

    class BSDateSerializer(BaseSerializer):
        """Serialise a :class:`BSDate` to its constructor call."""

        def serialize(self) -> tuple[str, set[str]]:
            """Return the source string and its required imports."""
            value: BSDate = self.value
            return (
                f"django_bikram.BSDate({value.year}, {value.month}, {value.day})",
                {"import django_bikram"},
            )

    MigrationWriter.register_serializer(BSDate, BSDateSerializer)


_register_migration_serializer()

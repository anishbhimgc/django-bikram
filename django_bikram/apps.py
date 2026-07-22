"""Django ``AppConfig``, needed only for the bundled date picker's assets.

Most of this package needs no app registration at all: a model field, a form
field and the lookup helpers are plain imports.
:class:`~django_bikram.django.forms.BSDatePickerInput` is the exception. Its CSS
and JavaScript live in ``django_bikram/static/``, and Django's
``AppDirectoriesFinder`` only searches **installed apps** -- so without this,
``collectstatic`` skips the files and the picker silently never loads.

Add it only if you use the picker::

    INSTALLED_APPS = [
        ...,
        "django_bikram",
    ]

Registering the app has no other effect. In particular it does **not** call
:func:`django_bikram.django.drf.register_serializer_field`: that mutates a
third-party class, so it stays something you ask for by name rather than
something that follows from adding an app to a list.
"""

from __future__ import annotations

from django.apps import AppConfig


class DjangoBikramConfig(AppConfig):
    """Registers the package so its static assets are discoverable."""

    name = "django_bikram"
    verbose_name = "Bikram Sambat dates"

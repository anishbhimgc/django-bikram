"""Compatibility shim: this project is now ``django-bikram-sambat``.

Importing ``django_bikram`` re-exports :mod:`django_bikram_sambat` unchanged, so
existing code keeps working. Nothing else is maintained here -- fixes and new
features land in the new package only.

Migrate with a find-and-replace::

    pip uninstall django-bikram
    pip install django-bikram-sambat

    from django_bikram_sambat import BSDate     # was: django_bikram

Submodules are aliased **lazily**, through a meta-path finder rather than by
importing them up front. That matters: ``django_bikram_sambat.django`` imports
Django, and the core package is deliberately usable without Django installed.
Eager aliasing would either drag Django into every ``import django_bikram``, or
silently fail to alias the submodule where Django is absent.
"""

from __future__ import annotations

import importlib
import importlib.abc
import importlib.util
import sys
import warnings
from types import ModuleType
from typing import Any

import django_bikram_sambat as _pkg
from django_bikram_sambat import *  # noqa: F403

__version__ = "0.4.0"
__all__ = list(_pkg.__all__)

_OLD = "django_bikram"
_NEW = "django_bikram_sambat"


class _AliasLoader(importlib.abc.Loader):
    """Return the real new-name module in place of the old name."""

    def __init__(self, target: str) -> None:
        self._target = target

    def create_module(self, spec: Any) -> ModuleType:
        """Import the target and hand it back as the aliased module."""
        return importlib.import_module(self._target)

    def exec_module(self, module: ModuleType) -> None:
        """No-op: importing the target already executed it."""


class _AliasFinder(importlib.abc.MetaPathFinder):
    """Resolve ``django_bikram.X`` to ``django_bikram_sambat.X`` on demand."""

    def find_spec(self, fullname: str, path: Any = None, target: Any = None) -> Any:
        """Alias a submodule, or return None to let normal imports proceed."""
        prefix = _OLD + "."
        if not fullname.startswith(prefix):
            return None
        return importlib.util.spec_from_loader(
            fullname, _AliasLoader(_NEW + fullname[len(_OLD) :])
        )


if not any(isinstance(_f, _AliasFinder) for _f in sys.meta_path):
    sys.meta_path.insert(0, _AliasFinder())

warnings.warn(
    "django-bikram has been renamed to django-bikram-sambat. Import "
    "'django_bikram_sambat' instead of 'django_bikram'; this shim will not "
    "receive further updates.",
    DeprecationWarning,
    stacklevel=2,
)

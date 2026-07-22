"""Empty URLconf.

``django.contrib.admin`` requires ``ROOT_URLCONF`` to resolve, but no test
follows a URL -- the admin tests drive ``ModelAdmin`` objects directly.
"""

from __future__ import annotations

urlpatterns: list = []

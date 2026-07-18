"""Models exercised by the Django integration tests."""

from __future__ import annotations

from django.db import models

from django_bikram.django import BSDateField


class Invoice(models.Model):
    """An invoice with Bikram Sambat dates in several configurations."""

    issued_on = BSDateField()
    due_on = BSDateField(null=True, blank=True)
    created_on = BSDateField(auto_now_add=True)
    updated_on = BSDateField(auto_now=True)

    class Meta:
        """Model metadata."""

        app_label = "tests"
        ordering = ["issued_on"]

"""Minimal Django settings for the test suite."""

SECRET_KEY = "django-bikram-test-key-not-secret"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "tests",
]

USE_TZ = True
TIME_ZONE = "Asia/Kathmandu"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_I18N = False

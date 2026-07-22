"""Minimal Django settings for the test suite."""

SECRET_KEY = "django-bikram-test-key-not-secret"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

INSTALLED_APPS = [
    # admin, sessions, messages and staticfiles are here so the admin
    # integration (the list filter and the widget swap) is exercised against a
    # real ModelAdmin rather than a mock. django_bikram itself is installed so
    # the picker's static assets are discoverable, exactly as a project using
    # the picker must do.
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.messages",
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    "django_bikram",
    "tests",
]

MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.request",
            ]
        },
    }
]

STATIC_URL = "/static/"
ROOT_URLCONF = "tests.urls"

USE_TZ = True
TIME_ZONE = "Asia/Kathmandu"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_I18N = False

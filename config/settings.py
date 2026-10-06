"""Shipora settings.

Single-file configuration, environment-driven (see .env.example). There is
deliberately no Django Admin: Shipora's own pages cover administration.
"""

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(DEBUG=(bool, False))
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY", default="dev-insecure-key-change-me-for-local-use-only")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    "rest_framework",
    "apps.accounts",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
            ],
        },
    },
]

DATABASES = {"default": env.db("DATABASE_URL", default="postgres://shipora:shipora@localhost:5432/shipora")}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Email-login custom user. accounts.0001 is the first project migration.
AUTH_USER_MODEL = "accounts.User"

REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.AllowAny",),
}

# Email. consolemail:// prints messages to the server log; set an smtp:// URL
# (smtp://user:password@host:587/?tls=True) for real delivery.
vars().update(env.email_url("EMAIL_URL", default="consolemail://"))
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="Shipora <no-reply@shipora.local>")

# The website: links in emails point here.
FRONTEND_URL = env("FRONTEND_URL", default="http://localhost:3000")

# How long an email verification link stays valid, in seconds (default 3 days).
EMAIL_VERIFICATION_MAX_AGE = env.int("EMAIL_VERIFICATION_MAX_AGE", default=3 * 24 * 60 * 60)

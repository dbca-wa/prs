import logging
import os

# Tests must be able to run without deployment configuration: settings.py
# refuses to start without a SECRET_KEY when DEBUG is False, so provide a
# throwaway value (never used outside of tests).
os.environ.setdefault("SECRET_KEY", "test-only-insecure-secret-key")

from .settings import *  # noqa: E402

# Modify project settings to speed up unit tests.
logging.disable(logging.CRITICAL)
DEBUG = False
# The test client speaks plain HTTP, and sessions are not security-relevant here.
SECURE_SSL_REDIRECT = False
SECURE_HSTS_SECONDS = 0
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
TEMPLATES[0]["OPTIONS"] = {
    "debug": False,
    "context_processors": [
        "django.contrib.auth.context_processors.auth",
        "django.template.context_processors.media",
        "django.template.context_processors.static",
        "django.template.context_processors.request",
        "django.template.context_processors.csrf",
        "django.contrib.messages.context_processors.messages",
        "prs.context_processors.template_context",
    ],
}
PASSWORD_HASHERS = ("django.contrib.auth.hashers.MD5PasswordHasher",)
MEDIA_ROOT = os.path.join(BASE_DIR, "media")
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

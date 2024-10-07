import os
import sys
import tomllib
from pathlib import Path
from zoneinfo import ZoneInfo

import dj_database_url
from dbca_utils.utils import env
from django.core.exceptions import DisallowedHost
from django.db.utils import OperationalError
from redis.exceptions import ConnectionError

# Project paths
# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = str(Path(__file__).resolve().parents[1])
PROJECT_DIR = str(Path(__file__).resolve().parents[0])
# Add PROJECT_DIR to the system path.
sys.path.insert(0, PROJECT_DIR)

# Application definition
DEBUG = env("DEBUG", False)
SECRET_KEY = env("SECRET_KEY", "PlaceholderSecretKey")
CSRF_COOKIE_SECURE = env("CSRF_COOKIE_SECURE", False)
CSRF_TRUSTED_ORIGINS = env("CSRF_TRUSTED_ORIGINS", "http://127.0.0.1").split(",")
SESSION_COOKIE_SECURE = env("SESSION_COOKIE_SECURE", False)
SECURE_SSL_REDIRECT = env("SECURE_SSL_REDIRECT", False)
SECURE_REFERRER_POLICY = env("SECURE_REFERRER_POLICY", None)
SECURE_HSTS_SECONDS = env("SECURE_HSTS_SECONDS", 0)
if not DEBUG:
    ALLOWED_HOSTS = env("ALLOWED_HOSTS", "localhost").split(",")
else:
    ALLOWED_HOSTS = ["*"]
INTERNAL_IPS = ["127.0.0.1", "::1"]
ROOT_URLCONF = "prs2.urls"
WSGI_APPLICATION = "prs2.wsgi.application"
DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

# Assume Azure blob storage is used for media uploads, unless explicitly set as local storage.
LOCAL_MEDIA_STORAGE = env("LOCAL_MEDIA_STORAGE", False)
if LOCAL_MEDIA_STORAGE:
    DEFAULT_FILE_STORAGE = "django.core.files.storage.FileSystemStorage"
    MEDIA_ROOT = os.path.join(BASE_DIR, "media")
    # Ensure that the local media directory exists.
    if not os.path.exists(MEDIA_ROOT):
        os.makedirs(MEDIA_ROOT)
else:
    DEFAULT_FILE_STORAGE = "storages.backends.azure_storage.AzureStorage"
    AZURE_ACCOUNT_NAME = env("AZURE_ACCOUNT_NAME", "name")
    AZURE_ACCOUNT_KEY = env("AZURE_ACCOUNT_KEY", "key")
    AZURE_CONTAINER = env("AZURE_CONTAINER", "container")
    AZURE_URL_EXPIRATION_SECS = env("AZURE_URL_EXPIRATION_SECS", 3600)  # Default one hour.

# PRS may deploy its own instance of Geoserver.
KMI_GEOSERVER_URL = env("KMI_GEOSERVER_URL", "")
PRS_LAYER_NAME = env("PRS_LAYER_NAME", "")
MAPPROXY_URL = env("MAPPROXY_URL", "")
GEOCODER_URL = env("GEOCODER_URL", "")
GEOSERVER_URL = env("GEOSERVER_URL", "")
GEOSERVER_SSO_USER = env("GEOSERVER_SSO_USER", "username")
GEOSERVER_SSO_PASS = env("GEOSERVER_SSO_PASS", "password")
CADASTRE_LAYER_NAME = env("CADASTRE_LAYER_NAME", "cadastre")

INSTALLED_APPS = (
    "whitenoise.runserver_nostatic",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.gis",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_extensions",
    "taggit",
    "reversion",
    "crispy_forms",
    "crispy_bootstrap5",
    "webtemplate_dbca",
    "django_celery_results",
    "referral",
    "reports",
    "harvester",
    "indexer",
)
MIDDLEWARE = [
    "prs2.middleware.HealthCheckMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.cache.UpdateCacheMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.cache.FetchFromCacheMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "reversion.middleware.RevisionMiddleware",
    "crum.CurrentRequestUserMiddleware",
    "dbca_utils.middleware.SSOLoginMiddleware",
    "prs2.middleware.PrsMiddleware",
]
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [
            os.path.join(PROJECT_DIR, "templates"),
        ],
        "APP_DIRS": True,
        "OPTIONS": {
            "debug": DEBUG,
            "context_processors": [
                "django.contrib.auth.context_processors.auth",
                "django.template.context_processors.debug",
                "django.template.context_processors.i18n",
                "django.template.context_processors.media",
                "django.template.context_processors.static",
                "django.template.context_processors.tz",
                "django.template.context_processors.request",
                "django.template.context_processors.csrf",
                "django.contrib.messages.context_processors.messages",
                "prs2.context_processors.template_context",
            ],
        },
    }
]
MANAGERS = (("Sean Walsh", "sean.walsh@dbca.wa.gov.au"),)
LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/"
APPLICATION_TITLE = "Planning Referral System"
APPLICATION_ACRONYM = "PRS"
project = tomllib.load(open(os.path.join(BASE_DIR, "pyproject.toml"), "rb"))
APPLICATION_VERSION_NO = project["tool"]["poetry"]["version"]
APPLICATION_ALERTS_EMAIL = "PRS-Alerts@dbca.wa.gov.au"
SITE_URL = env("SITE_URL", "localhost")
PRS_USER_GROUP = env("PRS_USER_GROUP", "PRS user")
PRS_POWER_USER_GROUP = env("PRS_PWUSER_GROUP", "PRS power user")
ALLOWED_UPLOAD_TYPES = [
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-word.document.12",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/xml",
    "application/pdf",
    "application/zip",
    "application/x-zip",
    "application/x-zip-compressed",
    "application/octet-stream",  # MIME type for zip files in Chrome.
    "application/vnd.ms-outlook",  # Outlook MSG format.
    "application/x-qgis-project",
    "image/tiff",
    "image/jpeg",
    "image/gif",
    "image/png",
    "text/csv",
    "text/html",
    "text/plain",
]

# Caching config
REDIS_CACHE_HOST = env("REDIS_CACHE_HOST", "")
REDIS_CACHE_PASSWORD = env("REDIS_CACHE_PASSWORD", "")
if REDIS_CACHE_HOST:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_CACHE_HOST,
        }
    }
    if REDIS_CACHE_PASSWORD:
        CACHES["default"]["OPTIONS"]["PASSWORD"] = REDIS_CACHE_PASSWORD
else:
    # Don't cache if we don't have a cache server configured.
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.dummy.DummyCache",
        }
    }
API_RESPONSE_CACHE_SECONDS = env("API_RESPONSE_CACHE_SECONDS", 60)
CACHE_MIDDLEWARE_SECONDS = env("CACHE_MIDDLEWARE_SECONDS", 0)

# Email settings
EMAIL_HOST = env("EMAIL_HOST", "email.host")
EMAIL_PORT = env("EMAIL_PORT", 25)
REFERRAL_EMAIL_HOST = env("REFERRAL_EMAIL_HOST", "host")
REFERRAL_EMAIL_USER = env("REFERRAL_EMAIL_USER", "referrals")
REFERRAL_EMAIL_PASSWORD = env("REFERRAL_EMAIL_PASSWORD", "password")
REFERRAL_ASSIGNEE_FALLBACK = env("REFERRAL_ASSIGNEE_FALLBACK", "admin")
# Whitelist of sender emails (only harvest referrals sent by these):
PLANNING_EMAILS = env("PLANNING_EMAILS", "referrals@dplh.wa.gov.au").split(",")
# Whitelist of receiving mailboxes (only harvest referrals sent to these):
ASSESSOR_EMAILS = env("ASSESSOR_EMAILS", "").split(",")

# Database configuration
DATABASES = {
    # Defined in the DATABASE_URL env variable.
    "default": dj_database_url.config(),
}

# Internationalization
TIME_ZONE = "Australia/Perth"
TZ = ZoneInfo(TIME_ZONE)
USE_TZ = True
USE_I18N = False
USE_L10N = True
# Sensible AU date input formats
DATE_INPUT_FORMATS = (
    "%d/%m/%Y",
    "%d/%m/%y",
    "%d-%m-%Y",
    "%d-%m-%y",
    "%d %b %Y",
    "%d %b, %Y",
    "%d %B %Y",
    "%d %B, %Y",
    "%Y-%m-%d",  # Needed for form validation.
)

# Static files (CSS, JavaScript, Images)
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")
STATIC_URL = "/static/"
STATICFILES_DIRS = (os.path.join(BASE_DIR, "prs2", "static"),)
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
WHITENOISE_ROOT = STATIC_ROOT

# Media uploads
MEDIA_URL = "/media/"

# This is required to add context variables to all templates:
STATIC_CONTEXT_VARS = {}

# Logging settings - log to stdout
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {"format": "%(asctime)s %(levelname)-12s %(name)-12s %(message)s"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
            "stream": sys.stdout,
            "level": "WARNING",
        },
        "harvester": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
            "stream": sys.stdout,
            "level": "INFO",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "ERROR",
        },
        "harvester": {
            "handlers": ["harvester"],
            "level": "INFO",
        },
        # Set the logging level for all azure-* libraries (the azure-storage-blob library uses this one).
        # Reference: https://learn.microsoft.com/en-us/azure/developer/python/sdk/azure-sdk-logging
        "azure": {
            "handlers": ["console"],
            "level": "ERROR",
        },
    },
}

# django-crispy-forms config
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

# Typesense config
TYPESENSE_API_KEY = env("TYPESENSE_API_KEY", "PlaceholderAPIKey")
TYPESENSE_HOST = env("TYPESENSE_HOST", "localhost")
TYPESENSE_PORT = env("TYPESENSE_PORT", 8108)
TYPESENSE_PROTOCOL = env("TYPESENSE_PROTOCOL", "http")
TYPESENSE_CONN_TIMEOUT = env("TYPESENSE_CONN_TIMEOUT", 2)

# Celery config
BROKER_URL = env("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = "django-db"
CELERY_TIMEZONE = TIME_ZONE


def sentry_excluded_exceptions(event, hint):
    """Exclude defined class(es) of Exception from being reported to Sentry.
    These exception classes are generally related to operational or configuration issues,
    and they are not errors that we want to capture.
    https://docs.sentry.io/platforms/python/configuration/filtering/#filtering-error-events
    """
    if "exc_info" in hint and hint["exc_info"]:
        # Exclude database-related errors (connection error, timeout, DNS failure, etc.)
        if hint["exc_info"][0] is OperationalError:
            return None
        # Exclude exceptions related to host requests not in ALLOWED_HOSTS.
        elif hint["exc_info"][0] is DisallowedHost:
            return None
        # Exclude Redis service connection errors.
        elif hint["exc_info"][0] is ConnectionError:
            return None

    return event


# Sentry config
SENTRY_DSN = env("SENTRY_DSN", None)
SENTRY_SAMPLE_RATE = env("SENTRY_SAMPLE_RATE", 1.0)  # Error sampling rate
SENTRY_TRANSACTION_SAMPLE_RATE = env("SENTRY_TRANSACTION_SAMPLE_RATE", 0.0)  # Transaction sampling
SENTRY_PROFILES_SAMPLE_RATE = env("SENTRY_PROFILES_SAMPLE_RATE", 0.0)  # Proportion of sampled transactions to profile.
SENTRY_ENVIRONMENT = env("SENTRY_ENVIRONMENT", None)
if SENTRY_DSN and SENTRY_ENVIRONMENT:
    import sentry_sdk

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        sample_rate=SENTRY_SAMPLE_RATE,
        traces_sample_rate=SENTRY_TRANSACTION_SAMPLE_RATE,
        profiles_sample_rate=SENTRY_PROFILES_SAMPLE_RATE,
        environment=SENTRY_ENVIRONMENT,
        release=APPLICATION_VERSION_NO,
        before_send=sentry_excluded_exceptions,
    )

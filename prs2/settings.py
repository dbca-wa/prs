from dbca_utils.utils import env
import dj_database_url
import os
from pathlib import Path
import sys


# Project paths
# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = str(Path(__file__).resolve().parents[1])
PROJECT_DIR = str(Path(__file__).resolve().parents[0])
# Add PROJECT_DIR to the system path.
sys.path.insert(0, PROJECT_DIR)

# Application definition
DEBUG = env('DEBUG', False)
DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'
SECRET_KEY = env('SECRET_KEY', 'PlaceholderSecretKey')
CSRF_COOKIE_SECURE = env('CSRF_COOKIE_SECURE', False)
SESSION_COOKIE_SECURE = env('SESSION_COOKIE_SECURE', False)
SECURE_SSL_REDIRECT = env('SECURE_SSL_REDIRECT', False)
SECURE_REFERRER_POLICY = env('SECURE_REFERRER_POLICY', None)
SECURE_HSTS_SECONDS = env('SECURE_HSTS_SECONDS', 0)
if not DEBUG:
    ALLOWED_HOSTS = env('ALLOWED_DOMAINS', 'localhost').split(',')
else:
    ALLOWED_HOSTS = ['*']
INTERNAL_IPS = ['127.0.0.1', '::1']
ROOT_URLCONF = 'prs2.urls'
WSGI_APPLICATION = 'prs2.wsgi.application'
GEOSERVER_WMTS_URL = env('GEOSERVER_WMTS_URL', '')
GEOSERVER_WFS_URL = env('GEOSERVER_WFS_URL', '')
GEOSERVER_SSO_USER = env('GEOSERVER_SSO_USER', 'username')
GEOSERVER_SSO_PASS = env('GEOSERVER_SSO_PASS', 'password')
GEOCODER_URL = env('GEOCODER_URL', '')
INSTALLED_APPS = (
    'whitenoise.runserver_nostatic',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.gis',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_extensions',
    'taggit',
    'reversion',
    'crispy_forms',
    'bootstrap_pagination',
    'tastypie',
    'webtemplate_dbca',
    'rest_framework',
    'django_celery_results',
    'referral',
    'reports',
    'harvester',
    'indexer',
)
MIDDLEWARE = [
    'prs2.middleware.HealthCheckMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'reversion.middleware.RevisionMiddleware',
    'dbca_utils.middleware.SSOLoginMiddleware',
    'prs2.middleware.PrsMiddleware',
]
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            os.path.join(PROJECT_DIR, 'templates'),
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'debug': DEBUG,
            'context_processors': [
                'django.contrib.auth.context_processors.auth',
                'django.template.context_processors.debug',
                'django.template.context_processors.i18n',
                'django.template.context_processors.media',
                'django.template.context_processors.static',
                'django.template.context_processors.tz',
                'django.template.context_processors.request',
                'django.template.context_processors.csrf',
                'django.contrib.messages.context_processors.messages',
                'prs2.context_processors.template_context',
            ],
        },
    }
]
MANAGERS = (
    ('Sean Walsh', 'sean.walsh@dbca.wa.gov.au'),
    ('Michael Roberts', 'michael.roberts@dbca.wa.gov.au'),
    # ('Cho Lamb', 'cho.lamb@dbca.wa.gov.au'),
)
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
APPLICATION_TITLE = 'Planning Referral System'
APPLICATION_ACRONYM = 'PRS'
APPLICATION_VERSION_NO = '2.5.19'
APPLICATION_ALERTS_EMAIL = 'PRS-Alerts@dbca.wa.gov.au'
SITE_URL = env('SITE_URL', 'localhost')
PRS_USER_GROUP = env('PRS_USER_GROUP', 'PRS user')
PRS_POWER_USER_GROUP = env('PRS_PWUSER_GROUP', 'PRS power user')
ALLOWED_UPLOAD_TYPES = [
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.ms-word.document.12',
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/xml',
    'application/pdf',
    'application/zip',
    'application/x-zip',
    'application/x-zip-compressed',
    'application/octet-stream',  # MIME type for zip files in Chrome.
    'application/vnd.ms-outlook',  # Outlook MSG format.
    'application/x-qgis-project',
    'image/tiff',
    'image/jpeg',
    'image/gif',
    'image/png',
    'text/csv',
    'text/html',
    'text/plain'
]
API_RESPONSE_CACHE_SECONDS = env('API_RESPONSE_CACHE_SECONDS', 60)

# Email settings
EMAIL_HOST = env('EMAIL_HOST', 'email.host')
EMAIL_PORT = env('EMAIL_PORT', 25)
REFERRAL_EMAIL_HOST = env('REFERRAL_EMAIL_HOST', 'host')
REFERRAL_EMAIL_USER = env('REFERRAL_EMAIL_USER', 'referrals')
REFERRAL_EMAIL_PASSWORD = env('REFERRAL_EMAIL_PASSWORD', 'password')
REFERRAL_ASSIGNEE_FALLBACK = env('REFERRAL_ASSIGNEE_FALLBACK', 'admin')
# Whitelist of sender emails (only harvest referrals sent by these):
PLANNING_EMAILS = env('PLANNING_EMAILS', 'referrals@dplh.wa.gov.au').split(',')
# Whitelist of receiving mailboxes (only harvest referrals sent to these):
ASSESSOR_EMAILS = env('ASSESSOR_EMAILS', '').split(',')
# Delete harvested referral emails after processing them?
REFERRAL_EMAIL_POST_DELETE = env('REFERRAL_EMAIL_POST_DELETE', True)

# Database configuration
DATABASES = {
    # Defined in the DATABASE_URL env variable.
    'default': dj_database_url.config(),
}

# Internationalization
TIME_ZONE = 'Australia/Perth'
USE_TZ = True
USE_I18N = False
USE_L10N = True
# Sensible AU date input formats
DATE_INPUT_FORMATS = (
    '%d/%m/%Y',
    '%d/%m/%y',
    '%d-%m-%Y',
    '%d-%m-%y',
    '%d %b %Y',
    '%d %b, %Y',
    '%d %B %Y',
    '%d %B, %Y',
    '%Y-%m-%d'  # Needed for form validation.
)

# Static files (CSS, JavaScript, Images)
# Ensure that the media directory exists:
if not os.path.exists(os.path.join(BASE_DIR, 'media')):
    os.mkdir(os.path.join(BASE_DIR, 'media'))
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
MEDIA_URL = '/media/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATIC_URL = '/static/'
STATICFILES_DIRS = (os.path.join(BASE_DIR, 'prs2', 'static'),)
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
WHITENOISE_ROOT = STATIC_ROOT

# This is required to add context variables to all templates:
STATIC_CONTEXT_VARS = {}

# Logging settings - log to stdout
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {'format': '%(asctime)s %(levelname)-12s %(name)-12s %(message)s'},
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
            'stream': sys.stdout,
            'level': 'WARNING',
        },
        'harvester': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
            'stream': sys.stdout,
            'level': 'INFO',
        },
    },
    'loggers': {
        '': {
            'handlers': ['console'],
            'level': 'WARNING',
        },
        'harvester': {
            'handlers': ['harvester'],
            'level': 'INFO',
        },
    }
}

# Tastypie settings
TASTYPIE_DEFAULT_FORMATS = ['json']

# crispy_forms settings
CRISPY_TEMPLATE_PACK = 'bootstrap4'

# django-rest-framework configuration
REST_FRAMEWORK = {
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.LimitOffsetPagination',
    'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.AllowAny'],
    'PAGE_SIZE': 100
}

# Typesense config
TYPESENSE_API_KEY = env('TYPESENSE_API_KEY', 'PlaceholderAPIKey')
TYPESENSE_HOST = env('TYPESENSE_HOST', 'localhost')
TYPESENSE_PORT = env('TYPESENSE_PORT', 8108)
TYPESENSE_PROTOCOL = env('TYPESENSE_PROTOCOL', 'http')
TYPESENSE_CONN_TIMEOUT = env('TYPESENSE_CONN_TIMEOUT', 2)

# Celery config
BROKER_URL = env('CELERY_BROKER_URL', 'pyamqp://localhost//')
CELERY_RESULT_BACKEND = 'django-db'
CELERY_TIMEZONE = TIME_ZONE

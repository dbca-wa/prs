from confy import env, database
import os
import sys
from pathlib import Path

# Project paths
# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = str(Path(__file__).resolve().parents[1])
PROJECT_DIR = str(Path(__file__).resolve().parents[0])
# Add PROJECT_DIR to the system path.
sys.path.insert(0, PROJECT_DIR)

# Application definition
DEBUG = env('DEBUG', False)
SECRET_KEY = env('SECRET_KEY', 'PlaceholderSecretKey')
CSRF_COOKIE_SECURE = env('CSRF_COOKIE_SECURE', False)
SESSION_COOKIE_SECURE = env('SESSION_COOKIE_SECURE', False)
if not DEBUG:
    ALLOWED_HOSTS = env('ALLOWED_DOMAINS', '').split(',')
else:
    ALLOWED_HOSTS = ['*']
INTERNAL_IPS = ['127.0.0.1', '::1']
ROOT_URLCONF = 'prs2.urls'
WSGI_APPLICATION = 'prs2.wsgi.application'
GEOSERVER_WMS_URL = env('GEOSERVER_WMS_URL', '')
GEOSERVER_WFS_URL = env('GEOSERVER_WFS_URL', '')
INSTALLED_APPS = (
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.gis',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_extensions',
    'raven.contrib.django.raven_compat',
    'taggit',
    'reversion',
    'crispy_forms',
    'bootstrap_pagination',
    'tastypie',
    'webtemplate_dbca',
    'referral',
    'reports',
    'harvester',
    'rest_framework',
)
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'reversion.middleware.RevisionMiddleware',
    'dpaw_utils.middleware.SSOLoginMiddleware',
]
AUTHENTICATION_BACKENDS = (
    'django.contrib.auth.backends.ModelBackend',
)
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
    ('Cho Lamb', 'cho.lamb@dbca.wa.gov.au'),
)
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
APPLICATION_TITLE = 'Planning Referral System'
APPLICATION_ACRONYM = 'PRS'
APPLICATION_VERSION_NO = '2.4.5'
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

# Email settings
ADMINS = ('asi@dbca.wa.gov.au',)
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

# Database configuration
DATABASES = {
    # Defined in the DATABASE_URL env variable.
    'default': database.config(),
}

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Australia/Perth'
USE_I18N = True
USE_L10N = True
USE_TZ = True
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

# This is required to add context variables to all templates:
STATIC_CONTEXT_VARS = {}

# Logging settings - log to stdout/stderr
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'console': {'format': '%(name)-12s %(message)s'},
        'verbose': {'format': '%(asctime)s %(levelname)-8s %(message)s'},
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'console'
        },
        'harvester': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'console'
        },
		'sentry': {
            'level': 'WARNING',
            'class': 'raven.contrib.django.raven_compat.handlers.SentryHandler',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
			'propagate': True,
        },
        'django.request': {
            'handlers': ['console', 'sentry'],
            'level': 'WARNING',
			'propagate': False,
        },
        'prs': {
            'handlers': ['console'],
            'level': 'INFO'
        },
        'harvester': {
            'handlers': ['harvester'],
            'level': 'INFO'
        },
    }
}

# Tastypie settings
TASTYPIE_DEFAULT_FORMATS = ['json']

# crispy_forms settings
CRISPY_TEMPLATE_PACK = 'bootstrap3'


# Sentry configuration
if env('RAVEN_DSN', False):
    RAVEN_CONFIG = {'dsn': env('RAVEN_DSN')}

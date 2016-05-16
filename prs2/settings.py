"""
Base Django settings for prs2 project.
Call and extend these settings by passing --settings=<PATH> to runserver, e.g.

> python manage.py runserver --settings=prs2.settings_dev.py
"""
from confy import env, database
import os
import sys
from unipath import Path

# Project paths
# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = Path(__file__).ancestor(2)
PROJECT_DIR = os.path.join(BASE_DIR, 'prs2')
# Add PROJECT_DIR to the system path.
sys.path.insert(0, PROJECT_DIR)

# Application definition
DEBUG = env('DEBUG', False)
SECRET_KEY = env('SECRET_KEY')
CSRF_COOKIE_SECURE = env('CSRF_COOKIE_SECURE', False)
SESSION_COOKIE_SECURE = env('SESSION_COOKIE_SECURE', False)
if not DEBUG:
    # Localhost, UAT and Production hosts:
    ALLOWED_HOSTS = [
        'localhost',
        '127.0.0.1',
        'prs.dpaw.wa.gov.au',
        'prs.dpaw.wa.gov.au.',
        'prs-uat.dpaw.wa.gov.au',
        'prs-uat.dpaw.wa.gov.au.',
    ]
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
    'taggit',
    'reversion',
    'crispy_forms',
    'bootstrap_pagination',
    'tastypie',
    'explorer',  # django-sql-explorer
    'webtemplate_dpaw',
    'referral',
    'reports',
)
MIDDLEWARE_CLASSES = (
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'reversion.middleware.RevisionMiddleware',
    'dpaw_utils.middleware.SSOLoginMiddleware',
)
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
                'django.core.context_processors.debug',
                'django.core.context_processors.i18n',
                'django.core.context_processors.media',
                'django.core.context_processors.static',
                'django.core.context_processors.tz',
                'django.core.context_processors.request',
                'django.core.context_processors.csrf',
                'django.contrib.messages.context_processors.messages',
                'prs2.context_processors.template_context',
            ],
        },
    }
]
MANAGERS = (
    ('Sean Walsh', 'sean.walsh@dpaw.wa.gov.au', '9442 0306'),
    ('Cho Lamb', 'cho.lamb@dpaw.wa.gov.au', '9442 0309'),
)
LOGIN_URL = '/login/'
#LOGIN_REDIRECT_URL = '/'
APPLICATION_TITLE = 'Planning Referral System'
APPLICATION_ACRONYM = 'PRS'
APPLICATION_VERSION_NO = '2.1'
APPLICATION_ALERTS_EMAIL = 'PRS-Alerts@dpaw.wa.gov.au'
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
ADMINS = ('asi@dpaw.wa.gov.au',)
EMAIL_HOST = env('EMAIL_HOST', 'email.host')
EMAIL_PORT = env('EMAIL_PORT', 25)

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

# Logging settings
# Ensure that the logs directory exists:
if not os.path.exists(os.path.join(BASE_DIR, 'logs')):
    os.mkdir(os.path.join(BASE_DIR, 'logs'))
LOGGING = {
    'version': 1,
    'formatters': {
        'verbose': {
            'format': '%(levelname)s %(asctime)s %(module)s %(message)s'
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(BASE_DIR, 'logs', 'prs.log'),
            'formatter': 'verbose',
            'maxBytes': 1024 * 1024 * 5
        },
    },
    'loggers': {
        'django.request': {
            'handlers': ['file'],
            'level': 'INFO'
        },
        'log': {
            'handlers': ['file'],
            'level': 'INFO'
        },
    }
}
DEBUG_LOGGING = {
    'version': 1,
    'formatters': {
        'verbose': {
            'format': '%(levelname)s %(asctime)s %(module)s %(process)d %(thread)d %(message)s'
        },
    },
    'handlers': {
        'file': {
            'level': 'DEBUG',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(BASE_DIR, 'logs', 'debug-prs.log'),
            'formatter': 'verbose',
            'maxBytes': 1024 * 1024 * 5
        },
    },
    'loggers': {
        'django.request': {
            'handlers': ['file'],
            'level': 'DEBUG'
        },
        'log': {
            'handlers': ['file'],
            'level': 'DEBUG'
        },
    }
}


# Supplement some settings when DEBUG is True.
if DEBUG:
    LOGGING = DEBUG_LOGGING
    # Developer local IP may be required for debug_toolbar to work/
    if env('INTERNAL_IP', False):
        INTERNAL_IPS.append(env('INTERNAL_IP'))
    INSTALLED_APPS += (
        'debug_toolbar',
    )
    DEBUG_TOOLBAR_PATCH_SETTINGS = True
    MIDDLEWARE_CLASSES = ('debug_toolbar.middleware.DebugToolbarMiddleware',) + MIDDLEWARE_CLASSES

# Tastypie settings
TASTYPIE_DEFAULT_FORMATS = ['json']

# crispy_forms settings
CRISPY_TEMPLATE_PACK = 'bootstrap3'

# django-sql-explorer settings
# Requires user is_staff==True and membership in 'PRS power user' group.
EXPLORER_PERMISSION_VIEW = lambda u: u.is_staff and u.userprofile.is_power_user()

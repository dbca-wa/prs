import logging
from .settings import *

# Modify project settings to speed up unit tests.
logging.disable(logging.CRITICAL)
DEBUG = False
TEMPLATES[0]['OPTIONS'] = {
    'debug': False,
    'context_processors': [
        'django.contrib.auth.context_processors.auth',
        'django.template.context_processors.media',
        'django.template.context_processors.static',
        'django.template.context_processors.request',
        'django.template.context_processors.csrf',
        'django.contrib.messages.context_processors.messages',
        'prs2.context_processors.template_context',
    ],
}
PASSWORD_HASHERS = (
    'django.contrib.auth.hashers.MD5PasswordHasher',
)
# Use local media storage
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
DEFAULT_FILE_STORAGE = 'django.core.files.storage.FileSystemStorage'
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

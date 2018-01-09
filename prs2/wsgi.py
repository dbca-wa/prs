"""
WSGI config for prs2 project.
It exposes the WSGI callable as a module-level variable named ``application``.
"""
import confy
confy.read_environment_file()  # Must precede dj_static imports.
from django.core.wsgi import get_wsgi_application
from dj_static import Cling, MediaCling
import os


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "prs2.settings")
application = Cling(MediaCling(get_wsgi_application()))

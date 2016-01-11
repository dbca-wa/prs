"""
WSGI config for prs2 project.
It exposes the WSGI callable as a module-level variable named ``application``.
"""
from django.core.wsgi import get_wsgi_application
import confy
confy.read_environment_file(".env")
from dj_static import Cling, MediaCling
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "prs2.settings")
application = Cling(MediaCling(get_wsgi_application()))

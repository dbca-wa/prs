"""
WSGI config for prs2 project.
It exposes the WSGI callable as a module-level variable named ``application``.
"""
import confy
from django.core.wsgi import get_wsgi_application
from dj_static import Cling, MediaCling

confy.read_environment_file('.env')
application = Cling(MediaCling(get_wsgi_application()))

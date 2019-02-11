"""
WSGI config for prs2 project.
It exposes the WSGI callable as a module-level variable named ``application``.
"""
import dotenv
from django.core.wsgi import get_wsgi_application
import os
from pathlib import Path

# These lines are required for interoperability between local and container environments.
d = Path(__file__).resolve().parents[1]
dot_env = os.path.join(str(d), '.env')
if os.path.exists(dot_env):
    dotenv.read_dotenv(dot_env)


from dj_static import Cling, MediaCling

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'prs2.settings')
application = Cling(MediaCling(get_wsgi_application()))

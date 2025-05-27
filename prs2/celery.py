import os
from pathlib import Path

from celery import Celery

base_dir = str(Path(__file__).resolve().parents[1])
dot_env_file = os.path.join(base_dir, ".env")
if os.path.exists(dot_env_file):
    from dotenv import load_dotenv

    load_dotenv()

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "prs2.settings")
app = Celery("prs2")
app.config_from_object("django.conf:settings")
app.autodiscover_tasks()

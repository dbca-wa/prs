"""Tests for project settings, focused on conditional configuration that only
activates when particular environment variables are present.
"""

import importlib.util
import os
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

SETTINGS_PATH = Path(settings.BASE_DIR, "prs", "settings.py")
CACHE_ENV_VARS = ("REDIS_CACHE_HOST", "REDIS_CACHE_PASSWORD", "VALKEY_CACHE_HOST")


def load_settings(**env_overrides):
    """Import prs/settings.py as a fresh module with a controlled environment.

    Caching is configured conditionally from the environment, so re-importing
    the settings module is the only way to exercise those branches.
    """
    saved = {key: os.environ.get(key) for key in CACHE_ENV_VARS}
    try:
        for key in CACHE_ENV_VARS:
            os.environ.pop(key, None)
        os.environ.update(env_overrides)
        spec = importlib.util.spec_from_file_location("prs_settings_probe", SETTINGS_PATH)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        for key in CACHE_ENV_VARS:
            os.environ.pop(key, None)
            if saved[key] is not None:
                os.environ[key] = saved[key]


class CacheSettingsTest(SimpleTestCase):
    def test_redis_cache_with_password(self):
        # A configured password must produce valid redis-py connection options
        # (previously this raised KeyError: 'OPTIONS' at startup).
        module = load_settings(REDIS_CACHE_HOST="redis://cache:6379/1", REDIS_CACHE_PASSWORD="s3cret")
        options = module.CACHES["default"]["OPTIONS"]
        self.assertEqual(options["password"], "s3cret")
        self.assertIn("socket_timeout", options)

    def test_redis_cache_without_password(self):
        module = load_settings(REDIS_CACHE_HOST="redis://cache:6379/1")
        options = module.CACHES["default"]["OPTIONS"]
        self.assertNotIn("password", options)
        self.assertIn("socket_connect_timeout", options)

    def test_valkey_cache(self):
        module = load_settings(VALKEY_CACHE_HOST="valkey://cache:6379/1")
        options = module.CACHES["default"]["OPTIONS"]
        self.assertIn("SOCKET_TIMEOUT", options)

    def test_dummy_cache_when_unconfigured(self):
        module = load_settings()
        self.assertEqual(module.CACHES["default"]["BACKEND"], "django.core.cache.backends.dummy.DummyCache")

    def test_redis_cache_options_are_accepted_by_redis_py(self):
        # Django hands OPTIONS straight to redis-py, so build a connection to
        # prove the option names are valid.
        from django.core.cache.backends.redis import RedisCache

        module = load_settings(REDIS_CACHE_HOST="redis://cache:6379/1", REDIS_CACHE_PASSWORD="s3cret")
        cache = RedisCache("redis://cache:6379/1", module.CACHES["default"])
        connection = cache._cache._get_connection_pool(write=True).make_connection()
        self.assertEqual(connection.password, "s3cret")
        self.assertEqual(connection.socket_timeout, 5)

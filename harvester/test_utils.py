from unittest.mock import Mock, patch

from django.conf import settings
from django.test import SimpleTestCase

from harvester.utils import query_slip, query_slip_esri


class SlipQueryTest(SimpleTestCase):
    """Outbound HTTP requests to the SLIP services must always specify a timeout,
    so an unresponsive upstream service cannot block a Celery worker indefinitely.
    """

    def test_query_slip_sets_timeout(self):
        response = Mock()
        response.json.return_value = {}
        with (
            patch("harvester.utils.env", return_value="https://slip.example"),
            patch("harvester.utils.requests.get", return_value=response) as mock_get,
        ):
            query_slip(12345)
        self.assertEqual(mock_get.call_args.kwargs["timeout"], settings.HTTP_TIMEOUT)

    def test_query_slip_esri_sets_timeout(self):
        response = Mock()
        response.json.return_value = {}
        with (
            patch("harvester.utils.env", return_value="https://slip.example"),
            patch("harvester.utils.requests.get", return_value=response) as mock_get,
        ):
            query_slip_esri(12345)
        self.assertEqual(mock_get.call_args.kwargs["timeout"], settings.HTTP_TIMEOUT)

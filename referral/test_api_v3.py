from django.urls import reverse

from referral.api_v3 import MAX_PAGE_SIZE
from referral.test_models import PrsTestCase

API_MODELS_LOOKUP = [
    "referraltype",
    "region",
    "organisation",
    "taskstate",
    "tasktype",
    "user",
    "tag",
]
API_MODELS = [
    "referral",
    "task",
    "clearance",
]


class PrsAPITest(PrsTestCase):
    def assert_anonymous_denied(self, url):
        """Anonymous requests must be redirected to the login page."""
        self.client.logout()
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith(f"{reverse('login')}?next="))

    def test_permission_resource_list(self):
        """Test auth and anon access permission to resource lists"""
        for model in API_MODELS_LOOKUP + API_MODELS:
            url = reverse(f"api:{model}_api_resource")
            # Anonymous users must not be able to read PRS data.
            self.assert_anonymous_denied(url)
            self.client.login(username="normaluser", password="pass")
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.client.login(username="readonlyuser", password="pass")
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)

    def test_permission_resource_detail(self):
        """Test auth and anon access permission to resource details"""
        for model in API_MODELS_LOOKUP:
            url = reverse(f"api:{model}_api_resource")
            self.client.login(username="normaluser", password="pass")
            response = self.client.get(url)
            res_list = response.json()
            obj_id = res_list[0]["id"]
            url = reverse(f"api:{model}_api_resource", kwargs={"pk": obj_id})
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.client.login(username="readonlyuser", password="pass")
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            # Anonymous users must not be able to read PRS data.
            self.assert_anonymous_denied(url)
        # The API response is a bit different for these models.
        for model in API_MODELS:
            url = reverse(f"api:{model}_api_resource")
            self.client.login(username="normaluser", password="pass")
            response = self.client.get(url)
            res_list = response.json()
            obj_id = res_list["objects"][0]["id"]
            url = reverse(f"api:{model}_api_resource", kwargs={"pk": obj_id})
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.client.login(username="readonlyuser", password="pass")
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            # Anonymous users must not be able to read PRS data.
            self.assert_anonymous_denied(url)


class PrsAPIPaginationTest(PrsTestCase):
    """Test pagination parameter handling on the paginated API resources."""

    def setUp(self):
        super().setUp()
        self.client.login(username="normaluser", password="pass")

    def get_url(self, model, **params):
        url = reverse(f"api:{model}_api_resource")
        if params:
            url = f"{url}?{'&'.join(f'{k}={v}' for k, v in params.items())}"
        return url

    def test_invalid_pagination_values_return_400(self):
        """Malformed offset/limit values must not raise a server error."""
        for model in API_MODELS:
            for params in (
                {"limit": "abc"},
                {"offset": "abc"},
                {"limit": -1},
                {"offset": -1},
                {"limit": 0},
                {"limit": ""},
            ):
                with self.subTest(model=model, params=params):
                    response = self.client.get(self.get_url(model, **params))
                    self.assertEqual(response.status_code, 400)
                    self.assertIn("error", response.json())

    def test_limit_is_capped(self):
        """A limit above MAX_PAGE_SIZE is clamped, not honoured."""
        for model in API_MODELS:
            with self.subTest(model=model):
                response = self.client.get(self.get_url(model, limit=MAX_PAGE_SIZE * 100))
                self.assertEqual(response.status_code, 200)
                self.assertLessEqual(len(response.json()["objects"]), MAX_PAGE_SIZE)

    def test_default_and_explicit_pagination(self):
        """Valid pagination values return the requested slice."""
        for model in API_MODELS:
            with self.subTest(model=model):
                default_resp = self.client.get(self.get_url(model))
                self.assertEqual(default_resp.status_code, 200)
                self.assertLessEqual(len(default_resp.json()["objects"]), 50)

                page_resp = self.client.get(self.get_url(model, offset=0, limit=1))
                self.assertEqual(page_resp.status_code, 200)
                page = page_resp.json()
                self.assertEqual(len(page["objects"]), 1)
                self.assertEqual(page["objects"][0]["id"], default_resp.json()["objects"][0]["id"])

    def test_offset_beyond_result_count_returns_first_page(self):
        """An offset greater than the result count is ignored."""
        for model in API_MODELS:
            with self.subTest(model=model):
                first_page = self.client.get(self.get_url(model)).json()
                response = self.client.get(self.get_url(model, offset=10000))
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["objects"][0]["id"], first_page["objects"][0]["id"])

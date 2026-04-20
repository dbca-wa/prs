from django.urls import reverse
from referral.test_models import PrsTestCase


class PublishViewTest(PrsTestCase):
    def test_reportview_anon_unauth_redirect(self):
        """Test that the ReportView redirects anonymous users"""
        url = reverse("reports")
        response = self.client.get(url)  # Anonymous user
        self.assertEqual(response.status_code, 302)

    def test_reportview_auth(self):
        """Test that authenticated users can open the ReportView"""
        url = reverse("reports")
        for user in ["admin", "poweruser", "normaluser"]:
            self.client.login(username=user, password="pass")
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)

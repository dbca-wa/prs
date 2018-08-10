from django.urls import reverse
from referral.test_models import PrsTestCase


API_MODELS = [
    'agency', 'clearance', 'condition', 'conditioncategory', 'doptrigger',
    'location', 'note', 'notetype', 'organisation', 'organisationtype',
    'record', 'referral', 'type', 'region', 'task', 'taskstate',
    'tasktype', 'userprofile', 'user', 'tag', 'modelcondition']

class PrsAPI2Test(PrsTestCase):

    def test_permission_view_list(self):
        """Test auth and anon access permission to view lists
        """
        for i in API_MODELS:
            url = reverse('referral_api:' + i + '-list')
            self.client.logout()
            response = self.client.get(url)  # Anonymous user
            self.assertEqual(response.status_code, 403)
            self.client.login(username='normaluser', password='pass')
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.client.login(username='readonlyuser', password='pass')
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)

    def test_permission_view_detail(self):
        """Test auth and anon access permission to view details
        """
        for i in API_MODELS:
            url = reverse('referral_api:' + i + '-list')
            self.client.login(username='normaluser', password='pass')
            response = self.client.get(url)
            res_list = response.json()
            if res_list[0]:  # Object(s) exist.
                obj_id = res_list[0]['id']
                url = reverse('referral_api:' + i + '-detail', args=[obj_id])
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.client.logout()
            self.client.login(username='readonlyuser', password='pass')
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.client.logout()
            response = self.client.get(url)
            self.assertEqual(response.status_code, 403)
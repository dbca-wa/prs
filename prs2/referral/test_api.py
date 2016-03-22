from django.core.urlresolvers import reverse
import json
from referral.test_models import PrsTestCase


API_MODELS = [
    'agency', 'clearance', 'condition', 'conditioncategory', 'doptrigger',
    'location', 'note', 'notetype', 'organisation', 'organisationtype',
    'record', 'referral', 'referraltype', 'region', 'task', 'taskstate',
    'tasktype', 'userprofile', 'user', 'tag', 'modelcondition']


class PrsAPITest(PrsTestCase):

    def test_permission_resource_list(self):
        """Test auth and anon access permission to resource lists
        """
        for i in API_MODELS:
            url = reverse(
                'api_dispatch_list', kwargs={'resource_name': i, 'api_name': 'v1'})
            self.client.logout()
            response = self.client.get(url)  # Anonymous user
            self.assertEqual(response.status_code, 401)
            self.client.login(username='normaluser', password='pass')
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)

    '''
    def test_permission_resource_detail(self):
        """Test auth and anon access permission to resource details
        """
        for i in API_MODELS:
            url = reverse(
                'api_dispatch_list', kwargs={'resource_name': i, 'api_name': 'v1'})
            self.client.login(username='normaluser', password='pass')
            response = self.client.get(url)
            res_list = json.loads(response.content)
            obj_id = res_list['objects'][0]['id']
            url = reverse(
                'api_dispatch_detail', kwargs={
                    'resource_name': i, 'api_name': 'v1', 'pk': obj_id}
            )
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.client.logout()
            response = self.client.get(url)
            self.assertEqual(response.status_code, 401)
    '''

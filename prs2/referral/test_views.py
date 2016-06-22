from __future__ import absolute_import, print_function, unicode_literals
from datetime import date
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Polygon
from django.core.urlresolvers import reverse
from django.test import Client
from django.utils.http import urlencode
from django_webtest import WebTest
from mixer.backend.django import mixer

from referral.models import (
    Agency, Organisation, OrganisationType, ReferralType, TaskType,
    TaskState, Task, Record, Note, Condition, Location, Clearance,
    Bookmark, Region, Referral, DopTrigger)
from referral.test_models import PrsTestCase
from taggit.models import Tag

User = get_user_model()


class PrsViewsTestCase(PrsTestCase):
    models = [
        Organisation, Referral, Task, Record, Note, Condition,
        Location, Clearance, Bookmark]
    client = Client()

    def setUp(self):
        super(PrsViewsTestCase, self).setUp()
        # Log in normaluser by default.
        self.client.login(username='normaluser', password='pass')


class SiteAuthViewsTest(PrsViewsTestCase):
    """Test the site login/login views.
    """

    def test_login(self):
        """Test login view renders
        """
        url = reverse('login')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'login.html')

    def test_logout(self):
        """Test logout view renders
        """
        url = reverse('logout')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'logged_out.html')


class BaseViewTest(PrsViewsTestCase):
    """Test the generic object list view.
    """

    def test_get(self):
        """Test prs_object_list view for each model type
        """
        for i in self.models:
            url = reverse('prs_object_list', kwargs={'model': i._meta.object_name.lower()})
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertTemplateUsed(response, 'referral/prs_object_list.html')
            # Also test with a view with a query string.
            url += '?q=foo+bar'
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)

    def test_nonsense_model(self):
        """Test an attempt to reverse the list view for a non-existent model.
        """
        url = reverse('prs_object_list', kwargs={'model': 'foobar'})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 400)  # Returns a HTTP 400 error.


class SiteHomeTest(PrsViewsTestCase):
    """Test the SiteHome view.
    """

    def test_homepage(self):
        """Test that site homepage view contains required elements
        """
        # Ensure normaluser has a task assigned.
        task = Task.objects.all()[0]
        task.assigned_user = self.n_user
        task.save()
        url = reverse('site_home')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'site_home.html')
        self.assertContains(response, 'ONGOING TASKS')
        self.assertContains(response, reverse('site_home_print'))

    def test_homepage_admin(self):
        """Test that the navbar only renders the admin link for superusers
        """
        url = reverse('site_home')
        response = self.client.get(url)
        link = '<a href="/admin/" title="Administration">Administration</a>'
        self.assertIs(response.content.find(link), -1)
        # Log in as admin user
        self.client.logout()
        self.client.login(username='admin', password='pass')
        response = self.client.get(url)
        self.assertIsNot(response.content.find(link), -1)

    def test_homepage_printable(self):
        """Test that the site printable homepage uses the correct template
        """
        url = reverse('site_home_print')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'site_home_print.html')

    def test_stopped_tasks(self):
        """Test the 'stopped tasks' homepage view
        """
        url = reverse('stopped_tasks_list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'site_home.html')
        self.assertContains(response, 'STOPPED TASKS')


class HelpPageTest(PrsViewsTestCase):

    def test_help_page(self):
        """Test that the site help page renders
        """
        url = reverse('help_page')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'help_page.html')
        self.assertContains(response, 'HELP')


class GeneralSearchTest(PrsViewsTestCase):

    def test_general_search(self):
        """Test that the general search page renders
        """
        url = reverse('prs_general_search')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'referral/prs_general_search.html')
        # Test the view with a query string.
        url += '?q=foo'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)


class ReferralDetailTest(PrsViewsTestCase):
    """Test the referral detail view.
    """

    def setUp(self):
        super(ReferralDetailTest, self).setUp()
        self.ref = Referral.objects.all()[0]

    def test_get(self):
        """Test that the referral detail page renders
        """
        url = self.ref.get_absolute_url()
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'referral/referral_detail.html')

    def test_related(self):
        """Test that each of the referral related object types render
        """
        for m in ['tasks', 'notes', 'records', 'locations', 'conditions']:
            url = reverse('referral_detail', kwargs={'pk': self.ref.pk, 'related_model': m})
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)

    def test_print_notes(self):
        """Test that the referral notes printable view renders
        """
        url = reverse('referral_detail', kwargs={'pk': self.ref.pk})
        url += '?' + urlencode({'print': 'notes'})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'referral/referral_notes_print.html')

    def test_referral_history(self):
        """Test that the referral history view renders
        """
        url = reverse('prs_object_history', kwargs={'model': 'referral', 'pk': self.ref.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'referral/prs_object_history.html')

    def test_referral_generate_qgis(self):
        """Test the the referral with locations can return a QGIS layer definition
        """
        l = Location.objects.all()[0]
        l.referral = self.ref
        l.poly = Polygon(((0.0, 0.0), (0.0, 50.0), (50.0, 50.0), (50.0, 0.0), (0.0, 0.0)))
        l.save()
        url = self.ref.get_absolute_url()
        response = self.client.get(url, {'generate_qgis': 'true'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['content-type'], 'application/x-qgis-project')


class ReferralCreateTest(PrsViewsTestCase, WebTest):
    """Test the customised referral create view.
    """

    def setUp(self):
        super(ReferralCreateTest, self).setUp()
        # We need a couple of specific objects to exist:
        if not Organisation.objects.filter(slug='wapc'):
            Organisation.objects.create(
                name='Western Australian Planning Commission',
                slug='wapc',
                type=OrganisationType.objects.all()[0],
                list_name='Western Australian Planning Commission (WAPC)')
        self.org = Organisation.objects.get(slug='wapc')
        if not TaskType.objects.filter(slug='assess-a-referral'):
            TaskType.objects.create(
                name='Assess a referral', slug='assess-a-referral',
                initial_state=TaskState.objects.all()[0])
        self.task_type = TaskType.objects.get(slug='assess-a-referral')
        if not ReferralType.objects.filter(slug='subdivision'):
            ReferralType.objects.create(
                name='Subdivision', slug='subdivision',
                initial_task=TaskType.objects.all()[0])
        self.ref_type = ReferralType.objects.get(slug='subdivision')
        self.url = reverse('referral_create')

    def test_get(self):
        """Test that the referral create view renders
        """
        r = self.app.get(self.url, user='normaluser')
        self.assertEqual(r.status_code, 200)
        self.assertTemplateUsed(r, 'referral/referral_create.html')

    def test_cancel(self):
        """Test the cancelling the referral create view redirects to home
        """
        r = self.app.get(self.url, user='normaluser')
        form = r.form
        r = form.submit('cancel')
        self.assertEqual(r.status_code, 302)
        self.assertRedirects(r, reverse('site_home'))

    def test_post(self):
        """Test referral creation form submit
        """
        r = self.app.get(self.url, user='normaluser')
        form = r.form
        form['reference'] = 'Test reference 1'
        form['description'] = 'Test description 1'
        form['referral_date'] = '21/12/2015'
        form['type'] = self.ref_type.pk
        form['assigned_user'] = self.n_user.pk
        form['region'] = [Region.objects.all()[0].pk]
        form['dop_triggers'] = [DopTrigger.objects.all()[0].pk]
        r = form.submit('save').follow()
        self.assertEqual(r.status_code, 200)
        ref = Referral.objects.get(reference='Test reference 1')
        self.assertTrue(ref in Referral.objects.all())

    def test_post_email(self):
        """Test referral creation form submit with email checked
        """
        r = self.app.get(self.url, user='normaluser')
        form = r.form
        form['reference'] = 'Test reference 2'
        form['description'] = 'Test description 2'
        form['referral_date'] = '21/12/2015'
        form['type'] = self.ref_type.pk
        form['assigned_user'] = self.n_user.pk
        form['email_user'] = True
        form['due_date'] = '21/1/2016'
        form['region'] = [Region.objects.all()[0].pk]
        form['dop_triggers'] = [DopTrigger.objects.all()[0].pk]
        r = form.submit().follow()
        self.assertEqual(r.status_code, 200)
        ref = Referral.objects.get(reference='Test reference 2')
        self.assertTrue(ref in Referral.objects.all())


class ReferralUpdateTest(PrsViewsTestCase, WebTest):
    """Test the generic object update view.
    """
    def setUp(self):
        super(ReferralUpdateTest, self).setUp()
        self.ref = Referral.objects.all()[0]
        self.url = reverse('prs_object_update', kwargs={'model': 'referral', 'pk': self.ref.pk})

    def test_get(self):
        """Test the referral update view
        """
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200, 'Update view failed: {0}'.format(self.url))
        self.assertTemplateUsed(r, 'referral/change_form.html')

    def test_cancel(self):
        """Test that cancelling the referral update view redirects correctly
        """
        r = self.client.post(self.url, {'cancel': 'Cancel'})
        self.assertRedirects(r, self.ref.get_absolute_url())

    def test_post(self):
        """Test that updating a referral actually changes it
        """
        r = self.app.get(self.url, user='normaluser')
        form = r.form
        form['reference'] = 'New reference value'
        r = form.submit()
        self.assertEqual(r.status_code, 200)
        ref = Referral.objects.get(pk=self.ref.pk)  # Re-read from db
        self.assertNotEqual(ref.reference, 'New reference value')


class ReferralRecentTest(PrsViewsTestCase):
    """Test the custom 'recent referrals' view.
    """

    def test_get(self):
        url = reverse('referral_recent')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'referral/referral_recent.html')
        self.assertContains(response, 'RECENTLY OPENED REFERRALS')


class LocationCreateTest(PrsViewsTestCase):
    """Test the custom LocationCreate view.
    TODO: test a POST request.
    """

    def test_get(self):
        """Test the location_create view
        """
        ref = Referral.objects.all()[0]
        url = reverse('referral_location_create', kwargs={'pk': ref.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200, 'Location create view failed: {0}'.format(url))
        self.assertTemplateUsed(response, 'referral/location_create.html')

    def test_cancel(self):
        """Test that cancelling the referral update view redirects correctly
        """
        ref = Referral.objects.all()[0]
        url = reverse('referral_location_create', kwargs={'pk': ref.pk})
        response = self.client.post(url, {'cancel': 'Cancel'})
        self.assertRedirects(response, ref.get_absolute_url())


class PrsObjectDeleteTest(PrsViewsTestCase):
    """
    Test the generic object delete view.
    """
    models = [Referral, Task, Record, Note, Condition, Location]

    def test_get(self):
        """Test the GET method of the generic delete view
        """
        for model in self.models:
            for i in model.objects.all():
                url = reverse(
                    'prs_object_delete',
                    kwargs={
                        'model': i._meta.object_name.lower(),
                        'pk': i.pk})
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, i.as_tbody())
                self.assertTemplateUsed(response, 'referral/prs_object_delete.html')

    def test_post(self):
        """Test the POST method of the generic delete view
        """
        for model in self.models:
            for obj in model.objects.all():
                # Child objects of referrals should redirect to the referral's URL.
                if hasattr(obj, 'referra'):
                    next_url = obj.referral.get_absolute_url()
                else:
                    next_url = reverse('site_home')
                url = reverse(
                    'prs_object_delete',
                    kwargs={
                        'model': obj._meta.object_name.lower(),
                        'pk': obj.pk})
                response = self.client.post(
                    url, {'delete': 'Delete', 'next': next_url}, follow=True)
                self.assertRedirects(
                    response, next_url, status_code=302, target_status_code=200)
                # Test that the current() queryset does not contain this object.
                self.assertNotIn(obj.pk, [i.pk for i in model.objects.current()])


class PrsObjectTagTest(PrsViewsTestCase):
    models = [Referral, Condition]

    def setUp(self):
        super(PrsObjectTagTest, self).setUp()
        self.tag = Tag.objects.get_or_create(name='TestTag')[0]

    def test_get(self):
        """Test that a GET request to this view returns a 405.
        """
        for model in self.models:
            for obj in model.objects.all():
                url = reverse(
                    'prs_object_tag',
                    kwargs={
                        'model': obj._meta.object_name.lower(),
                        'pk': obj.pk})
                response = self.client.get(url)
                self.assertEqual(response.status_code, 405)

    def test_post_create(self):
        """Test a POST request to create a tag on an object.
        """
        for model in self.models:
            for obj in model.objects.all():
                url = reverse(
                    'prs_object_tag',
                    kwargs={
                        'model': obj._meta.object_name.lower(),
                        'pk': obj.pk})
                response = self.client.post(url, {'tag': self.tag.name})
                self.assertEqual(response.status_code, 200)
                self.assertTrue(self.tag in obj.tags.all())

    def test_post_delete(self):
        """Test a POST request to delete a tag on an object.
        """
        for model in self.models:
            for obj in model.objects.all():
                obj.tags.add(self.tag)
                self.assertTrue(self.tag in obj.tags.all())
                url = reverse(
                    'prs_object_tag',
                    kwargs={
                        'model': obj._meta.object_name.lower(),
                        'pk': obj.pk})
                response = self.client.post(url, {'tag': self.tag.name, 'delete': ''})
                self.assertEqual(response.status_code, 200)
                self.assertFalse(self.tag in obj.tags.all())

    def test_post_faulty(self):
        """Test a faulty POST request to create a tag (missing tag parameter)
        """
        for model in self.models:
            for obj in model.objects.all():
                url = reverse(
                    'prs_object_tag',
                    kwargs={
                        'model': obj._meta.object_name.lower(),
                        'pk': obj.pk})
                response = self.client.post(url)
                self.assertEqual(response.status_code, 400)


class TagListTest(PrsViewsTestCase):

    def setUp(self):
        super(TagListTest, self).setUp()
        # Create a bunch of additional Tags.
        tags = (tag for tag in ['tag1', 'tag2', 'tag3', 'tag4', 'tag5'])
        for counter in range(5):
            mixer.blend(Tag, name=tags)

    def test_get(self):
        """Test that the rendered response contains text of all tags
        """
        url = reverse('tag_list')
        response = self.client.get(url)
        self.assertEquals(response.status_code, 200)
        for tag in Tag.objects.all():
            self.assertContains(response, tag.name)

    def test_get_json(self):
        """Test that a request for tags as JSON data returns correctly
        """
        url = reverse('tag_list')
        response = self.client.get(url, data={'json': 'true'})
        self.assertEquals(response.get('Content-Type'), 'application/json')

    def test_post(self):
        """Test that POST requests are not allowed
        """
        url = reverse('tag_list')
        response = self.client.post(url)
        self.assertEquals(response.status_code, 405)


class TagReplaceTest(PrsViewsTestCase, WebTest):
    """Integrated WebTest to test form submission easily.
    """

    def setUp(self):
        super(TagReplaceTest, self).setUp()
        self.url = reverse('tag_replace')
        # Create some new Tags.
        self.old_tag = mixer.blend(Tag)
        self.new_tag = mixer.blend(Tag)
        # Start each test logged out.
        self.client.logout()

    def test_get_normaluser(self):
        """Test that non-power-user can't access the view
        """
        # Log in as normal PRS user
        self.client.login(username='normaluser', password='pass')
        response = self.client.get(self.url)
        self.assertEquals(response.status_code, 403)
        # Log in as read-only user
        self.client.logout()
        self.client.login(username='readonlyuser', password='pass')
        response = self.client.get(self.url)
        self.assertEquals(response.status_code, 403)

    def test_get_poweruser(self):
        """Test that a power user or superuser can access the view
        """
        # Log in as PRS power user
        self.client.login(username='poweruser', password='pass')
        response = self.client.get(self.url)
        self.assertEquals(response.status_code, 200)
        # Log in as admin user
        self.client.logout()
        self.client.login(username='admin', password='pass')
        response = self.client.get(self.url)
        self.assertEquals(response.status_code, 200)

    def test_cancel(self):
        """Test the cancel redirects to tag list view
        """
        self.client.login(username='poweruser', password='pass')
        response = self.client.post(self.url, {'cancel': 'Cancel'})
        self.assertRedirects(response, reverse('tag_list'))

    def test_post(self):
        """Test that replacing a tag works correctly
        """
        ref = Referral.objects.all()[0]
        ref.tags.add(self.old_tag)
        self.assertTrue(self.old_tag in ref.tags.all())
        self.assertFalse(self.new_tag in ref.tags.all())
        r = self.app.get(self.url, user='poweruser')
        form = r.form
        form['old_tag'] = self.old_tag.pk
        form['replace_with'] = self.new_tag.pk
        form.submit().follow()
        ref = Referral.objects.get(pk=ref.pk)  # Re-read from db
        self.assertTrue(self.new_tag in ref.tags.all())
        self.assertFalse(self.old_tag in ref.tags.all())


class ReferralTaggedTest(PrsViewsTestCase):

    def setUp(self):
        super(ReferralTaggedTest, self).setUp()
        self.tag = Tag.objects.get_or_create(name='TestTag')[0]
        # Tag one referral only.
        self.ref_tagged = Referral.objects.all()[0]
        self.ref_tagged.tags.add(self.tag)
        self.ref_untagged = Referral.objects.exclude(pk=self.ref_tagged.pk)[0]

    def test_get(self):
        """Test that a tagged referral is present in the referral_tagged view context
        """
        url = reverse('referral_tagged', kwargs={'slug': self.tag.slug})
        response = self.client.get(url)
        self.assertEquals(response.status_code, 200)
        self.assertTrue(self.ref_tagged in response.context['object_list'])
        self.assertFalse(self.ref_untagged in response.context['object_list'])


class TaskActionTest(PrsViewsTestCase):

    def setUp(self):
        super(TaskActionTest, self).setUp()
        self.task = Task.objects.all()[0]

    def test_get_update(self):
        """Test the Task update view responds
        """
        url = reverse('task_action', kwargs={'pk': self.task.pk, 'action': 'update'})
        response = self.client.get(url)
        self.assertEquals(response.status_code, 200)

    def test_cant_update_stopped_task(self):
        """Test that a stopped task can't be updated
        """
        self.task.stop_date = date.today()
        self.task.save()
        url = reverse('task_action', kwargs={'pk': self.task.pk, 'action': 'update'})
        response = self.client.get(url)
        # Response should be a redirect to the object URL.
        self.assertRedirects(response, self.task.get_absolute_url())
        # Test that the redirected response contains an error message.
        response = self.client.get(url, follow=True)
        messages = response.context['messages']._get()[0]
        self.assertIsNot(messages[0].message.find("You can't edit a stopped task"), -1)

    def test_cant_stop_completed_task(self):
        """Test that a completed task can't be stopped
        """
        self.task.complete_date = date.today()
        self.task.save()
        url = reverse('task_action', kwargs={'pk': self.task.pk, 'action': 'stop'})
        response = self.client.get(url)
        # Response should be a redirect to the object URL.
        self.assertRedirects(response, self.task.get_absolute_url())
        # Test that the redirected response contains an error message.
        response = self.client.get(url, follow=True)
        messages = response.context['messages']._get()[0]
        self.assertIsNot(messages[0].message.find("You can't stop a completed task"), -1)

    def test_cant_restart_unstopped_task(self):
        """Test that a non-stopped task can't be started
        """
        url = reverse('task_action', kwargs={'pk': self.task.pk, 'action': 'start'})
        response = self.client.get(url)
        # Response should be a redirect to the object URL.
        self.assertRedirects(response, self.task.get_absolute_url())
        # Test that the redirected response contains an error message.
        response = self.client.get(url, follow=True)
        messages = response.context['messages']._get()[0]
        self.assertIsNot(messages[0].message.find("You can't restart a non-stopped task"), -1)

    def test_cant_inherit_owned_task_task(self):
        """Test that you can't inherit a task assigned to you
        """
        self.task.assigned_user = self.n_user
        self.task.save()
        url = reverse('task_action', kwargs={'pk': self.task.pk, 'action': 'inherit'})
        response = self.client.get(url)
        # Response should be a redirect to the object URL.
        self.assertRedirects(response, self.task.get_absolute_url())
        # Test that the redirected response contains an error message.
        response = self.client.get(url, follow=True)
        messages = response.context['messages']._get()[0]
        self.assertIsNot(messages[0].message.find("That task is already assigned to you"), -1)

    def test_cant_cancel_completed_task(self):
        """Test that a completed task can't be cancelled
        """
        self.task.complete_date = date.today()
        self.task.save()
        url = reverse('task_action', kwargs={'pk': self.task.pk, 'action': 'cancel'})
        response = self.client.get(url)
        # Response should be a redirect to the object URL.
        self.assertRedirects(response, self.task.get_absolute_url())
        # Test that the redirected response contains an error message.
        response = self.client.get(url, follow=True)
        messages = response.context['messages']._get()[0]
        self.assertIsNot(messages[0].message.find('That task is already completed'), -1)

    def test_cant_add_task_to_task(self):
        """Test that a task can't be added to another task
        """
        url = reverse('task_action', kwargs={'pk': self.task.pk, 'action': 'add'})
        response = self.client.get(url)
        # Response should be a redirect to the object URL.
        self.assertRedirects(response, self.task.get_absolute_url())

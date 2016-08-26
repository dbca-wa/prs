from __future__ import absolute_import, print_function, unicode_literals
from datetime import date, timedelta
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Polygon
from django.core.urlresolvers import reverse
from django.test import Client
from django.utils.http import urlencode
from django_webtest import WebTest
from mixer.backend.django import mixer
import uuid

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

    def setUp(self):
        super(BaseViewTest, self).setUp()
        # Generate enough objects to paginate list views.
        mixer.cycle(25).blend(
            Referral, type=mixer.SELECT, agency=mixer.SELECT,
            referring_org=mixer.SELECT, referral_date=date.today())
        mixer.cycle(25).blend(
            Task, type=mixer.SELECT, referral=mixer.SELECT, state=mixer.SELECT)
        mixer.cycle(25).blend(
            Note, referral=mixer.SELECT, type=mixer.SELECT, note=mixer.RANDOM)
        mixer.cycle(25).blend(Record, referral=mixer.SELECT)
        mixer.cycle(25).blend(
            Condition, referral=mixer.SELECT, category=mixer.SELECT,
            condition=mixer.RANDOM, model_condition=mixer.SELECT,
            proposed_condition=mixer.RANDOM)
        mixer.cycle(25).blend(
            Clearance, condition=mixer.SELECT, task=mixer.SELECT)
        mixer.cycle(25).blend(Location, referral=mixer.SELECT)

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
        task = Task.objects.first()
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
        self.ref = Referral.objects.first()

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
        """Test that the referral with locations can return a QGIS layer definition
        """
        l = Location.objects.first()
        l.referral = self.ref
        l.poly = Polygon(((0.0, 0.0), (0.0, 50.0), (50.0, 50.0), (50.0, 0.0), (0.0, 0.0)))
        l.save()
        url = self.ref.get_absolute_url()
        r = self.client.get(url, {'generate_qgis': 'true'})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['content-type'], 'application/x-qgis-project')

    def test_referral_deleted_redirect(self):
        """Test that the detail page for a deleted referral redirects to home
        """
        url = self.ref.get_absolute_url()
        self.ref.delete()
        r = self.client.get(url)
        self.assertEqual(r.status_code, 302)
        self.assertRedirects(r, reverse('site_home'))

    def test_referral_bookmarked(self):
        """Test the referral detail page renders differently if bookmarked
        """
        url = self.ref.get_absolute_url()
        response = self.client.get(url)
        self.assertContains(response, 'Bookmark this referral')
        # Bookmark the referral.
        Bookmark.objects.create(referral=self.ref, user=self.n_user)
        response = self.client.get(url)
        self.assertContains(response, 'Remove bookmark')


class ReferralCreateTest(PrsViewsTestCase, WebTest):
    """Test the customised referral create view.
    """

    def setUp(self):
        super(ReferralCreateTest, self).setUp()
        self.org = Organisation.objects.get(slug='wapc')
        self.task_type = TaskType.objects.get(name='Assess a referral')
        self.ref_type = ReferralType.objects.get(name='Subdivision')
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
        form['region'] = [Region.objects.first().pk]
        form['dop_triggers'] = [DopTrigger.objects.first().pk]
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
        form['region'] = [Region.objects.first().pk]
        form['dop_triggers'] = [DopTrigger.objects.first().pk]
        r = form.submit().follow()
        self.assertEqual(r.status_code, 200)
        ref = Referral.objects.get(reference='Test reference 2')
        self.assertTrue(ref in Referral.objects.all())


class ReferralUpdateTest(PrsViewsTestCase, WebTest):
    """Test the generic object update view.
    """
    def setUp(self):
        super(ReferralUpdateTest, self).setUp()
        self.ref = Referral.objects.first()
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


class ReferralCreateChildTest(PrsViewsTestCase):
    """Test views related to creating child objects on a referral
    """
    def setUp(self):
        super(ReferralCreateChildTest, self).setUp()
        self.ref = Referral.objects.first()
        # Ensure that conditions with 'approved' text exist on the referral.
        mixer.cycle(3).blend(
            Condition, referral=self.ref, category=mixer.SELECT,
            condition=mixer.RANDOM, model_condition=mixer.SELECT,
            proposed_condition=mixer.RANDOM)
        for i in Condition.objects.filter(referral=self.ref):
            i.proposed_condition_html = '<p>Proposed condition</p>'
            i.condition_html = '<p>Actual condition</p>'
            i.save()

    def test_create_get(self):
        """Test GET request for each of: task, record, note, condition
        """
        for i in ['task', 'record', 'note', 'condition']:
            url = reverse('referral_create_child', kwargs={'pk': self.ref.pk, 'model': i})
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200)

    def test_cancel(self):
        """Test that cancelling the create view redirects correctly
        """
        for i in ['task', 'record', 'note', 'condition']:
            url = reverse('referral_create_child', kwargs={'pk': self.ref.pk, 'model': i})
            r = self.client.post(url, {'cancel': 'Cancel'})
            self.assertRedirects(r, self.ref.get_absolute_url())

    def test_create_related_get(self):
        """Test GET for relating 'child' objects together
        """
        # Relate existing record to note
        n = Note.objects.first()
        url = reverse('referral_create_child_related', kwargs={
            'pk': self.ref.pk, 'model': 'note', 'id': n.pk, 'type': 'addrecord'})
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        # Create new record on note
        url = reverse('referral_create_child_related', kwargs={
            'pk': self.ref.pk, 'model': 'note', 'id': n.pk, 'type': 'addnewrecord'})
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        # Relate existing note to record
        rec = Record.objects.first()
        url = reverse('referral_create_child_related', kwargs={
            'pk': self.ref.pk, 'model': 'record', 'id': rec.pk, 'type': 'addnote'})
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        # Create new note on record
        url = reverse('referral_create_child_related', kwargs={
            'pk': self.ref.pk, 'model': 'record', 'id': rec.pk, 'type': 'addnewnote'})
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

    def test_create_clearance_redirect(self):
        """Test redirect where no approved conditions on the referral
        """
        # Delete any existing conditions on the referral.
        for i in Condition.objects.filter(referral=self.ref):
            i.delete()
        url = reverse('referral_create_child_type', kwargs={
            'pk': self.ref.pk, 'model': 'task', 'type': 'clearance'})
        r = self.client.get(url)
        self.assertEqual(r.status_code, 302)

    def test_create_child_type(self):
        """Test GET for creating a child object of defined type (clearance)
        """
        url = reverse('referral_create_child_type', kwargs={
            'pk': self.ref.pk, 'model': 'task', 'type': 'clearance'})
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

    def test_create_clearance_request(self):
        """Test POST request for creating a clearance request on a referral
        """
        url = reverse('referral_create_child_type', kwargs={
            'pk': self.ref.pk, 'model': 'task', 'type': 'clearance'})
        cond = Condition.objects.filter(referral=self.ref).first()
        # Test that no clearance tasks exist on the Condition.
        self.assertEqual(cond.clearance_tasks.count(), 0)
        resp = self.client.post(url, {
            'conditions': [cond.pk],
            'assigned_user': self.n_user.pk,
            'start_date': date.strftime(date.today(), '%d/%m/%Y'),
            'description': 'Test clearance',
            'email_user': True,
        })
        # Response should be a redirect.
        self.assertEqual(resp.status_code, 302)
        # Test that a clearance task now exists on the Condition.
        self.assertEqual(cond.clearance_tasks.count(), 1)

    def test_create_task(self):
        """Test POST request to create a new task on a referral
        """
        url = reverse('referral_create_child', kwargs={'pk': self.ref.pk, 'model': 'task'})
        init_tasks = self.ref.task_set.count()
        resp = self.client.post(url, {
            'assigned_user': self.n_user.pk,
            'type': TaskType.objects.first().pk,
            'start_date': date.strftime(date.today(), '%d/%m/%Y'),
            'due_date': date.strftime(date.today() + timedelta(days=30), '%d/%m/%Y'),
            'description': 'Test clearance',
            'email_user': True,
        })
        # Response should be a redirect.
        self.assertEqual(resp.status_code, 302)
        # Test that a new task now exists on the referral.
        self.assertTrue(self.ref.task_set.count() > init_tasks)

    def test_create_record(self):
        """Test POST request to create a new record on a referral
        """
        url = reverse('referral_create_child', kwargs={'pk': self.ref.pk, 'model': 'record'})
        init_records = self.ref.record_set.count()
        resp = self.client.post(url, {
            'name': 'Test record',
            'infobase_id': 'test',
        })
        # Response should be a redirect.
        self.assertEqual(resp.status_code, 302)
        # Test that a new record now exists on the referral.
        self.assertTrue(self.ref.record_set.count() > init_records)

    def test_create_note(self):
        """Test POST request to create a new note on a referral
        """
        url = reverse('referral_create_child', kwargs={'pk': self.ref.pk, 'model': 'note'})
        init_notes = self.ref.note_set.count()
        resp = self.client.post(url, {'note_html': '<p>Test note</p>'})
        # Response should be a redirect.
        self.assertEqual(resp.status_code, 302)
        # Test that a new record now exists on the referral.
        self.assertTrue(self.ref.note_set.count() > init_notes)

    def test_create_condition(self):
        """Test POST request to create a new condition on a referral
        """
        url = reverse('referral_create_child', kwargs={'pk': self.ref.pk, 'model': 'condition'})
        init_conditions = self.ref.condition_set.count()
        resp = self.client.post(url, {'proposed_condition_html': '<p>Test condition</p>'})
        # Response should be a redirect.
        self.assertEqual(resp.status_code, 302)
        # Test that a new record now exists on the referral.
        self.assertTrue(self.ref.condition_set.count() > init_conditions)

    def test_relate_existing_object_to_task(self):
        """Test POST to relate existing note/record to a task
        """
        # First, ensure that a task, record and note all exist.
        task = mixer.blend(Task, referral=self.ref)
        note = mixer.blend(Note, referral=self.ref)
        record = mixer.blend(Record, referral=self.ref)
        init_records = task.records.count()
        init_notes = task.notes.count()
        url = reverse('referral_create_child_related', kwargs={
            'pk': self.ref.pk,
            'model': 'task',
            'id': task.pk,
            'type': 'addrecord'})
        resp = self.client.post(url, {'records': [record.pk]})
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(task.records.count() > init_records)
        url = reverse('referral_create_child_related', kwargs={
            'pk': self.ref.pk,
            'model': 'task',
            'id': task.pk,
            'type': 'addnote'})
        resp = self.client.post(url, {'notes': [note.pk]})
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(task.notes.count() > init_notes)

    def test_relate_new_object_to_task(self):
        """Test POST to relate new note/record to a task
        """
        task = mixer.blend(Task, referral=self.ref)
        init_records = task.records.count()
        init_notes = task.notes.count()
        url = reverse('referral_create_child_related', kwargs={
            'pk': self.ref.pk,
            'model': 'task',
            'id': task.pk,
            'type': 'addnewrecord'})
        resp = self.client.post(url, {
            'name': 'Test record',
            'infobase_id': 'test',
        })
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(task.records.count() > init_records)
        url = reverse('referral_create_child_related', kwargs={
            'pk': self.ref.pk,
            'model': 'task',
            'id': task.pk,
            'type': 'addnewnote'})
        resp = self.client.post(url, {'note_html': '<p>Test note</p>'})
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(task.notes.count() > init_notes)


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
        ref = Referral.objects.first()
        url = reverse('referral_location_create', kwargs={'pk': ref.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200, 'Location create view failed: {0}'.format(url))
        self.assertTemplateUsed(response, 'referral/location_create.html')

    def test_cancel(self):
        """Test that cancelling the referral update view redirects correctly
        """
        ref = Referral.objects.first()
        url = reverse('referral_location_create', kwargs={'pk': ref.pk})
        response = self.client.post(url, {'cancel': 'Cancel'})
        self.assertRedirects(response, ref.get_absolute_url())

    def test_post(self):
        """Test POST request for the create location view.
        """
        ref = Referral.objects.first()
        url = reverse('referral_location_create', kwargs={'pk': ref.pk})
        init_locs = ref.location_set.count()
        resp = self.client.post(url, {
            'form-1-address_no': '1',
            'form-1-address_suffix': 'A',
            'form-1-road_name': 'TEST',
            'form-1-road_suffix': 'STREET',
            'form-1-locality': 'SUBURB',
            'form-1-postcode': '1111',
            'form-1-wkt': 'POLYGON ((0 0, 0 50, 50 50, 50 0, 0 0))',
        })
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(ref.location_set.count() > init_locs)


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
        self.tag = Tag.objects.create(name='Test Tag')

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
        ref = Referral.objects.first()
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
        self.tag = Tag.objects.create(name='Test Tag')
        # Tag one referral only.
        self.ref_tagged = Referral.objects.first()
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
        self.task = Task.objects.first()

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

    def test_cant_complete_task_without_location(self):
        """Test rule that some tasks can't be completed without a location on the referral
        """
        # First, ensure that the parent referral is a specific type.
        self.task.referral.type = ReferralType.objects.get(name='Subdivision')
        self.task.referral.save()
        # Ensure that no locations exist on the parent referral.
        for l in self.task.referral.location_set.all():
            l.delete()
        url = reverse('task_action', kwargs={'pk': self.task.pk, 'action': 'complete'})
        response = self.client.get(url)
        # Response should be a redirect to the task URL.
        self.assertRedirects(response, self.task.get_absolute_url())


class ReferralRelateTest(PrsViewsTestCase):
    """Test view for relating a referral to another referral
    """
    def setUp(self):
        super(ReferralRelateTest, self).setUp()
        [self.ref1, self.ref2] = Referral.objects.all()[:2]

    def test_get(self):
        """Test GET for the referral_relate view
        """
        url = reverse('referral_relate', kwargs={'pk': self.ref1.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'referral/referral_relate.html')

    def test_post_create(self):
        """Test post for the referral_relate create view
        """
        # First, prove that a relationship does not exist.
        self.assertTrue(self.ref2 not in self.ref1.related_refs.all())
        url = reverse('referral_relate', kwargs={'pk': self.ref1.pk})
        # NOTE: setting the ``data`` dict in the post below form-encodes the parameters.
        # We need them as query params instead, so manually build the query.
        url += '?ref_pk={}&create=true'.format(self.ref2.pk)
        response = self.client.post(url, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.ref2 in self.ref1.related_refs.all())

    def test_post_delete(self):
        """Test post for the referral_relate delete view
        """
        # First, prove that a relationship exists.
        self.ref1.add_relationship(self.ref2)
        self.assertTrue(self.ref2 in self.ref1.related_refs.all())
        url = reverse('referral_relate', kwargs={'pk': self.ref1.pk})
        # NOTE: setting the ``data`` dict in the post below form-encodes the parameters.
        # We need them as query params instead, so manually build the query.
        url += '?ref_pk={}&delete=true'.format(self.ref2.pk)
        response = self.client.post(url, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.ref2 not in self.ref1.related_refs.all())


class OverdueEmailTest(PrsViewsTestCase):
    """Test view for sending emails about overdue tasks.
    """
    def test_get(self):
        """Test GET for the overdue tasks email view
        """
        # Ensure that an incomplete Task is overdue.
        for i in Task.objects.all():
            i.due_date = date.today() - timedelta(days=1)
            i.save()
            state = i.state
            state.is_ongoing = True
            state.save()
        url = reverse('overdue_tasks_email')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)


class InfobaseShortcutTest(PrsViewsTestCase):

    def test_get_no_id(self):
        """Test GET for the Infobase shortcut view with no ID
        """
        for i in Record.objects.all():
            i.infobase_id = None
            i.save()
            url = reverse('infobase_shortcut', kwargs={'pk': i.pk})
            response = self.client.get(url)
            # View response shoud be 302 redirect.
            self.assertEqual(response.status_code, 302)

    def test_get_with_id(self):
        """Test GET for the Infobase shortcut view with an ID
        """
        for i in Record.objects.all():
            i.infobase_id = str(uuid.uuid4())[:8]
            i.save()
            url = reverse('infobase_shortcut', kwargs={'pk': i.pk})
            response = self.client.get(url)
            # View response shoud be file.
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get('Content-Type'), 'application/octet-stream')
            self.assertEqual(response.content, i.infobase_id)

import json
import uuid
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Polygon
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse
from mixer.backend.django import mixer
from referral.models import (
    Bookmark,
    Clearance,
    Condition,
    DopTrigger,
    Location,
    Note,
    Organisation,
    Record,
    Referral,
    ReferralType,
    Region,
    Task,
    TaskType,
)
from referral.test_models import PrsTestCase
from taggit.models import Tag

User = get_user_model()


class PrsViewsTestCase(PrsTestCase):
    models = [
        Organisation,
        Referral,
        Task,
        Record,
        Note,
        Condition,
        Location,
        Clearance,
        Bookmark,
    ]
    client = Client()

    def setUp(self):
        super(PrsViewsTestCase, self).setUp()
        # Log in normaluser by default.
        self.client.login(username="normaluser", password="pass")


class SiteAuthViewsTest(PrsViewsTestCase):
    """Test the site login/login views."""

    def test_login(self):
        """Test login view responds to GET"""
        url = reverse("login")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "login.html")

    def test_logout(self):
        """Test logout view responds to POST"""
        url = reverse("logout")
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "logged_out.html")


class BaseViewTest(PrsViewsTestCase):
    """Test the generic object list view."""

    def setUp(self):
        super(BaseViewTest, self).setUp()
        # Generate enough objects to paginate list views.
        mixer.cycle(25).blend(
            Referral,
            type=mixer.SELECT,
            agency=mixer.SELECT,
            referring_org=mixer.SELECT,
            referral_date=date.today(),
            search_vector=None,
        )
        mixer.cycle(25).blend(Task, type=mixer.SELECT, referral=mixer.SELECT, state=mixer.SELECT, search_vector=None)
        mixer.cycle(25).blend(Note, referral=mixer.SELECT, type=mixer.SELECT, note=mixer.RANDOM, search_vector=None)
        mixer.cycle(25).blend(Record, referral=mixer.SELECT, search_vector=None)
        mixer.cycle(25).blend(
            Condition,
            referral=mixer.SELECT,
            category=mixer.SELECT,
            condition=mixer.RANDOM,
            model_condition=mixer.SELECT,
            proposed_condition=mixer.RANDOM,
            search_vector=None,
        )
        mixer.cycle(25).blend(Clearance, condition=mixer.SELECT, task=mixer.SELECT)
        mixer.cycle(25).blend(Location, referral=mixer.SELECT)

    def test_get(self):
        """Test prs_object_list view for each model type"""
        for i in self.models:
            url = reverse("prs_object_list", kwargs={"model": i._meta.object_name.lower()})
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 200)
            self.assertTemplateUsed(resp, "referral/prs_object_list.html")
            # Also test with a view with a query string.
            resp = self.client.get(f"{url}?q=foo+bar")
            self.assertEqual(resp.status_code, 200)

    def test_nonsense_model(self):
        """Test an attempt to reverse the list view for a non-existent model."""
        url = reverse("prs_object_list", kwargs={"model": "foobar"})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 400)  # Returns a HTTP 400 error.


class SiteHomeTest(PrsViewsTestCase):
    """Test the SiteHome view."""

    def test_homepage(self):
        """Test that site homepage view contains required elements"""
        # Ensure normaluser has a task assigned.
        task = Task.objects.first()
        task.assigned_user = self.n_user
        task.save()
        url = reverse("site_home")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "site_home.html")
        self.assertContains(resp, "ONGOING TASKS")
        self.assertContains(resp, reverse("site_home_print"))

    def test_homepage_admin(self):
        """Test that the navbar only renders the admin link for superusers"""
        url = reverse("site_home")
        resp = self.client.get(url)
        link = b'href="/admin/"'
        self.assertIs(resp.content.find(link), -1)
        # Log in as admin user
        self.client.logout()
        self.client.login(username="admin", password="pass")
        resp = self.client.get(url)
        self.assertIsNot(resp.content.find(link), -1)

    def test_homepage_printable(self):
        """Test that the site printable homepage uses the correct template"""
        url = reverse("site_home_print")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "site_home_print.html")

    def test_stopped_tasks(self):
        """Test the 'stopped tasks' homepage view"""
        url = reverse("stopped_tasks_list")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "site_home.html")
        self.assertContains(resp, "STOPPED TASKS")


class HelpPageTest(PrsViewsTestCase):
    def test_help_page(self):
        """Test that the site help page renders"""
        url = reverse("help_page")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "help_page.html")
        self.assertContains(resp, "HELP")


class GeneralSearchTest(PrsViewsTestCase):
    def test_general_search(self):
        """Test that the general search page renders"""
        url = reverse("prs_index_search_combined")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "referral/prs_index_search_combined.html")


class ReferralDetailTest(PrsViewsTestCase):
    """Test the referral detail view."""

    def setUp(self):
        super(ReferralDetailTest, self).setUp()
        self.ref = Referral.objects.first()

    def test_get(self):
        """Test that the referral detail page renders"""
        url = self.ref.get_absolute_url()
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "referral/referral_detail.html")

    def test_related(self):
        """Test that each of the referral related object types render"""
        for m in ["tasks", "notes", "records", "locations", "conditions"]:
            url = reverse("referral_detail", kwargs={"pk": self.ref.pk, "related_model": m})
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 200)

    def test_print_notes(self):
        """Test that the referral notes printable view renders"""
        url = reverse("referral_detail", kwargs={"pk": self.ref.pk})
        resp = self.client.get(f"{url}?print=notes")
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "referral/referral_notes_print.html")

    def test_referral_history(self):
        """Test that the referral history view renders"""
        url = reverse("prs_object_history", kwargs={"model": "referral", "pk": self.ref.pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "referral/prs_object_history.html")

    def test_referral_location_download(self):
        """Test that the referral with locations can return spatial data"""
        loc = Location.objects.first()
        loc.referral = self.ref
        loc.poly = Polygon(((0.0, 0.0), (0.0, 50.0), (50.0, 50.0), (50.0, 0.0), (0.0, 0.0)))
        loc.save()
        url = reverse("referral_location_download", kwargs={"pk": self.ref.pk})
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["content-type"], "application/geo+json")
        url = reverse("referral_location_download", kwargs={"pk": self.ref.pk})
        r = self.client.get(f"{url}?format=gpkg")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["content-type"], "application/x-sqlite3")

    def test_referral_deleted_redirect(self):
        """Test that the detail page for a deleted referral redirects to home"""
        url = self.ref.get_absolute_url()
        self.ref.delete()
        r = self.client.get(url)
        self.assertEqual(r.status_code, 302)
        self.assertRedirects(r, reverse("site_home"))

    def test_referral_bookmarked(self):
        """Test the referral detail page renders differently if bookmarked"""
        url = self.ref.get_absolute_url()
        resp = self.client.get(url)
        self.assertContains(resp, "Bookmark this referral")
        # Bookmark the referral.
        Bookmark.objects.create(referral=self.ref, user=self.n_user)
        resp = self.client.get(url)
        self.assertContains(resp, "Remove bookmark")


class ReferralCreateTest(PrsViewsTestCase):
    """Test the customised referral create view."""

    def setUp(self):
        super(ReferralCreateTest, self).setUp()
        self.org = Organisation.objects.get(slug="wapc")
        self.task_type = TaskType.objects.get(name="Assess a referral")
        self.ref_type = ReferralType.objects.get(name="Subdivision")
        self.url = reverse("referral_create")

    def test_get(self):
        """Test that the referral create view renders"""
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "referral/referral_create.html")

    def test_cancel(self):
        """Test the cancelling the referral create view redirects to home"""
        resp = self.client.post(self.url, {"cancel": "Cancel"})
        self.assertEqual(resp.status_code, 302)
        self.assertRedirects(resp, reverse("site_home"))

    def test_post(self):
        """Test referral creation form submit"""
        resp = self.client.post(
            self.url,
            {
                "referring_org": self.org.pk,
                "reference": "Test reference 1",
                "description": "Test description 1",
                "referral_date": "21/12/2022",
                "type": self.ref_type.pk,
                "task_type": self.task_type.pk,
                "assigned_user": self.n_user.pk,
                "regions": [Region.objects.first().pk],
                "dop_triggers": [DopTrigger.objects.first().pk],
                "save": "Save",
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(Referral.objects.filter(reference="Test reference 1").exists())

    def test_post_email(self):
        """Test referral creation form submit with email checked"""
        resp = self.client.post(
            self.url,
            {
                "referring_org": self.org.pk,
                "reference": "Test reference 2",
                "description": "Test description 2",
                "referral_date": "21/12/2022",
                "due_date": "30/12/2022",
                "type": self.ref_type.pk,
                "task_type": self.task_type.pk,
                "assigned_user": self.n_user.pk,
                "regions": [Region.objects.first().pk],
                "dop_triggers": [DopTrigger.objects.first().pk],
                "email_user": True,
                "save": "Save",
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(Referral.objects.filter(reference="Test reference 2").exists())


class ReferralUpdateTest(PrsViewsTestCase):
    """Test the generic object update view."""

    def setUp(self):
        super(ReferralUpdateTest, self).setUp()
        self.ref = Referral.objects.first()
        self.url = reverse("prs_object_update", kwargs={"model": "referral", "pk": self.ref.pk})

    def test_get(self):
        """Test the referral update view"""
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "referral/change_form.html")

    def test_cancel(self):
        """Test that cancelling the referral update view redirects correctly"""
        resp = self.client.post(self.url, {"cancel": "Cancel"})
        self.assertRedirects(resp, self.ref.get_absolute_url())

    def test_post(self):
        """Test that updating a referral actually changes it"""
        # Use referral type without avoid additional form validation.
        ref_type = ReferralType.objects.get(slug="clearing-permit-dwer")
        resp = self.client.post(
            self.url,
            {
                "referring_org": self.ref.referring_org.pk,
                "reference": "New reference value",
                "referral_date": "21/12/2022",
                "type": ref_type.pk,
                "regions": [Region.objects.first().pk],
                "save": "Save",
            },
        )
        self.assertRedirects(resp, self.ref.get_absolute_url())
        self.assertTrue(Referral.objects.filter(reference="New reference value").exists())


class ReferralCreateChildTest(PrsViewsTestCase):
    """Test views related to creating child objects on a referral"""

    def setUp(self):
        super(ReferralCreateChildTest, self).setUp()
        self.ref = Referral.objects.first()
        # Ensure that conditions with 'approved' text exist on the referral.
        mixer.cycle(3).blend(
            Condition,
            referral=self.ref,
            category=mixer.SELECT,
            condition=mixer.RANDOM,
            model_condition=mixer.SELECT,
            proposed_condition=mixer.RANDOM,
            search_vector=None,
        )
        for i in Condition.objects.filter(referral=self.ref):
            i.proposed_condition_html = "<p>Proposed condition</p>"
            i.condition_html = "<p>Actual condition</p>"
            i.save()

    def test_create_get(self):
        """Test GET request for each of: task, record, note, condition"""
        for i in ["task", "record", "note", "condition"]:
            url = reverse("referral_create_child", kwargs={"pk": self.ref.pk, "model": i})
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200)

    def test_cancel(self):
        """Test that cancelling the create view redirects correctly"""
        for i in ["task", "record", "note", "condition"]:
            url = reverse("referral_create_child", kwargs={"pk": self.ref.pk, "model": i})
            resp = self.client.post(url, {"cancel": "Cancel"})
            self.assertRedirects(resp, self.ref.get_absolute_url())

    def test_create_related_get(self):
        """Test GET for relating 'child' objects together"""
        # Relate existing record to note
        n = Note.objects.first()
        url = reverse(
            "referral_create_child_related",
            kwargs={
                "pk": self.ref.pk,
                "model": "note",
                "id": n.pk,
                "type": "addrecord",
            },
        )
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        # Create new record on note
        url = reverse(
            "referral_create_child_related",
            kwargs={
                "pk": self.ref.pk,
                "model": "note",
                "id": n.pk,
                "type": "addnewrecord",
            },
        )
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        # Relate existing note to record
        rec = Record.objects.first()
        url = reverse(
            "referral_create_child_related",
            kwargs={
                "pk": self.ref.pk,
                "model": "record",
                "id": rec.pk,
                "type": "addnote",
            },
        )
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        # Create new note on record
        url = reverse(
            "referral_create_child_related",
            kwargs={
                "pk": self.ref.pk,
                "model": "record",
                "id": rec.pk,
                "type": "addnewnote",
            },
        )
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

    def test_create_clearance_redirect(self):
        """Test redirect where no approved conditions on the referral"""
        # Delete any existing conditions on the referral.
        for i in Condition.objects.filter(referral=self.ref):
            i.delete()
        url = reverse(
            "referral_create_child_type",
            kwargs={"pk": self.ref.pk, "model": "task", "type": "clearance"},
        )
        r = self.client.get(url)
        self.assertEqual(r.status_code, 302)

    def test_create_child_type(self):
        """Test GET for creating a child object of defined type (clearance)"""
        url = reverse(
            "referral_create_child_type",
            kwargs={"pk": self.ref.pk, "model": "task", "type": "clearance"},
        )
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

    def test_create_clearance_request(self):
        """Test POST request for creating a clearance request on a referral"""
        url = reverse(
            "referral_create_child_type",
            kwargs={"pk": self.ref.pk, "model": "task", "type": "clearance"},
        )
        cond = Condition.objects.filter(referral=self.ref).first()
        # Test that no clearance tasks exist on the Condition.
        self.assertEqual(cond.clearance_tasks.count(), 0)
        resp = self.client.post(
            url,
            {
                "conditions": [cond.pk],
                "assigned_user": self.n_user.pk,
                "start_date": date.strftime(date.today(), "%d/%m/%Y"),
                "description": "Test clearance",
                "email_user": True,
            },
        )
        # Response should be a redirect.
        self.assertEqual(resp.status_code, 302)
        # Test that a clearance task now exists on the Condition.
        self.assertEqual(cond.clearance_tasks.count(), 1)

    def test_create_task(self):
        """Test POST request to create a new task on a referral"""
        url = reverse("referral_create_child", kwargs={"pk": self.ref.pk, "model": "task"})
        init_tasks = self.ref.task_set.count()
        resp = self.client.post(
            url,
            {
                "assigned_user": self.n_user.pk,
                "type": TaskType.objects.first().pk,
                "start_date": date.strftime(date.today(), "%d/%m/%Y"),
                "due_date": date.strftime(date.today() + timedelta(days=30), "%d/%m/%Y"),
                "description": "Test clearance",
                "email_user": True,
            },
        )
        # Response should be a redirect.
        self.assertEqual(resp.status_code, 302)
        # Test that a new task now exists on the referral.
        self.assertTrue(self.ref.task_set.count() > init_tasks)

    def test_create_record(self):
        """Test POST request to create a new record on a referral"""
        url = reverse("referral_create_child", kwargs={"pk": self.ref.pk, "model": "record"})
        init_records = self.ref.record_set.count()
        resp = self.client.post(
            url,
            {
                "name": "Test record",
                "infobase_id": "test",
            },
        )
        # Response should be a redirect.
        self.assertEqual(resp.status_code, 302)
        # Test that a new record now exists on the referral.
        self.assertTrue(self.ref.record_set.count() > init_records)

    def test_create_note(self):
        """Test POST request to create a new note on a referral"""
        # The text below contains character(s) that have caused issues before.
        note_html = """<div><p>Hello Paul</p>\r\n<p>I refer to your email below
        and your request for clearance of conditions for WAPC 12345 Goodwood
        Estate Stage 2.</p>\r\n<p> </p>\r\n<p>The attached email dated 16 August
        2016 advised that a copy of the Deposited Plan was required for clearance
        stamping purposes and also requested a copy of the <u>signed </u>documentation
        for declared rare flora notification on titles when it is has been
        finalised.</p>\r\n<p> </p>\r\n<p>Can you please forward a copy of the
        draft deposited plan and the <u>signed </u>DRF notification documentation.
        </p>\r\n<p> </p>\r\n<p>In addition, can you advise when clearing of native
        vegetation for the subdivision works and building envelope locations is
        expected to be undertaken.</p>\r\n<p>Regards</p>\r\n<p>Joe Smith</p>\r\n
        <p><em>Planning Officer (Land Use)</em></p>\r\n<p><em>Department of Parks
        and Wildlife</em></p>\r\n<p><em>South West Region</em></p>\r\n<p> </p>\r\n
        <p><strong>From:</strong> John Snow [
        <a href="mailto:john.snow@environmental.com.au">
        mailto:john.snow@environmental.com.au</a>]
        <br> <strong>Sent:</strong> Wednesday, 7 September 2016 1:30 PM<br>
        <strong>To:</strong> Smith, Joe<br> <strong>Subject:</strong> RE: John Snow
        shared "MPL12345 R001 Rev 2.pdf" with you</p>\r\n<p> </p>\r\n
        <p>Hi Joe</p>\r\n<p>Just following up on the clearance of the remaining
        conditions.  Did the additional information supplied recently meet the
        Department\u2019s requirements?</p>\r\n<p>Regards</p>\r\n<p>John</p>\r\n
        </div>"""
        url = reverse("referral_create_child", kwargs={"pk": self.ref.pk, "model": "note"})
        initial_count = self.ref.note_set.count()
        resp = self.client.post(url, {"note_html": note_html})
        # Response should be a redirect.
        self.assertEqual(resp.status_code, 302)
        # Test that a new record now exists on the referral.
        self.assertTrue(self.ref.note_set.count() > initial_count)

    def test_create_condition(self):
        """Test POST request to create a new condition on a referral"""
        url = reverse("referral_create_child", kwargs={"pk": self.ref.pk, "model": "condition"})
        initial_count = self.ref.condition_set.count()
        resp = self.client.post(url, {"proposed_condition_html": "<p>Test condition</p>"})
        # Response should be a redirect.
        self.assertEqual(resp.status_code, 302)
        # Test that a new record now exists on the referral.
        self.assertTrue(self.ref.condition_set.count() > initial_count)

    def test_relate_existing_object_to_task(self):
        """Test POST to relate existing note/record to a task"""
        # First, ensure that a task, record and note all exist.
        task = mixer.blend(Task, referral=self.ref, search_vector=None)
        note = mixer.blend(Note, referral=self.ref, search_vector=None)
        record = mixer.blend(Record, referral=self.ref, search_vector=None)
        init_records = task.records.count()
        init_notes = task.notes.count()
        url = reverse(
            "referral_create_child_related",
            kwargs={
                "pk": self.ref.pk,
                "model": "task",
                "id": task.pk,
                "type": "addrecord",
            },
        )
        resp = self.client.post(url, {"records": [record.pk]})
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(task.records.count() > init_records)
        url = reverse(
            "referral_create_child_related",
            kwargs={
                "pk": self.ref.pk,
                "model": "task",
                "id": task.pk,
                "type": "addnote",
            },
        )
        resp = self.client.post(url, {"notes": [note.pk]})
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(task.notes.count() > init_notes)

    def test_relate_new_object_to_task(self):
        """Test POST to relate new note/record to a task"""
        task = mixer.blend(Task, referral=self.ref, search_vector=None)
        init_records = task.records.count()
        init_notes = task.notes.count()
        url = reverse(
            "referral_create_child_related",
            kwargs={
                "pk": self.ref.pk,
                "model": "task",
                "id": task.pk,
                "type": "addnewrecord",
            },
        )
        resp = self.client.post(
            url,
            {
                "name": "Test record",
                "infobase_id": "test",
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(task.records.count() > init_records)
        url = reverse(
            "referral_create_child_related",
            kwargs={
                "pk": self.ref.pk,
                "model": "task",
                "id": task.pk,
                "type": "addnewnote",
            },
        )
        resp = self.client.post(url, {"note_html": "<p>Test note</p>"})
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(task.notes.count() > init_notes)


class ReferralRecentTest(PrsViewsTestCase):
    """Test the custom 'recent referrals' view."""

    def test_get(self):
        url = reverse("referral_recent")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "referral/referral_recent.html")
        self.assertContains(resp, "RECENTLY OPENED REFERRALS")


class LocationCreateTest(PrsViewsTestCase):
    """Test the custom LocationCreate view.
    TODO: test a POST request.
    """

    def test_get(self):
        """Test the location_create view"""
        ref = Referral.objects.first()
        url = reverse("referral_location_create", kwargs={"pk": ref.pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200, f"Location create view failed: {url}")
        self.assertTemplateUsed(resp, "referral/location_create.html")

    def test_cancel(self):
        """Test that cancelling the referral update view redirects correctly"""
        ref = Referral.objects.first()
        url = reverse("referral_location_create", kwargs={"pk": ref.pk})
        resp = self.client.post(url, {"cancel": "Cancel"})
        self.assertRedirects(resp, ref.get_absolute_url())

    def test_post(self):
        """Test POST request for the create location view."""
        ref = Referral.objects.first()
        url = reverse("referral_location_create", kwargs={"pk": ref.pk})
        init_locs = ref.location_set.count()
        resp = self.client.post(
            url,
            {
                "form-1-address_no": "1",
                "form-1-address_suffix": "A",
                "form-1-road_name": "TEST",
                "form-1-road_suffix": "STREET",
                "form-1-locality": "SUBURB",
                "form-1-postcode": "1111",
                "form-1-wkt": "POLYGON ((0 0, 0 50, 50 50, 50 0, 0 0))",
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(ref.location_set.count() > init_locs)


class PrsObjectDeleteTest(PrsViewsTestCase):
    """
    Test the generic object delete view.
    """

    models = [Referral, Task, Record, Note, Condition, Location]

    def test_get(self):
        """Test the GET method of the generic delete view"""
        for model in self.models:
            for i in model.objects.all():
                url = reverse(
                    "prs_object_delete",
                    kwargs={"model": i._meta.object_name.lower(), "pk": i.pk},
                )
                resp = self.client.get(url)
                self.assertEqual(resp.status_code, 200)
                self.assertContains(resp, i.as_tbody())
                self.assertTemplateUsed(resp, "referral/prs_object_delete.html")

    def test_post(self):
        """Test the POST method of the generic delete view"""
        for model in self.models:
            for obj in model.objects.all():
                # Child objects of referrals should redirect to the referral's URL.
                if hasattr(obj, "referral"):
                    next_url = obj.referral.get_absolute_url()
                else:
                    next_url = reverse("site_home")
                url = reverse(
                    "prs_object_delete",
                    kwargs={"model": obj._meta.object_name.lower(), "pk": obj.pk},
                )
                self.client.post(url, {"delete": "Delete", "next": next_url}, follow=True)
                # Test that the current() queryset does not contain this object.
                self.assertNotIn(obj.pk, [i.pk for i in model.objects.current()])


class PrsObjectTagTest(PrsViewsTestCase):
    models = [Referral, Condition]

    def setUp(self):
        super(PrsObjectTagTest, self).setUp()
        self.tag = Tag.objects.create(name="Test Tag")

    def test_get(self):
        """Test that a GET request to this view returns a 405."""
        for model in self.models:
            for obj in model.objects.all():
                url = reverse(
                    "prs_object_tag",
                    kwargs={"model": obj._meta.object_name.lower(), "pk": obj.pk},
                )
                resp = self.client.get(url)
                self.assertEqual(resp.status_code, 405)

    def test_post_create(self):
        """Test a POST request to create a tag on an object."""
        for model in self.models:
            for obj in model.objects.all():
                url = reverse(
                    "prs_object_tag",
                    kwargs={"model": obj._meta.object_name.lower(), "pk": obj.pk},
                )
                resp = self.client.post(url, {"tag": self.tag.name})
                self.assertEqual(resp.status_code, 200)
                self.assertTrue(self.tag in obj.tags.all())

    def test_post_delete(self):
        """Test a POST request to delete a tag on an object."""
        for model in self.models:
            for obj in model.objects.all():
                obj.tags.add(self.tag)
                self.assertTrue(self.tag in obj.tags.all())
                url = reverse(
                    "prs_object_tag",
                    kwargs={"model": obj._meta.object_name.lower(), "pk": obj.pk},
                )
                resp = self.client.post(url, {"tag": self.tag.name, "delete": ""})
                self.assertEqual(resp.status_code, 200)
                self.assertFalse(self.tag in obj.tags.all())

    def test_post_faulty(self):
        """Test a faulty POST request to create a tag (missing tag parameter)"""
        for model in self.models:
            for obj in model.objects.all():
                url = reverse(
                    "prs_object_tag",
                    kwargs={"model": obj._meta.object_name.lower(), "pk": obj.pk},
                )
                resp = self.client.post(url)
                self.assertEqual(resp.status_code, 400)


class TagListTest(PrsViewsTestCase):
    def setUp(self):
        super(TagListTest, self).setUp()
        # Create a bunch of additional Tags.
        tags = (tag for tag in ["tag1", "tag2", "tag3", "tag4", "tag5"])
        for _ in range(5):
            mixer.blend(Tag, name=tags)

    def test_get(self):
        """Test that the rendered response contains text of all tags"""
        url = reverse("tag_list")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        for tag in Tag.objects.all():
            self.assertContains(resp, tag.name)

    def test_get_json(self):
        """Test that a request for tags as JSON data returns correctly"""
        url = reverse("tag_list")
        resp = self.client.get(url, data={"json": "true"})
        self.assertEqual(resp.get("Content-Type"), "application/json")

    def test_post(self):
        """Test that POST requests are not allowed"""
        url = reverse("tag_list")
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 405)


class ReferralTaggedTest(PrsViewsTestCase):
    def setUp(self):
        super(ReferralTaggedTest, self).setUp()
        self.tag = Tag.objects.create(name="Test Tag")
        # Tag one referral only.
        self.ref_tagged = Referral.objects.first()
        self.ref_tagged.tags.add(self.tag)
        self.ref_untagged = Referral.objects.exclude(pk=self.ref_tagged.pk)[0]

    def test_get(self):
        """Test that a tagged referral is present in the referral_tagged view context"""
        url = reverse("referral_tagged", kwargs={"slug": self.tag.slug})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(self.ref_tagged in resp.context["object_list"])
        self.assertFalse(self.ref_untagged in resp.context["object_list"])


class TaskActionTest(PrsViewsTestCase):
    def setUp(self):
        super(TaskActionTest, self).setUp()
        self.task = Task.objects.first()

    def test_get_update(self):
        """Test the Task update view responds"""
        url = reverse("task_action", kwargs={"pk": self.task.pk, "action": "update"})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

    def test_can_reassign_incomplete_task(self):
        """ """
        url = reverse("task_action", kwargs={"pk": self.task.pk, "action": "reassign"})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

    def test_cant_update_stopped_task(self):
        """Test that a stopped task can't be updated"""
        self.task.stop_date = date.today()
        self.task.save()
        url = reverse("task_action", kwargs={"pk": self.task.pk, "action": "update"})
        resp = self.client.get(url)
        # Response should be a redirect to the object URL.
        self.assertRedirects(resp, self.task.get_absolute_url())
        # Test that the redirected response contains an error message.
        resp = self.client.get(url, follow=True)
        messages = resp.context["messages"]._get()[0]
        self.assertIsNot(messages[0].message.find("You can't edit a stopped task"), -1)

    def test_cant_stop_completed_task(self):
        """Test that a completed task can't be stopped"""
        self.task.complete_date = date.today()
        self.task.save()
        url = reverse("task_action", kwargs={"pk": self.task.pk, "action": "stop"})
        resp = self.client.get(url)
        # Response should be a redirect to the object URL.
        self.assertRedirects(resp, self.task.get_absolute_url())
        # Test that the redirected response contains an error message.
        resp = self.client.get(url, follow=True)
        messages = resp.context["messages"]._get()[0]
        self.assertIsNot(messages[0].message.find("You can't stop a completed task"), -1)

    def test_cant_restart_unstopped_task(self):
        """Test that a non-stopped task can't be started"""
        url = reverse("task_action", kwargs={"pk": self.task.pk, "action": "start"})
        resp = self.client.get(url)
        # Response should be a redirect to the object URL.
        self.assertRedirects(resp, self.task.get_absolute_url())
        # Test that the redirected response contains an error message.
        resp = self.client.get(url, follow=True)
        messages = resp.context["messages"]._get()[0]
        self.assertIsNot(messages[0].message.find("You can't restart a non-stopped task"), -1)

    def test_cant_inherit_owned_task_task(self):
        """Test that you can't inherit a task assigned to you"""
        self.task.assigned_user = self.n_user
        self.task.save()
        url = reverse("task_action", kwargs={"pk": self.task.pk, "action": "inherit"})
        resp = self.client.get(url)
        # Response should be a redirect to the object URL.
        self.assertRedirects(resp, self.task.get_absolute_url())
        # Test that the redirected response contains an error message.
        resp = self.client.get(url, follow=True)
        messages = resp.context["messages"]._get()[0]
        self.assertIsNot(messages[0].message.find("That task is already assigned to you"), -1)

    def test_cant_alter_completed_task(self):
        """Test that a completed task can't be cancelled, reassigned or completed"""
        self.task.complete_date = date.today()
        self.task.save()
        for action in ["cancel", "complete", "reassign"]:
            url = reverse("task_action", kwargs={"pk": self.task.pk, "action": action})
            resp = self.client.get(url)
            # Response should be a redirect to the object URL.
            self.assertRedirects(resp, self.task.get_absolute_url())
            # Test that the redirected response contains an error message.
            resp = self.client.get(url, follow=True)
            messages = resp.context["messages"]._get()[0]
            self.assertIsNot(messages[0].message.find("That task is already completed"), -1)

    def test_cant_add_task_to_task(self):
        """Test that a task can't be added to another task"""
        url = reverse("task_action", kwargs={"pk": self.task.pk, "action": "add"})
        resp = self.client.get(url)
        # Response should be a redirect to the object URL.
        self.assertRedirects(resp, self.task.get_absolute_url())

    def test_cant_complete_task_without_location(self):
        """Test rule that some tasks can't be completed without a location on the referral"""
        for ref_type in [
            "Development application",
            "Subdivision",
            "Clearing Permit - DWER",
        ]:
            # First, ensure that the parent referral is a specific type.
            self.task.referral.type = ReferralType.objects.get(name=ref_type)
            self.task.referral.save()
            # Ensure that no locations exist on the parent referral.
            for loc in self.task.referral.location_set.all():
                loc.delete()
            url = reverse("task_action", kwargs={"pk": self.task.pk, "action": "complete"})
            resp = self.client.get(url)
            # Response should be a redirect to the task URL.
            self.assertRedirects(resp, self.task.get_absolute_url())


class ReferralRelateTest(PrsViewsTestCase):
    """Test view for relating a referral to another referral"""

    def setUp(self):
        super(ReferralRelateTest, self).setUp()
        [self.ref1, self.ref2] = Referral.objects.all()[:2]

    def test_get(self):
        """Test GET for the referral_relate view"""
        url = reverse("referral_relate", kwargs={"pk": self.ref1.pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "referral/referral_relate.html")

    def test_post_create(self):
        """Test post for the referral_relate create view"""
        # First, prove that a relationship does not exist.
        self.assertTrue(self.ref2 not in self.ref1.related_refs.all())
        url = reverse("referral_relate", kwargs={"pk": self.ref1.pk})
        # NOTE: setting the ``data`` dict in the post below form-encodes the parameters.
        # We need them as query params instead, so manually build the query.
        resp = self.client.post(f"{url}?ref_pk={self.ref2.pk}&create=true", follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(self.ref2 in self.ref1.related_refs.all())

    def test_post_delete(self):
        """Test post for the referral_relate delete view"""
        # First, prove that a relationship exists.
        self.ref1.add_relationship(self.ref2)
        self.assertTrue(self.ref2 in self.ref1.related_refs.all())
        url = reverse("referral_relate", kwargs={"pk": self.ref1.pk})
        # NOTE: setting the ``data`` dict in the post below form-encodes the parameters.
        # We need them as query params instead, so manually build the query.
        resp = self.client.post(f"{url}?ref_pk={self.ref2.pk}&delete=true", follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(self.ref2 not in self.ref1.related_refs.all())


class InfobaseShortcutTest(PrsViewsTestCase):
    def test_get_no_id(self):
        """Test GET for the Infobase shortcut view with no ID"""
        for i in Record.objects.all():
            i.infobase_id = None
            i.save()
            url = reverse("infobase_shortcut", kwargs={"pk": i.pk})
            resp = self.client.get(url)
            # View response shoud be 302 redirect.
            self.assertEqual(resp.status_code, 302)

    def test_get_with_id(self):
        """Test GET for the Infobase shortcut view with an ID"""
        for i in Record.objects.all():
            i.infobase_id = str(uuid.uuid4())[:8]
            i.save()
            url = reverse("infobase_shortcut", kwargs={"pk": i.pk})
            resp = self.client.get(url)
            # View response shoud be file.
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.get("Content-Type"), "application/octet-stream")
            # resp.content is a bytestring.
            self.assertEqual(resp.content.decode(), i.infobase_id)


class RecordUploadViewTest(PrsViewsTestCase):
    def test_post(self):
        """Test POST response for an authorised user"""
        referral = Referral.objects.first()
        url = reverse("referral_record_upload", kwargs={"pk": referral.pk})
        f = SimpleUploadedFile("file.txt", b"file_content")
        resp = self.client.post(url, {"file": f})
        self.assertEqual(resp.status_code, 200)
        result = json.loads(resp.content.decode("utf8"))
        self.assertTrue(Record.objects.filter(pk=result["object"]["id"]).exists())

    def test_post_forbidden(self):
        """Test POST response for an unauthorised user"""
        url = reverse("referral_record_upload", kwargs={"pk": Referral.objects.first().pk})
        f = SimpleUploadedFile("file.txt", b"file_content")
        # Log in as read-only user
        self.client.logout()
        self.client.login(username="readonlyuser", password="pass")
        resp = self.client.post(url, {"file": f})
        self.assertEqual(resp.status_code, 403)

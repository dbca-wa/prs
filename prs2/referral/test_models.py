import os
from datetime import date, timedelta
from tempfile import NamedTemporaryFile

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Polygon
from django.core import mail
from django.test import TestCase
from django.urls import reverse
from mixer.backend.django import mixer
from referral.models import (Agency, Bookmark, Clearance, Condition,
                             ConditionCategory, DopTrigger, LocalGovernment,
                             Location, ModelCondition, Note, NoteType,
                             Organisation, OrganisationType, Record, Referral,
                             ReferralType, Region, RelatedReferral, Task,
                             TaskState, TaskType, UserProfile)
from referral.utils import user_referral_history
from taggit.models import Tag

User = get_user_model()


class PrsTestCase(TestCase):
    """Defines setup and teardown common to all PRS test cases.
    """
    fixtures = ['groups.json', 'test-users.json']

    def setUp(self):
        # Need to reset user passwords to enable test db re-use.
        self.admin_user = User.objects.get(username='admin')
        self.admin_user.is_superuser = True
        self.admin_user.set_password('pass')
        self.admin_user.save()
        profile, c = UserProfile.objects.get_or_create(user=self.admin_user)
        self.p_user = User.objects.get(username='poweruser')
        self.p_user.set_password('pass')
        self.p_user.save()
        profile, c = UserProfile.objects.get_or_create(user=self.p_user)
        self.n_user = User.objects.get(username='normaluser')
        self.n_user.set_password('pass')
        self.n_user.save()
        profile, c = UserProfile.objects.get_or_create(user=self.n_user)
        self.ro_user = User.objects.get(username='readonlyuser')
        self.ro_user.set_password('pass')
        self.ro_user.save()
        profile, c = UserProfile.objects.get_or_create(user=self.ro_user)

        # Create some random lookup data
        mixer.cycle(2).blend(DopTrigger)
        mixer.cycle(2).blend(Region)
        mixer.cycle(2).blend(OrganisationType)
        mixer.cycle(2).blend(ConditionCategory)
        mixer.cycle(2).blend(LocalGovernment)
        mixer.blend(
            Organisation, name='Western Australian Planning Commission',
            slug='wapc')
        mixer.cycle(2).blend(Organisation, type=mixer.SELECT)
        # Ensure that required TaskState objects exist.
        mixer.blend(TaskState, name='Stopped')
        mixer.blend(TaskState, name='In progress')
        mixer.blend(TaskState, name='Completed')
        # Ensure that required TaskType objects exist.
        mixer.blend(TaskType, name='Assess a referral')
        mixer.blend(TaskType, name='Conditions clearance request')
        # Ensure that required referral types exists.
        mixer.blend(ReferralType, name='Subdivision', slug='subdivision')
        mixer.blend(
            ReferralType, name='Development application',
            slug='development-application')
        mixer.blend(ReferralType, name='Clearing Permit - DWER', slug='clearing-permit-dwer')
        mixer.cycle(2).blend(ReferralType, initial_task=mixer.SELECT)
        mixer.cycle(2).blend(NoteType)
        mixer.cycle(2).blend(Agency)
        mixer.cycle(2).blend(Tag)

        if not Referral.objects.exists():
            # Create some referral data
            mixer.cycle(2).blend(
                Referral, type=mixer.SELECT, agency=mixer.SELECT,
                referring_org=mixer.SELECT, referral_date=date.today())
            mixer.cycle(2).blend(
                Task, type=mixer.SELECT, referral=mixer.SELECT, state=mixer.SELECT,
                assigned_user=self.n_user)
            mixer.cycle(2).blend(
                Note, referral=mixer.SELECT, type=mixer.SELECT, note=mixer.RANDOM)
            mixer.cycle(2).blend(Record, referral=mixer.SELECT)
            mixer.cycle(2).blend(ModelCondition, category=mixer.SELECT)
            mixer.cycle(2).blend(
                Condition, referral=mixer.SELECT, category=mixer.SELECT,
                condition=mixer.RANDOM, model_condition=mixer.SELECT,
                proposed_condition=mixer.RANDOM)
            mixer.cycle(2).blend(
                Clearance, condition=mixer.SELECT, task=mixer.SELECT)
            mixer.cycle(2).blend(Location, referral=mixer.SELECT)
            # Generate some geometry in one Location.
            loc = Location.objects.first()
            loc.poly = Polygon(((0.0, 0.0), (0.0, 50.0), (50.0, 50.0), (50.0, 0.0), (0.0, 0.0)))
            loc.save()
            mixer.cycle(2).blend(Bookmark, referral=mixer.SELECT, user=mixer.SELECT)


class ReferralLookupModelTest(PrsTestCase):
    """Unit tests for the abstract lookup model class in the referral app.
    Uses DopTrigger model as a proxy for testing.
    """

    def setUp(self):
        super(ReferralLookupModelTest, self).setUp()
        self.obj = DopTrigger.objects.first()

    def test_get_absolute_url(self):
        """Test ReferralLookupModel get_absolute_url() method
        """
        self.assertTrue(self.obj.get_absolute_url())

    def test_as_row(self):
        """Test ReferralLookupModel as_row() method.
        """
        self.assertTrue(self.obj.as_row())
        row = self.obj.as_row()
        # Object name & URL will be in returned output.
        self.assertIsNot(row.find(self.obj.name), -1)
        self.assertIsNot(row.find(self.obj.get_absolute_url()), -1)

    def test_as_tbody(self):
        """Test ReferralLookupModel as_tbody() method.
        """
        self.assertTrue(self.obj.as_tbody())
        tbody = self.obj.as_tbody()
        # Object name will be in returned output.
        self.assertIsNot(tbody.find(self.obj.name), -1)

    def test_manager_methods(self):
        """Test the inherited ReferralLookup manager methods.
        """
        mixer.cycle(2).blend(DopTrigger)  # Some extras.
        obj_del = mixer.blend(DopTrigger)  # One to delete.
        obj_del.delete()
        all_pks = [i.pk for i in DopTrigger.objects.all()]
        current_pks = [i.pk for i in DopTrigger.objects.current()]
        del_pks = [i.pk for i in DopTrigger.objects.deleted()]
        self.assertTrue(obj_del.pk in all_pks)
        self.assertFalse(obj_del.pk in current_pks)
        self.assertTrue(obj_del.pk in del_pks)
        self.assertFalse(self.obj.pk in del_pks)


class ReferralBaseModelTest(PrsTestCase):
    """Unit tests for the abstract base model class in the referral app.
    Uses the Referral model as a proxy for testing.
    """

    def setUp(self):
        super(ReferralBaseModelTest, self).setUp()
        self.obj = Referral.objects.first()

    def test_get_absolute_url(self):
        """Test ReferralBaseModel get_absolute_url() method
        """
        self.assertTrue(self.obj.get_absolute_url())


class OrganisationTest(PrsTestCase):
    """Unit tests specific to the Organisation model class.
    """

    def test_as_tbody(self):
        """Test the Organisation model as_tbody() method
        """
        org = Organisation.objects.first()
        tbody = org.as_tbody()
        # Object name will be in returned output.
        self.assertIsNot(tbody.find(org.name), -1)
        self.assertIsNot(tbody.find('Telephone'), -1)


class ReferralTest(PrsTestCase):
    """Unit tests specific to the Referral model class.
    """

    def test_regions_str(self):
        """Test the Referral model regions_str property.
        """
        for r in Referral.objects.all():
            # Get a random Region and add it to the Referral
            region = Region.objects.order_by('?')[0]
            r.regions.add(region)
            s = r.regions_str
            # String contains the region name.
            self.assertIsNot(s.find(region.name), -1)

    def test_dop_triggers_str(self):
        """Test the Referral model dop_triggers_str property.
        """
        for r in Referral.objects.all():
            # All referrals start with no triggers assigned.
            self.assertIsNone(r.dop_triggers_str)
            # Get a random trigger.
            trigger = DopTrigger.objects.order_by('?')[0]
            r.dop_triggers.add(trigger)
            s = r.dop_triggers_str
            # String contains the trigger name.
            self.assertIsNot(s.find(trigger.name), -1)

    def test_has_location(self):
        """Test the Referral model has_location property
        """
        for r in Referral.objects.all():
            self.assertEqual(r.has_location, r.location_set.current().exists())

    def test_has_condition(self):
        """Test the Referral model has_condition property
        """
        for r in Referral.objects.all():
            self.assertEqual(r.has_condition, r.condition_set.current().exists())

    def test_has_proposed_condition(self):
        """Test the Referral model has_proposed_condition property
        """
        for r in Referral.objects.all():
            result = r.has_condition and any(c.proposed_condition for c in r.condition_set.current())
            self.assertEqual(r.has_proposed_condition, result)

    def test_as_row(self):
        """Test the Referral model as_row() method
        """
        for r in Referral.objects.all():
            row = r.as_row()
            # String contains referral type name.
            self.assertIsNot(row.find(r.type.name), -1)
            # String contains absolute URL.
            self.assertIsNot(row.find(r.get_absolute_url()), -1)

    def test_as_tbody(self):
        """Test the Referral model as_tbody() method
        """
        for r in Referral.objects.all():
            # Get a random Region and add it to the Referral
            region = Region.objects.order_by('?')[0]
            r.regions.add(region)
            body = r.as_tbody()
            # String contains referral type name.
            self.assertIsNot(body.find(r.type.name), -1)
            # String contains the region name.
            self.assertIsNot(body.find(region.name), -1)

    def test_add_relationship(self):
        """Test the Referral model add_relationship() method
        """
        q = Referral.objects.all().order_by('pk')
        ref1, ref2 = q[0], q[1]
        # Referrals start with no relationships.
        self.assertFalse(ref1.related_referrals.all())
        # Test that we can't relate a referral to itself.
        self.assertIsNone(ref1.add_relationship(ref1))
        rel = ref1.add_relationship(ref2)
        self.assertEqual(rel.to_referral, ref2)
        self.assertEqual(rel.from_referral, ref1)
        self.assertEqual(ref1.related_referrals.count(), 1)

    def test_remove_relationship(self):
        """Test the Referral model remove_relationship() method
        """
        q = Referral.objects.all().order_by('pk')
        ref1, ref2 = q[0], q[1]
        ref1.add_relationship(ref2)
        # The remove_relationship method returns True.
        self.assertTrue(ref1.remove_relationship(ref2))
        self.assertEqual(ref1.related_referrals.count(), 0)
        # Trying remove_relationship a second time returns False.
        self.assertFalse(ref1.remove_relationship(ref2))

    def test_generate_qgis_layer(self):
        """Test the Referral model generate_qgis_layer() method
        """
        for r in Referral.objects.all():
            if r.location_set.current().filter(poly__isnull=False).exists():
                # The method will return a unicode string.
                self.assertTrue(r.generate_qgis_layer())
            else:
                self.assertIsNone(r.generate_qgis_layer())

    def test_generate_qgis_layer_specify_template(self):
        """Test the Referral model generate_qgis_layer() method with the template version specified
        """
        for r in Referral.objects.all():
            if r.location_set.current().filter(poly__isnull=False).exists():
                # The method will return a unicode string.
                self.assertTrue(r.generate_qgis_layer('qgis_layer_v2-16'))
            else:
                self.assertIsNone(r.generate_qgis_layer('qgis_layer_v2-16'))


class TaskTest(PrsTestCase):
    """Unit tests specific to the ``Task`` model class.
    """

    def test_as_row(self):
        """Test the Task model as_row() method.
        """
        t = Task.objects.first()
        # Test that the return string contains task type and
        # absolute URL, plus referral absolute URL.
        row = t.as_row()
        self.assertIsNot(row.find(t.type.name), -1)
        self.assertIsNot(row.find(t.get_absolute_url()), -1)
        self.assertIsNot(row.find(t.referral.get_absolute_url()), -1)
        # Test again with some fields now having values.
        t.description = 'Description'
        t.start_date = date.today()
        t.due_date = date.today() + timedelta(14)
        t.complete_date = date.today() + timedelta(7)
        row = t.as_row()
        self.assertIsNot(row.find(t.type.name), -1)

    def test_as_row_actions(self):
        """Test the Task model as_row_actions() method.
        """
        t = Task.objects.first()
        t.state = TaskState.objects.get(name='In progress')
        t.save()
        row = t.as_row_actions()
        # Non-stopped tasks should have a bunch of options, but not 'Start'
        self.assertIs(row.find('Start'), -1)
        self.assertIsNot(row.find('Edit'), -1)
        self.assertIsNot(row.find('Complete'), -1)
        self.assertIsNot(row.find('Stop'), -1)
        self.assertIsNot(row.find('Cancel'), -1)
        self.assertIsNot(row.find('Delete'), -1)
        # Stopped tasks should have only one option - "Start"
        t.state = TaskState.objects.get(name='Stopped')
        t.stop_date = date.today()
        t.save()
        row = t.as_row_actions()
        self.assertIsNot(row.find('Start'), -1)
        self.assertIs(row.find('Edit'), -1)
        self.assertIs(row.find('Complete'), -1)
        self.assertIs(row.find('Stop'), -1)
        self.assertIs(row.find('Cancel'), -1)
        self.assertIs(row.find('Delete'), -1)
        # Completed tasks should have no actions
        t.state = TaskState.objects.get(name='Completed')
        t.complete_date = date.today()
        t.save()
        row = t.as_row_actions()
        self.assertIs(row.find('Start'), -1)
        self.assertIs(row.find('Edit'), -1)
        self.assertIs(row.find('Complete'), -1)
        self.assertIs(row.find('Stop'), -1)
        self.assertIs(row.find('Cancel'), -1)
        self.assertIs(row.find('Delete'), -1)

    def test_as_row_minus_referral(self):
        """Test the Task model as_row_minus_referral() method.
        """
        t = Task.objects.first()
        row = t.as_row_minus_referral()
        self.assertIs(row.find(t.referral.get_absolute_url()), -1)
        self.assertIs(row.find('class="referral-id-cell"'), -1)

    def test_is_overdue(self):
        """Test the Task model is_overdue property.
        """
        t = Task.objects.first()
        t.due_date = date.today() + timedelta(7)  # Future
        t.save()
        self.assertFalse(t.is_overdue)
        t.due_date = date.today()  # Today
        t.save()
        self.assertFalse(t.is_overdue)
        t.due_date = date.today() + timedelta(-7)  # Past
        t.save()
        self.assertTrue(t.is_overdue)

    def test_is_stopped(self):
        """Test the Task model is_stopped property.
        """
        t = Task.objects.first()
        t.state = TaskState.objects.get(name='In progress')
        t.save()
        self.assertFalse(t.is_stopped)
        t.state = TaskState.objects.get(name='Stopped')
        t.stop_date = date.today()
        t.save()
        self.assertTrue(t.is_stopped)

    def test_as_row_for_site_home(self):
        """Test the Task model as_row_for_site_home() method.
        """
        t = Task.objects.first()
        t.state = TaskState.objects.get(name='In progress')
        t.save()
        row = t.as_row_for_site_home()
        self.assertIs(row.find('Start'), -1)
        # Task referral has no address.
        self.assertIsNot(row.find(t.referral.get_absolute_url()), -1)
        self.assertIs(row.find('Address:'), -1)
        # Task referral has an address.
        t.referral.address = 'Address'
        t.referral.save()
        row = t.as_row_for_site_home()
        self.assertIsNot(row.find('Address:'), -1)
        # Task has a due date and stop date.
        t.state = TaskState.objects.get(name='Stopped')
        t.due_date = date.today() + timedelta(14)
        t.stop_date = date.today()
        t.save()
        row = t.as_row_for_site_home()
        self.assertIsNot(row.find('Start'), -1)
        # Task is completed.
        t.state = TaskState.objects.get(name='Completed')
        t.complete_date = date.today()
        t.save()
        row = t.as_row_for_site_home()
        # Actions cell contains no images.
        self.assertIs(row.find('img src'), -1)

    def test_as_row_for_index_print(self):
        """Test the Task model as_row_for_index_print() method.
        """
        t = Task.objects.first()
        row = t.as_row_for_index_print()
        # Row should never contain the icon cell.
        self.assertIs(row.find('<td class="action-icons-cell">'), -1)
        # Task referral has an address.
        t.referral.address = 'Address'
        t.referral.save()
        row = t.as_row_for_index_print()
        self.assertIsNot(row.find('Address:'), -1)
        # Task has a due date.
        t.due_date = date.today() + timedelta(14)
        t.save()
        row = t.as_row_for_index_print()
        self.assertIsNot(row.find(t.due_date.strftime("%d %b %Y")), -1)

    def test_as_tbody(self):
        """Test the Task model as_tbody() method
        """
        t = Task.objects.first()
        body = t.as_tbody()
        self.assertIsNot(body.find(t.type.name), -1)
        self.assertIsNot(body.find(t.state.name), -1)
        # Add some dates to the task, for coverage.
        t.start_date = date.today()
        t.due_date = date.today()
        t.complete_date = date.today()
        t.stop_date = date.today()
        t.restart_date = date.today()
        t.save()
        body = t.as_tbody()
        self.assertIsNot(body.find(t.type.name), -1)

    def test_email_user(self):
        """Test the Task model email_user() method.
        """
        t = Task.objects.first()
        t.assigned_user = self.n_user
        t.save()
        t.email_user()
        self.assertEqual(len(mail.outbox), 1)
        subject = 'PRS task assignment notification (referral ID {0})'.format(
            t.referral.pk)
        self.assertEqual(mail.outbox[0].subject, subject)


class RecordTest(PrsTestCase):
    """Unit tests specific to the ``Record`` model class.
    """

    def setUp(self):
        super(RecordTest, self).setUp()
        # Create a name temporary file within the project media directory.
        self.tmp_f = NamedTemporaryFile(mode='w', suffix='.txt', dir='media', delete=False)
        self.tmp_f.write('Hello, World!')
        self.tmp_f.close()
        self.r = Record.objects.first()

    def tearDown(self):
        # Clean up the temp file.
        os.remove(self.tmp_f.name)

    def test_extension(self):
        """Test the Record model extension property.
        """
        self.assertTrue(hasattr(self.r, 'extension'))
        self.assertFalse(self.r.extension)  # No file assigned yet.
        self.r.uploaded_file = self.tmp_f.name
        self.r.save()
        self.assertEqual(self.r.extension, 'TXT')

    def test_filesize_str(self):
        """Test the Record model filesize_str property.
        """
        self.assertTrue(hasattr(self.r, 'extension'))
        self.assertFalse(self.r.filesize_str)  # No file assigned yet.
        self.tmp_f = open(settings.MEDIA_ROOT + '/test.txt', 'w')
        self.tmp_f.write('x' * 1024 * 10)  # Write 10k of junk in the file.
        self.tmp_f.close()
        self.r.uploaded_file = self.tmp_f.name
        self.r.save()
        self.assertEqual(self.r.filesize_str, u'10.0Kb')

    def test_as_row(self):
        """Test the Record model as_row() method.
        """
        # Test that the return string contains record name and
        # absolute URL, plus referral absolute URL.
        row = self.r.as_row()
        self.assertIsNot(row.find(self.r.name), -1)
        self.assertIsNot(row.find(self.r.get_absolute_url()), -1)
        self.assertIsNot(row.find(self.r.referral.get_absolute_url()), -1)
        # Add some field values, for coverage.
        self.r.order_date = date.today()
        self.r.infobase_id = 'foo'
        self.r.uploaded_file = self.tmp_f.name
        self.r.save()
        row = self.r.as_row()
        # Row will contain the Infobase ID.
        self.assertIsNot(row.find('foo'), -1)

    def test_as_row_actions(self):
        """Test the Record model as_row_actions() method.
        """
        row = self.r.as_row_actions()
        self.assertIsNot(row.find('Edit'), -1)
        self.assertIsNot(row.find('Delete'), -1)

    def test_as_row_minus_referral(self):
        """Test the Record model as_row_minus_referral() method.
        """
        row = self.r.as_row_minus_referral()
        self.assertIs(row.find(self.r.referral.get_absolute_url()), -1)

    def test_as_tbody(self):
        """Test the Record mode as_tbody() method.
        """
        body = self.r.as_tbody()
        self.assertIsNot(body.find(self.r.name), -1)
        # Add some field values, for coverage.
        self.r.order_date = date.today()
        self.r.infobase_id = 'foo'
        self.r.uploaded_file = self.tmp_f.name
        self.r.save()
        body = self.r.as_tbody()
        # as_tbody will now contain the Infobase ID.
        self.assertIsNot(body.find('foo'), -1)


class NoteTest(PrsTestCase):
    """Unit tests specific to the ``Note`` model class.
    """

    def test_save(self):
        """Test the Note model save() override.
        """
        n = Note.objects.first()
        n.note_html = 'foo ' * 100
        n.note = 'foo ' * 100  # We normally only edit note_html
        n.save()
        # save() will format the note_html value as valid HTML, while the
        # note value will be plain text.
        self.assertNotEqual(n.note_html, n.note)
        # save() will surround the note_html value in <p> tags.
        self.assertTrue(n.note_html.startswith('<p>'))
        self.assertTrue(n.note_html.endswith('</p>'))

    def test_short_code(self):
        """Test the Note model short_note property.
        """
        n = Note.objects.first()
        # Ensure that the text is lengthy.
        n.note_html = '<p>{}</p>'.format('foo ' * 1000)
        n.save()
        # The note text should be truncated and end with '...'
        self.assertNotEqual(n.short_note, n.note_html)
        self.assertTrue(n.short_note.endswith('...'))
        self.assertTrue(n.__str__().endswith('...'))
        # Short note text should not be truncated.
        n.note_html = 'Foo bar baz'
        n.save()
        self.assertFalse(n.short_note.endswith('...'))

    def test_as_row(self):
        """Test the Note model as_row() method.
        """
        # Test that the return string contains record name and
        # absolute URL, plus referral absolute URL.
        n = Note.objects.first()
        row = n.as_row()
        self.assertIsNot(row.find(n.get_absolute_url()), -1)
        self.assertIsNot(row.find(n.referral.get_absolute_url()), -1)
        self.assertIsNot(row.find(n.note), -1)
        # Change some field values, for coverage.
        n.type = None
        n.order_date = date.today()
        n.save()
        row = n.as_row()
        self.assertIsNot(row.find(n.note), -1)

    def test_as_row_actions(self):
        """Test the Note model as_row_actions() method.
        """
        n = Note.objects.first()
        row = n.as_row_actions()
        self.assertIsNot(row.find('Edit'), -1)
        self.assertIsNot(row.find('Delete'), -1)

    def test_as_row_minus_referral(self):
        """Test the Note model as_row_minus_referral() method.
        """
        n = Note.objects.first()
        row = n.as_row_minus_referral()
        self.assertIs(row.find(n.referral.get_absolute_url()), -1)
        self.assertIs(row.find('class="referral-id-cell"'), -1)

    def test_as_tbody(self):
        """Test the Note mode as_tbody() method.
        """
        n = Note.objects.first()
        body = n.as_tbody()
        self.assertIsNot(body.find(n.note_html), -1)
        # Change some field values, for coverage.
        n.order_date = date.today()
        n.save()
        body = n.as_tbody()
        # Body will contain the order_date.
        self.assertIsNot(body.find(n.order_date.strftime('%d-%b-%Y')), -1)


class ConditionTest(PrsTestCase):
    """Unit tests specific to the ``Condition`` model class.
    """

    def test_save(self):
        """Test the Condition model save() override.
        """
        c = Condition.objects.first()
        c.condition_html = '<div class="MsoNormal">Test</div>'
        c.proposed_condition_html = '<span lang="EN-AU">Test</span>'
        c.save()
        self.assertNotEqual(c.condition_html, c.condition)
        # save() should have cleaned up the HTML a little.
        self.assertIs(c.condition_html.find('"MsoNormal"'), -1)
        self.assertIs(c.proposed_condition_html.find('"EN-AU"'), -1)

    def test_blank_condition(self):
        """Test if a condition can be saved without any text.
        """
        c = Condition.objects.first()
        c.proposed_condition_html = ''
        c.condition_html = ''
        c.save()
        self.assertEqual(c.proposed_condition_html, c.proposed_condition)
        self.assertEqual(c.condition_html, c.condition)

    def test_as_row(self):
        """Test the Condition model as_row() method.
        """
        # Test that the return string contains condition absolute URL,
        # plus referral absolute URL.
        c = Condition.objects.first()
        c.proposed_condition_html = '<span lang="EN-AU">Test</span>'
        c.save()
        row = c.as_row()
        self.assertIsNot(row.find(c.get_absolute_url()), -1)
        self.assertIsNot(row.find(c.referral.get_absolute_url()), -1)
        self.assertIsNot(row.find(c.condition), -1)
        # Change some field values, for coverage.
        cat = ConditionCategory.objects.first()
        c.referral = None
        c.category = cat
        c.save()
        row = c.as_row()
        self.assertIsNot(row.find(cat.name), -1)  # Category name should be in output

    def test_as_row_actions(self):
        """Test the Condition model as_row_actions() method.
        """
        c = Condition.objects.first()
        row = c.as_row_actions()
        self.assertIsNot(row.find('Edit'), -1)
        self.assertIsNot(row.find('Delete'), -1)
        url = reverse('condition_clearance_add', kwargs={'pk': c.pk})
        self.assertIsNot(row.find(url), -1)

    def test_as_tbody(self):
        """Test the Condition mode as_tbody() method.
        """
        c = Condition.objects.first()
        body = c.as_tbody()
        self.assertIsNot(body.find(c.referral.get_absolute_url()), -1)
        # Change some field values, for coverage.
        url = c.referral.get_absolute_url()
        c.referral = None
        c.save()
        body = c.as_tbody()
        self.assertIs(body.find(url), -1)

    def test_add_clearance(self):
        """
        """
        c = Condition.objects.first()
        t = mixer.blend(Task, type=mixer.SELECT, referral=mixer.SELECT, state=mixer.SELECT)
        clear = c.add_clearance(t)
        self.assertIsInstance(clear, Clearance)


class ClearanceTest(PrsTestCase):
    """Unit tests specific to the ``Clearance`` model class.
    """

    def setUp(self):
        super(ClearanceTest, self).setUp()
        self.tag = Tag.objects.create(name='Test Tag')

    def test_as_row(self):
        """Test the Clearance model as_row() method.
        """
        c = Clearance.objects.first()
        row = c.as_row()
        self.assertIsNot(row.find(c.task.referral.get_absolute_url()), -1)
        # Change some field values, for coverage.
        c.condition.tags.add(self.tag)
        c.task.description = 'test'
        c.task.save()
        row = c.as_row()
        self.assertIsNot(row.find(c.task.description), -1)
        self.assertIsNot(row.find(self.tag.name), -1)

    def test_as_tbody(self):
        """Test the Clearance model as_tbody() method.
        """
        c = Clearance.objects.first()
        body = c.as_tbody()
        self.assertIsNot(body.find(c.task.referral.get_absolute_url()), -1)


class LocationTest(PrsTestCase):
    """Unit tests specific to the ``Location`` model class.
    """

    def test_nice_address(self):
        """Test the Location model nice_address() method
        """
        loc = Location.objects.first()
        loc.address_no = '1'
        loc.address_suffix = 'A'
        loc.lot_no = '10'
        loc.road_name = 'Foo'
        loc.road_suffix = 'Street'
        loc.locality = 'Perth'
        loc.postcode = '6000'
        loc.save()
        self.assertEqual(loc.nice_address, '1A (Lot 10) Foo Street Perth 6000')
        # Change some field values, for coverage.
        loc.address_no = None
        loc.postcode = None
        loc.save()
        self.assertEqual(loc.nice_address, 'Lot 10 Foo Street Perth')

    def test_as_row(self):
        """Test the Location model as_row() method.
        """
        loc = Location.objects.first()
        row = loc.as_row()
        self.assertIsNot(row.find(loc.referral.get_absolute_url()), -1)

    def test_as_row_actions(self):
        """Test the Location model as_row_actions() method.
        """
        loc = Location.objects.first()
        row = loc.as_row_actions()
        self.assertIsNot(row.find('Edit'), -1)
        self.assertIsNot(row.find('Delete'), -1)

    def test_as_row_minus_referral(self):
        """Test the Location model as_row_minus_referral() method.
        """
        loc = Location.objects.first()
        row = loc.as_row_minus_referral()
        self.assertIs(row.find(loc.referral.get_absolute_url()), -1)
        self.assertIs(row.find('class="referral-id-cell"'), -1)

    def test_as_tbody(self):
        """Test the Location mode as_tbody() method.
        """
        loc = Location.objects.first()
        body = loc.as_tbody()
        self.assertIsNot(body.find(loc.referral.get_absolute_url()), -1)


class BookmarkTest(PrsTestCase):

    def test_as_row(self):
        """Test the Bookmark model as_row() method.
        """
        b = Bookmark.objects.first()
        row = b.as_row()
        self.assertIsNot(row.find(b.referral.get_absolute_url()), -1)

    def test_as_tbody(self):
        """Test the Bookmark mode as_tbody() method.
        """
        b = Bookmark.objects.first()
        body = b.as_tbody()
        self.assertIsNot(body.find(b.referral.get_absolute_url()), -1)


class RelatedReferralTest(PrsTestCase):

    def setUp(self):
        super(RelatedReferralTest, self).setUp()
        q = Referral.objects.all().order_by('pk')
        ref1, ref2 = q[0], q[1]
        ref1.add_relationship(ref2)
        self.obj = RelatedReferral.objects.first()


class UserProfileTest(PrsTestCase):

    def test_is_prs_user(self):
        self.assertFalse(self.admin_user.userprofile.is_prs_user())
        self.assertTrue(self.p_user.userprofile.is_prs_user())
        self.assertTrue(self.n_user.userprofile.is_prs_user())
        self.assertFalse(self.ro_user.userprofile.is_prs_user())

    def test_is_power_user(self):
        self.assertTrue(self.admin_user.userprofile.is_power_user())
        self.assertTrue(self.p_user.userprofile.is_power_user())
        self.assertFalse(self.n_user.userprofile.is_power_user())
        self.assertFalse(self.ro_user.userprofile.is_power_user())

    def test_last_referral(self):
        # User with no referral history.
        self.assertFalse(self.n_user.userprofile.last_referral())
        # Give the user a referral history.
        ref = Referral.objects.first()
        user_referral_history(self.n_user, ref)
        self.assertEqual(self.n_user.userprofile.last_referral(), ref)
        # Deleted referrals should not be returned for history.
        ref.delete()
        self.assertFalse(self.n_user.userprofile.last_referral())

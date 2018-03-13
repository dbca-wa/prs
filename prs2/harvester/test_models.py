from django.core.files import File
from django.utils import timezone
from mixer.backend.django import mixer
import os
from referral.models import Agency, Region, DopTrigger, Referral, Task, Record
from referral.test_models import PrsTestCase
import sys

from harvester.models import EmailedReferral, EmailAttachment, RegionAssignee


class HarvesterModelTestCase(PrsTestCase):

    def setUp(self):
        super(HarvesterModelTestCase, self).setUp()
        mixer.cycle(2).blend(RegionAssignee)


class RegionAssigneeModelTest(HarvesterModelTestCase):

    def test_unicode(self):
        """Test the RegionAssignee __str__() method
        """
        for obj in RegionAssignee.objects.all():
            self.assertTrue(str(obj))


class EmailedReferralModelTest(HarvesterModelTestCase):

    def setUp(self):
        super(EmailedReferralModelTest, self).setUp()
        # Instantiate some objects from real data.
        curr = os.path.dirname(os.path.abspath(__file__))
        email_body = open(os.path.join(curr, 'test_files', 'test_referral_email.txt')).read()
        self.e_ref = mixer.blend(
            EmailedReferral, received=timezone.now(), body=email_body, processed=False)
        xml = File(open(os.path.join(curr, 'test_files', 'application.xml')))
        self.app_xml = EmailAttachment(
            emailed_referral=self.e_ref, name='application.xml')
        self.app_xml.attachment.save('application.xml', xml, save=False)
        self.app_xml.save()
        if sys.version_info > (3, 0):
            letter = File(open(os.path.join(curr, 'test_files', 'test_referral_letter.pdf'), encoding='latin1'))
        else:
            letter = File(open(os.path.join(curr, 'test_files', 'test_referral_letter.pdf')))
        self.app_letter = EmailAttachment(
            emailed_referral=self.e_ref, name='referral_letter.pdf')
        self.app_letter.attachment.save('referral_letter.pdf', letter, save=False)
        self.app_letter.save()
        # Generate some required related objects.
        mixer.blend(
            Agency, name='Department of Biodiversity, Conservation and Attractions',
            slug='dbca')
        mixer.blend(Region, name='Swan')
        mixer.blend(DopTrigger, name='No Parks and Wildlife trigger')

    def test_harvest(self):
        """Test the harvest() method
        """
        ref_count = Referral.objects.count()
        task_count = Task.objects.count()
        record_count = Record.objects.count()
        # NOTE: we don't test email harvesting or parsing.
        # NOTE: creation of Locations requires that we query the Landgate SLIP service.
        # As we can't commit the username or password, explicitly skip creation of locations here.
        actions = self.e_ref.harvest(create_locations=False, assignee=self.n_user)
        # actions should not be an empty list.
        self.assertTrue(bool(actions))
        # >0 Referrals, Tasks and Records should have been created.
        self.assertTrue(Referral.objects.count() > ref_count)
        self.assertTrue(Task.objects.count() > task_count)
        self.assertTrue(Record.objects.count() > record_count)

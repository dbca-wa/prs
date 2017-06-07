from mixer.backend.django import mixer
from harvester.models import EmailedReferral, EmailAttachment, RegionAssignee
from referral.test_models import PrsTestCase


class HarvesterModelTestCase(PrsTestCase):

    def setUp(self):
        super(HarvesterModelTestCase, self).setUp()
        mixer.cycle(2).blend(EmailedReferral)
        mixer.cycle(2).blend(EmailAttachment)
        mixer.cycle(2).blend(RegionAssignee)


class RegionAssigneeModelTest(HarvesterModelTestCase):

    def test_unicode(self):
        """Test the RegionAssignee __str__() method
        """
        for obj in RegionAssignee.objects.all():
            self.assertTrue(str(obj))

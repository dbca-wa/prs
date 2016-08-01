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
        """Test the RegionAssignee __unicode__() method returns unicode.
        """
        for obj in RegionAssignee.objects.all():
            self.assertIsInstance(obj.__unicode__(), unicode)

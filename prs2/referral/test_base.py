from datetime import date
from referral.test_models import PrsTestCase
from referral.models import Referral, ReferralType, Organisation


class AuditTestCase(PrsTestCase):

    def test_save(self):
        """Test that the save() method sets a creator and modifier outside of a HTTP request
        """
        r = Referral.objects.create(
            type=ReferralType.objects.first(), referring_org=Organisation.objects.first(),
            reference='foo', referral_date=date.today())
        self.assertEquals(r.creator.pk, 1)
        self.assertEquals(r.modifier.pk, 1)

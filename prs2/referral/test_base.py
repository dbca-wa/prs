from datetime import date

from referral.models import Organisation, Referral, ReferralType
from referral.test_models import PrsTestCase


class AuditTestCase(PrsTestCase):
    def test_save(self):
        """Test that the save() method sets a creator and modifier outside of a HTTP request"""
        r = Referral.objects.create(
            type=ReferralType.objects.first(),
            referring_org=Organisation.objects.first(),
            reference="foo",
            referral_date=date.today(),
        )
        self.assertEqual(r.creator.pk, 1)
        self.assertEqual(r.modifier.pk, 1)

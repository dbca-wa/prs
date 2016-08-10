from datetime import date
from referral.test_models import PrsTestCase
from referral.forms import ReferralForm, OrganisationForm
from referral.models import Organisation, OrganisationType, ReferralType, TaskType, Region, DopTrigger


class ReferralFormTest(PrsTestCase):
    """Test ReferralForm class
    """
    def setUp(self):
        super(ReferralFormTest, self).setUp()
        # We need a couple of specific objects to exist:
        if not Organisation.objects.filter(slug='wapc'):
            Organisation.objects.create(
                name='Western Australian Planning Commission',
                slug='wapc',
                type=OrganisationType.objects.all()[0],
                list_name='Western Australian Planning Commission (WAPC)',
                public=True)
        self.org = Organisation.objects.get(slug='wapc')
        if not ReferralType.objects.filter(slug='subdivision'):
            ReferralType.objects.create(
                name='Subdivision', slug='subdivision',
                initial_task=TaskType.objects.all()[0])
        self.ref_type = ReferralType.objects.get(slug='subdivision')
        if not ReferralType.objects.filter(slug='development-application'):
            ReferralType.objects.create(
                name='Development application', slug='development-application',
                initial_task=TaskType.objects.all()[0])

    def test_form_clean(self):
        """Test the ReferralForm clean method rules
        """
        form_data = {
            'referring_org': self.org.pk,
            'reference': '123456',
            'description': 'Test referral',
            'referral_date': date.today(),
            'type': self.ref_type.pk,
            'assigned_user': self.n_user,
            'region': list(Region.objects.all()),
        }
        form = ReferralForm(data=form_data)
        # Validation should fail (WAPC subdivision referral, no DoP triggers).
        self.assertFalse(form.is_valid())
        # Change the referring org and validation should pass.
        org2 = Organisation.objects.exclude(slug='wapc').first()
        form_data['referring_org'] = org2.pk
        form = ReferralForm(data=form_data)
        self.assertTrue(form.is_valid())
        # Add in a DoP trigger and validation should pass
        form_data['referring_org'] = self.org.pk
        form_data['dop_triggers'] = list(DopTrigger.objects.all())
        form = ReferralForm(data=form_data)
        self.assertTrue(form.is_valid())


class OrganisationFormTest(PrsTestCase):

    def setUp(self):
        super(OrganisationFormTest, self).setUp()
        if not Organisation.objects.filter(slug='wapc'):
            Organisation.objects.create(
                name='Western Australian Planning Commission',
                slug='wapc',
                type=OrganisationType.objects.all()[0],
                list_name='Western Australian Planning Commission (WAPC)',
                public=True)
        self.org = Organisation.objects.get(slug='wapc')

    def test_form_clean(self):
        """Test the OrganisationForm clean method
        """
        form_data = {
            'name': self.org.name,
            'type': self.org.type.pk,
            'list_name': self.org.list_name,
            'state': self.org.state
        }
        form = OrganisationForm(data=form_data)
        # Validation should fail (duplicate name).
        self.assertFalse(form.is_valid())

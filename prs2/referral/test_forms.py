from datetime import date
from django.core.files.uploadedfile import SimpleUploadedFile
from referral.test_models import PrsTestCase
from referral.forms import ReferralForm, OrganisationForm, RecordForm, RecordCreateForm
from referral.models import (
    Organisation, OrganisationType, ReferralType, TaskType, Region, DopTrigger)
from tempfile import NamedTemporaryFile


class ReferralFormTest(PrsTestCase):
    """Test ReferralForm class
    """
    def setUp(self):
        super(ReferralFormTest, self).setUp()
        self.org = Organisation.objects.get(slug='wapc')
        self.ref_type = ReferralType.objects.get(name='Subdivision')

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
            'regions': list(Region.objects.all()),
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


class RecordFormTest(PrsTestCase):

    def test_form_clean(self):
        """Test the RecordForm clean method
        """
        f1 = NamedTemporaryFile('w+b')
        f1.write(b'Test data')
        f1.seek(0)
        f2 = NamedTemporaryFile('w+b')
        f2.write(b'Test data')
        f2.seek(0)
        # An accepted file type.
        up_file1 = SimpleUploadedFile(
            name=f1.name, content=f1.read(), content_type='text/plain')
        # Non-accepted file type.
        up_file2 = SimpleUploadedFile(
            name=f2.name, content=f2.read(), content_type='application/x-shockwave-flash')
        file_data = {'uploaded_file': up_file1}
        form_data = {'name': 'Test file', 'uploaded_file': up_file1.name}
        form = RecordForm(data=form_data, files=file_data)
        # Validation should pass (accepted file type).
        self.assertTrue(form.is_valid())
        file_data = {'uploaded_file': up_file2}
        form = RecordForm(data=form_data, files=file_data)
        # Validation should fail (non-accepted file type).
        self.assertFalse(form.is_valid())


class RecordCreateFormTest(PrsTestCase):

    def test_form_clean(self):
        """Test the RecordCreateForm clean method
        """
        f = NamedTemporaryFile('w+b')
        f.write(b'Test data')
        f.seek(0)
        # An accepted file type.
        up_file = SimpleUploadedFile(name=f.name, content=f.read())
        file_data = {'uploaded_file': up_file}
        form_data = {'name': 'Test file'}
        form = RecordCreateForm(data=form_data)
        # Validation should fail (no uploaded file or Infobase ID).
        self.assertFalse(form.is_valid())
        # Add both Infobase ID and uploaded file, validation passes.
        form_data['uploaded_file'] = up_file.name
        form_data['infobase_id'] = 'TestID'
        form = RecordForm(data=form_data, files=file_data)
        self.assertTrue(form.is_valid())
        # Include just the file, validation passes.
        form_data.pop('infobase_id')
        form = RecordForm(data=form_data, files=file_data)
        self.assertTrue(form.is_valid())
        # Include just the Infobase ID, validation passes.
        form_data.pop('uploaded_file')
        form_data['infobase_id'] = 'TestID'
        form = RecordForm(data=form_data)
        self.assertTrue(form.is_valid())

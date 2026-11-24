import zipfile
from datetime import date
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile

from referral.forms import OrganisationForm, RecordCreateForm, RecordForm, ReferralForm, ShapefileUploadForm
from referral.models import DopTrigger, Organisation, ReferralType, Region
from referral.test_models import PrsTestCase


def _zip_bytes(members: dict[str, bytes]) -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, data in members.items():
            archive.writestr(name, data)
    return buffer.getvalue()


class ReferralFormTest(PrsTestCase):
    """Test ReferralForm class"""

    def setUp(self):
        super().setUp()
        self.org = Organisation.objects.get(slug="wapc")
        self.ref_type = ReferralType.objects.get(name="Subdivision")

    def test_form_clean(self):
        """Test the ReferralForm clean method rules"""
        form_data = {
            "referring_org": self.org.pk,
            "reference": "123456",
            "description": "Test referral",
            "referral_date": date.today(),
            "type": self.ref_type.pk,
            "assigned_user": self.n_user,
            "regions": list(Region.objects.all()),
        }
        form = ReferralForm(data=form_data)
        # Validation should fail (WAPC subdivision referral, no DoP triggers).
        self.assertFalse(form.is_valid())
        # Change the referring org and validation should pass.
        org2 = Organisation.objects.exclude(slug="wapc").first()
        form_data["referring_org"] = org2.pk
        form = ReferralForm(data=form_data)
        self.assertTrue(form.is_valid())
        # Add in a DoP trigger and validation should pass
        form_data["referring_org"] = self.org.pk
        form_data["dop_triggers"] = list(DopTrigger.objects.all())
        form = ReferralForm(data=form_data)
        self.assertTrue(form.is_valid())


class OrganisationFormTest(PrsTestCase):
    def setUp(self):
        super().setUp()
        self.org = Organisation.objects.get(slug="wapc")

    def test_form_clean(self):
        """Test the OrganisationForm clean method"""
        form_data = {"name": self.org.name, "type": self.org.type.pk, "list_name": self.org.list_name, "state": self.org.state}
        form = OrganisationForm(data=form_data)
        # Validation should fail (duplicate name).
        self.assertFalse(form.is_valid())


class RecordFormTest(PrsTestCase):
    def setUp(self):
        super().setUp()
        self.form_data = {"name": "Test file"}

    def test_form_accepts_allowed_file(self):
        """An allowed file (by extension and content) should validate"""
        upload = SimpleUploadedFile("test.txt", b"Test data", content_type="text/plain")
        form = RecordForm(data=self.form_data, files={"uploaded_file": upload})
        self.assertTrue(form.is_valid(), form.errors)

    def test_form_rejects_disallowed_extension(self):
        """A disallowed extension must be rejected even when the browser
        claims the file has an allowed Content-Type"""
        upload = SimpleUploadedFile("payload.exe", b"Test data", content_type="text/plain")
        form = RecordForm(data=self.form_data, files={"uploaded_file": upload})
        self.assertFalse(form.is_valid())
        self.assertIn("uploaded_file", form.errors)

    def test_form_rejects_disallowed_content(self):
        """HTML content must be rejected even when the filename and the
        declared Content-Type look harmless"""
        upload = SimpleUploadedFile("notes.txt", b"<html><script>alert(1)</script></html>", content_type="text/plain")
        form = RecordForm(data=self.form_data, files={"uploaded_file": upload})
        self.assertFalse(form.is_valid())
        self.assertIn("uploaded_file", form.errors)

    def test_form_rejects_oversized_file(self):
        """A file larger than MAX_UPLOAD_SIZE_BYTES must be rejected"""
        upload = SimpleUploadedFile("test.txt", b"Test data", content_type="text/plain")
        with self.settings(MAX_UPLOAD_SIZE_BYTES=4):
            form = RecordForm(data=self.form_data, files={"uploaded_file": upload})
            valid = form.is_valid()
        self.assertFalse(valid)
        self.assertIn("uploaded_file", form.errors)


class ShapefileUploadFormTest(PrsTestCase):
    def test_accepts_zip_with_shapefile(self):
        """A zip containing a .shp member is accepted; the shapefile itself is
        only parsed later, in the view."""
        upload = SimpleUploadedFile("shapefile.zip", _zip_bytes({"polygons.shp": b"not parsed here"}), content_type="text/plain")
        form = ShapefileUploadForm(data={}, files={"uploaded_shapefile": upload})
        self.assertTrue(form.is_valid(), form.errors)

    def test_accepts_zip_with_nested_shapefile(self):
        """A shapefile inside a folder is just as valid as one at the root."""
        upload = SimpleUploadedFile("shapefile.zip", _zip_bytes({"Spatial/polygons.shp": b"not parsed here"}), content_type="text/plain")
        form = ShapefileUploadForm(data={}, files={"uploaded_shapefile": upload})
        self.assertTrue(form.is_valid(), form.errors)

    def test_rejects_zip_without_shapefile(self):
        """A safe zip that contains no shapefile can never be imported."""
        upload = SimpleUploadedFile("shapefile.zip", _zip_bytes({"readme.txt": b"Not a shapefile"}), content_type="text/plain")
        form = ShapefileUploadForm(data={}, files={"uploaded_shapefile": upload})
        self.assertFalse(form.is_valid())
        self.assertIn("uploaded_shapefile", form.errors)

    def test_rejects_non_zip(self):
        upload = SimpleUploadedFile("shapefile.txt", b"Test data", content_type="application/zip")
        form = ShapefileUploadForm(data={}, files={"uploaded_shapefile": upload})
        self.assertFalse(form.is_valid())
        self.assertIn("uploaded_shapefile", form.errors)


class RecordCreateFormTest(PrsTestCase):
    def test_form_clean(self):
        """Test the RecordCreateForm clean method"""
        up_file = SimpleUploadedFile("test.txt", b"Test data")
        file_data = {"uploaded_file": up_file}
        form_data = {"name": "Test file"}
        form = RecordCreateForm(data=form_data)
        # Validation should fail (no uploaded file or Infobase ID).
        self.assertFalse(form.is_valid())
        # Add both Infobase ID and uploaded file, validation passes.
        form_data["uploaded_file"] = up_file.name
        form_data["infobase_id"] = "TestID"
        form = RecordForm(data=form_data, files=file_data)
        self.assertTrue(form.is_valid())
        # Include just the file, validation passes.
        form_data.pop("infobase_id")
        form = RecordForm(data=form_data, files=file_data)
        self.assertTrue(form.is_valid())
        # Include just the Infobase ID, validation passes.
        form_data.pop("uploaded_file")
        form_data["infobase_id"] = "TestID"
        form = RecordForm(data=form_data)
        self.assertTrue(form.is_valid())

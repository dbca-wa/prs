import os
from email.message import EmailMessage
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.core.files import File
from django.core.files.base import ContentFile
from django.test import override_settings
from django.utils import timezone
from mixer.backend.django import mixer

from harvester import utils
from harvester.models import EmailAttachment, EmailedReferral, RegionAssignee
from referral.models import Agency, DopTrigger, LocalGovernment, Record, Referral, Region, Task
from referral.test_models import PrsTestCase

User = get_user_model()


class HarvesterModelTestCase(PrsTestCase):
    def setUp(self):
        super().setUp()
        mixer.cycle(2).blend(RegionAssignee)
        mixer.blend(LocalGovernment, name="BUNBURY", slug="bunbury")
        self.admin = User.objects.get_or_create(username="admin")


class RegionAssigneeModelTest(HarvesterModelTestCase):
    def test_unicode(self):
        """Test the RegionAssignee __str__() method"""
        for obj in RegionAssignee.objects.all():
            self.assertTrue(str(obj))


class EmailedReferralModelTest(HarvesterModelTestCase):
    def setUp(self):
        super().setUp()
        # Instantiate some objects from real data.
        curr = os.path.dirname(os.path.abspath(__file__))
        email = open(os.path.join(curr, "test_data", "test_referral_email.txt"))
        email_body = email.read()
        email.close()
        self.e_ref = mixer.blend(EmailedReferral, received=timezone.now(), body=email_body, processed=False)
        xml = File(open(os.path.join(curr, "test_data", "application.xml")))
        self.app_xml = EmailAttachment(emailed_referral=self.e_ref, name="application.xml")
        self.app_xml.attachment.save("application.xml", xml, save=False)
        self.app_xml.save()
        xml.close()
        self.app_letter = EmailAttachment(emailed_referral=self.e_ref, name="referral_letter.pdf")
        letter = File(open(os.path.join(curr, "test_data", "test_referral_letter.pdf"), encoding="latin1"))
        self.app_letter.attachment.save("referral_letter.pdf", letter, save=False)
        self.app_letter.save()
        letter.close()
        # Generate some required related objects.
        mixer.blend(Agency, name="Department of Biodiversity, Conservation and Attractions", slug="dbca")
        mixer.blend(Region, name="Swan")
        mixer.blend(DopTrigger, name="No Parks and Wildlife trigger")

    def _create_email_with_attachment(self, subject, *, name="application.xml", content=b"content", body="email body"):
        referral = mixer.blend(EmailedReferral, subject=subject, body=body, processed=False)
        attachment = EmailAttachment.objects.create(emailed_referral=referral, name=name)
        attachment.attachment.save(name, ContentFile(content), save=False)
        attachment.save()
        return referral

    def _create_xml(self, app_type="DEVELOPMENT APPLICATION", local_government="BUNBURY"):
        return (
            "<?xml version=\"1.0\"?>"
            "<APPLICATION>"
            "<WAPC_APPLICATION_NO>1586-26</WAPC_APPLICATION_NO>"
            f"<APP_TYPE>{app_type}</APP_TYPE>"
            "<TENURE_TYPE>Survey-strata</TENURE_TYPE>"
            f"<LOCAL_GOVERNMENT>{local_government}</LOCAL_GOVERNMENT>"
            "<DEVELOPMENT_DESCRIPTION>Subdivision</DEVELOPMENT_DESCRIPTION>"
            "<LOCATION>Lot 6 Example Highway</LOCATION>"
            "<DUE_DATE>26-Nov-26</DUE_DATE>"
            "<MRSZONE_TEXT>Threatened fauna buffer</MRSZONE_TEXT>"
            "<ADDRESS_DETAIL><DOP_ADDRESS_TYPE>"
            "<PIN>654321</PIN>"
            "<LATITUDE>-36.0091335</LATITUDE>"
            "<LONGITUDE>116.87039852</LONGITUDE>"
            "<NUMBER_FROM>60</NUMBER_FROM>"
            "<NUMBER_FROM_SUFFIX> </NUMBER_FROM_SUFFIX>"
            "<STREET_NAME>EXAMPLE</STREET_NAME>"
            "<STREET_SUFFIX>HWY</STREET_SUFFIX>"
            "<SUBURB>EASTON VALE</SUBURB>"
            "<POSTCODE>6331</POSTCODE>"
            "</DOP_ADDRESS_TYPE></ADDRESS_DETAIL>"
            "</APPLICATION>"
        ).encode("utf-8")

    def test_harvest(self):
        """Test the harvest() method"""
        ref_count = Referral.objects.count()
        task_count = Task.objects.count()
        record_count = Record.objects.count()
        # NOTE: we don't test email harvesting or parsing.
        # NOTE: creation of Locations requires that we query the Landgate SLIP service.
        # As we can't commit the username or password, explicitly skip creation of locations here.
        actions = self.e_ref.harvest(create_locations=False, assignee=self.admin_user)
        # actions should not be an empty list.
        self.assertTrue(bool(actions))
        # >0 Referrals, Tasks and Records should have been created.
        self.assertTrue(Referral.objects.count() > ref_count)
        self.assertTrue(Task.objects.count() > task_count)
        self.assertTrue(Record.objects.count() > record_count)
        # Admin user should now have a task.
        self.assertTrue(Task.objects.filter(assigned_user=self.admin_user))

    def test_harvest_with_assignee(self):
        """Test the harvest() method with an assignee set"""
        task_count = Task.objects.filter(assigned_user=self.n_user).count()
        self.e_ref.harvest(create_locations=False, assignee=self.n_user)
        # Normal user should now have a new task.
        self.assertTrue(Task.objects.filter(assigned_user=self.n_user).count() > task_count)

    def test_harvest_skips_no_attachments(self):
        """Test the no-attachment skip path."""
        e_ref = mixer.blend(EmailedReferral, subject="Standard email", body="Body", processed=False)

        actions = e_ref.harvest(create_locations=False, assignee=self.admin_user)

        self.assertTrue(e_ref.processed)
        self.assertIsNone(e_ref.referral)
        self.assertTrue(any("no attachments" in action.lower() for action in actions))

    def test_harvest_skips_overdue_notice(self):
        """Test the overdue-notice skip path."""
        e_ref = self._create_email_with_attachment("Re: WAPC eOverdue referral 1586-26", content=b"payload")

        actions = e_ref.harvest(create_locations=False, assignee=self.admin_user)

        self.assertTrue(e_ref.processed)
        self.assertIsNone(e_ref.referral)
        self.assertTrue(any("overdue notice" in action.lower() for action in actions))

    def test_harvest_skips_decision_letter_without_reference(self):
        """Test decision-letter handling when a reference cannot be identified."""
        e_ref = self._create_email_with_attachment("Decision letter for a referral", content=b"payload")

        actions = e_ref.harvest(create_locations=False, assignee=self.admin_user)

        self.assertTrue(e_ref.processed)
        self.assertTrue(any("unable to find reference" in action.lower() for action in actions))

    def test_harvest_skips_missing_application_xml(self):
        """Test standard referral processing with no XML attachment."""
        e_ref = self._create_email_with_attachment("Standard referral", name="referral_letter.pdf", content=b"pdf")

        e_ref.harvest(create_locations=False, assignee=self.admin_user)

        self.assertTrue(e_ref.processed)
        self.assertIn("no xml attachment", e_ref.log.lower())

    def test_harvest_skips_unrecognised_referral_type(self):
        """Test the unrecognised referral-type skip path."""
        e_ref = self._create_email_with_attachment("Standard referral", content=self._create_xml(app_type="UNKNOWN TYPE"))

        actions = e_ref.harvest(create_locations=False, assignee=self.admin_user)

        self.assertTrue(e_ref.processed)
        self.assertTrue(any("not recognised type" in action.lower() for action in actions))

    def test_normalise_imap_uid(self):
        """Test IMAP UID validation helper."""
        self.assertIsNone(utils.normalise_imap_uid(None))
        self.assertIsNone(utils.normalise_imap_uid("0"))
        self.assertIsNone(utils.normalise_imap_uid("abc"))
        self.assertEqual(utils.normalise_imap_uid(b"42"), "42")
        self.assertEqual(utils.normalise_imap_uid(99), "99")
        self.assertEqual(utils.normalise_imap_uid("123"), "123")

    def test_email_get_unread_ok(self):
        """Test email_get_unread() on a successful response."""
        imap = Mock()
        imap.uid.return_value = ("OK", [b"10 20 30"])

        status, uids = utils.email_get_unread(imap, "sender@example.com")

        self.assertEqual(status, "OK")
        self.assertEqual(uids, [b"10", b"20", b"30"])
        imap.uid.assert_called_once_with("SEARCH", '(UNSEEN FROM "sender@example.com" UNFLAGGED)')

    def test_email_fetch_valid_message(self):
        """Test email_fetch() for valid parsible message data."""
        msg = EmailMessage()
        msg["From"] = "sender@example.com"
        msg["To"] = "assessor@example.com"
        msg["Subject"] = "Referral test"
        msg.set_content("Body")

        imap = Mock()
        imap.uid.return_value = ("OK", [(b"123", msg.as_bytes())])

        status, email_msg = utils.email_fetch(imap, "123")

        self.assertEqual(status, "OK")
        self.assertEqual(email_msg["Subject"], "Referral test")

    def test_harvest_email_creates_emailed_referral_and_attachment(self):
        """Test harvest_email() for HTML email with attachment creation."""
        msg = EmailMessage()
        msg["From"] = "sender@example.com"
        msg["To"] = "assessor@example.com"
        msg["Date"] = "Tue, 01 Jan 2024 12:00:00 +0000"
        msg["Subject"] = "Referral 123"
        msg.set_content("Plain text alternative")
        msg.add_alternative("<p>HTML body</p>", subtype="html")
        msg.add_attachment(b"pdf-data", maintype="application", subtype="pdf", filename="doc.pdf")

        with override_settings(ASSESSOR_EMAILS=["assessor@example.com"]):
            result = utils.harvest_email("321", msg)

        self.assertTrue(result)
        self.assertTrue(EmailedReferral.objects.filter(email_uid="321", subject="Referral 123").exists())
        self.assertTrue(EmailAttachment.objects.filter(name="doc.pdf").exists())

    def test_harvest_email_fails_without_message_body(self):
        """Test harvest_email() when no text body is present."""
        msg = EmailMessage()
        msg["From"] = "sender@example.com"
        msg["To"] = "assessor@example.com"
        msg["Date"] = "Tue, 01 Jan 2024 12:00:00 +0000"
        msg["Subject"] = "Referral without body"
        msg.add_attachment(b"payload", maintype="application", subtype="octet-stream", filename="doc.pdf")

        result = utils.harvest_email("322", msg)

        self.assertFalse(result)

    def test_harvest_unread_emails_purges_and_logs(self):
        """Test harvest_unread_emails() with purge email enabled."""
        imap = Mock()
        msg = EmailMessage()
        msg["From"] = "sender@example.com"
        msg["To"] = "assessor@example.com"
        msg["Date"] = "Tue, 01 Jan 2024 12:00:00 +0000"
        msg["Subject"] = "Referral"
        msg.set_content("Body")

        with patch("harvester.utils.get_imap", return_value=imap), \
            patch("harvester.utils.email_get_unread", return_value=("OK", [b"1"])), \
            patch("harvester.utils.email_fetch", return_value=("OK", msg)), \
            patch("harvester.utils.harvest_email", return_value=True) as harvest_email_mock, \
            patch("harvester.utils.email_mark_read", return_value=("OK", [])) as mark_read, \
            patch("harvester.utils.email_mark_deleted", return_value=("OK", [])) as mark_deleted:
            actions = utils.harvest_unread_emails("sender@example.com", purge_email=True)

        self.assertTrue(actions)
        harvest_email_mock.assert_called_once_with("1", msg)
        mark_read.assert_called_once_with(imap, "1")
        mark_deleted.assert_called_once_with(imap, "1")
        imap.expunge.assert_called_once()
        imap.logout.assert_called_once()

    def test_import_harvested_refs_calls_harvest(self):
        """Test import_harvested_refs() iterates captured harvested referrals."""
        e_ref = mixer.blend(EmailedReferral, processed=False, referral=None)

        with patch.object(EmailedReferral, "harvest", return_value=["harvested"]) as harvest_mock:
            actions = utils.import_harvested_refs()

        self.assertTrue(actions[0].endswith("Starting import of harvested referrals"))
        self.assertIn("harvested", actions)
        self.assertTrue(actions[-1].endswith("Import process completed"))
        self.assertGreaterEqual(harvest_mock.call_count, 1)
        self.assertTrue(any(call.args == () and call.kwargs == {} for call in harvest_mock.call_args_list))

    def test_email_harvest_actions_sends_report(self):
        """Test email_harvest_actions() sends a monitoring email."""
        email_instance = Mock()

        with patch("harvester.utils.EmailMultiAlternatives") as email_multi:
            email_multi.return_value = email_instance
            utils.email_harvest_actions(["ops@example.com"], ["one", "two"])

        email_multi.assert_called_once()
        self.assertEqual(email_instance.attach_alternative.call_count, 1)
        email_instance.send.assert_called_once_with(fail_silently=True)

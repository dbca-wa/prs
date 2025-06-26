import logging
import re
from datetime import datetime, timedelta

import xmltodict
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import GEOSGeometry, Point, Polygon
from django.core.files.base import ContentFile
from django.db import models
from referral.models import (
    Agency,
    DopTrigger,
    LocalGovernment,
    Location,
    Organisation,
    Record,
    Referral,
    ReferralType,
    Region,
    Task,
    TaskType,
)
from reversion.revisions import create_revision, set_comment

from .utils import query_slip_esri

LOGGER = logging.getLogger("harvester")
# The list below is a case-sensitive list of filenames of email attachments
# which will be skipped for import as PRS Records (they will still be downloaded).
ATTACHMENT_FILENAME_BLOCKLIST = [
    "image.png",
]


class EmailedReferral(models.Model):
    """A model to record details about emailed planning referrals."""

    harvested = models.DateTimeField(auto_now_add=True)
    received = models.DateTimeField(blank=True, null=True, editable=False)
    email_uid = models.CharField(max_length=256)
    to_email = models.CharField(max_length=256)
    from_email = models.CharField(max_length=256)
    subject = models.CharField(max_length=512)
    body = models.TextField()
    referral = models.ForeignKey(Referral, null=True, blank=True, on_delete=models.PROTECT)
    processed = models.BooleanField(default=False)
    log = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.subject

    def save(self, *args, **kwargs):
        self.subject = self.subject.replace("\r\n", "").strip()
        # Fix rare strange subject line text encoding issue.
        pattern = r"(\=\?Windows-1252\?Q\?)"
        if re.match(pattern, self.subject):
            self.subject = re.sub(pattern, "", self.subject)
            self.subject = self.subject.replace("=96", "").replace("?=", "").replace("_", " ").strip()
        # Clean up any HTML markup in the email body.
        self.body = self.body.replace("=\r\n", "").replace("=E2=80=93", "-").strip()
        pattern = r"^(<!--)(.+)(-->)"
        self.body = re.sub(pattern, "", self.body, flags=re.DOTALL)
        pattern = r"(&nbsp;)"
        self.body = re.sub(pattern, "", self.body)
        pattern = r"(<.+>)"
        self.body = re.sub(pattern, "", self.body)
        self.body = self.body.replace("=96", "").strip()
        super().save(*args, **kwargs)

    def harvest(self, create_tasks=True, create_locations=True, create_records=True, assignee=False):
        """Undertake the harvest process for this emailed referral.
        Allows tasks, locations and records to be optionally created.
        """
        actions = []

        if self.processed:
            LOGGER.info(f"Emailed referral {self.pk} is already processed, aborting")
            return actions

        User = get_user_model()
        region = None
        dbca = Agency.objects.get(slug="dbca")
        wapc = Organisation.objects.get(slug="wapc")
        attachments = self.emailattachment_set.all()
        self.log = ""

        # SCENARIO: no email attachments, skip harvest.
        if not attachments.exists():
            log = f"Skipping emailed referral {self.pk} (no attachments)"
            LOGGER.info(log)
            self.log = log
            self.processed = True
            self.save()
            actions.append(f"{datetime.now().isoformat()} {log}")
            return actions

        # SCENARIO: overdue referral reminders: skip harvest.
        overdue_subject_prefixes = (
            "wapc eoverdue referral",
            "re: wapc eoverdue referral",
        )
        if any([self.subject.lower().startswith(i) for i in overdue_subject_prefixes]):
            log = f"Skipping harvested referral {self} (overdue notice)"
            LOGGER.info(log)
            self.log = log
            self.processed = True
            self.save()
            actions.append(f"{datetime.now().isoformat()} {log}")
            return actions

        # SCENARIO: email referral supplement.
        # Some emailed referrals contain "additional documents" where the size
        # limit of attachments have been exceeded for the first email.
        additional_documents_subject = (
            "additional documents",
            "additional referral documents",
        )
        if any([i in self.subject.lower() for i in additional_documents_subject]) and attachments.exists():
            log = f"Harvested referral {self} appears to be a supplement to an existing email"
            LOGGER.info(log)
            # Try to parse the referral reference from the email subject (it's normally the first
            # element in the string).
            reference = self.subject.split()[0]
            if Referral.objects.current().filter(reference__iexact=reference):
                referral = Referral.objects.current().filter(reference__iexact=reference).order_by("-pk").first()
                log = f"Referral ref. {reference} is already in database; using existing referral {referral.pk}"
                LOGGER.info(log)
                self.log = self.log + f"{log}\n"
                actions.append(f"{datetime.now().isoformat()} {log}")
                self.referral = referral

                # Save the EmailedReferral as a record on the referral.
                if create_records:
                    new_record = Record.objects.create(name=self.subject, referral=referral, order_date=datetime.today())
                    file_name = f"emailed_referral_{reference}.html"
                    new_file = ContentFile(str.encode(self.body))
                    new_record.uploaded_file.save(file_name, new_file)
                    with create_revision():
                        new_record.save()
                        set_comment("Initial version.")
                    log = f"New PRS record generated: {new_record}"
                    LOGGER.info(log)
                    self.log = self.log + f"{log}\n"
                    actions.append(f"{datetime.now().isoformat()} {log}")

                    # Add records to the referral (one per attachment).
                    for emailattachment in attachments:
                        if emailattachment.name in ATTACHMENT_FILENAME_BLOCKLIST:
                            continue
                        new_record = Record.objects.create(name=emailattachment.name, referral=referral, order_date=datetime.today())
                        # Duplicate the uploaded file.
                        new_file = ContentFile(emailattachment.attachment.read())
                        new_record.uploaded_file.save(emailattachment.name, new_file)
                        new_record.save()
                        log = f"New PRS record generated: {new_record}"
                        LOGGER.info(log)
                        self.log = self.log + f"{log}\n"
                        actions.append(f"{datetime.now().isoformat()} {log}")
                        # Link the attachment to the new, generated record.
                        emailattachment.record = new_record
                        emailattachment.save()
            else:
                LOGGER.info(f"Referral ref. {reference} not found, skipping")

            LOGGER.info(f"Marking emailed referral {self.pk} as processed")
            self.processed = True
            self.save()
            LOGGER.info("Done")
            return actions

        # SCENARIO: Decision letter for an existing referral.
        if "decision letter" in self.subject.lower():
            log = f"Processing: {self.subject}"
            LOGGER.info(log)
            self.log = self.log + f"{log}\n"
            actions.append(f"{datetime.now().isoformat()} {log}")

            # Try to parse a reference number from the subject line.
            subject = self.subject.lower()
            pattern = r"application\s(.+)"
            m = re.search(pattern, subject)
            if not m:
                log = f"Skipping harvested decision letter {self.pk} (unable to find reference)"
                LOGGER.info(log)
                self.log = log
                self.processed = True
                self.save()
                actions.append(f"{datetime.now().isoformat()} {log}")
                return actions

            # We parsed a reference number from the subject line.
            reference = m.group(1)
            if not Referral.objects.current().filter(reference__iexact=reference).exists():
                log = f"Skipping harvested decision letter {self.pk} (no existing referral)"
                LOGGER.info(log)
                self.log = log
                self.processed = True
                self.save()
                actions.append(f"{datetime.now().isoformat()} {log}")
                return actions

            # We matched an existing referral.
            log = f"Referral ref. {reference} is present in database"
            LOGGER.info(log)
            self.log = self.log + f"{log}\n"
            actions.append(f"{datetime.now().isoformat()} {log}")
            referral = Referral.objects.current().filter(reference__iexact=reference).order_by("-pk").first()

            # Save the EmailedReferral as a record on the referral.
            if create_records:
                new_record = Record.objects.create(name=self.subject, referral=referral, order_date=datetime.today())
                file_name = f"emailed_referral_{reference}.html"
                new_file = ContentFile(str.encode(self.body))
                new_record.uploaded_file.save(file_name, new_file)
                with create_revision():
                    new_record.save()
                    set_comment("Initial version.")
                log = f"New PRS record generated: {new_record}"
                LOGGER.info(log)
                self.log = self.log + f"{log}\n"
                actions.append(f"{datetime.now().isoformat()} {log}")

                # Add records to the referral (one per attachment).
                for emailattachment in attachments:
                    if emailattachment.name in ATTACHMENT_FILENAME_BLOCKLIST:
                        continue
                    new_record = Record.objects.create(name=emailattachment.name, referral=referral, order_date=datetime.today())
                    # Duplicate the uploaded file.
                    new_file = ContentFile(emailattachment.attachment.read())
                    new_record.uploaded_file.save(emailattachment.name, new_file)
                    new_record.save()
                    log = f"New PRS record generated: {new_record}"
                    LOGGER.info(log)
                    self.log = self.log + f"{log}\n"
                    actions.append(f"{datetime.now().isoformat()} {log}")
                    # Link the attachment to the new, generated record.
                    emailattachment.record = new_record
                    emailattachment.save()

            # Link the emailed referral to the new or existing referral.
            LOGGER.info(f"Marking emailed referral {self.pk} as processed and linking it to {referral}")
            self.referral = referral
            self.processed = True
            self.save()
            LOGGER.info("Done")
            return actions

        # SCENARIO: a standard emailed referral.
        # Must be an attachment named 'application.xml' present to import.
        # Note that the email might be "x of y" emails, where the referral
        # attachments are too large to send as a single email.
        if not attachments.filter(name__istartswith="application.xml"):
            log = f"Skipping harvested referral {self.pk} (no XML attachment)"
            LOGGER.info(log)
            self.log = log
            self.processed = True
            self.save()
            actions.append(f"{datetime.now().isoformat()} {log}")
            return actions
        else:
            xml_file = attachments.get(name__istartswith="application.xml")

        # Parse the attached XML file.
        try:
            d = xmltodict.parse(xml_file.attachment.read())
        except Exception as e:
            log = f"Harvested referral {self.pk} parsing of application.xml failed"
            LOGGER.error(log)
            LOGGER.exception(e)
            self.log = self.log + f"{log}\n{e}\n"
            LOGGER.info(f"Marking emailed referral {self.pk} as processed")
            self.processed = True
            self.save()
            LOGGER.info("Done")
            actions.append(f"{datetime.now().isoformat()} {log}")
            return actions

        app = d["APPLICATION"]
        reference = app["WAPC_APPLICATION_NO"]

        # Determine if this is a new or existing referral.
        if Referral.objects.current().filter(reference__iexact=reference):
            # Note if the the reference no. exists in PRS already.
            log = f"Referral ref. {reference} is already in database; using existing referral"
            LOGGER.info(log)
            self.log = self.log + f"{log}\n"
            actions.append(f"{datetime.now().isoformat()} {log}")
            referral = Referral.objects.current().filter(reference__iexact=reference).order_by("-pk").first()
            referral_preexists = True
        else:
            # No match with existing references; create a new referral.
            log = f"Importing harvested referral ref. {reference} as new referral"
            LOGGER.info(log)
            self.log = f"{log}\n"
            actions.append(f"{datetime.now().isoformat()} {log}")
            referral = Referral(reference=reference)
            referral_preexists = False
            # Referral type
            if not ReferralType.objects.filter(name__istartswith=app["APP_TYPE"]).exists():
                log = f'Referral type {app["APP_TYPE"]} is not recognised type; skipping'
                LOGGER.warning(log)
                self.log = f"{log}\n"
                self.processed = True
                self.save()
                actions.append(f"{datetime.now().isoformat()} {log}")
                return actions
            else:
                referral.type = ReferralType.objects.filter(name__istartswith=app["APP_TYPE"]).first()

        # Save a new referral.
        if referral_preexists is False:
            referral.agency = dbca
            referral.referring_org = wapc
            referral.reference = reference
            referral.description = app["DEVELOPMENT_DESCRIPTION"] if "DEVELOPMENT_DESCRIPTION" in app else ""
            referral.referral_date = self.received.date()
            referral.address = app["LOCATION"] if "LOCATION" in app else ""

            # Set the LGA, if possible.
            if LocalGovernment.objects.filter(name=app["LOCAL_GOVERNMENT"]).exists():
                referral.lga = LocalGovernment.objects.filter(name=app["LOCAL_GOVERNMENT"]).first()
            else:
                log = f'LGA {app["LOCAL_GOVERNMENT"]} was not recognised'
                LOGGER.warning(log)
                self.log = self.log + f"{log}\n"
                actions.append(f"{datetime.now().isoformat()} {log}")

            with create_revision():
                referral.save()
                set_comment("Initial version.")

            log = f"New PRS referral generated: {referral}"
            LOGGER.info(log)
            self.log = self.log + f"{log}\n"
            actions.append(f"{datetime.now().isoformat()} {log}")

        # For new referrals, record any WAPC triggers.
        if referral_preexists is False:
            # Add triggers to the new referral.
            if "MRSZONE_TEXT" in app and app["MRSZONE_TEXT"]:
                triggers = [i.strip() for i in app["MRSZONE_TEXT"].split(",")]
            else:
                triggers = []
            added_trigger = False
            for i in triggers:
                # A couple of exceptions for DoP triggers follow (specific -> general trigger).
                if i.startswith("BUSH FOREVER SITE"):
                    added_trigger = True
                    referral.dop_triggers.add(DopTrigger.objects.get(name="Bush Forever site"))
                elif i.startswith("DPW ESTATE"):
                    added_trigger = True
                    referral.dop_triggers.add(DopTrigger.objects.get(name="Parks and Wildlife estate"))
                elif i.find("REGIONAL PARK") > -1:
                    added_trigger = True
                    referral.dop_triggers.add(DopTrigger.objects.get(name="Regional Park"))
                # All other triggers (don't use exists() in case of duplicates).
                elif DopTrigger.objects.current().filter(name__istartswith=i).count() == 1:
                    added_trigger = True
                    referral.dop_triggers.add(DopTrigger.objects.current().get(name__istartswith=i))
            # If we didn't link any DoP triggers, link the "No Parks and Wildlife trigger" tag.
            if not added_trigger:
                referral.dop_triggers.add(DopTrigger.objects.get(name="No Parks and Wildlife trigger"))

        # For new referrals, add locations to the referral (one per polygon in each MP geometry).
        # Obtain location geometry from Landgate SLIP.
        # Also determine the intersecting DBCA region(s).
        if create_locations and referral_preexists is False:
            locations = []
            regions = []
            # ADDRESS_DETAIL may or may not be a list :/
            if not isinstance(app["ADDRESS_DETAIL"]["DOP_ADDRESS_TYPE"], list):
                addresses = [app["ADDRESS_DETAIL"]["DOP_ADDRESS_TYPE"]]
            else:
                addresses = app["ADDRESS_DETAIL"]["DOP_ADDRESS_TYPE"]

            for a in addresses:
                # Use the long/lat info to intersect DBCA regions.
                try:
                    p = Point(x=float(a["LONGITUDE"]), y=float(a["LATITUDE"]))
                    for r in Region.objects.all():
                        if r.region_mpoly and r.region_mpoly.intersects(p) and r not in regions:
                            regions.append(r)
                    intersected_region = True
                except Exception:
                    log = f'Address long/lat could not be parsed ({a["LONGITUDE"]}, {a["LATITUDE"]})'
                    LOGGER.warning(log)
                    self.log = f"{log}\n"
                    actions.append(f"{datetime.now().isoformat()} {log}")
                    intersected_region = False

                # Use the PIN field to query SLIP for geometry.
                if "PIN" in a and a["PIN"]:
                    try:
                        resp = query_slip_esri(a["PIN"])
                        features = resp["features"]  # List of spatial features.
                        if len(features) > 0:
                            a["FEATURES"] = features
                            locations.append(a)  # A dict for each address location.
                            # If we haven't yet, use the feature geom to intersect DBCA regions.
                            if not intersected_region:
                                for f in features:
                                    att = f["attributes"]
                                    if "centroid_longitude" in att and "centroid_latitude" in att:
                                        p = Point(x=att["centroid_longitude"], y=att["centroid_latitude"])
                                        for r in Region.objects.all():
                                            if r.region_mpoly and r.region_mpoly.intersects(p) and r not in regions:
                                                regions.append(r)
                        log = f'Address PIN {a["PIN"]} returned geometry from SLIP'
                        self.log = self.log + f"{log}\n"
                        LOGGER.info(log)
                    except Exception as e:
                        log = f"Error querying Landgate SLIP for spatial data (referral ref. {reference})"
                        LOGGER.error(log)
                        LOGGER.exception(e)
                else:
                    log = f'Address PIN could not be parsed ({a["PIN"]})'
                    LOGGER.warning(log)
                    self.log = self.log + f"{log}\n"

            # Determine the intersecting DBCA region(s).
            regions = set(regions)

            # Business rules:
            # Didn't intersect a region? Might be bad geometry in the XML.
            # Likewise if >1 region was intersected, default to Swan Region.
            if len(regions) == 0:
                region = Region.objects.get(name="Swan")
                log = f"No regions were intersected, defaulting to {region}"
                LOGGER.info(log)
                self.log = self.log + f"{log}\n"
            elif len(regions) > 1:
                region = Region.objects.get(name="Swan")
                log = f">1 regions were intersected ({regions}), defaulting to {region}"
                LOGGER.info(log)
                self.log = self.log + f"{log}\n"

            if regions:
                region = regions.pop()
                referral.regions.add(region)

            # Create new location objects.
            new_locations = []
            for l in locations:
                for feature in l["FEATURES"]:
                    poly = Polygon(feature["geometry"]["rings"][0])
                    geom = GEOSGeometry(poly.wkt)
                    new_loc = Location(
                        address_suffix=l["NUMBER_FROM_SUFFIX"],
                        road_name=l["STREET_NAME"],
                        road_suffix=l["STREET_SUFFIX"],
                        locality=l["SUBURB"],
                        postcode=l["POSTCODE"],
                        referral=referral,
                        poly=geom,
                    )
                    try:  # NUMBER_FROM XML fields started to contain non-integer values :(
                        new_loc.address_no = int(l["NUMBER_FROM"]) if l["NUMBER_FROM"] else None
                    except:
                        pass  # Just ignore the value if it can't be parsed as an integer.
                    with create_revision():
                        try:
                            new_loc.save()
                            set_comment("Initial version.")
                        except:
                            LOGGER.error(f"Create Location failed (data: {l})")
                            continue
                    new_locations.append(new_loc)
                    log = f"New PRS location generated: {new_loc}"
                    LOGGER.info(log)
                    self.log = self.log + f"{log}\n"
                    actions.append(f"{datetime.now().isoformat()} {log}")

            # Check to see if new locations intersect with any existing locations.
            intersecting = []
            for l in new_locations:
                other_l = Location.objects.current().exclude(pk=l.pk).filter(poly__isnull=False, poly__intersects=l.poly)
                if other_l.exists():
                    intersecting += list(other_l)
            # For any intersecting locations, relate the new and existing referrals.
            for l in intersecting:
                if l.referral.pk != referral.pk:
                    referral.add_relationship(l.referral)
                    log = f"New referral {referral.pk} related to existing referral {l.referral.pk}"
                    LOGGER.info(log)
                    self.log = self.log + f"{log}\n"
                    actions.append(f"{datetime.now().isoformat()} {log}")

        # New referrals only: create an "Assess a referral" task and assign it to a user.
        if create_tasks and referral_preexists is False:
            assess_task = TaskType.objects.get(name="Assess a referral")

            # If a task assignee has not been specified, try to determine one from the region default.
            if not assignee:
                if region and RegionAssignee.objects.filter(region=region).exists():
                    assignee_default = RegionAssignee.objects.get(region=region).user
                else:
                    assignee_default = User.objects.get(username=settings.REFERRAL_ASSIGNEE_FALLBACK)
                    log = f"No task assignee set, defaulting to {assignee_default}"
                    LOGGER.info(log)
                    self.log = self.log + f"{log}\n"
                    actions.append(f"{datetime.now().isoformat()} {log}")
            else:
                assignee_default = assignee

            new_task = Task(
                type=assess_task,
                referral=referral,
                start_date=referral.referral_date,
                description=referral.description,
                assigned_user=assignee_default,
            )
            new_task.state = assess_task.initial_state
            if "DUE_DATE" in app and app["DUE_DATE"]:
                try:
                    due = datetime.strptime(app["DUE_DATE"], "%d-%b-%y")
                except Exception:
                    due = datetime.today() + timedelta(assess_task.target_days)
            else:
                due = datetime.today() + timedelta(assess_task.target_days)
            new_task.due_date = due
            with create_revision():
                new_task.save()
                set_comment("Initial version.")
            log = f"New PRS task generated: {new_task} assigned to {assignee_default.get_full_name()}"
            LOGGER.info(log)
            self.log = self.log + f"{log}\n"
            actions.append(f"{datetime.now().isoformat()} {log}")

            # Email the assigned user about the new task.
            new_task.email_user()
            log = f"Task assignment email sent to {assignee_default.email}"
            LOGGER.info(log)
            self.log = self.log + f"{log}\n"
            actions.append(f"{datetime.now().isoformat()} {log}")

        log = f"Emailed referral {self} includes {attachments.count()} attachments"
        LOGGER.info(log)
        actions.append(log)

        # Save the EmailedReferral as a record on the new or existing referral.
        if create_records:
            new_record = Record.objects.create(name=self.subject, referral=referral, order_date=datetime.today())
            file_name = f"emailed_referral_{reference}.html"
            new_file = ContentFile(str.encode(self.body))
            new_record.uploaded_file.save(file_name, new_file)
            with create_revision():
                new_record.save()
                set_comment("Initial version.")
            log = f"New PRS record generated for the referral: {new_record}"
            LOGGER.info(log)
            self.log = self.log + f"{log}\n"
            actions.append(f"{datetime.now().isoformat()} {log}")

            # Add records to the referral (one per attachment).
            for emailattachment in attachments:
                if emailattachment.name in ATTACHMENT_FILENAME_BLOCKLIST:
                    continue
                new_record = Record.objects.create(
                    name=emailattachment.name,
                    referral=referral,
                    order_date=datetime.today(),
                )
                # Duplicate the uploaded file.
                new_file = ContentFile(emailattachment.attachment.read())
                new_record.uploaded_file.save(emailattachment.name, new_file)
                new_record.save()
                log = f"New PRS record generated for the attachment: {new_record}"
                LOGGER.info(log)
                self.log = self.log + f"{log}\n"
                actions.append(f"{datetime.now().isoformat()} {log}")
                # Link the attachment to the new, generated record.
                emailattachment.record = new_record
                emailattachment.save()

        # Link the emailed referral to the new or existing referral.
        LOGGER.info(f"Marking emailed referral {self.pk} as processed and linking it to {referral}")
        self.referral = referral
        self.processed = True
        self.save()
        LOGGER.info("Done")
        return actions


class EmailAttachment(models.Model):
    """A saved email file attachment."""

    emailed_referral = models.ForeignKey(EmailedReferral, on_delete=models.CASCADE)
    name = models.CharField(max_length=512)
    attachment = models.FileField(max_length=255, upload_to="email_attachments/%Y/%m/%d")
    record = models.ForeignKey(Record, null=True, blank=True, on_delete=models.SET_NULL)

    def __str__(self):
        return self.name

    def get_xml_data(self):
        """Convenience function to conditionally return XML data from the attachment.xml (returns None otherwise)."""
        d = None
        if self.name.lower() == "application.xml":
            self.attachment.seek(0)
            d = xmltodict.parse(self.attachment.read())
        return d


class RegionAssignee(models.Model):
    """A model to define which user will be assigned any generated referrals
    for a region.
    """

    region = models.OneToOneField(Region, on_delete=models.CASCADE)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        limit_choices_to={"groups__name__in": ["PRS user"], "is_active": True},
        help_text="Default assigned user for this region.",
    )

    def __str__(self):
        if self.user:
            return f"{self.region} -> {self.user.get_full_name()}"
        else:
            return f"{self.region} -> none"

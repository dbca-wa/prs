import logging
import os
from copy import copy
from datetime import date
from tempfile import NamedTemporaryFile

import reversion
from django.conf import settings
from django.contrib.gis.db import models
from django.contrib.gis.geos import GeometryCollection
from django.contrib.postgres.fields import ArrayField
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.core.mail import EmailMultiAlternatives
from django.core.validators import MaxLengthValidator
from django.db.models import Q
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.html import escape, format_html
from django.utils.safestring import mark_safe
from extract_msg import Message
from geojson import Feature, FeatureCollection, Polygon, dumps
from indexer.utils import get_typesense_client
from lxml.html import fromstring
from lxml_html_clean import clean_html
from pygeopkg.conversion.to_geopkg_geom import make_gpkg_geom_header, point_lists_to_gpkg_polygon
from pygeopkg.core.field import Field
from pygeopkg.core.geopkg import GeoPackage
from pygeopkg.core.srs import SRS
from pygeopkg.shared.constants import SHAPE
from pygeopkg.shared.enumeration import GeometryType, SQLFieldTypes
from referral.base import ActiveModel, Audit
from referral.tasks import index_object, index_record
from referral.utils import as_row_subtract_referral_cell, dewordify_text, search_document_normalise, smart_truncate
from taggit.managers import TaggableManager
from typesense.exceptions import ObjectNotFound
from unidecode import unidecode

LOGGER = logging.getLogger("prs")
# Australian state choices, for addresses.
AU_STATE_CHOICES = (
    (1, "ACT"),
    (2, "NSW"),
    (3, "NT"),
    (4, "QLD"),
    (5, "SA"),
    (6, "TAS"),
    (7, "VIC"),
    (8, "WA"),
)


class ReferralLookup(ActiveModel, Audit):
    """Abstract model type for lookup-table objects."""

    name = models.CharField(max_length=200)
    description = models.CharField(max_length=200, null=True, blank=True, validators=[MaxLengthValidator(200)])
    slug = models.SlugField(unique=True, help_text="Must be unique. Automatically generated from name.")
    public = models.BooleanField(default=True, help_text="Is this lookup selection available to all users?")

    class Meta:
        abstract = True
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        """Overide save() to cleanse text input fields."""
        self.name = unidecode(self.name)
        if self.description:
            self.description = unidecode(self.description)
        super().save(*args, **kwargs)

    @classmethod
    def get_headers(cls):
        """Return a list of string values as headers for any list view."""
        return ["Name", "Description", "Last modified"]

    def get_absolute_url(self):
        return reverse(
            "prs_object_detail",
            kwargs={
                "model": self._meta.verbose_name_plural.lower().replace(" ", ""),
                "pk": self.pk,
            },
        )

    def as_row(self):
        """
        Returns a string of HTML that renders the object details as table row cells.
        Remember to enclose output of this function in <tr> tags.
        """
        template = """<td><a href="{url}">{name}</a></td>
            <td>{description}</td>
            <td><span style="display:none">{modified_ts} </span>{modified}</td>"""
        d = copy(self.__dict__)
        d["url"] = self.get_absolute_url()
        if self.description:
            d["description"] = unidecode(self.description)
        else:
            d["description"] = ""
        d["modified"] = self.modified.strftime("%d %b %Y")
        d["modified_ts"] = self.modified.isoformat()
        return format_html(template, **d)

    def as_tbody(self):
        """
        Returns a string of HTML to render the object details inside <tbody> tags.
        """
        template = """<tr><th>ID</th><td>{id}</td></tr>
            <tr><th>Name</th><td>{name}</td></tr>
            <tr><th>Description</th><td>{description}</td></tr>
            <tr><th>Date created</th><td>{created}</td></tr>
            <tr><th>Created by</th><td>{creator}</td</tr>
            <tr><th>Last modified</th><td>{modified}</td></tr>
            <tr><th>Last changed by</th><td>{modifier}</td></tr>"""
        d = copy(self.__dict__)
        d["created"] = self.created.strftime("%d-%b-%Y")
        d["creator"] = self.creator.get_full_name()
        d["modified"] = self.modified.strftime("%d-%b-%Y")
        d["modifier"] = self.modifier.get_full_name()
        return format_html(template, **d)


class DopTrigger(ReferralLookup):
    """
    Lookup table of Dept of Planning triggers.
    """

    class Meta(ReferralLookup.Meta):
        verbose_name = "DoP trigger"


class Region(ReferralLookup):
    """
    Lookup table of DPaW regions.
    """

    region_mpoly = models.MultiPolygonField(srid=4283, null=True, blank=True, help_text="Optional.")


class LocalGovernment(ReferralLookup):
    """Lookup table of Local Government Authority name."""

    pass


class OrganisationType(ReferralLookup):
    """
    Lookup table for Organistion types.
    """

    pass


class Organisation(ReferralLookup):
    """
    Lookup table of Organisations that send planning referrals to the department.
    """

    type = models.ForeignKey(OrganisationType, on_delete=models.PROTECT, help_text="The organisation type.")
    list_name = models.CharField(
        max_length=100,
        help_text="""Name as it will appear in the alphabetised selection lists (e.g. "Broome,
            Shire of"). Put acronyms (e.g. OEPA) at the end.""",
        validators=[MaxLengthValidator(100)],
    )
    telephone = models.CharField(max_length=20, null=True, blank=True, help_text="Include the area code.")
    fax = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        help_text="Include the area code.",
        validators=[MaxLengthValidator(20)],
    )
    email = models.EmailField(null=True, blank=True)
    address1 = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="Address line 1",
        help_text="Postal address (optional). Maximum 100 characters.",
        validators=[MaxLengthValidator(100)],
    )
    address2 = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="Address line 2",
        help_text="Postal address line 2 (optional). Maximum 100 characters.",
        validators=[MaxLengthValidator(100)],
    )
    suburb = models.CharField(max_length=100, null=True, blank=True, validators=[MaxLengthValidator(100)])
    state = models.IntegerField(choices=AU_STATE_CHOICES, default=8)
    postcode = models.CharField(max_length=4, null=True, blank=True, validators=[MaxLengthValidator(4)])
    # Use alt_model_name when we don't want to override Meta verbose_name.
    alt_model_name = "referring organisation"

    def as_tbody(self):
        """
        Returns a string of HTML to render the object details inside <tbody> tags.
        """
        template = """<tr><th>Name</th><td>{name}</td></tr>
            <tr><th>Description</th><td>{description}</td></tr>
            <tr><th>Type</th><td>{type}</td></tr>
            <tr><th>List name</th><td>{list_name}</td></tr>
            <tr><th>Telephone</th><td>{telephone}</td></tr>
            <tr><th>Fax</th><td>{fax}</td></tr>
            <tr><th>Email</th><td>{email}</td></tr>
            <tr><th>Address</th><td>{address1}</td></tr>
            <tr><th></th><td>{address2}</td></tr>
            <tr><th>Suburb</th><td>{suburb}</td></tr>
            <tr><th>State</th><td>{state}</td></tr>
            <tr><th>Postcode</th><td>{postcode}</td></tr>
            <tr><th>Date created</th><td>{created}</td></tr>
            <tr><th>Created by</th><td>{creator}</td</tr>
            <tr><th>Last modified</th><td>{modified}</td></tr>
            <tr><th>Last changed by</th><td>{modifier}</td></tr>"""
        d = copy(self.__dict__)
        d["type"] = self.type.name
        d["created"] = self.created.strftime("%d-%b-%Y")
        d["creator"] = self.creator.get_full_name()
        d["modified"] = self.modified.strftime("%d-%b-%Y")
        d["modifier"] = self.modifier.get_full_name()
        d["address2"] = d["address2"] or "&nbsp;"
        d["state"] = self.get_state_display()
        return format_html(template, **d)


class TaskState(ReferralLookup):
    """
    Lookup table of all the defined states/outcomes for tasks.
    Includes descriptions e.g. "In progress", "Stopped" as well as outcomes e.g.
    "Response with advice", "Cancelled".
    A boolean field (is_active) is used to separate outcomes indicating the task
    remains active.
    A boolean field (is_assessment) is used to separate descriptions from
    assessments.
    Tasks can be:
    * ongoing and not an assessment (e.g. In progress)
    * ongoing and an assessment (e.g. Deferred)
    * not ongoing and not an assessment (e.g. Stopped, Cancelled)
    * not ongoing and an assessment (e.g. Response with advice, Response with
      objection)
    """

    task_type = models.ForeignKey(
        "TaskType",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        help_text="Optional - does this state relate to a single task type only?",
    )
    is_ongoing = models.BooleanField(
        default=True,
        help_text="Does this task state indicate that the task remains active?",
    )
    is_assessment = models.BooleanField(
        default=False,
        help_text="Does this task state represent an assessment by staff?",
    )


class TaskType(ReferralLookup):
    """
    Lookup table of the types of user tasks that can be recorded in the database.
    All task types have a default initial status and time limit.
    Due date is required in tasks, but if the user doesn't supply it then we need
    something to fall back on. This is an arbitrary number which can be changed
    for each type.
    """

    initial_state = models.ForeignKey(
        TaskState,
        on_delete=models.PROTECT,
        limit_choices_to=Q(effective_to__isnull=True),
        help_text="The initial state for this task type.",
    )
    target_days = models.IntegerField(
        default=35,
        help_text="Time limit to fall back on if there is no user-supplied due date.",
    )


class ReferralType(ReferralLookup):
    """
    Lookup table of the types of planning referrals that can be registered in the
    database.
    Having a "default" task type is not essential, though highly recommended.
    """

    initial_task = models.ForeignKey(
        TaskType,
        on_delete=models.PROTECT,
        limit_choices_to=Q(effective_to__isnull=True),
        null=True,
        blank=True,
        help_text="Optional, but highly recommended.",
    )


class NoteType(ReferralLookup):
    """
    Lookup field for Note model type - e.g. email, letter, conversation. Not meant
    to be accessed anywhere but the Admin site.
    """

    # TODO: deprecate model and replace with static method.

    icon = models.ImageField(upload_to="img", blank=True, null=True)


class Agency(ReferralLookup):
    """
    Lookup field to distinguish different govt Agencies by acronym (DBCA, DWER, etc.)
    """

    # TODO: deprecate model (unused).

    code = models.CharField(max_length=16)

    class Meta(ReferralLookup.Meta):
        verbose_name_plural = "agencies"


class ReferralBaseModel(ActiveModel, Audit):
    """
    Base abstract model class for object types that are not lookups.
    """

    class Meta:
        abstract = True
        ordering = ["-created"]

    def __str__(self):
        return f"{self._meta.object_name} {self.pk}"

    def get_absolute_url(self):
        return reverse(
            "prs_object_detail",
            kwargs={
                "model": self._meta.verbose_name_plural.lower().replace(" ", ""),
                "pk": self.pk,
            },
        )

    @classmethod
    def get_tools_template(cls):
        """Return the path to a model class template include."""
        return f"referral/{cls._meta.model_name}_tools.html"


@reversion.register()
class Referral(ReferralBaseModel):
    """
    A planning referral which has been sent to the department for comment.
    """

    type = models.ForeignKey(
        ReferralType,
        on_delete=models.PROTECT,
        verbose_name="referral type",
        help_text="""[Searchable] The referral type; explanation of these categories is also found
            in the <a href="/help/">PRS User documentation</a>.""",
    )
    agency = models.ForeignKey(
        Agency,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        help_text="[Searchable] The agency to which this referral relates.",
    )
    regions = models.ManyToManyField(
        Region,
        related_name="regions",
        blank=True,
        help_text="[Searchable] The region(s) in which this referral belongs.",
    )
    regions_str = models.CharField(max_length=256, blank=True, null=True, editable=False)
    referring_org = models.ForeignKey(
        Organisation,
        on_delete=models.PROTECT,
        verbose_name="referring organisation",
        help_text="[Searchable] The referring organisation or individual.",
    )
    reference = models.CharField(
        max_length=100,
        validators=[MaxLengthValidator(100)],
        help_text="[Searchable] Referrer's reference no. Maximum 100 characters.",
    )
    file_no = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        validators=[MaxLengthValidator(100)],
        help_text="[Searchable] The DPaW file this referral is filed within. Maximum 100 characters.",
    )
    description = models.TextField(blank=True, null=True, help_text="[Searchable] Optional.")
    referral_date = models.DateField(verbose_name="received date", help_text="Date that the referral was received.")
    address = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        validators=[MaxLengthValidator(200)],
        help_text="[Searchable] Physical address of the planning proposal. Maximum 200 characters.",
    )
    point = models.PointField(srid=4283, blank=True, null=True, editable=False, help_text="Optional.")
    dop_triggers = models.ManyToManyField(
        DopTrigger,
        related_name="dop_triggers",
        blank=True,
        verbose_name="DoP triggers",
        help_text="[Searchable] The Department of Planning trigger(s) for this referral.",
    )
    tags = TaggableManager(
        blank=True,
        verbose_name="Issues/tags",
        help_text="[Searchable] A list of issues or tags.",
    )
    related_refs = models.ManyToManyField(
        "self",
        through="RelatedReferral",
        editable=False,
        symmetrical=False,
        related_name="related_referrals",
    )
    lga = models.ForeignKey(
        LocalGovernment,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        verbose_name="local government",
        help_text="[Searchable] The LGA in which this referral resides.",
    )
    search_document = models.TextField(blank=True, null=True, editable=False)
    search_vector = SearchVectorField(null=True, editable=False)

    class Meta:
        ordering = ["-created"]
        indexes = [GinIndex(fields=["search_vector"], name="idx_referral_search_vector")]

    @classmethod
    def get_headers(cls):
        """Return a list of string values as headers for any list view."""
        return [
            "Referral ID",
            "Received date",
            "Description",
            "Address",
            "Referrer's reference",
            "Referred by",
            "Region(s)",
            "Type",
        ]

    def save(self, *args, **kwargs):
        """Overide save to cleanse text input to the description, address fields.
        Set the point field value based on any assocated Location objects to the centroid.
        Update the search_document field value for search purposes.
        """
        if self.address:
            self.address = unidecode(self.address)
        # We need a PK to call self.location_set
        if self.pk and self.location_set.current().exists():
            collection = GeometryCollection([l.poly for l in self.location_set.current() if l.poly])
            self.point = collection.centroid
        # Update the regions_str field (only if the object already has a PK).
        if self.pk:
            self.regions_str = self.get_regions_str()

        self.search_document = f"{self.reference} {self.type.name} {self.referring_org.name} {self.address or ''} {self.file_no or ''} {self.description or ''}"
        self.search_document = search_document_normalise(self.search_document)

        super().save(*args, **kwargs)

        # Index the referral.
        try:
            index_object.delay_on_commit(pk=self.pk, model="referral")
        except Exception:
            # Indexing failure should never block or return an exception. Log the error to stdout.
            LOGGER.exception(f"Error during indexing referral {self}")

    def get_absolute_url(self):
        return reverse("referral_detail", kwargs={"pk": self.pk})

    def get_regions_str(self):
        """
        Return a unicode string of all the regions that this referral belongs to (or None).
        """
        if not self.regions.current().exists():
            return None
        return ", ".join([r.name for r in self.regions.current()])

    @property
    def dop_triggers_str(self):
        """
        Return a unicode string of all the DoP Triggers that this referral has (or None).
        """
        if not self.dop_triggers.all():
            return None
        return ", ".join([r.name for r in self.dop_triggers.all()])

    @property
    def has_location(self):
        """Returns True if Locations exist on this referral, else False."""
        return self.location_set.current().exists()

    @property
    def has_condition(self):
        """Returns True if Conditions exist on this referral, else False."""
        return self.condition_set.current().exists()

    @property
    def has_proposed_condition(self):
        """Checks if Task has 'Proposed Condition' text"""
        return self.has_condition and any(c.proposed_condition for c in self.condition_set.current())

    def as_row(self):
        """
        Returns a string of HTML that renders the object details as table row cells.
        Remember to enclose this function in <tr> tags.
        """
        template = """<td><a href="{url}">{id}</a></td>
            <td><span style="display:none">{referral_date_ts} </span>{referral_date}</td>
            <td>{description}</td></td>
            <td>{address}</td>
            <td>{reference}</td>
            <td>{referring_org}</td>
            <td>{regions}</td>
            <td>{type}</td>"""
        d = copy(self.__dict__)
        d["url"] = self.get_absolute_url()
        d["type"] = self.type.name
        d["regions"] = self.regions_str or self.get_regions_str()
        d["referring_org"] = self.referring_org
        if self.referral_date:
            d["referral_date"] = self.referral_date.strftime("%d %b %Y")
            d["referral_date_ts"] = self.referral_date.isoformat()
        else:
            d["referral_date"] = ""
            d["referral_date_ts"] = ""
        if self.address:
            d["address"] = unidecode(self.address)
        else:
            d["address"] = ""
        if self.description:
            d["description"] = smart_truncate(self.description, length=200)
        else:
            d["description"] = ""
        return format_html(template, **d)

    def as_tbody(self):
        """
        Returns a string of HTML to render the object details inside <tbody> tags.
        """
        template = """<tr><th>Referral ID</th><td><a href="{url}">{id}</a></td></tr>
            <tr><th>Referrer's reference</th><td>{reference}</td></tr>
            <tr><th>Description</th><td>{description}</td></tr>
            <tr><th>Address</th><td>{address}</td></tr>
            <tr><th>Local Government</th><td>{lga}</td></tr>
            <tr><th>Referrer</th><td>{referring_org}</td></tr>
            <tr><th>Received date</th><td>{referral_date}</td></tr>
            <tr><th>Type</th><td>{type}</td></tr>
            <tr><th>Region(s)</th><td>{regions}</td></tr>
            <tr><th>DoP Trigger(s)</th><td>{dop_triggers}</td></tr>
            <tr><th>File no.</th><td>{file_no}</td></tr>"""
        d = copy(self.__dict__)
        d["url"] = self.get_absolute_url()
        d["type"] = self.type.name
        d["regions"] = self.regions_str or self.get_regions_str()
        d["dop_triggers"] = self.dop_triggers_str
        d["referring_org"] = self.referring_org
        d["file_no"] = self.file_no or ""
        if self.description:
            d["description"] = unidecode(self.description)
        else:
            d["description"] = ""
        d["referral_date"] = self.referral_date.strftime("%d-%b-%Y")
        if self.address:
            d["address"] = unidecode(self.address)
        else:
            d["address"] = ""
        d["lga"] = self.lga.name if self.lga else ""
        return format_html(template, **d)

    def add_relationship(self, referral):
        # Disallow self-referential relationships:
        if self == referral:
            return None
        else:
            forward_rel, created = RelatedReferral.objects.get_or_create(from_referral=self, to_referral=referral)
            backward_rel, created = RelatedReferral.objects.get_or_create(from_referral=referral, to_referral=self)
            return forward_rel

    def remove_relationship(self, referral):
        qs1 = RelatedReferral.objects.filter(from_referral=self, to_referral=referral)
        qs2 = RelatedReferral.objects.filter(from_referral=referral, to_referral=self)

        if qs1 or qs2:
            qs1.delete()
            qs2.delete()
            return True
        return False

    def generate_qgis_layer(self, template="qgis_layer_v3-40"):
        """Generates and returns the content for a QGIS layer definition.
        Optionally specify the name of the template (defaults to the v3.40
        compatible template).
        """
        # Only return a value for a referral with child locations.
        if not self.location_set.current().filter(poly__isnull=False).exists():
            return None
        xml = f"referral/{template}.xml"
        return render_to_string(
            xml,
            {
                "REFERRAL_PK": self.pk,
                "GEOSERVER_URL": f"{settings.GEOSERVER_URL}/ows",
                "PRS_LAYER_NAME": f"{settings.PRS_LAYER_NAME}",
            },
        )

    def generate_gpkg(self, source_url=""):
        """Generates and returns a Geopackage file-like object."""
        tmp = NamedTemporaryFile()
        gpkg = GeoPackage.create(tmp.name, flavor="EPSG")
        srs_wkt = 'GEOGCS["WGS 84",DATUM["WGS_1984",SPHEROID["WGS 84",6378137,298.257223563,AUTHORITY["EPSG","7030"]],AUTHORITY["EPSG","6326"]],PRIMEM["Greenwich",0,AUTHORITY["EPSG","8901"]],UNIT["degree",0.0174532925199433,AUTHORITY["EPSG","9122"]],AUTHORITY["EPSG","4326"]]'
        srs = SRS("WGS 84", "EPSG", 4326, srs_wkt)
        fields = (
            Field("referral", SQLFieldTypes.integer),
            Field("referral_type", SQLFieldTypes.text),
            Field("referral_reference", SQLFieldTypes.text),
            Field("referring_org", SQLFieldTypes.text),
            Field("source_url", SQLFieldTypes.text),
        )
        fc = gpkg.create_feature_class("prs_referrals", srs, fields=fields, shape_type=GeometryType.polygon)
        field_names = [
            SHAPE,
            "referral",
            "referral_type",
            "referral_reference",
            "referring_org",
            "source_url",
        ]
        rows = []
        # We have to use the point_lists_to_gpkg_polygon function to insert WKB into the geopkg.
        hdr = make_gpkg_geom_header(4326)
        for loc in self.location_set.current().filter(poly__isnull=False):
            gpkg_wkb = point_lists_to_gpkg_polygon(hdr, loc.poly.coords)
            rows.append(
                (
                    gpkg_wkb,
                    loc.referral.pk,
                    loc.referral.type.name,
                    loc.referral.reference,
                    loc.referral.referring_org.name,
                    source_url,
                )
            )
        fc.insert_rows(field_names, rows)
        resp = open(tmp.name, "rb").read()
        tmp.close()
        return resp  # Return the gpkg content.

    def generate_geojson(self, source_url=""):
        """Generates and returns GeoJSON."""
        features = []
        for loc in self.location_set.current().filter(poly__isnull=False):
            features.append(
                Feature(
                    geometry=Polygon(loc.poly.coords),
                    properties={
                        "referral": loc.referral.pk,
                        "referral_type": loc.referral.type.name,
                        "referral_reference": loc.referral.reference,
                        "referring_org": loc.referral.referring_org.name,
                        "source_url": source_url,
                    },
                )
            )
        return dumps(FeatureCollection(features))


class RelatedReferral(models.Model):
    """
    Intermediate class for relationships between Referral objects.
    Trying to create this relationship without the intermediate class generated
    some really odd recursion errors.
    """

    from_referral = models.ForeignKey(Referral, on_delete=models.PROTECT, related_name="from_referral")
    to_referral = models.ForeignKey(Referral, on_delete=models.PROTECT, related_name="to_referral")

    def __str__(self):
        return f"{self.pk} ({self.from_referral.pk} to {self.to_referral.pk})"


@reversion.register()
class Task(ReferralBaseModel):
    """
    Tasks that must be completed by users. Added against individual Referrals.
    This is how we record and manage our workflow.
    """

    type = models.ForeignKey(
        TaskType,
        on_delete=models.PROTECT,
        verbose_name="task type",
        help_text="The task type.",
    )
    referral = models.ForeignKey(Referral, on_delete=models.PROTECT)
    assigned_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="refer_task_assigned_user",
        help_text="The officer responsible for completing the task.",
    )
    description = models.TextField(blank=True, null=True, help_text="Description of the task requirements.")
    start_date = models.DateField(blank=True, null=True, help_text="Date on which this task was started.")
    due_date = models.DateField(blank=True, null=True, help_text="Date by which the task must be completed.")
    complete_date = models.DateField(
        blank=True,
        null=True,
        verbose_name="completed date",
        help_text="Date that the task was completed.",
    )
    stop_date = models.DateField(blank=True, null=True, help_text="Date that the task was stopped.")
    restart_date = models.DateField(blank=True, null=True, help_text="Date that a stopped task was restarted.")
    stop_time = models.IntegerField(default=0, editable=False, help_text="Cumulative time stopped in days.")
    state = models.ForeignKey(
        TaskState,
        on_delete=models.PROTECT,
        verbose_name="status",
        help_text="The status of the task.",
    )
    records = models.ManyToManyField("Record", blank=True)
    notes = models.ManyToManyField("Note", blank=True)
    search_document = models.TextField(blank=True, null=True, editable=False)
    search_vector = SearchVectorField(null=True, editable=False)

    class Meta:
        ordering = ["-pk", "due_date"]
        indexes = [GinIndex(fields=["search_vector"], name="idx_task_search_vector")]

    @classmethod
    def get_headers(cls):
        """Return a list of string values as headers for any list view."""
        return [
            "Task ID",
            "Type",
            "Task description",
            "Address",
            "Referral ID",
            "Assigned",
            "Start",
            "Due",
            "Completed",
            "Status",
        ]

    @classmethod
    def get_headers_site_home(cls):
        return [
            "Type",
            "Task description",
            "Referral ID",
            "Referral type",
            "Referrer",
            "Referrers reference",
            "Due",
            "Actions",
        ]

    def save(self, *args, **kwargs):
        """Overide save() to cleanse and populate the search_document field."""
        self.search_document = f"{self.type.name} {self.description or ''}"
        self.search_document = search_document_normalise(self.search_document)

        super().save(*args, **kwargs)

        # Index the task.
        try:
            index_object.delay_on_commit(pk=self.pk, model="task")
        except Exception:
            # Indexing failure should never block or return an exception. Log the error to stdout.
            LOGGER.exception(f"Error during indexing task {self}")

    def as_row(self):
        """
        Returns a string of HTML that renders the object details as table row cells.
        Remember to enclose this function in <tr> tags.
        """
        template = """<td><a href="{url}">{id}</a></td>
            <td>{type}</td>
            <td>{description}</td>
            <td>{address}</td>
            <td class="referral-id-cell"><a href="{referral_url}">{referral_id}</a></td>
            <td>{assigned_user}</td>
            <td><span style="display:none">{start_date_ts} </span>{start_date}</td>
            <td><span style="display:none">{due_date_ts} </span>{due_date}</td>
            <td><span style="display:none">{complete_date_ts} </span>{complete_date}</td>
            <td>{state}</td>"""
        d = copy(self.__dict__)
        d["url"] = self.get_absolute_url()
        d["type"] = self.type.name
        if self.description:
            d["description"] = smart_truncate(self.description, length=200)
        else:
            d["description"] = ""
        d["address"] = self.referral.address or ""
        d["referral_url"] = self.referral.get_absolute_url()
        d["referral_id"] = self.referral.pk
        d["assigned_user"] = self.assigned_user.get_full_name()
        if self.start_date:
            d["start_date"] = self.start_date.strftime("%d %b %Y")
            d["start_date_ts"] = self.start_date.isoformat()
        else:
            d["start_date"] = ""
            d["start_date_ts"] = ""
        if self.due_date:
            d["due_date"] = self.due_date.strftime("%d %b %Y")
            d["due_date_ts"] = self.due_date.isoformat()
        else:
            d["due_date"] = ""
            d["due_date_ts"] = ""
        if self.complete_date:
            d["complete_date"] = self.complete_date.strftime("%d %b %Y")
            d["complete_date_ts"] = self.complete_date.isoformat()
        else:
            d["complete_date"] = ""
            d["complete_date_ts"] = ""
        d["state"] = self.state
        return format_html(template, **d)

    def as_row_actions(self):
        """Returns a HTML table cell containing icons with links to suitable
        actions for the task object (e.g. stop/start, complete, etc.)
        """
        d = copy(self.__dict__)
        if self.state.name == "Stopped":
            template = """<td><a href="{start_url}" title="Start"><i class="fa fa-play"></i></a></td>"""
            d["start_url"] = reverse("task_action", kwargs={"pk": self.pk, "action": "start"})
        elif not self.complete_date:
            template = """<td><a href="{edit_url}" title="Edit"><i class="far fa-edit"></i></a>"""
            template += """ <a href="{complete_url}" title="Complete"><i class="far fa-check-circle"></i></a>"""
            template += """
                <a href="{stop_url}" title="Stop"><i class="fa fa-stop"></i></a>
                <a href="{reassign_url}" title="Reassign"><i class="fa fa-share"></i></a>
                <a href="{cancel_url}" title="Cancel"><i class="fa fa-ban"></i></a>
                <a href="{delete_url}" title="Delete"><i class="far fa-trash-alt"></i></a></td>"""
            d["edit_url"] = reverse("task_action", kwargs={"pk": self.pk, "action": "update"})
            d["reassign_url"] = reverse("task_action", kwargs={"pk": self.pk, "action": "reassign"})
            d["complete_url"] = reverse("task_action", kwargs={"pk": self.pk, "action": "complete"})
            d["stop_url"] = reverse("task_action", kwargs={"pk": self.pk, "action": "stop"})
            d["cancel_url"] = reverse("task_action", kwargs={"pk": self.pk, "action": "cancel"})
            d["delete_url"] = reverse("prs_object_delete", kwargs={"pk": self.pk, "model": "tasks"})
        else:
            template = "<td></td>"
        return format_html(template, **d)

    def as_row_minus_referral(self):
        """
        Removes the HTML cell containing the parent referral details.
        """
        return as_row_subtract_referral_cell(self.as_row())

    @property
    def is_overdue(self):
        """
        Checks whether the task is overdue and returns True if so.
        """
        if self.due_date and self.due_date < date.today():
            return True
        else:
            return False

    @property
    def is_stopped(self):
        """
        Return True if the task is stopped.
        """
        if self.state.name == "Stopped":
            return True
        else:
            return False

    def as_row_for_site_home(self):
        """Similar to as_row_with_actions(), but this returns a different set
        of values as a row for the site home view.
        """
        template = "<td>{type}</td>"
        if self.referral.address:  # If the referral has an address, include it in the description field.
            template += "<td>{description}<br><b>Address: </b>{address}</td>"
        else:
            template += "<td>{description}</td>"
        template += """<td><a href="{referral_url}">{referral_pk}</a></td>
            <td>{type}</td>
            <td>{referring_org}</td>
            <td>{reference}</td>
            <td><span style="display:none">{due_date_ts} </span>{due_date}</td>"""
        if self.is_stopped:  # Render a different set of action icons if the task is stopped.
            template += """<td class="action-icons-cell">
                <a href="{start_url}" title="Start"><i class="fa fa-play"></i></a></td>"""
        elif not self.complete_date:  # Render icons if the task is not completed.
            template += """<td class="action-icons-cell">
                <a href="{complete_url}" title="Complete"><i class="far fa-check-circle"></i></a>
                <a href="{stop_url}" title="Stop"><i class="fa fa-stop"></i></a>
                <a href="{reassign_url}" title="Reassign"><i class="fa fa-share"></i></a>
                <a href="{cancel_url}" title="Cancel"><i class="fa fa-ban"></i></a>"""
        else:  # Render an empty table cell.
            template += '<td class="action-icons-cell"></td>'
        d = copy(self.__dict__)
        d["type"] = self.type.name
        if self.description:
            d["description"] = smart_truncate(self.description, length=200)
        else:
            d["description"] = ""
        d["referral_url"] = self.referral.get_absolute_url()
        d["referral_pk"] = self.referral.pk
        d["referring_org"] = self.referral.referring_org
        d["reference"] = self.referral.reference
        if self.referral.address:
            d["address"] = unidecode(self.referral.address)
        else:
            d["address"] = ""
        if self.due_date:
            d["due_date"] = self.due_date.strftime("%d %b %Y")
            d["due_date_ts"] = self.due_date.isoformat()
        else:
            d["due_date"] = ""
            d["due_date_ts"] = ""
        d["start_url"] = reverse("task_action", kwargs={"pk": self.pk, "action": "start"})
        d["complete_url"] = reverse("task_action", kwargs={"pk": self.pk, "action": "complete"})
        d["reassign_url"] = reverse("task_action", kwargs={"pk": self.pk, "action": "reassign"})
        d["stop_url"] = reverse("task_action", kwargs={"pk": self.pk, "action": "stop"})
        d["cancel_url"] = reverse("task_action", kwargs={"pk": self.pk, "action": "cancel"})
        return format_html(template, **d)

    def as_row_for_index_print(self):
        """As above, minus the column for icons."""
        template = """<td>{type}</td>"""
        # If the task referral has an address, combine it into the next cell.
        if self.referral.address:
            template += "<td>{description}<br><b>Address: </b>{address}</td>"
        else:
            template += "<td>{description}</td>"
        template += """<td>{referral_pk}</td>
            <td>{type}</td>
            <td>{referring_org}</td>
            <td>{reference}</td>
            <td>{due_date}</td>"""
        d = copy(self.__dict__)
        d["type"] = self.type.name
        if self.description:
            d["description"] = unidecode(self.description)
        else:
            d["description"] = ""
        d["referral_pk"] = self.referral.pk
        d["referring_org"] = self.referral.referring_org
        d["type"] = self.referral.type
        d["reference"] = self.referral.reference
        if self.referral.address:
            d["address"] = unidecode(self.referral.address)
        else:
            d["address"] = ""
        if self.due_date:
            d["due_date"] = self.due_date.strftime("%d %b %Y")
        else:
            d["due_date"] = ""
        return format_html(template, **d)

    def as_tbody(self):
        """
        Returns a string of HTML to render the object details inside <tbody> tags.
        """
        template = """<tr><th>Type</th><td>{type}</td></tr>
            <tr><th>Referral</th><td><a href="{referral_url}">{referral}</a></td></tr>
            <tr><th>Referral reference</th><td>{reference}</td></tr>
            <tr><th>Assigned to</th><td>{assigned_user}</td></tr>
            <tr><th>Description</th><td>{description}</td></tr>
            <tr><th>Start date</th><td>{start_date}</td></tr>
            <tr><th>Due date</th><td>{due_date}</td></tr>
            <tr><th>Status</th><td>{state}</td></tr>
            <tr><th>Completion date</th><td>{complete_date}</td></tr>
            <tr><th>Stop date</th><td>{stop_date}</td></tr>
            <tr><th>Restart date</th><td>{restart_date}</td></tr>
            <tr><th>Stop time (days)</th><td>{stop_time}</td></tr>"""
        d = copy(self.__dict__)
        d["type"] = self.type.name
        d["referral_url"] = reverse("referral_detail", kwargs={"pk": self.referral.pk, "related_model": "tasks"})
        d["referral"] = self.referral
        d["reference"] = self.referral.reference
        d["assigned_user"] = self.assigned_user.get_full_name()
        d["state"] = self.state.name
        if self.start_date:
            d["start_date"] = self.start_date.strftime("%d-%b-%Y")
        else:
            d["start_date"] = ""
        if d["due_date"]:
            d["due_date"] = self.due_date.strftime("%d-%b-%Y")
        if d["complete_date"]:
            d["complete_date"] = self.complete_date.strftime("%d-%b-%Y")
        else:
            d["complete_date"] = ""
        if d["stop_date"]:
            d["stop_date"] = self.stop_date.strftime("%d-%b-%Y")
        else:
            d["stop_date"] = ""
        if d["restart_date"]:
            d["restart_date"] = self.restart_date.strftime("%d-%b-%Y")
        else:
            d["restart_date"] = ""
        if d["stop_time"] == 0:
            d["stop_time"] = ""
        if self.description:
            d["description"] = unidecode(self.description)
        else:
            d["description"] = ""
        return format_html(template, **d)

    def email_user(self, from_email=None):
        """Method to email the assigned user a notification message about this
        task.
        """
        subject = f"PRS task assignment notification (referral ID {self.referral.pk})"
        if not from_email:
            from_email = settings.APPLICATION_ALERTS_EMAIL
        to_email = self.assigned_user.email
        referral_url = f"https://{settings.SITE_URL}{self.referral.get_absolute_url()}"
        address = self.referral.address or "not recorded"
        text_content = f"""This is an automated message to let you know that you have
            been assigned a PRS task ({self.pk}).\n
            This task is attached to referral ID {self.referral.pk}.\n
            The referral reference is: {self.referral.reference}.\n
            The referral address is: {address}\n
            """
        html_content = f"""<p>This is an automated message to let you know that you have
            been assigned a PRS task ({self.type.name}).</p>
            <p>The task is attached to referral ID {self.referral.pk}, located at this URL:</p>
            <p><a href="{referral_url}">{referral_url}</a></p>
            <p>The referral reference is: {self.referral.reference}</p>
            <p>The referral address is: {address}</p>
            """
        msg = EmailMultiAlternatives(subject, text_content, from_email, [to_email])
        msg.attach_alternative(html_content, "text/html")
        msg.send(fail_silently=False)


@reversion.register()
class Record(ReferralBaseModel):
    """A record is a reference to an electronic file, and is associated with a
    Referral.
    """

    name = models.CharField(
        max_length=512,
        help_text="The name/description of the record (max 512 characters).",
        validators=[MaxLengthValidator(512)],
    )
    referral = models.ForeignKey(Referral, on_delete=models.PROTECT)
    uploaded_file = models.FileField(
        blank=True,
        null=True,
        max_length=255,
        upload_to="uploads/%Y/%m/%d",
        help_text="Allowed file types: TIF,JPG,GIF,PNG,DOC,DOCX,XLS,XLSX,CSV,PDF,TXT,ZIP,MSG,QGS,XML",
    )
    infobase_id = models.SlugField(
        blank=True,
        null=True,
        verbose_name="Infobase ID",
        help_text="Infobase object ID (optional).",
    )
    description = models.TextField(blank=True, null=True)
    order_date = models.DateField(
        blank=True,
        null=True,
        verbose_name="date",
        help_text="Optional date (for sorting purposes).",
    )
    notes = models.ManyToManyField("Note", blank=True)
    uploaded_file_content = models.TextField(blank=True, null=True, editable=False)
    search_document = models.TextField(blank=True, null=True, editable=False)
    search_vector = SearchVectorField(null=True, editable=False)

    class Meta:
        ordering = ["-created"]
        indexes = [GinIndex(fields=["search_vector"], name="idx_record_search_vector")]

    def __str__(self):
        return f"Record {self.pk} ({smart_truncate(self.name, length=256)})"

    @classmethod
    def get_headers(cls):
        """Return a list of string values as headers for any list view."""
        return ["Record ID", "Date", "Name", "Infobase ID", "Referral ID", "Type", "Size"]

    def save(self, index=True, **kwargs):
        """Overide save() to cleanse text input fields and populate the search_document field."""
        self.name = unidecode(self.name).replace("\r\n", "").strip()

        # If the file is a .MSG we take the sent date of the email and use it for order_date.
        if self.extension == "MSG":
            msg = Message(self.uploaded_file)
            if msg.date and not self.order_date:  # Don't override any existing order_date.
                self.order_date = msg.date

        self.search_document = f"{self.name} {self.infobase_id or ''} {self.uploaded_file_content or ''} {self.description or ''}"
        self.search_document = search_document_normalise(self.search_document)

        super().save(**kwargs)

        # Index the record file content.
        try:
            if index:
                index_object.delay_on_commit(pk=self.pk, model="record")
                index_record.delay_on_commit(pk=self.pk)
        except Exception:
            # Indexing failure should never block or return an exception. Log the error to stdout.
            LOGGER.exception(f"Error indexing record {self}")

    def get_indexed_document(self, client=None):
        """Query Typesense for any indexed document of this record."""
        if not self.uploaded_file:
            return None

        if not client:
            client = get_typesense_client()

        try:
            document = client.collections["records"].documents[self.pk].retrieve()
            return document
        except ObjectNotFound:
            # The uploaded file may not be indexed.
            return None

    @property
    def filename(self):
        if settings.LOCAL_MEDIA_STORAGE:
            if self.uploaded_file and os.path.exists(self.uploaded_file.path):
                return self.uploaded_file.name.rsplit("/", 1)[-1]
            else:
                return ""
        else:
            if self.uploaded_file:
                return self.uploaded_file.name.rsplit("/", 1)[-1]
            else:
                return ""

    @property
    def extension(self):
        try:
            if self.uploaded_file:
                ext = os.path.splitext(self.uploaded_file.name)[1]
                return ext.replace(".", "").upper()
            else:
                return ""
        except:
            return ""

    @property
    def filesize_str(self):
        try:
            if self.uploaded_file:
                num = self.uploaded_file.size
                for x in ["b", "Kb", "Mb", "Gb"]:
                    if num < 1024.0:
                        return f"{num:3.1f} {x}"
                    num /= 1024.0
            else:
                return ""
        except:
            return ""

    def as_row(self):
        """
        Returns a string of HTML that renders the object details as table row cells.
        Remember to enclose this function in <tr> tags.
        """
        template = """<td><a href="{url}">{id}</a></td>
            <td><span style="display:none">{order_date_ts} </span>{order_date}</td>
            <td>{name}</td>
            <td><a href="{infobase_url}">{infobase_id}</a></td>
            <td class="referral-id-cell"><a href="{referral_url}">{referral_id}</a></td>
            <td>{download_url}</td>
            <td>{filesize}</td>"""
        d = copy(self.__dict__)
        d["url"] = self.get_absolute_url()
        if self.order_date:
            d["order_date"] = self.order_date.strftime("%d %b %Y")
            d["order_date_ts"] = self.order_date.isoformat()
        else:
            d["order_date"] = ""
            d["order_date_ts"] = ""
        d["referral_url"] = self.referral.get_absolute_url()
        d["referral_id"] = self.referral.pk
        if self.infobase_id:
            d["infobase_url"] = reverse("infobase_shortcut", kwargs={"pk": self.pk})
            d["infobase_id"] = self.infobase_id
        else:
            d["infobase_url"] = ""
            d["infobase_id"] = ""
        if self.uploaded_file:
            d["download_url"] = mark_safe(f"<a href='{self.uploaded_file.url}'><i class='fa-solid fa-download'></i> {self.extension}</a>")
            d["filesize"] = self.filesize_str
        else:
            d["download_url"] = ""
            d["filesize"] = ""
        return format_html(template, **d)

    def as_row_actions(self):
        """Returns a HTML table cell containing icons with links to suitable
        actions for the record object (edit, delete, etc.)
        """
        template = """<td><a href="{edit_url}" title="Edit"><i class="far fa-edit"></i></a>
            <a href="{delete_url}" title="Delete"><i class="far fa-trash-alt"></i></a></td>"""
        d = copy(self.__dict__)
        d["edit_url"] = reverse("prs_object_update", kwargs={"pk": self.pk, "model": "records"})
        d["delete_url"] = reverse("prs_object_delete", kwargs={"pk": self.pk, "model": "records"})
        return format_html(template, **d)

    def as_row_minus_referral(self):
        """Removes the HTML cell containing the parent referral details."""
        return as_row_subtract_referral_cell(self.as_row())

    def as_tbody(self):
        """Returns a string of HTML to render the object details inside <tbody>
        tags.
        """
        template = """<tr><th>Name</th><td>{name}</td></tr>
            <tr><th>Referral</th><td><a href="{referral_url}">{referral}</a></td></tr>
            <tr><th>Referral reference</th><td>{reference}</td></tr>
            <tr><th>Infobase ID</th><td><a href="{infobase_url}">{infobase_id}</a></td></tr>
            <tr><th>Description</th><td>{description}</td></tr>
            <tr><th>File type</th><td>{download_url}</td></tr>
            <tr><th>File size</th><td>{filesize}</td></tr>
            <tr><th>Date</th><td>{order_date}</td</tr>"""
        d = copy(self.__dict__)
        d["referral_url"] = reverse(
            "referral_detail",
            kwargs={"pk": self.referral.pk, "related_model": "records"},
        )
        d["referral"] = self.referral
        d["reference"] = self.referral.reference
        if self.infobase_id:
            d["infobase_url"] = reverse("infobase_shortcut", kwargs={"pk": self.pk})
            d["infobase_id"] = self.infobase_id
        else:
            d["infobase_url"] = ""
            d["infobase_id"] = ""
        d["description"] = self.description or ""
        if self.uploaded_file:
            d["download_url"] = mark_safe(f"<a href='{self.uploaded_file.url}'><i class='fa-solid fa-download'></i> {self.extension}</a>")
            d["filesize"] = self.filesize_str
        else:
            d["download_url"] = ""
            d["filesize"] = ""
        if self.order_date:
            d["order_date"] = self.order_date.strftime("%d-%b-%Y")
        else:
            d["order_date"] = ""
        d["creator"] = self.creator.get_full_name()
        return format_html(template, **d)


@reversion.register()
class Note(ReferralBaseModel):
    """
    A note or comment about a referral. These notes are meant to supplement
    formal record-keeping procedures only. HTML-formatted text is allowed.
    """

    referral = models.ForeignKey(Referral, on_delete=models.PROTECT)
    type = models.ForeignKey(
        NoteType,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        verbose_name="note type",
        help_text="The type of note (optional).",
    )
    note_html = models.TextField(verbose_name="note")
    note = models.TextField(editable=False)  # TODO: deprecate field.
    order_date = models.DateField(
        blank=True,
        null=True,
        verbose_name="date",
        help_text="Optional date (for sorting purposes).",
    )
    records = models.ManyToManyField("Record", blank=True)
    search_document = models.TextField(blank=True, null=True, editable=False)
    search_vector = SearchVectorField(null=True, editable=False)

    class Meta:
        ordering = ["order_date"]
        indexes = [GinIndex(fields=["search_vector"], name="idx_note_search_vector")]

    def __str__(self):
        return self.short_note

    @classmethod
    def get_headers(cls):
        """Return a list of string values as headers for any list view."""
        return ["Note ID", "Type", "Creator", "Date", "Note text", "Referral ID"]

    def save(self, *args, **kwargs):
        """Overide the Note model save() to cleanse the HTML used and populate the search_document field."""
        self.note_html = dewordify_text(self.note_html)
        if self.note_html:
            self.note_html = clean_html(self.note_html)
        # Strip HTML tags and save as plain text.
        if self.note_html:
            t = fromstring(self.note_html)
            self.note = t.text_content().strip()

        self.search_document = f"{self.note}"
        self.search_document = search_document_normalise(self.search_document)

        super().save(*args, **kwargs)

        # Index the note.
        try:
            index_object.delay_on_commit(pk=self.pk, model="note")
        except Exception:
            # Indexing failure should never block or return an exception. Log the error to stdout.
            LOGGER.exception(f"Error during indexing note {self}")

    @property
    def short_note(self, x=12):
        text = unidecode(self.note)
        text = text.replace("\n", " ").replace("\r", " ")  # Replace newlines.
        words = text.split(" ")
        if len(words) > x:
            return f"{' '.join(words[:x])}..."
        else:
            return text

    def as_row(self):
        """
        Returns a string of HTML that renders the object details as table row cells.
        Remember to enclose this function in <tr> tags.
        """
        template = """<td><a href="{url}">{id}</a></td>
            <td>{type}</td>
            <td>{creator}</td>
            <td><span style="display:none">{order_date_ts} </span>{order_date}</td>
            <td>{note}</td>
            <td class="referral-id-cell"><a href="{referral_url}">{referral_id}</a></td>"""
        d = copy(self.__dict__)
        icon_map = {
            "conversation": "<i class='fa-solid fa-comments'></i>",
            "email": "<i class='fa-solid fa-inbox'></i>",
            "file-note": "<i class='fa-solid fa-note-sticky'></i>",
            "letter-in": "<i class='fa-solid fa-envelope'></i>",
            "letter_out": "<i class='fa-solid fa-square-envelope'></i>",
            "report": "<i class='fa-solid fa-book'></i>",
        }
        d["url"] = self.get_absolute_url()
        if self.type and self.type.slug in icon_map:
            d["type"] = mark_safe(icon_map[self.type.slug])
        else:
            d["type"] = ""
        d["creator"] = self.creator.get_full_name()
        if self.order_date:
            d["order_date"] = self.order_date.strftime("%d %b %Y")
            d["order_date_ts"] = self.order_date.isoformat()
        else:
            d["order_date"] = ""
            d["order_date_ts"] = ""
        d["note"] = smart_truncate(unidecode(self.note), length=400)
        d["referral_url"] = self.referral.get_absolute_url()
        d["referral_id"] = self.referral.pk
        return format_html(template, **d)

    def as_row_actions(self):
        """Returns a HTML table cell containing icons with links to suitable
        actions for the note object (edit, delete, etc.)
        """
        d = copy(self.__dict__)
        template = """<td><a href="{edit_url}" title="Edit"><i class="far fa-edit"></i></a>
            <a href="{delete_url}" title="Delete"><i class="far fa-trash-alt"></i></a></td>"""
        d["edit_url"] = reverse("prs_object_update", kwargs={"pk": self.pk, "model": "notes"})
        d["delete_url"] = reverse("prs_object_delete", kwargs={"pk": self.pk, "model": "notes"})
        return format_html(template, **d)

    def as_row_minus_referral(self):
        """Removes the HTML cell containing the parent referral details."""
        return as_row_subtract_referral_cell(self.as_row())

    def as_tbody(self):
        """Returns a string of HTML to render the object details inside <tbody> tags."""
        template = """<tr><th>Referral</th><td><a href="{referral_url}">{referral}</a></td></tr>
            <tr><th>Referral reference</th><td>{reference}</td></tr>
            <tr><th>Type</th><td>{type}</td></tr>
            <tr><th>Created by</th><td>{creator}</td</tr>
            <tr><th>Date</th><td>{order_date}</td</tr>
            <tr class="highlight"><th>Note</th><td>{note_html}</td></tr>"""
        d = copy(self.__dict__)
        d["referral_url"] = reverse("referral_detail", kwargs={"pk": self.referral.pk, "related_model": "notes"})
        d["referral"] = self.referral
        d["reference"] = self.referral.reference
        d["type"] = self.type or ""
        d["creator"] = self.creator.get_full_name()
        if self.order_date:
            d["order_date"] = self.order_date.strftime("%d-%b-%Y")
        else:
            d["order_date"] = ""
        d["note_html"] = mark_safe(unidecode(self.note_html))
        return format_html(template, **d)


class ConditionCategory(ReferralLookup):
    """Lookup table for Condition categories."""

    class Meta(ReferralLookup.Meta):
        verbose_name_plural = "condition categories"


class ModelCondition(ReferralBaseModel):
    """Represents a 'model condition' with standard text."""

    category = models.ForeignKey(ConditionCategory, on_delete=models.PROTECT, blank=True, null=True)
    condition = models.TextField(help_text="Model condition")
    identifier = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="The decision-making authority's identifying number or code for this condition.",
        validators=[MaxLengthValidator(100)],
    )


@reversion.register()
class Condition(ReferralBaseModel):
    """Model type to handle proposed & approved conditions on referrals.
    Note that referral may be blank; this denotes a "standard" model condition.
    """

    referral = models.ForeignKey(Referral, on_delete=models.PROTECT, blank=True, null=True)
    condition = models.TextField(editable=False, blank=True, null=True)  # TODO: deprecate field.
    condition_html = models.TextField(
        blank=True,
        null=True,
        verbose_name="approved condition",
        help_text="""Insert words exactly as in the decision-maker's letter
        of approval, and add any advice notes relating to DPaW.""",
    )
    proposed_condition = models.TextField(editable=False, blank=True, null=True)  # TODO: deprecate field.
    proposed_condition_html = models.TextField(
        verbose_name="proposed condition",
        blank=True,
        null=True,
        help_text="Condition text proposed by DPaW.",
    )
    identifier = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="The decision-making authority's identifying number or code for this condition.",
        validators=[MaxLengthValidator(100)],
    )
    tags = TaggableManager(blank=True)
    clearance_tasks = models.ManyToManyField(
        Task,
        through="Clearance",
        editable=False,
        symmetrical=True,
    )
    category = models.ForeignKey(ConditionCategory, on_delete=models.PROTECT, blank=True, null=True)
    model_condition = models.ForeignKey(
        ModelCondition,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name="model_condition",
        help_text="Model text on which this condition is based",
    )
    search_document = models.TextField(blank=True, null=True, editable=False)
    search_vector = SearchVectorField(null=True, editable=False)

    class Meta:
        ordering = ["-created"]
        indexes = [GinIndex(fields=["search_vector"], name="idx_condition_search_vector")]

    @classmethod
    def get_headers(cls):
        """Return a list of string values as headers for any list view."""
        return [
            "Condition ID",
            "No.",
            "Proposed condition",
            "Approved condition",
            "Category",
            "Referral ID",
        ]

    def save(self, *args, **kwargs):
        """Overide the Condition models's save() to cleanse the HTML input and populate the search_document field."""
        if self.condition_html:
            self.condition_html = dewordify_text(self.condition_html)
            if self.condition_html:
                self.condition_html = clean_html(self.condition_html)
            t = fromstring(self.condition_html)
            self.condition = t.text_content().strip()
        else:
            self.condition_html = ""
            self.condition = ""
        if self.proposed_condition_html:
            self.proposed_condition_html = dewordify_text(self.proposed_condition_html)
            if self.proposed_condition_html:
                self.proposed_condition_html = clean_html(self.proposed_condition_html)
            t = fromstring(self.proposed_condition_html)
            self.proposed_condition = t.text_content().strip()
        else:
            self.proposed_condition_html = ""
            self.proposed_condition = ""

        self.search_document = f"{self.condition} {self.proposed_condition} {self.identifier}"
        self.search_document = search_document_normalise(self.search_document)

        super().save(*args, **kwargs)

        # Index the condition.
        if self.referral:
            try:
                index_object.delay_on_commit(pk=self.pk, model="condition")
            except Exception:
                LOGGER.exception(f"Error during indexing condition {self}")

    def as_row(self):
        """
        Returns a string of HTML that renders the object details as table row cells.
        Remember to enclose this function in <tr> tags.
        """
        template = """<td><a href="{url}">{id}</a></td>
            <td>{identifier}</td>
            <td>{proposed_condition}</td>
            <td>{condition}</td>
            <td>{category}</td>
            <td class="referral-id-cell"><a href="{referral_url}">{referral_id}</a></td>"""
        d = copy(self.__dict__)
        d["url"] = self.get_absolute_url()
        d["identifier"] = self.identifier or ""
        if self.proposed_condition:
            d["proposed_condition"] = smart_truncate(self.proposed_condition, length=300)
        else:
            d["proposed_condition"] = ""
        d["condition"] = smart_truncate(self.condition, length=300)
        # Condition "category" is actually an optional single Tag.
        if self.category:
            d["category"] = self.category.name
        else:
            d["category"] = ""
        if self.referral:
            d["referral_url"] = reverse(
                "referral_detail",
                kwargs={"pk": self.referral.pk, "related_model": "conditions"},
            )
        else:
            d["referral_url"] = ""
        d["referral_id"] = self.referral.pk if self.referral else ""
        return format_html(template, **d)

    def as_row_actions(self):
        """Returns a HTML table cell containing icons with links to suitable
        actions for the condition object (edit, delete, etc.)
        """
        template = """<td><a href="{add_clearance_url}" title="Add clearance"><i class="fa fa-plus"></i></a>
            <a href="{edit_url}" title="Edit"><i class="far fa-edit"></i></a>
            <a href="{delete_url}" title="Delete"><i class="far fa-trash-alt"></i></a></td>"""
        d = copy(self.__dict__)
        d["add_clearance_url"] = reverse("condition_clearance_add", kwargs={"pk": self.pk})
        d["edit_url"] = reverse("prs_object_update", kwargs={"pk": self.pk, "model": "conditions"})
        d["delete_url"] = reverse("prs_object_delete", kwargs={"pk": self.pk, "model": "conditions"})
        return format_html(template, **d)

    def as_row_minus_referral(self):
        """
        Removes the HTML cell containing the parent referral details.
        """
        return as_row_subtract_referral_cell(self.as_row())

    def as_tbody(self):
        """
        Returns a string of HTML to render the object details inside <tbody> tags.
        """
        template = """<tr><th>Referral</th><td><a href="{referral_url}">{referral}</a></td></tr>
            <tr><th>Referral reference</th><td>{reference}</td></tr>
            <tr><th>Number</th><td>{identifier}</td></tr>
            <tr><th>Model condition</th><td>{model_condition}</td></tr>
            <tr><th>Proposed condition text</th><td>{proposed_condition_html}</td></tr>
            <tr><th>Approved condition text</th><td>{condition_html}</td></tr>
            <tr><th>Category</th><td>{category}</td></tr>"""
        d = copy(self.__dict__)
        if self.referral:
            d["referral_url"] = reverse(
                "referral_detail",
                kwargs={"pk": self.referral.pk, "related_model": "conditions"},
            )
            d["referral"] = self.referral
            d["reference"] = self.referral.reference
        else:
            d["referral_url"] = ""
            d["referral"] = ""
            d["reference"] = ""
        d["identifier"] = self.identifier or ""
        if self.model_condition:
            d["model_condition"] = self.model_condition.condition
        else:
            d["model_condition"] = ""
        d["proposed_condition_html"] = mark_safe(unidecode(self.proposed_condition_html))
        d["condition_html"] = mark_safe(unidecode(self.condition_html))
        if self.category:
            d["category"] = self.category.name
        else:
            d["category"] = ""
        return format_html(template, **d)

    def add_clearance(self, task, deposited_plan=None):
        """Get or create a Clearance object on this Condition."""
        clearance, created = Clearance.objects.get_or_create(condition=self, task=task, deposited_plan=deposited_plan)
        return clearance


class ClearanceManager(models.Manager):
    """
    Custom Manager for Clearance models to return current clearances.
    """

    def current(self):
        return self.filter(task__effective_to__isnull=True, condition__effective_to__isnull=True)

    def active(self):
        return self.filter(task__effective_to__isnull=True, condition__effective_to__isnull=True)

    def deleted(self):
        return self.filter(task__effective_to__isnull=False)


class Clearance(models.Model):
    """
    Intermediate class for relationships between Condition and Task objects.
    """

    condition = models.ForeignKey(Condition, on_delete=models.PROTECT)
    task = models.ForeignKey(Task, on_delete=models.PROTECT)
    date_created = models.DateField(auto_now_add=True)
    deposited_plan = models.CharField(max_length=200, null=True, blank=True, validators=[MaxLengthValidator(200)])
    objects = ClearanceManager()

    class Meta:
        ordering = ["-pk"]

    def __str__(self):
        return f"{self.pk} condition {self.condition.pk} has task {self.task.pk}"

    @classmethod
    def get_headers(cls):
        """Return a list of string values as headers for any list view."""
        return [
            "Clearance ID",
            "Condition no.",
            "Condition",
            "Category",
            "Task",
            "Deposited plan",
            "Referral ID",
        ]

    def get_absolute_url(self):
        return reverse("prs_object_detail", kwargs={"model": "clearance", "pk": self.pk})

    def as_row(self):
        """
        Returns a string of HTML that renders the object details as table row
        cells. Remember to enclose this function in <tr> tags.
        """
        template = """<td><a href="{url}">{id}</a></td>
            <td>{identifier}</td>
            <td>{condition}</td>
            <td>{category}</td>
            <td>{task}</td>
            <td>{deposited_plan}</td>
            <td class="referral-id-cell"><a href="{referral_url}">{referral_id}</a></td>"""
        d = copy(self.__dict__)
        d["url"] = self.get_absolute_url()
        d["identifier"] = self.condition.identifier or ""
        d["condition"] = smart_truncate(self.condition.condition, length=400)
        # Condition "category" is actually an optional single tag.
        if self.condition.tags.exists():
            d["category"] = self.condition.tags.first().name
        else:
            d["category"] = ""
        if self.task.description:
            d["task"] = smart_truncate(unidecode(self.task.description), length=400)
        else:
            d["task"] = self.task.type.name
        d["deposited_plan"] = self.deposited_plan or ""
        d["referral_url"] = self.task.referral.get_absolute_url()
        d["referral_id"] = self.task.referral.pk
        return format_html(template, **d)

    def as_tbody(self):
        """
        Returns a string of HTML to render the object details inside <tbody> tags.
        """
        template = """<tr><th>Referral</th><td><a href="{referral_url}">{referral}</a></td></tr>
            <tr><th>Referral reference</th><td>{reference}</td></tr>
            <tr><th>Referral description</th><td>{referral_desc}</td></tr>
            <tr><th>Condition</th><td><a href="{condition_url}">{condition}</a></td></tr>
            <tr><th>Approved condition text</th><td>{condition_html}</td></tr>
            <tr><th>Task</th><td><a href="{task_url}">{task}</a></td></tr>
            <tr><th>Task description</th><td>{task_desc}</td></tr>
            <tr><th>Deposited plan</th><td>{deposited_plan}</td></tr>"""
        d = copy(self.__dict__)
        d["referral"] = self.task.referral
        d["referral_url"] = self.task.referral.get_absolute_url()
        d["reference"] = self.task.referral.reference
        if self.task.referral.description:
            d["referral_desc"] = unidecode(self.task.referral.description)
        else:
            d["referral_desc"] = ""
        d["condition_url"] = reverse("prs_object_detail", kwargs={"pk": self.condition.pk, "model": "conditions"})
        d["condition"] = self.condition
        d["condition_html"] = mark_safe(self.condition.condition_html)
        d["task_url"] = reverse("prs_object_detail", kwargs={"pk": self.task.pk, "model": "tasks"})
        d["task"] = self.task
        if self.task.description:
            d["task_desc"] = unidecode(self.task.description)
        else:
            d["task_desc"] = ""
        d["deposited_plan"] = self.deposited_plan or ""
        return format_html(template, **d)


@reversion.register()
class Location(ReferralBaseModel):
    """
    A physical location that is associated with a single referral.
    """

    address_no = models.IntegerField(null=True, blank=True, verbose_name="address number")
    address_suffix = models.CharField(max_length=10, null=True, blank=True, validators=[MaxLengthValidator(10)])
    road_name = models.CharField(max_length=100, null=True, blank=True, validators=[MaxLengthValidator(100)])
    road_suffix = models.CharField(max_length=100, null=True, blank=True, validators=[MaxLengthValidator(100)])
    locality = models.CharField(max_length=100, null=True, blank=True, validators=[MaxLengthValidator(100)])
    postcode = models.CharField(max_length=32, null=True, blank=True, validators=[MaxLengthValidator(32)])
    landuse = models.TextField(null=True, blank=True)
    lot_no = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="lot number",
        validators=[MaxLengthValidator(100)],
    )
    lot_desc = models.TextField(null=True, blank=True)
    strata_lot_no = models.CharField(max_length=100, null=True, blank=True, validators=[MaxLengthValidator(100)])
    strata_lot_desc = models.TextField(null=True, blank=True)
    reserve = models.TextField(null=True, blank=True)
    cadastre_obj_id = models.IntegerField(null=True, blank=True)
    referral = models.ForeignKey(Referral, on_delete=models.PROTECT)
    poly = models.PolygonField(srid=4283, null=True, blank=True, help_text="Optional.")
    address_string = models.TextField(null=True, blank=True, editable=True)

    @classmethod
    def get_headers(cls):
        """Return a list of string values as headers for any list view."""
        return ["Location ID", "Address", "Street View", "Referral ID"]

    def save(self, *args, **kwargs):
        """
        Overide the standard save method; inserts nice_address into address_string field.
        """
        self.address_string = self.nice_address.lower()
        super().save(*args, **kwargs)

    @property
    def nice_address(self):
        address = ""
        if self.address_no:
            address += str(self.address_no)
        if self.address_suffix and self.address_no:
            address += self.address_suffix
        if self.lot_no and self.address_no:
            address += " (Lot " + self.lot_no + ")"
        elif self.lot_no:
            address += "Lot " + self.lot_no
        if self.road_name:
            address += " " + self.road_name
        if self.road_suffix:
            address += " " + self.road_suffix
        if self.locality:
            address += " " + self.locality
        if self.postcode:
            address += " " + self.postcode
        return escape(address)

    def as_row(self):
        """
        Returns a string of HTML that renders the object details as table row cells.
        Remember to enclose this function in <tr> tags.
        """
        template = """<td><a href="{url}">{id}</a></td>
            <td>{address}</td>
            <td>{streetview_url}</td>
            <td class="referral-id-cell"><a href="{referral_url}">{referral_id}</a></td>"""
        d = copy(self.__dict__)
        d["url"] = reverse("prs_object_detail", kwargs={"pk": self.pk, "model": "locations"})
        d["address"] = self.nice_address or "none"
        if self.poly:
            d["streetview_url"] = mark_safe(
                f'<a href="http://maps.google.com/maps?q=&layer=c&cbll={self.poly.centroid.y},{self.poly.centroid.x}" title="Open in Google Street View" target="_blank"><i class="fa-solid fa-street-view"></i></a>'
            )
        else:
            d["streetview_url"] = ""
        d["referral_url"] = reverse(
            "referral_detail",
            kwargs={"pk": self.referral.pk, "related_model": "locations"},
        )
        d["referral_id"] = self.referral.pk
        return format_html(template, **d)

    def as_row_actions(self):
        """Returns a HTML table cell containing icons with links to suitable
        actions for the location object (edit, delete, etc.)
        """
        template = """<td><a href="{edit_url}" title="Edit"><i class="far fa-edit"></i></a>
            <a href="{delete_url}" title="Delete"><i class="far fa-trash-alt"></i></a></td>"""
        d = copy(self.__dict__)
        d["edit_url"] = reverse("prs_object_update", kwargs={"pk": self.pk, "model": "locations"})
        d["delete_url"] = reverse("prs_object_delete", kwargs={"pk": self.pk, "model": "locations"})
        return format_html(template, **d)

    def as_row_minus_referral(self):
        """Removes the HTML cell containing the parent referral details."""
        return as_row_subtract_referral_cell(self.as_row())

    def as_tbody(self):
        """
        Returns a string of HTML to render the object details inside <tbody> tags.
        """
        template = """<tr><th>Referral</th><td><a href="{referral_url}">{referral}</a></td></tr>
            <tr><th>Referral reference</th><td>{reference}</td></tr>
            <tr><th>Address</th><td>{address}</td></tr>"""
        d = copy(self.__dict__)
        d["url"] = self.get_absolute_url()
        d["referral_url"] = reverse(
            "referral_detail",
            kwargs={"pk": self.referral.pk, "related_model": "locations"},
        )
        d["referral"] = self.referral
        d["reference"] = self.referral.reference
        d["address"] = self.nice_address or "none"

        if self.poly:
            template += "<tr><th>Google Street View</th><td><a href='{streetview_url}' title='Open in Google Street View' target='_blank'><i class='fa-solid fa-street-view'></i></a></td></tr>"
            d["streetview_url"] = f"http://maps.google.com/maps?q=&layer=c&cbll={self.poly.centroid.y},{self.poly.centroid.x}"
        return format_html(template, **d)

    def get_regions_intersected(self):
        """Returns a list of Regions whose geometry intersects this Location."""
        regions = []
        if not self.poly:
            return regions
        else:
            for r in Region.objects.all():
                if r.region_mpoly and r.region_mpoly.intersects(self.poly):
                    regions.append(r)
            return regions


class Bookmark(ReferralBaseModel):
    """
    Users are able to bookmark referrals for faster access.
    """

    referral = models.ForeignKey(Referral, on_delete=models.PROTECT)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="referral_user_bookmark",
    )
    description = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        help_text="Maximum 200 characters.",
        validators=[MaxLengthValidator(200)],
    )

    @classmethod
    def get_headers(cls):
        """Return a list of string values as headers for any list view."""
        return ["Referral ID", "Bookmark description", "Actions"]

    def save(self, *args, **kwargs):
        """Overide save() to cleanse text input to the description field."""
        if self.description:
            self.description = unidecode(self.description)
        super().save(*args, **kwargs)

    def as_row(self):
        """
        Returns a string of HTML that renders the object details as table row
        cells. Remember to enclose this function in <tr> tags.
        """
        template = """<td><a href="{referral_url}">{referral}</a></td>
            <td>{description}</td>
            <td><a href="{delete_url}" title="Delete"><i class="far fa-trash-alt"></i></a></td>"""
        d = copy(self.__dict__)
        d["referral_url"] = self.referral.get_absolute_url()
        d["referral"] = self.referral
        d["description"] = self.description
        d["delete_url"] = reverse("prs_object_delete", kwargs={"pk": self.pk, "model": "bookmarks"})
        return format_html(template, **d)

    def as_tbody(self):
        """
        Returns a string of HTML to render the object details inside <tbody> tags.
        """
        template = """<tr><th>Referral</th><td><a href="{referral_url}">{referral}</a></td></tr>
            <tr><th>Referral reference</th><td>{reference}</td></tr>
            <tr><th>User</th><td>{user}</td></tr>
            <tr><th>Description</th><td>{description}</td></tr>"""
        d = copy(self.__dict__)
        d["referral_url"] = reverse("referral_detail", kwargs={"pk": self.referral.pk})
        d["referral"] = self.referral
        d["reference"] = self.referral.reference
        d["user"] = self.user.get_full_name()
        d["description"] = self.description
        return format_html(template, **d)


class UserProfile(models.Model):
    """
    An extension of the Django auth model, to add additional fields to each User
    """

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    agency = models.ForeignKey(Agency, on_delete=models.PROTECT, blank=True, null=True)
    referral_history_array = ArrayField(models.IntegerField(), size=20, default=list, blank=True)

    def __str__(self):
        return self.user.username

    def last_referral(self):
        """Return the referral that the user most-recently opened, or None.
        The last referral opened is the final item on the referral_history_array list in the user's profile.
        """
        if not self.referral_history_array:
            return None

        for pk in reversed(self.referral_history_array):
            if Referral.objects.current().filter(pk=pk).exists():
                return Referral.objects.get(pk=pk)

        return None

    def update_referral_history(self, referral):
        history = [pk for pk in self.referral_history_array if pk != referral.pk]
        history.append(referral.pk)
        if len(history) > 20:
            self.referral_history_array = history[-20:]
        else:
            self.referral_history_array = history

        self.save()

    def is_prs_user(self):
        """Returns group membership of the PRS user group."""
        return self.user.groups.filter(name=settings.PRS_USER_GROUP).exists()

    def is_power_user(self):
        """Returns group membership of the PRS power user group (or is_superuser==True)."""
        return self.user.is_superuser or self.user.groups.filter(name=settings.PRS_POWER_USER_GROUP).exists()

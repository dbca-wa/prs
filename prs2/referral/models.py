from copy import copy
from datetime import date
import dateparser
import json
import os
from django.conf import settings
from django.contrib.auth.signals import user_logged_in
from django.contrib.gis.db import models
from django.core.exceptions import SuspiciousFileOperation
from django.core.mail import EmailMultiAlternatives
from django.urls import reverse
from django.core.validators import MaxLengthValidator
from django.db.models import Q
from django.utils.encoding import python_2_unicode_compatible
from django.utils.safestring import mark_safe
from jinja2 import Template
from lxml.html import clean, fromstring
from model_utils import Choices
from taggit.managers import TaggableManager
from unidecode import unidecode

from referral.base import Audit, ActiveModel
from referral.utils import smart_truncate, dewordify_text, as_row_subtract_referral_cell, Message


# Australian state choices, for addresses.
AU_STATE_CHOICES = Choices(
    (1, "act", ("ACT")),
    (2, "nsw", ("NSW")),
    (3, "nt", ("NT")),
    (4, "qld", ("QLD")),
    (5, "sa", ("SA")),
    (6, "tas", ("TAS")),
    (7, "vic", ("VIC")),
    (8, "wa", ("WA")),
)


@python_2_unicode_compatible
class ReferralLookup(ActiveModel, Audit):
    """Abstract model type for lookup-table objects.
    """
    name = models.CharField(max_length=200)
    description = models.CharField(
        max_length=200, null=True, blank=True, validators=[MaxLengthValidator(200)]
    )
    slug = models.SlugField(
        unique=True, help_text="Must be unique. Automatically generated from name."
    )
    public = models.BooleanField(
        default=True, help_text="Is this lookup selection available to all users?"
    )
    headers = ["Name", "Description", "Last modified"]

    class Meta:
        abstract = True
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, force_insert=False, force_update=False, *args, **kwargs):
        """Overide save() to cleanse text input fields.
        """
        self.name = unidecode(self.name)
        if self.description:
            self.description = unidecode(self.description)
        super(ReferralLookup, self).save(force_insert, force_update)

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
        template = (
            '<td><a href="{url}">{name}</a></td><td>{description}</td><td>{modified}</td>'
        )
        d = copy(self.__dict__)
        d["url"] = self.get_absolute_url()
        if self.description:
            d["description"] = unidecode(self.description)
        else:
            d["description"] = ""
        d["modified"] = self.modified.strftime("%d %b %Y")
        return mark_safe(template.format(**d))

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
        return mark_safe(template.format(**d))


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
    region_mpoly = models.MultiPolygonField(
        srid=4283, null=True, blank=True, help_text="Optional."
    )


class LocalGovernment(ReferralLookup):
    """Lookup table of Local Government Authority name.
    """
    pass


class OrganisationType(ReferralLookup):
    """
    Lookup table for Organistion types.
    """
    pass


class Organisation(ReferralLookup):
    """
    Lookup table of Organisations that send planning referrals to DPaW.
    """
    type = models.ForeignKey(
        OrganisationType, on_delete=models.PROTECT, help_text="The organisation type."
    )
    list_name = models.CharField(
        max_length=100,
        help_text="""Name as it will appear in the alphabetised selection lists (e.g. "Broome,
            Shire of"). Put acronyms (e.g. OEPA) at the end.""",
        validators=[MaxLengthValidator(100)],
    )
    telephone = models.CharField(
        max_length=20, null=True, blank=True, help_text="Include the area code."
    )
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
    suburb = models.CharField(
        max_length=100, null=True, blank=True, validators=[MaxLengthValidator(100)]
    )
    state = models.IntegerField(choices=AU_STATE_CHOICES, default=AU_STATE_CHOICES.wa)
    postcode = models.CharField(
        max_length=4, null=True, blank=True, validators=[MaxLengthValidator(4)]
    )
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
        d["type"] = self.type
        d["created"] = self.created.strftime("%d-%b-%Y")
        d["creator"] = self.creator.get_full_name()
        d["modified"] = self.modified.strftime("%d-%b-%Y")
        d["modifier"] = self.modifier.get_full_name()
        d["address2"] = d["address2"] or "&nbsp;"
        d["state"] = self.get_state_display()
        return mark_safe(template.format(**d))


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
    icon = models.ImageField(upload_to="img", blank=True, null=True)


class Agency(ReferralLookup):
    """
    Lookup field to distinguish different govt Agencies by acronym (DER, DPaW, etc.)
    """
    code = models.CharField(max_length=16)

    class Meta(ReferralLookup.Meta):
        verbose_name_plural = "agencies"


@python_2_unicode_compatible
class ReferralBaseModel(ActiveModel, Audit):
    """
    Base abstract model class for object types that are not lookups.
    """
    headers = None
    tools_template = None

    class Meta:
        abstract = True
        ordering = ["-created"]

    def __str__(self):
        return "{0} {1}".format(self._meta.object_name, self.pk)

    def get_absolute_url(self):
        return reverse(
            "prs_object_detail",
            kwargs={
                "model": self._meta.verbose_name_plural.lower().replace(" ", ""),
                "pk": self.pk,
            },
        )


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
    description = models.TextField(
        blank=True, null=True, help_text="[Searchable] Optional."
    )
    referral_date = models.DateField(
        verbose_name="received date", help_text="Date that the referral was received."
    )
    address = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        validators=[MaxLengthValidator(200)],
        help_text="[Searchable] Physical address of the planning proposal. Maximum 200 characters.",
    )
    point = models.PointField(
        srid=4283, blank=True, null=True, editable=False, help_text="Optional."
    )
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
    headers = [
        "Referral ID",
        "Received date",
        "Description",
        "Address",
        "Referrer's reference",
        "Referred by",
        "Region(s)",
        "Type",
    ]
    tools_template = "referral/referral_tools.html"

    def save(self, force_insert=False, force_update=False, *args, **kwargs):
        """Overide save to cleanse text input to the description, address fields.
        """
        if self.description:
            self.description = unidecode(self.description)
        if self.address:
            self.address = unidecode(self.address)
        super(Referral, self).save(force_insert, force_update)

    def get_absolute_url(self):
        return reverse("referral_detail", kwargs={"pk": self.pk})

    @property
    def regions_str(self):
        """
        Return a unicode string of all the regions that this referral belongs to (or None).
        """
        if not self.regions.all():
            return None
        return ", ".join([r.name for r in self.regions.all()])

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
        """Returns True if Locations exist on this referral, else False.
        """
        return self.location_set.current().exists()

    @property
    def has_condition(self):
        """Returns True if Conditions exist on this referral, else False.
        """
        return self.condition_set.current().exists()

    @property
    def has_proposed_condition(self):
        """ Checks if Task has 'Proposed Condition' text
        """
        return self.has_condition and any(
            c.proposed_condition for c in self.condition_set.current()
        )

    def as_row(self):
        """
        Returns a string of HTML that renders the object details as table row cells.
        Remember to enclose this function in <tr> tags.
        """
        template = """<td><a href="{url}">{id}</a></td>
            <td>{referral_date}</td>
            <td>{description}</td></td>
            <td>{address}</td>
            <td>{reference}</td>
            <td>{referring_org}</td>
            <td>{regions}</td>
            <td>{type}</td>"""
        d = copy(self.__dict__)
        d["url"] = self.get_absolute_url()
        d["type"] = self.type
        d["regions"] = self.regions_str
        d["referring_org"] = self.referring_org
        d["referral_date"] = self.referral_date.strftime("%d %b %Y") or ""
        if self.address:
            d["address"] = unidecode(self.address)
        else:
            d["address"] = ""
        if self.description:
            d["description"] = unidecode(self.description)
        else:
            d["description"] = ""
        return mark_safe(template.format(**d))

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
        d["type"] = self.type
        d["regions"] = self.regions_str
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
        return mark_safe(template.format(**d).strip())

    def add_relationship(self, referral):
        # Disallow self-referential relationships:
        if self == referral:
            return None
        else:
            forward_rel, created = RelatedReferral.objects.get_or_create(
                from_referral=self, to_referral=referral
            )
            backward_rel, created = RelatedReferral.objects.get_or_create(
                from_referral=referral, to_referral=self
            )
            return forward_rel

    def remove_relationship(self, referral):
        qs1 = RelatedReferral.objects.filter(from_referral=self, to_referral=referral)
        qs2 = RelatedReferral.objects.filter(from_referral=referral, to_referral=self)

        if qs1 or qs2:
            qs1.delete()
            qs2.delete()
            return True
        return False

    def generate_qgis_layer(self, template=None):
        """Generates and returns the content for a QGIS layer definition.
        Optionally specify the name of the template (defaults to the v2.8
        compatible template).
        """
        # Only return a value for a referral with child locations.
        if not self.location_set.current().filter(poly__isnull=False).exists():
            return None
        # Read in the base Jinja template.
        if template:  # Specify template version.
            t = Template(
                open("prs2/referral/templates/{}.jinja".format(template), "r").read()
            )
        else:  # Default to QGIS 2.8-compatible template.
            t = Template(open("prs2/referral/templates/qgis_layer.jinja", "r").read())
        # Build geographical extent of associated locations.
        qs = (
            self.location_set.current()
            .filter(poly__isnull=False)
            .aggregate(models.Extent("poly"))
        )
        xmin, ymin, xmax, ymax = qs["poly__extent"]
        d = {"REFERRAL_PK": self.pk}
        return t.render(**d)


@python_2_unicode_compatible
class RelatedReferral(models.Model):
    """
    Intermediate class for relationships between Referral objects.
    Trying to create this relationship without the intermediate class generated
    some really odd recursion errors.
    """
    from_referral = models.ForeignKey(
        Referral, on_delete=models.PROTECT, related_name="from_referral"
    )
    to_referral = models.ForeignKey(
        Referral, on_delete=models.PROTECT, related_name="to_referral"
    )

    def __str__(self):
        return "{0} ({1} to {2})".format(
            self.pk, self.from_referral.pk, self.to_referral.pk
        )


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
    description = models.TextField(
        blank=True, null=True, help_text="Description of the task requirements."
    )
    start_date = models.DateField(
        blank=True, null=True, help_text="Date on which this task was started."
    )
    due_date = models.DateField(
        blank=True, null=True, help_text="Date by which the task must be completed."
    )
    complete_date = models.DateField(
        blank=True,
        null=True,
        verbose_name="completed date",
        help_text="Date that the task was completed.",
    )
    stop_date = models.DateField(
        blank=True, null=True, help_text="Date that the task was stopped."
    )
    restart_date = models.DateField(
        blank=True, null=True, help_text="Date that a stopped task was restarted."
    )
    stop_time = models.IntegerField(
        default=0, editable=False, help_text="Cumulative time stopped in days."
    )
    state = models.ForeignKey(
        TaskState,
        on_delete=models.PROTECT,
        verbose_name="status",
        help_text="The status of the task.",
    )
    headers = [
        "Task",
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
    headers_site_home = [
        "Type",
        "Task description",
        "Referral ID",
        "Referral type",
        "Referrer",
        "Referrers reference",
        "Due",
        "Actions",
    ]
    tools_template = "referral/task_tools.html"
    records = models.ManyToManyField("Record", blank=True)
    notes = models.ManyToManyField("Note", blank=True)

    class Meta:
        ordering = ["-pk", "due_date"]

    def save(self, force_insert=False, force_update=False, *args, **kwargs):
        """Overide save() to cleanse text input to the description field.
        """
        if self.description:
            self.description = unidecode(self.description)
        super(Task, self).save(force_insert, force_update)

    def as_row(self):
        """
        Returns a string of HTML that renders the object details as table row cells.
        Remember to enclose this function in <tr> tags.
        """
        template = """<td><a href="{url}">Open</a></td>
            <td>{type}</td>
            <td>{description}</td>
            <td>{address}</td>
            <td class="referral-id-cell"><a href="{referral_url}">{referral}</a></td>
            <td>{assigned_user}</td>
            <td>{start_date}</td>
            <td>{due_date}</td>
            <td>{complete_date}</td>
            <td>{state}</td>"""
        d = copy(self.__dict__)
        d["url"] = self.get_absolute_url()
        d["type"] = self.type
        if self.description:
            d["description"] = smart_truncate(self.description, length=400)
        else:
            d["description"] = ""
        d["address"] = self.referral.address or ""
        d["referral_url"] = self.referral.get_absolute_url()
        d["referral"] = self.referral
        d["assigned_user"] = self.assigned_user.get_full_name()
        if self.start_date:
            d["start_date"] = self.start_date.strftime("%d %b %Y")
        else:
            d["start_date"] = ""
        if self.due_date:
            d["due_date"] = self.due_date.strftime("%d %b %Y")
        else:
            d["due_date"] = ""
        if self.complete_date:
            d["complete_date"] = self.complete_date.strftime("%d %b %Y")
        else:
            d["complete_date"] = ""
        d["state"] = self.state
        return mark_safe(template.format(**d))

    def as_row_actions(self):
        """
        Returns a HTML table cell containing icons with links to suitable
        actions for the task object (e.g. stop/start, complete, etc.)

        html attr class="is_prs_user_action" is used by javascript in the template to
        check prs_user permissions and disables Actions for readonly users.
        """
        d = copy(self.__dict__)
        if self.state.name == "Stopped":
            template = (
                """<td><a class="is_prs_user_action" href="{start_url}" title="Start"><i class="fa fa-play"></i></a></td>"""
            )
            d["start_url"] = reverse(
                "task_action", kwargs={"pk": self.pk, "action": "start"}
            )
        elif not self.complete_date:
            template = (
                """<td><a class="is_prs_user_action" href="{edit_url}" title="Edit"><i class="fa fa-pencil"></i></a>"""
            )
            template += (
                """ <a class="is_prs_user_action" href="{complete_url}" title="Complete"><i class="fa fa-check-square-o"></i></a>"""
            )
            template += """
                <a class="is_prs_user_action" href="{stop_url}" title="Stop"><i class="fa fa-stop"></i></a>
                <a class="is_prs_user_action" href="{reassign_url}" title="Reassign"><i class="fa fa-share"></i></a>
                <a class="is_prs_user_action" href="{cancel_url}" title="Cancel"><i class="fa fa-ban"></i></a>
                <a class="is_prs_user_action" href="{delete_url}" title="Delete"><i class="fa fa-trash-o"></i></a></td>"""
            d["edit_url"] = reverse(
                "task_action", kwargs={"pk": self.pk, "action": "update"}
            )
            d["reassign_url"] = reverse(
                "task_action", kwargs={"pk": self.pk, "action": "reassign"}
            )
            d["complete_url"] = reverse(
                "task_action", kwargs={"pk": self.pk, "action": "complete"}
            )
            d["stop_url"] = reverse(
                "task_action", kwargs={"pk": self.pk, "action": "stop"}
            )
            d["cancel_url"] = reverse(
                "task_action", kwargs={"pk": self.pk, "action": "cancel"}
            )
            d["delete_url"] = reverse(
                "prs_object_delete", kwargs={"pk": self.pk, "model": "task"}
            )
        else:
            template = "<td></td>"
        return mark_safe(template.format(**d))

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
        html attr class="is_prs_user_action" is used by javascript in the
        template to check prs_user permissions and disables Actions for
        readonly users.
        """
        template = "<td>{type}</td>"
        if (
            self.referral.address
        ):  # If the referral has an address, include it in the description field.
            template += "<td>{description}<br><b>Address: </b>{address}</td>"
        else:
            template += "<td>{description}</td>"
        template += """<td><a href="{referral_url}">{referral_pk}</a></td>
            <td>{type}</td>
            <td>{referring_org}</td>
            <td>{reference}</td>
            <td>{due_date}</td>"""
        if (
            self.is_stopped
        ):  # Render a different set of action icons if the task is stopped.
            template += """<td class="action-icons-cell">
                <a class="is_prs_user_action" href="{start_url}" title="Start"><i class="fa fa-play"></i></a></td>"""
        elif not self.complete_date:  # Render icons if the task is not completed.
            template += """<td class="action-icons-cell">
                <a class="is_prs_user_action" href="{complete_url}" title="Complete"><i class="fa fa-check-square-o"></i></a>
                <a class="is_prs_user_action" href="{stop_url}" title="Stop"><i class="fa fa-stop"></i></a>
                <a class="is_prs_user_action" href="{reassign_url}" title="Reassign"><i class="fa fa-share"></i></a>
                <a class="is_prs_user_action" href="{cancel_url}" title="Cancel"><i class="fa fa-ban"></i></a>"""
        else:  # Render an empty table cell.
            template += '<td class="action-icons-cell"></td>'
        d = copy(self.__dict__)
        d["type"] = self.type
        if self.description:
            d["description"] = unidecode(self.description)
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
        else:
            d["due_date"] = ""
        d["start_url"] = reverse(
            "task_action", kwargs={"pk": self.pk, "action": "start"}
        )
        d["complete_url"] = reverse(
            "task_action", kwargs={"pk": self.pk, "action": "complete"}
        )
        d["reassign_url"] = reverse(
            "task_action", kwargs={"pk": self.pk, "action": "reassign"}
        )
        d["stop_url"] = reverse("task_action", kwargs={"pk": self.pk, "action": "stop"})
        d["cancel_url"] = reverse(
            "task_action", kwargs={"pk": self.pk, "action": "cancel"}
        )
        return mark_safe(template.format(**d))

    def as_row_for_index_print(self):
        """As above, minus the column for icons.
        """
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
        d["type"] = self.type
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
        return mark_safe(template.format(**d))

    def as_tbody(self):
        """
        Returns a string of HTML to render the object details inside <tbody> tags.
        """
        template = """<tr><th>Type</th><td>{type}</td></tr>
            <tr><th>Referral ID</th><td><a href="{referral_url}">{referral_id}</a></td></tr>
            <tr><th>Referrer's reference</th><td>{reference}</td></tr>
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
        d["type"] = self.type
        d["referral_url"] = reverse(
            "referral_detail", kwargs={"pk": self.referral.pk, "related_model": "tasks"}
        )
        d["referral_id"] = self.referral.pk
        d["reference"] = self.referral.reference
        d["assigned_user"] = self.assigned_user.get_full_name()
        d["state"] = self.state
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
        return mark_safe(template.format(**d).strip())

    def email_user(self, from_email=None):
        """Method to email the assigned user a notification message about this
        task.
        """
        subject = "PRS task assignment notification (referral ID {0})".format(
            self.referral.pk
        )
        if not from_email:
            from_email = settings.APPLICATION_ALERTS_EMAIL
        to_email = self.assigned_user.email
        referral_url = settings.SITE_URL + self.referral.get_absolute_url()
        address = self.referral.address or "(not recorded)"
        text_content = """This is an automated message to let you know that you have
            been assigned a PRS task ({0}) by the sending user.\n
            This task is attached to referral ID {1}.\nThe referral reference is: {2}.\n
            The referral address is: {3}\n
            """.format(
            self.pk, self.referral.pk, self.referral.reference, address
        )
        html_content = """<p>This is an automated message to let you know that you have
            been assigned a PRS task ({0}) by the sending user.</p>
            <p>The task is attached to referral {1}, located at this URL:</p>
            <p>{2}</p>
            <p>The referral reference is: {3}</p>
            <p>The referral address is: {4}</p>
            """.format(
            self.type.name,
            self.referral.pk,
            referral_url,
            self.referral.reference,
            address,
        )
        msg = EmailMultiAlternatives(subject, text_content, from_email, [to_email])
        msg.attach_alternative(html_content, "text/html")
        msg.send(fail_silently=False)


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
    headers = ["Record", "Date", "Name", "Infobase ID", "Referral ID", "Type", "Size"]
    tools_template = "referral/record_tools.html"

    def __str__(self):
        return smart_truncate(self.name, length=256)

    def save(self, force_insert=False, force_update=False, *args, **kwargs):
        """Overide save() to cleanse text input fields.
        """
        self.name = unidecode(self.name)
        if self.description:
            self.description = unidecode(self.description)
        super(Record, self).save(force_insert, force_update)

        # If the file is a .MSG we take the sent date of the email and use it for order_date.
        if self.extension == "MSG":
            msg = Message(os.path.realpath(self.uploaded_file.path))
            if msg.date:
                date = dateparser.parse(msg.date)
                if date and self.order_date != date:
                    self.order_date = date
                    self.save()

    @property
    def filename(self):
        if self.uploaded_file and os.path.exists(self.uploaded_file.path):
            return self.uploaded_file.name.rsplit("/", 1)[-1]
        else:
            return ""

    @property
    def extension(self):
        try:  # Account for SuspiciousFileOperation exceptions.
            if self.uploaded_file and os.path.exists(self.uploaded_file.path):
                ext = os.path.splitext(self.uploaded_file.name)[1]
                return ext.replace(".", "").upper()
            else:
                return ""
        except SuspiciousFileOperation:
            return ""

    @property
    def filesize_str(self):
        try:  # Account for SuspiciousFileOperation exceptions.
            if self.uploaded_file and os.path.exists(self.uploaded_file.path):
                num = self.uploaded_file.size
                for x in ["b", "Kb", "Mb", "Gb"]:
                    if num < 1024.0:
                        return "{:3.1f}{}".format(num, x)
                    num /= 1024.0
            else:
                return ""
        except SuspiciousFileOperation:
            return ""

    def as_row(self):
        """
        Returns a string of HTML that renders the object details as table row cells.
        Remember to enclose this function in <tr> tags.
        """
        template = """<td><a href="{url}">Open</a></td>
            <td>{order_date}</td>
            <td>{name}</td>
            <td><a href="{infobase_url}">{infobase_id}</a></td>
            <td class="referral-id-cell"><a href="{referral_url}">{referral}</a></td>
            <td><a href="{download_url}">{filetype}</a></td>
            <td>{filesize}</td>"""
        d = copy(self.__dict__)
        d["url"] = self.get_absolute_url()
        if self.order_date:
            d["order_date"] = self.order_date.strftime("%d %b %Y")
        else:
            d["order_date"] = ""
        d["referral_url"] = self.referral.get_absolute_url()
        d["referral"] = self.referral
        if self.infobase_id:
            d["infobase_url"] = reverse("infobase_shortcut", kwargs={"pk": self.pk})
            d["infobase_id"] = self.infobase_id
        else:
            d["infobase_url"] = ""
            d["infobase_id"] = ""
        if self.uploaded_file:
            d["download_url"] = reverse("download_record", kwargs={"pk": self.pk})
            d["filetype"] = self.extension
            d["filesize"] = self.filesize_str
        else:
            d["download_url"] = ""
            d["filetype"] = ""
            d["filesize"] = ""
        return mark_safe(template.format(**d))

    def as_row_actions(self):
        """
        Returns a HTML table cell containing icons with links to suitable
        actions for the record object (edit, delete, etc.)

        html attr class="is_prs_user_action" is used by javascript in the template to
        check prs_user permissions and disables Actions for readonly users.
        """
        template = """<td><a class="is_prs_user_action" href="{edit_url}" title="Edit"><i class="fa fa-pencil"></i></a>
            <a class="is_prs_user_action" href="{delete_url}" title="Delete"><i class="fa fa-trash-o"></i></a></td>"""
        d = copy(self.__dict__)
        d["edit_url"] = reverse(
            "prs_object_update", kwargs={"pk": self.pk, "model": "records"}
        )
        d["delete_url"] = reverse(
            "prs_object_delete", kwargs={"pk": self.pk, "model": "records"}
        )
        return mark_safe(template.format(**d))

    def as_row_minus_referral(self):
        """Removes the HTML cell containing the parent referral details.
        """
        return as_row_subtract_referral_cell(self.as_row())

    def as_tbody(self):
        """Returns a string of HTML to render the object details inside <tbody>
        tags.
        """
        template = """<tr><th>Name</th><td>{name}</td></tr>
            <tr><th>Referral</th><td><a href="{referral_url}">{referral}</a></td></tr>
            <tr><th>Referrer's reference</th><td>{reference}</td></tr>
            <tr><th>Infobase ID</th><td><a href="{infobase_url}">{infobase_id}</a></td></tr>
            <tr><th>Description</th><td>{description}</td></tr>
            <tr><th>File type</th><td><a href="{download_url}">{filetype}</a></td></tr>
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
        if self.uploaded_file:
            d["download_url"] = reverse("download_record", kwargs={"pk": self.pk})
            d["filetype"] = self.extension
            d["filesize"] = self.filesize_str
        else:
            d["download_url"] = ""
            d["filetype"] = ""
            d["filesize"] = ""
        if self.order_date:
            d["order_date"] = self.order_date.strftime("%d-%b-%Y")
        else:
            d["order_date"] = ""
        d["creator"] = self.creator.get_full_name()
        return mark_safe(template.format(**d).strip())


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
    note = models.TextField(editable=False)
    order_date = models.DateField(
        blank=True,
        null=True,
        verbose_name="date",
        help_text="Optional date (for sorting purposes).",
    )
    headers = ["Note", "Type", "Creator", "Date", "Note", "Referral ID"]
    tools_template = "referral/note_tools.html"
    records = models.ManyToManyField("Record", blank=True)

    class Meta:
        ordering = ["order_date"]

    def __str__(self):
        return self.short_note

    def save(self, force_insert=False, force_update=False, *args, **kwargs):
        """
        Overide the Note model save() to cleanse the HTML used.
        """
        self.note_html = dewordify_text(self.note_html)
        self.note_html = clean.clean_html(self.note_html)
        # Strip HTML tags and save as plain text.
        t = fromstring(self.note_html)
        self.note = t.text_content().strip()
        super(Note, self).save(force_insert, force_update)

    @property
    def short_note(self, x=12):
        text = unidecode(self.note)
        text = text.replace("\n", " ").replace("\r", " ")  # Replace newlines.
        words = text.split(" ")
        if len(words) > x:
            return "{}...".format(" ".join(words[:x]))
        else:
            return text

    def as_row(self):
        """
        Returns a string of HTML that renders the object details as table row cells.
        Remember to enclose this function in <tr> tags.
        """
        template = """<td><a href="{url}">Open</a></td>
            <td>{type}</td>
            <td>{creator}</td>
            <td>{order_date}</td>
            <td>{note}</td>
            <td class="referral-id-cell"><a href="{referral_url}">{referral}</a></td>"""
        d = copy(self.__dict__)
        d["url"] = self.get_absolute_url()
        if self.type:
            d["type"] = '<img src="/static/{}" title="{}" />'.format(
                self.type.icon.__str__(), self.type.name
            )
        else:
            d["type"] = ""
        d["creator"] = self.creator.get_full_name()
        if self.order_date:
            d["order_date"] = self.order_date.strftime("%d %b %Y")
        else:
            d["order_date"] = ""
        d["note"] = smart_truncate(unidecode(self.note), length=400)
        d["referral_url"] = self.referral.get_absolute_url()
        d["referral"] = self.referral
        return mark_safe(template.format(**d))

    def as_row_actions(self):
        """Returns a HTML table cell containing icons with links to suitable
        actions for the note object (edit, delete, etc.)

        html attr class="is_prs_user_action" is used by javascript in the template to
        check prs_user permissions and disables Actions for readonly users.
        """
        template = """<td><a class="is_prs_user_action" href="{edit_url}" title="Edit"><i class="fa fa-pencil"></i></a>
            <a class="is_prs_user_action" href="{delete_url}" title="Delete"><i class="fa fa-trash-o"></i></a></td>"""
        d = copy(self.__dict__)
        d["edit_url"] = reverse(
            "prs_object_update", kwargs={"pk": self.pk, "model": "notes"}
        )
        d["delete_url"] = reverse(
            "prs_object_delete", kwargs={"pk": self.pk, "model": "notes"}
        )
        return mark_safe(template.format(**d))

    def as_row_minus_referral(self):
        """Removes the HTML cell containing the parent referral details.
        """
        return as_row_subtract_referral_cell(self.as_row())

    def as_tbody(self):
        """
        Returns a string of HTML to render the object details inside <tbody> tags.
        """
        template = """<tr><th>Referral</th><td><a href="{referral_url}">{referral}</a></td></tr>
            <tr><th>Referrer's reference</th><td>{reference}</td></tr>
            <tr><th>Type</th><td>{type}</td></tr>
            <tr><th>Created by</th><td>{creator}</td</tr>
            <tr><th>Date</th><td>{order_date}</td</tr>
            <tr class="highlight"><th>Note</th><td>{note_html}</td></tr>"""
        d = copy(self.__dict__)
        d["referral_url"] = reverse(
            "referral_detail", kwargs={"pk": self.referral.pk, "related_model": "notes"}
        )
        d["referral"] = self.referral
        d["reference"] = self.referral.reference
        d["type"] = self.type or ""
        d["creator"] = self.creator.get_full_name()
        if self.order_date:
            d["order_date"] = self.order_date.strftime("%d-%b-%Y")
        else:
            d["order_date"] = ""
        d["note_html"] = unidecode(self.note_html)
        return mark_safe(template.format(**d).strip())


class ConditionCategory(ReferralLookup):
    """Lookup table for Condition categories.
    """

    class Meta(ReferralLookup.Meta):
        verbose_name_plural = "condition categories"


class ModelCondition(ReferralBaseModel):
    """Represents a 'model condition' with standard text.
    """
    category = models.ForeignKey(
        ConditionCategory, on_delete=models.PROTECT, blank=True, null=True
    )
    condition = models.TextField(help_text="Model condition")
    identifier = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="The decision-making authority's identifying number or code for this condition.",
        validators=[MaxLengthValidator(100)],
    )


class Condition(ReferralBaseModel):
    """Model type to handle proposed & approved conditions on referrals.
    Note that referral may be blank; this denotes a "standard" model condition.
    """
    referral = models.ForeignKey(
        Referral, on_delete=models.PROTECT, blank=True, null=True
    )
    condition = models.TextField(editable=False, blank=True, null=True)
    condition_html = models.TextField(
        blank=True,
        null=True,
        verbose_name="approved condition",
        help_text="""Insert words exactly as in the decision-maker's letter
        of approval, and add any advice notes relating to DPaW.""",
    )
    proposed_condition = models.TextField(editable=False, blank=True, null=True)
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
        related_name="clearance_requests",
    )
    category = models.ForeignKey(
        ConditionCategory, on_delete=models.PROTECT, blank=True, null=True
    )
    model_condition = models.ForeignKey(
        ModelCondition,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name="model_condition",
        help_text="Model text on which this condition is based",
    )
    headers = [
        "Condition",
        "No.",
        "Proposed condition",
        "Approved condition",
        "Category",
        "Referral ID",
    ]
    tools_template = "referral/condition_tools.html"

    def save(self, force_insert=False, force_update=False, *args, **kwargs):
        """
        Overide the Condition models's save() to cleanse the HTML input.
        """
        if self.condition_html:
            self.condition_html = dewordify_text(self.condition_html)
            self.condition_html = clean.clean_html(self.condition_html)
            t = fromstring(self.condition_html)
            self.condition = t.text_content().strip()
        else:
            self.condition_html = ""
            self.condition = ""
        if self.proposed_condition_html:
            self.proposed_condition_html = dewordify_text(self.proposed_condition_html)
            self.proposed_condition_html = clean.clean_html(
                self.proposed_condition_html
            )
            t = fromstring(self.proposed_condition_html)
            self.proposed_condition = t.text_content().strip()
        else:
            self.proposed_condition_html = ""
            self.proposed_condition = ""
        super(Condition, self).save(force_insert, force_update)

    def as_row(self):
        """
        Returns a string of HTML that renders the object details as table row cells.
        Remember to enclose this function in <tr> tags.
        """
        template = """<td><a href="{url}">Open</a></td>
            <td>{identifier}</td>
            <td>{proposed_condition}</td>
            <td>{condition}</td>
            <td>{category}</td>
            <td class="referral-id-cell"><a href="{referral_url}">{referral}</a></td>"""
        d = copy(self.__dict__)
        d["url"] = self.get_absolute_url()
        d["identifier"] = self.identifier or ""
        if self.proposed_condition:
            d["proposed_condition"] = smart_truncate(
                self.proposed_condition, length=300
            )
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
        d["referral"] = self.referral or ""
        return mark_safe(template.format(**d))

    def as_row_actions(self):
        """Returns a HTML table cell containing icons with links to suitable
        actions for the condition object (edit, delete, etc.)

        html attr class="is_prs_user_action" is used by javascript in the template to
        check prs_user permissions and disables Actions for readonly users.
        """
        template = """<td><a class="is_prs_user_action" href="{add_clearance_url}" title="Add clearance"><i class="fa fa-plus"></i></a>
            <a class="is_prs_user_action" href="{edit_url}" title="Edit"><i class="fa fa-pencil"></i></a>
            <a class="is_prs_user_action" href="{delete_url}" title="Delete"><i class="fa fa-trash-o"></i></a></td>"""
        d = copy(self.__dict__)
        d["add_clearance_url"] = reverse(
            "condition_clearance_add", kwargs={"pk": self.pk}
        )
        d["edit_url"] = reverse(
            "prs_object_update", kwargs={"pk": self.pk, "model": "conditions"}
        )
        d["delete_url"] = reverse(
            "prs_object_delete", kwargs={"pk": self.pk, "model": "conditions"}
        )
        return mark_safe(template.format(**d))

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
            <tr><th>Referrer's reference</th><td>{reference}</td></tr>
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
        d["proposed_condition_html"] = unidecode(self.proposed_condition_html)
        d["condition_html"] = unidecode(self.condition_html)
        if self.category:
            d["category"] = self.category.name
        else:
            d["category"] = ""
        return mark_safe(template.format(**d).strip())

    def add_clearance(self, task, deposited_plan=None):
        """Get or create a Clearance object on this Condition.
        """
        clearance, created = Clearance.objects.get_or_create(
            condition=self, task=task, deposited_plan=deposited_plan
        )
        return clearance


class ClearanceManager(models.Manager):
    """
    Custom Manager for Clearance models to return current clearances.
    """

    def current(self):
        return self.filter(
            task__effective_to__isnull=True, condition__effective_to__isnull=True
        )

    def active(self):
        return self.filter(
            task__effective_to__isnull=True, condition__effective_to__isnull=True
        )

    def deleted(self):
        return self.filter(task__effective_to__isnull=False)


@python_2_unicode_compatible
class Clearance(models.Model):
    """
    Intermediate class for relationships between Condition and Task objects.
    """
    condition = models.ForeignKey(Condition, on_delete=models.PROTECT)
    task = models.ForeignKey(Task, on_delete=models.PROTECT)
    date_created = models.DateField(auto_now_add=True)
    deposited_plan = models.CharField(
        max_length=200, null=True, blank=True, validators=[MaxLengthValidator(200)]
    )
    headers = [
        "Clearance",
        "Condition no.",
        "Condition",
        "Category",
        "Task",
        "Deposited plan",
        "Referral ID",
    ]
    objects = ClearanceManager()

    def __str__(self):
        return "{0} condition {1} has task {2}".format(
            self.pk, self.condition.pk, self.task.pk
        )

    def get_absolute_url(self):
        return reverse(
            "prs_object_detail", kwargs={"model": "clearance", "pk": self.pk}
        )

    def as_row(self):
        """
        Returns a string of HTML that renders the object details as table row
        cells. Remember to enclose this function in <tr> tags.
        """
        template = """<td><a href="{url}">Open</a></td>
            <td>{identifier}</td>
            <td>{condition}</td>
            <td>{category}</td>
            <td>{task}</td>
            <td>{deposited_plan}</td>
            <td class="referral-id-cell"><a href="{referral_url}">{referral}</a></td>"""
        d = copy(self.__dict__)
        d["url"] = self.get_absolute_url()
        d["identifier"] = self.condition.identifier or ""
        d["condition"] = smart_truncate(self.condition.condition, length=400)
        # Condition "category" is actually an optional single tag.
        if self.condition.tags.all():
            d["category"] = self.condition.tags.all()[0].name
        else:
            d["category"] = ""
        if self.task.description:
            d["task"] = smart_truncate(unidecode(self.task.description), length=400)
        else:
            d["task"] = self.task.type.name
        d["deposited_plan"] = self.deposited_plan or ""
        d["referral"] = self.task.referral
        d["referral_url"] = self.task.referral.get_absolute_url()
        return mark_safe(template.format(**d))

    def as_tbody(self):
        """
        Returns a string of HTML to render the object details inside <tbody> tags.
        """
        template = """<tr><th>Referral</th><td><a href="{referral_url}">{referral}</a></td></tr>
            <tr><th>Referrer's reference</th><td>{reference}</td></tr>
            <tr><th>Referral description</th><td>{referral_desc}</td></tr>
            <tr><th>Condition ID</th><td><a href="{condition_url}">{condition}</a></td></tr>
            <tr><th>Approved condition text</th><td>{condition_html}</td></tr>
            <tr><th>Task ID</th><td><a href="{task_url}">{task}</a></td></tr>
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
        d["condition_url"] = reverse(
            "prs_object_detail", kwargs={"pk": self.condition.pk, "model": "conditions"}
        )
        d["condition"] = self.condition
        d["condition_html"] = self.condition.condition_html
        d["task_url"] = reverse(
            "prs_object_detail", kwargs={"pk": self.task.pk, "model": "tasks"}
        )
        d["task"] = self.task
        if self.task.description:
            d["task_desc"] = unidecode(self.task.description)
        else:
            d["task_desc"] = ""
        d["deposited_plan"] = self.deposited_plan or ""
        return mark_safe(template.format(**d).strip())


class Location(ReferralBaseModel):
    """
    A physical location that is associated with a single referral.
    """
    address_no = models.IntegerField(
        null=True, blank=True, verbose_name="address number"
    )
    address_suffix = models.CharField(
        max_length=10, null=True, blank=True, validators=[MaxLengthValidator(10)]
    )
    road_name = models.CharField(
        max_length=100, null=True, blank=True, validators=[MaxLengthValidator(100)]
    )
    road_suffix = models.CharField(
        max_length=100, null=True, blank=True, validators=[MaxLengthValidator(100)]
    )
    locality = models.CharField(
        max_length=100, null=True, blank=True, validators=[MaxLengthValidator(100)]
    )
    postcode = models.CharField(
        max_length=6, null=True, blank=True, validators=[MaxLengthValidator(6)]
    )
    landuse = models.TextField(null=True, blank=True)
    lot_no = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="lot number",
        validators=[MaxLengthValidator(100)],
    )
    lot_desc = models.TextField(null=True, blank=True)
    strata_lot_no = models.CharField(
        max_length=100, null=True, blank=True, validators=[MaxLengthValidator(100)]
    )
    strata_lot_desc = models.TextField(null=True, blank=True)
    reserve = models.TextField(null=True, blank=True)
    cadastre_obj_id = models.IntegerField(null=True, blank=True)
    referral = models.ForeignKey(Referral, on_delete=models.PROTECT)
    poly = models.PolygonField(srid=4283, null=True, blank=True, help_text="Optional.")
    address_string = models.TextField(null=True, blank=True, editable=True)
    headers = ["Location", "Address", "Polygon", "Referral ID"]
    tools_template = "referral/location_tools.html"

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
        return address

    def save(self, *args, **kwargs):
        """
        Overide the standard save method; inserts nice_address into address_string field.
        """
        self.address_string = self.nice_address.lower()
        super(Location, self).save(*args, **kwargs)

    def as_row(self):
        """
        Returns a string of HTML that renders the object details as table row cells.
        Remember to enclose this function in <tr> tags.
        """
        template = """<td><a href="{url}">Open</a></td>
            <td>{address}</td>
            <td>{polygon}</td>
            <td class="referral-id-cell"><a href="{referral_url}">{referral}</a></td>"""
        d = copy(self.__dict__)
        d["url"] = reverse(
            "prs_object_detail", kwargs={"pk": self.pk, "model": "locations"}
        )
        d["address"] = self.nice_address or "none"
        if self.poly:
            d["polygon"] = '<img src="/static/img/draw_polyline.png" alt="Polygon" />'
        else:
            d["polygon"] = ""
        d["referral_url"] = reverse(
            "referral_detail",
            kwargs={"pk": self.referral.pk, "related_model": "locations"},
        )
        d["referral"] = self.referral
        return mark_safe(template.format(**d))

    def as_row_actions(self):
        """Returns a HTML table cell containing icons with links to suitable
        actions for the location object (edit, delete, etc.)

        html attr class="is_prs_user_action" is used by javascript in the template to
        check prs_user permissions and disables Actions for readonly users.
        """
        template = """<td><a class="is_prs_user_action" href="{edit_url}" title="Edit"><i class="fa fa-pencil"></i></a>
            <a class="is_prs_user_action" href="{delete_url}" title="Delete"><i class="fa fa-trash-o"></i></a></td>"""
        d = copy(self.__dict__)
        d["edit_url"] = reverse(
            "prs_object_update", kwargs={"pk": self.pk, "model": "locations"}
        )
        d["delete_url"] = reverse(
            "prs_object_delete", kwargs={"pk": self.pk, "model": "locations"}
        )
        return mark_safe(template.format(**d))

    def as_row_minus_referral(self):
        """Removes the HTML cell containing the parent referral details.
        """
        return as_row_subtract_referral_cell(self.as_row())

    def as_tbody(self):
        """
        Returns a string of HTML to render the object details inside <tbody> tags.
        """
        template = """<tr><th>Referral</th><td><a href="{referral_url}">{referral}</a></td></tr>
            <tr><th>Referrer's reference</th><td>{reference}</td></tr>
            <tr><th>Short address</th><td>{address}</td></tr>
            <tr><th>Lot no</th><td>{lot_no}</td></tr>
            <tr><th>Address no</th><td>{address_no}</td></tr>
            <tr><th>Address suffix</th><td>{address_suffix}</td></tr>
            <tr><th>Road name</th><td>{road_name}</td></tr>
            <tr><th>Road suffix</th><td>{road_suffix}</td></tr>
            <tr><th>Locality</th><td>{locality}</td></tr>
            <tr><th>Postcode</th><td>{postcode}</td></tr>"""
        d = copy(self.__dict__)
        d["url"] = self.get_absolute_url()
        d["referral_url"] = reverse(
            "referral_detail",
            kwargs={"pk": self.referral.pk, "related_model": "locations"},
        )
        d["referral"] = self.referral
        d["reference"] = self.referral.reference
        d["address"] = self.nice_address or "none"
        d["lot_no"] = self.lot_no or ""
        d["address_no"] = self.address_no or ""
        d["address_suffix"] = self.address_suffix or ""
        d["road_name"] = self.road_name or ""
        d["road_suffix"] = self.road_suffix or ""
        d["locality"] = self.locality or ""
        d["postcode"] = self.postcode or ""
        return mark_safe(template.format(**d).strip())

    def get_regions_intersected(self):
        """Returns a list of Regions whose geometry intersects this Location.
        """
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
    headers = ["Referral ID", "Bookmark description", "Actions"]

    def save(self, force_insert=False, force_update=False, *args, **kwargs):
        """Overide save() to cleanse text input to the description field.
        """
        if self.description:
            self.description = unidecode(self.description)
        super(Bookmark, self).save(force_insert, force_update)

    def as_row(self):
        """
        Returns a string of HTML that renders the object details as table row
        cells. Remember to enclose this function in <tr> tags.

        html attr class="is_prs_user_action" is used by javascript in the
        template to check prs_user permissions and disables Actions for
        readonly users.
        """
        template = """<td><a href="{referral_url}">{referral}</a></td>
            <td>{description}</td>
            <td><a class="is_prs_user_action" href="{delete_url}" title="Delete"><i class="fa fa-trash-o"></i></a></td>"""
        d = copy(self.__dict__)
        d["referral_url"] = self.referral.get_absolute_url()
        d["referral"] = self.referral
        d["description"] = self.description
        d["delete_url"] = reverse(
            "prs_object_delete", kwargs={"pk": self.pk, "model": "bookmarks"}
        )
        return mark_safe(template.format(**d))

    def as_tbody(self):
        """
        Returns a string of HTML to render the object details inside <tbody> tags.
        """
        template = """<tr><th>Referral</th><td><a href="{referral_url}">{referral}</a></td></tr>
            <tr><th>Referrer's reference</th><td>{reference}</td></tr>
            <tr><th>User</th><td>{user}</td></tr>
            <tr><th>Description</th><td>{description}</td></tr>"""
        d = copy(self.__dict__)
        d["referral_url"] = reverse("referral_detail", kwargs={"pk": self.referral.pk})
        d["referral"] = self.referral
        d["reference"] = self.referral.reference
        d["user"] = self.user.get_full_name()
        d["description"] = self.description
        return mark_safe(template.format(**d))


@python_2_unicode_compatible
class UserProfile(models.Model):
    """
    An extension of the Django auth model, to add additional fields to each User
    """
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    agency = models.ForeignKey(Agency, on_delete=models.PROTECT, blank=True, null=True)
    # Referral history is a list of 2-tuples: (referral pk, datetime)
    referral_history = models.TextField(blank=True, null=True)
    task_history = models.TextField(blank=True, null=True)

    def __str__(self):
        return "{0}".format(self.user.username)

    def last_referral(self):
        """
        Return the last referral that the user opened, or None.
        The last referral opened is the last item on the referral_history list in the user's profile.
        """
        if not self.referral_history:
            return None
        ref_history = json.loads(self.referral_history)
        # Reverse the list, then iterate through it until we open a non-deleted referral.
        ref_history.reverse()
        for i in ref_history:
            r = Referral.objects.get(pk=i[0])
            if not r.effective_to:  # Referral hasn't been deleted.
                return r

    def is_prs_user(self):
        """Returns group membership of the PRS user group.
        """
        return self.user.groups.filter(name=settings.PRS_USER_GROUP).exists()

    def is_power_user(self):
        """Returns group membership of the PRS power user group.
        """
        return (
            self.user.is_superuser
            or self.user.groups.filter(name=settings.PRS_POWER_USER_GROUP).exists()
        )


def create_user_profile(**kwargs):
    UserProfile.objects.get_or_create(user=kwargs["user"])


# Connect the user_logged_in signal to the method above to ensure that user
# profiles exist.
user_logged_in.connect(create_user_profile)

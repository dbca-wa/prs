import magic
from crum import get_current_user
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.gis.db import models
from django.core.exceptions import ValidationError
from django.db.models import FileField
from django.urls import reverse
from django.utils import timezone


class ActiveModelManager(models.Manager):
    def current(self):
        """Returns current/non-deleted models only"""
        return self.filter(effective_to=None)

    def deleted(self):
        """Returns non-current/deleted models only"""
        return self.filter(effective_to__isnull=False)


class AuditMixin(models.Model):
    """Model mixin class to provide fields related to auditing."""

    class Meta:
        abstract = True

    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="%(app_label)s_%(class)s_created", editable=False
    )
    modifier = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="%(app_label)s_%(class)s_modified", editable=False
    )
    created = models.DateTimeField(default=timezone.now, editable=False, db_index=True)
    modified = models.DateTimeField(auto_now=True, editable=False, db_index=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._initial = {}
        if self.pk:
            self._reset_initial()

    def __str__(self):
        return str(self.pk)

    def _reset_initial(self):
        """Snapshot the current field values as the baseline for change tracking."""
        self._initial = {field.attname: self.__dict__[field.attname] for field in self._meta.fields if field.attname in self.__dict__}

    def save(self, *args, **kwargs):
        """Set the creator field to the request user on initial save. This falls back on using an admin user if a request user object is absent (i.e. the
        object was saved outside the web application).
        """
        user = get_current_user()
        if not user or (user and not user.pk):
            User = get_user_model()
            user = User.objects.get(id=1)

        self.modifier = user
        if not self.pk:
            self.creator = user

        super().save(*args, **kwargs)

        # Refresh the snapshot, otherwise changed_data would keep reporting the
        # changes that were just saved.
        self._reset_initial()

    def get_absolute_url(self):
        return reverse(f"admin:{self._meta.app_label}_{self._meta.model_name}_change", args=(self.pk,))

    def refresh_from_db(self, *args, **kwargs):
        super().refresh_from_db(*args, **kwargs)
        self._reset_initial()

    @property
    def changed_data(self):
        """Returns a list of fields with data that differs from initial
        values. May be utilised by revision mechanisms, as required.
        """
        self._changed_data = []
        for field, value in self._initial.items():
            if field in ["modified", "modifier_id"]:
                continue  # Disregard modifer field as a test for changed data.
            if getattr(self, field) != value:
                self._changed_data.append(field)
        return self._changed_data


class ActiveModelMixin(models.Model):
    """
    Model mixin to allow objects to be saved as 'non-current' or 'inactive',
    instead of deleting those objects.
    The standard model delete() method is overridden.

    "effective_to" is used to 'delete' objects (null==not deleted).
    """

    effective_to = models.DateTimeField(null=True, blank=True, db_index=True)
    objects = ActiveModelManager()

    class Meta:
        abstract = True

    def is_active(self):
        return self.effective_to is None

    def is_deleted(self):
        return not self.is_active()

    def delete(self, *args, **kwargs):
        """Override the standard delete method; sets effective_to to the current
        date and time, unless ``force=True`` is passed.
        """
        force = kwargs.pop("force", False)
        if force:
            return super().delete(*args, **kwargs)
        self.effective_to = timezone.now()
        super().save(*args, **kwargs)


class ContentTypeRestrictedFileField(FileField):
    """
    Same as Django's normal FileField, but you can specify:
    * content_types - a list containing allowed MIME types.
        Example: ['application/pdf', 'image/jpeg']
    """

    default_error_messages = {
        "filetype": "That file type is not permitted.",
    }

    def __init__(self, content_types=None, *args, **kwargs):
        self.content_types = content_types
        super().__init__(*args, **kwargs)

    def to_python(self, data):
        f = super().to_python(data)
        if f is None or f == "":
            return None
        content_type = magic.from_file(f.path, mime=True)
        if content_type not in self.content_types:
            raise ValidationError(self.error_messages["filetype"])

        return f

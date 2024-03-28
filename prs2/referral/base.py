from crum import get_current_user
from django.conf import settings
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.contrib.gis.db import models
from django.urls import reverse
from django.db.models import FileField
from django.utils import timezone
import magic


class ActiveModelManager(models.Manager):

    def current(self):
        return self.filter(effective_to=None)

    def deleted(self):
        return self.filter(effective_to__isnull=False)


class Audit(models.Model):

    class Meta:
        abstract = True

    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name='%(app_label)s_%(class)s_created', editable=False)
    modifier = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name='%(app_label)s_%(class)s_modified', editable=False)
    created = models.DateTimeField(default=timezone.now, editable=False)
    modified = models.DateTimeField(auto_now=True, editable=False)

    def save(self, *args, **kwargs):
        """This falls back on using an admin user if a request user object is absent (i.e. the
        object was saved outside the web application).
        """
        user = get_current_user()
        if not user or (user and not user.pk):
            User = get_user_model()
            user = User.objects.get(id=1)

        self.modifier = user
        if not self.pk:
            self.creator = user

        super(Audit, self).save(*args, **kwargs)

    def __str__(self):
        return str(self.pk)

    def get_absolute_url(self):
        opts = self._meta.app_label, self._meta.module_name
        return reverse("admin:%s_%s_change" % opts, args=(self.pk, ))


class ActiveModel(models.Model):
    '''
    Model mixin to allow objects to be saved as 'non-current' or 'inactive',
    instead of deleting those objects.
    The standard model delete() method is overridden.

    "effective_to" is used to 'delete' objects (null==not deleted).
    '''
    effective_to = models.DateTimeField(null=True, blank=True)
    objects = ActiveModelManager()

    class Meta:
        abstract = True

    def is_active(self):
        return self.effective_to is None

    def is_deleted(self):
        return not self.is_active()

    def delete(self, *args, **kwargs):
        '''
        Overide the standard delete method; sets effective_to the current date
        and time.
        '''
        self.effective_to = timezone.now()
        super(ActiveModel, self).save(*args, **kwargs)


class ContentTypeRestrictedFileField(FileField):
    """
    Same as Django's normal FileField, but you can specify:
    * content_types - a list containing allowed MIME types.
        Example: ['application/pdf', 'image/jpeg']
    """
    default_error_messages = {
        'filetype': 'That file type is not permitted.',
    }

    def __init__(self, content_types=None, *args, **kwargs):
        self.content_types = content_types
        super(ContentTypeRestrictedFileField, self).__init__(*args, **kwargs)

    def to_python(self, data):
        f = super(ContentTypeRestrictedFileField, self).to_python(data)
        if f is None or f == '':
            return None
        content_type = magic.from_file(f.path, mime=True)
        if content_type not in self.content_types:
            raise ValidationError(self.error_messages['filetype'])

        return f

from __future__ import unicode_literals
from django.conf import settings
from django.db import models
from django.utils.encoding import python_2_unicode_compatible
import xmltodict

from referral.models import Referral, Record, Region


@python_2_unicode_compatible
class EmailedReferral(models.Model):
    """A model to record details about emailed planning referrals.
    """
    harvested = models.DateTimeField(auto_now_add=True)
    received = models.DateTimeField(blank=True, null=True, editable=False)
    email_uid = models.CharField(max_length=256)
    to_email = models.CharField(max_length=256)
    from_email = models.CharField(max_length=256)
    subject = models.CharField(max_length=256)
    body = models.TextField()
    referral = models.ForeignKey(
        Referral, null=True, blank=True, on_delete=models.PROTECT)
    processed = models.BooleanField(default=False)

    def __str__(self):
        return self.subject


@python_2_unicode_compatible
class EmailAttachment(models.Model):
    """A saved email file attachment.
    """
    emailed_referral = models.ForeignKey(EmailedReferral, on_delete=models.PROTECT)
    name = models.CharField(max_length=256)
    attachment = models.FileField(
        max_length=255, upload_to='email_attachments/%Y/%m/%d')
    record = models.ForeignKey(
        Record, null=True, blank=True, on_delete=models.PROTECT)

    def __str__(self):
        return self.name

    def get_xml_data(self):
        """Convenience function to conditionally return XML data from the
        attachment (returns None if not an XML file).
        """
        d = None
        if self.name.startswith('Application.xml'):
            self.attachment.seek(0)
            d = xmltodict.parse(self.attachment.read())
        return d


@python_2_unicode_compatible
class RegionAssignee(models.Model):
    """A model to define which user will be assigned any generated referrals
    for a region.
    """
    region = models.OneToOneField(Region)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        limit_choices_to={'groups__name__in': ['PRS user'], 'is_active': True},
        help_text='Default assigned user for this region.')

    def __str__(self):
        return '{} -> {}'.format(self.region, self.user.get_full_name())

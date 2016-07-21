from __future__ import unicode_literals
from django.db import models

from referral.models import Referral, Record


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


class EmailAttachment(models.Model):
    """A saved email file attachment.
    """
    emailed_referral = models.ForeignKey(EmailedReferral, on_delete=models.PROTECT)
    name = models.CharField(max_length=256)
    attachment = models.FileField(
        max_length=255, upload_to='email_attachments/%Y/%m/%d')
    record = models.ForeignKey(
        Record, null=True, blank=True, on_delete=models.PROTECT)

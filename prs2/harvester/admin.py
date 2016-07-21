from django.contrib import admin
from harvester.models import EmailedReferral, EmailAttachment


@admin.register(EmailedReferral)
class EmailedReferralAdmin(admin.ModelAdmin):
    pass


@admin.register(EmailAttachment)
class EmailAttachmentAdmin(admin.ModelAdmin):
    pass

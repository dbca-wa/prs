from django.contrib import admin
from harvester.models import EmailedReferral, EmailAttachment


@admin.register(EmailedReferral)
class EmailedReferralAdmin(admin.ModelAdmin):
    date_hierarchy = 'received'
    list_display = (
        'subject', 'received', 'harvested', 'attachments', 'referral')
    search_fields = ('subject',)

    def attachments(self, instance):
        return instance.emailattachment_set.count()


@admin.register(EmailAttachment)
class EmailAttachmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'emailed_referral', 'record')
    search_fields = ('name', 'emailed_referral__subject',)

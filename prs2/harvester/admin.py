from django.contrib import admin
from django.core.urlresolvers import reverse
from django.utils.safestring import mark_safe
from harvester.models import EmailedReferral, EmailAttachment, RegionAssignee


@admin.register(EmailedReferral)
class EmailedReferralAdmin(admin.ModelAdmin):
    date_hierarchy = 'received'
    list_display = (
        'to_email', 'subject', 'received', 'harvested', 'attachments',
        'referral_detail', 'processed')
    raw_id_fields = ('referral',)
    search_fields = ('subject',)

    def attachments(self, instance):
        return instance.emailattachment_set.count()

    def referral_detail(self, instance):
        if not instance.referral:
            return ''
        url = reverse('referral_detail', args=[instance.referral.pk])
        return mark_safe('<a href="{}">{}</a>'.format(url, instance.referral.pk))
    referral_detail.short_description = 'Referral'


@admin.register(EmailAttachment)
class EmailAttachmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'emailed_referral', 'record')
    raw_id_fields = ('record',)
    search_fields = ('name', 'emailed_referral__subject',)


@admin.register(RegionAssignee)
class RegionAssigneeAdmin(admin.ModelAdmin):
    list_display = ('region', 'user')
    raw_id_fields = ('user',)

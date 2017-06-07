from django.contrib import admin
from django.core.urlresolvers import reverse
from django.utils.safestring import mark_safe
from harvester.models import EmailedReferral, EmailAttachment, RegionAssignee


@admin.register(EmailedReferral)
class EmailedReferralAdmin(admin.ModelAdmin):
    date_hierarchy = 'received'
    list_display = (
        'to_email', 'subject', 'received', 'harvested', 'attachments',
        'referral_url', 'processed')
    raw_id_fields = ('referral',)
    search_fields = ('subject',)

    def attachments(self, instance):
        return instance.emailattachment_set.count()

    def referral_url(self, instance):
        if not instance.referral:
            return ''
        url = reverse('admin:referral_referral_change', args=[instance.referral.pk])
        return mark_safe('<a href="{}">{}</a>'.format(url, instance.referral.pk))
    referral_url.short_description = 'Referral'


@admin.register(EmailAttachment)
class EmailAttachmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'emailed_referral_url', 'record_url')
    raw_id_fields = ('record',)
    search_fields = ('name', 'emailed_referral__subject',)

    def emailed_referral_url(self, instance):
        url = reverse('admin:harvester_emailedreferral_change', args=[instance.emailed_referral.pk])
        return mark_safe('<a href="{}">{}</a>'.format(url, instance.emailed_referral))
    emailed_referral_url.short_description = 'Emailed referral'

    def record_url(self, instance):
        if not instance.record:
            return ''
        url = reverse('admin:referral_record_change', args=[instance.record.pk])
        return mark_safe('<a href="{}">{}</a>'.format(url, instance.record.pk))
    record_url.short_description = 'Record'


@admin.register(RegionAssignee)
class RegionAssigneeAdmin(admin.ModelAdmin):
    list_display = ('region', 'user')
    raw_id_fields = ('user',)

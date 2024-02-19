from django.contrib import admin, messages
from django.urls import reverse
from django.utils.safestring import mark_safe
from harvester.models import EmailedReferral, EmailAttachment, RegionAssignee


@admin.register(EmailedReferral)
class EmailedReferralAdmin(admin.ModelAdmin):

    def harvest_referral(modeladmin, request, queryset):
        """A custom admin action to call an EmailedReferral object harvest() method.
        """
        for er in queryset:
            actions = []
            if not er.processed:
                try:
                    actions.append(er.harvest())
                except Exception:
                    actions.append('Emailed referral {} failed to import; notify the custodian to investigate'.format(er))
            else:
                actions.append('Emailed referral {} is already processed'.format(er))
            msg = ''
            for action in actions:
                msg += '{}\n'.format(action)
            messages.success(request, msg)

    harvest_referral.short_description = 'Run the harvest function for selected emailed referrals'

    actions = [harvest_referral]
    date_hierarchy = 'received'
    list_display = (
        'received', 'from_email', 'subject', 'harvested', 'attachments_url',
        'referral_url', 'processed')
    raw_id_fields = ('referral',)
    search_fields = ('subject',)
    readonly_fields = ['email_uid', 'to_email', 'from_email', 'subject', 'body', 'processed', 'log']

    def attachments_url(self, instance):
        if not instance.emailattachment_set.exists():
            return ""
        count = instance.emailattachment_set.count()
        url = reverse("admin:harvester_emailattachment_changelist")
        return mark_safe(f"<a href='{url}?emailed_referral_id__exact={instance.pk}'>{count}</a>")
    attachments_url.short_description = 'attachments'

    def referral_url(self, instance):
        if not instance.referral:
            return ""
        url = reverse("admin:referral_referral_change", args=[instance.referral.pk])
        return mark_safe(f"<a href='{url}'>{instance.referral.pk}</a>")
    referral_url.short_description = "Referral"


@admin.register(EmailAttachment)
class EmailAttachmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'emailed_referral_url', 'record_url')
    raw_id_fields = ('record',)
    search_fields = ('name', 'emailed_referral__subject',)
    readonly_fields = ['emailed_referral', 'name', 'attachment']

    def emailed_referral_url(self, instance):
        url = reverse('admin:harvester_emailedreferral_change', args=[instance.emailed_referral.pk])
        return mark_safe(f'<a href="{url}">{instance.emailed_referral}</a>')
    emailed_referral_url.short_description = 'Emailed referral'

    def record_url(self, instance):
        if not instance.record:
            return ''
        url = reverse('admin:referral_record_change', args=[instance.record.pk])
        return mark_safe(f'<a href="{url}">{instance.record.pk}</a>')
    record_url.short_description = 'Record'


@admin.register(RegionAssignee)
class RegionAssigneeAdmin(admin.ModelAdmin):
    list_display = ('region', 'user')
    raw_id_fields = ('user',)

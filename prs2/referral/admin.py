# Core Django imports
from django.contrib.gis import admin
from django.contrib.gis.admin import ModelAdmin
# Third-party app imports
from reversion.admin import VersionAdmin
# PRS project imports
from referral.models import (
    DopTrigger, Region, OrganisationType, Organisation, TaskType,
    TaskState, NoteType, ReferralType, Referral, Task, Record,
    Note, Condition, Location, Bookmark, Clearance, Agency,
    ConditionCategory, ModelCondition, UserProfile)


class AuditAdmin(VersionAdmin, ModelAdmin):
    search_fields = [
        'id', 'creator__username', 'modifier__username', 'creator__email',
        'modifier__email']
    list_display = ['__unicode__', 'creator', 'modifier', 'created', 'modified']
    raw_id_fields = ['creator', 'modifier']


class LookupAdmin(AuditAdmin):
    list_display = (
        'id', 'name', 'slug', 'public', 'created', 'modified', 'effective_to')
    raw_id_fields = ('creator', 'modifier')
    search_fields = ('name', 'slug')

admin.site.register(Region, LookupAdmin)
admin.site.register(OrganisationType, LookupAdmin)
admin.site.register(DopTrigger, LookupAdmin)
admin.site.register(TaskType, LookupAdmin)
admin.site.register(NoteType, LookupAdmin)
admin.site.register(ConditionCategory, LookupAdmin)


class OrganisationAdmin(LookupAdmin):
    list_display = (
        'id', 'name', 'list_name', 'slug', 'created', 'modified', 'effective_to')
admin.site.register(Organisation, OrganisationAdmin)


class TaskStateAdmin(LookupAdmin):
    list_display = (
        'id', 'name', 'slug', 'public', 'task_type', 'is_ongoing',
        'is_assessment', 'created', 'modified', 'effective_to')
admin.site.register(TaskState, TaskStateAdmin)


class ReferralTypeAdmin(LookupAdmin):
    list_display = (
        'id', 'name', 'slug', 'initial_task', 'public', 'created', 'modified',
        'effective_to')
admin.site.register(ReferralType, ReferralTypeAdmin)


class ReferralBaseModelAdmin(AuditAdmin):
    list_display = ('id', 'creator', 'created', 'modifed', 'effective_to')
    raw_id_fields = ['creator', 'modifier']


class ReferralAdmin(ReferralBaseModelAdmin):
    list_display = (
        'id', 'regions_display', 'type', 'reference', 'referring_org', 'creator',
        'created', 'modified', 'effective_to')
    list_filter = ('type', 'referring_org', 'region')
    date_hierarchy = 'referral_date'
    raw_id_fields = ReferralBaseModelAdmin.raw_id_fields + ['referring_org']
    search_fields = (
        'id', 'region__name', 'type__name', 'reference', 'file_no',
        'referring_org__name', 'creator__username', 'description', 'tags__name',
        'address', 'dop_triggers__name')

    def regions_display(self, obj):
        return obj.regions_str
    regions_display.short_description = 'region(s)'

admin.site.register(Referral, ReferralAdmin)


class TaskAdmin(ReferralBaseModelAdmin):
    list_display = (
        'id', 'type', 'referral', 'assigned_user', 'state', 'creator', 'created',
        'modified', 'effective_to')
    raw_id_fields = ('creator', 'modifier', 'referral', 'assigned_user')
    date_hierarchy = 'created'
    search_fields = (
        'id', 'type__name', 'referral__id', 'assigned_user__username', 'description',
        'assigned_user__first_name', 'assigned_user__last_name', 'state__name')
admin.site.register(Task, TaskAdmin)


class RecordAdmin(ReferralBaseModelAdmin):
    list_display = (
        'id', 'name', 'infobase_id', 'creator', 'created', 'modified', 'effective_to')
    raw_id_fields = ReferralBaseModelAdmin.raw_id_fields + ['referral']
    date_hierarchy = 'created'
    search_fields = ('id', 'name', 'infobase_id', 'description')
admin.site.register(Record, RecordAdmin)


class NoteAdmin(ReferralBaseModelAdmin):
    list_display = (
        'id', 'referral', 'note', 'creator', 'created', 'modified', 'effective_to')
    raw_id_fields = ReferralBaseModelAdmin.raw_id_fields + ['referral']
    date_hierarchy = 'created'
    search_fields = ('id', 'note')
admin.site.register(Note, NoteAdmin)


class ModelConditionAdmin(ReferralBaseModelAdmin):
    list_display = (
        'id', 'condition', 'category', 'identifier', 'creator', 'created',
        'modified', 'effective_to')
    search_fields = (
        'id', 'condition', 'category__name', 'identifier', 'creator__username')
admin.site.register(ModelCondition, ModelConditionAdmin)


class ConditionAdmin(ReferralBaseModelAdmin):
    list_display = (
        'id', 'referral', 'condition', 'creator', 'created', 'modified',
        'effective_to')
    raw_id_fields = ReferralBaseModelAdmin.raw_id_fields + ['referral']
    date_hierarchy = 'created'
    search_fields = ('id', 'condition', 'creator__username', 'tags__name')
admin.site.register(Condition, ConditionAdmin)


class LocationAdmin(ReferralBaseModelAdmin):
    list_display = (
        'id', 'referral', 'creator', 'created', 'modified', 'effective_to')
    raw_id_fields = ReferralBaseModelAdmin.raw_id_fields + ['referral']
    date_hierarchy = 'created'
    search_fields = (
        'id', 'address_no', 'lot_no', 'road_name', 'road_suffix', 'locality',
        'postcode', 'address_string')
admin.site.register(Location, LocationAdmin)


class BookmarkAdmin(ReferralBaseModelAdmin):
    list_display = (
        'id', 'referral', 'user', 'description', 'created', 'modified',
        'effective_to')
    raw_id_fields = ReferralBaseModelAdmin.raw_id_fields + ['referral']
    date_hierarchy = 'created'
    search_fields = ('id', 'referral__id', 'user__username', 'description')
admin.site.register(Bookmark, BookmarkAdmin)


class ClearanceAdmin(admin.ModelAdmin):
    list_display = ('id', 'condition', 'task', 'date_created', 'deposited_plan')
    raw_id_fields = ('condition', 'task')
    date_hierarchy = 'date_created'
    search_fields = (
        'condition__id', 'condition__condition', 'task__id', 'task__description',
        'deposited_plan')
admin.site.register(Clearance, ClearanceAdmin)


class AgencyAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'code')
    search_fields = ('name', 'code')
admin.site.register(Agency, AgencyAdmin)


class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('id', 'user')
    search_fields = ('user__username', 'user__first_name', 'user__last_name')
admin.site.register(UserProfile, UserProfileAdmin)

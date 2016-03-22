from tastypie import fields
from tastypie.authentication import SessionAuthentication
from tastypie.authorization import DjangoAuthorization
from tastypie.cache import SimpleCache
from tastypie.resources import ModelResource, ALL_WITH_RELATIONS

from referral.models import (
    DopTrigger, Region, OrganisationType, Organisation, TaskState, TaskType,
    ReferralType, NoteType, Agency, Referral, Task, Record, Note, Condition,
    ConditionCategory, Clearance, Location, UserProfile, ModelCondition)


def generate_filtering(mdl):
    """Utility function to add all model fields to filtering whitelist.
    """
    filtering = {}
    for field in mdl._meta.fields:
        filtering.update({field.name: ALL_WITH_RELATIONS})
    return filtering


def generate_meta(klass, overrides={}):
    """Utility function to generate a standard ModelResource Meta class.
    """
    metaitems = {
        'authentication': SessionAuthentication(),
        'authorization': DjangoAuthorization(),
        'queryset': klass.objects.all(),
        'resource_name': klass._meta.model_name,
        'filtering': generate_filtering(klass),
        'cache': SimpleCache(),
        'allowed_methods': ['get'],
    }
    metaitems.update(overrides)
    return type('Meta', (object,), metaitems)


class DopTriggerResource(ModelResource):
    Meta = generate_meta(DopTrigger)


class RegionResource(ModelResource):
    Meta = generate_meta(Region)


class OrganisationTypeResource(ModelResource):
    Meta = generate_meta(OrganisationType)


class OrganisationResource(ModelResource):
    Meta = generate_meta(Organisation)
    type = fields.ToOneField(
        OrganisationTypeResource, attribute='type', full=True)


class TaskStateResource(ModelResource):
    Meta = generate_meta(TaskState)
    task_type = fields.ToOneField(
        'referral.api.TaskTypeResource', attribute='task_type', full=True,
        null=True, blank=True)


class TaskTypeResource(ModelResource):
    Meta = generate_meta(TaskType)
    initial_state = fields.ToOneField(
        'referral.api.TaskStateResource', attribute='initial_state', full=True,
        null=True, blank=True)


class ReferralTypeResource(ModelResource):
    Meta = generate_meta(ReferralType)


class NoteTypeResource(ModelResource):
    Meta = generate_meta(NoteType)


class AgencyResource(ModelResource):
    Meta = generate_meta(Agency)


class ReferralResource(ModelResource):
    Meta = generate_meta(Referral)
    type = fields.ToOneField(ReferralTypeResource, attribute='type', full=True)
    agency = fields.ToOneField(
        AgencyResource, attribute='agency', full=True, null=True, blank=True)
    region = fields.ToManyField(
        RegionResource, attribute='region', full=True, null=True, blank=True)
    referring_org = fields.ToOneField(
        OrganisationResource, attribute='referring_org', full=True)
    dop_triggers = fields.ToManyField(
        DopTriggerResource, attribute='dop_triggers', full=True, null=True,
        blank=True)
    related_refs = fields.ToManyField(
        'self', attribute='related_refs', null=True, blank=True)
    tags = fields.ToManyField(
        'prs2.api.TagResource', attribute='tags', full=True, null=True, blank=True)
    # Update Meta filtering to include M2M fields.
    Meta.filtering.update({
        'region': ALL_WITH_RELATIONS,
        'dop_triggers': ALL_WITH_RELATIONS,
        'tags': ALL_WITH_RELATIONS,
    })


class TaskResource(ModelResource):
    Meta = generate_meta(Task)
    type = fields.ToOneField(TaskTypeResource, attribute='type', full=True)
    referral = fields.ToOneField(
        ReferralResource, attribute='referral', full=True)
    assigned_user = fields.ToOneField(
        'prs2.api.UserResource', attribute='assigned_user', full=True)
    state = fields.ToOneField(TaskStateResource, attribute='state', full=True)


class RecordResource(ModelResource):
    Meta = generate_meta(Record)
    referral = fields.ToOneField(
        ReferralResource, attribute='referral', full=True)
    notes = fields.ToManyField(
        'referral.api.NoteResource', attribute='notes', full=True, null=True,
        blank=True)


class NoteResource(ModelResource):
    Meta = generate_meta(Note)
    referral = fields.ToOneField(
        ReferralResource, attribute='referral', full=True)
    type = fields.ToOneField(
        NoteTypeResource, attribute='type', full=True, null=True, blank=True)
    records = fields.ToManyField(
        'referral.api.RecordResource', attribute='records', full=True,
        null=True, blank=True)


class ConditionCategoryResource(ModelResource):
    Meta = generate_meta(ConditionCategory)


class ModelConditionResource(ModelResource):
    Meta = generate_meta(ModelCondition)
    category = fields.ToOneField(
        ConditionCategoryResource, attribute='category', full=True, null=True)


class ConditionResource(ModelResource):
    Meta = generate_meta(Condition)
    referral = fields.ToOneField(
        ReferralResource, attribute='referral', full=True, null=True,
        blank=True)
    clearance_tasks = fields.ToManyField(
        TaskResource, attribute='clearance_tasks', full=True, null=True,
        blank=True)
    category = fields.ToOneField(
        ConditionCategoryResource, attribute='category', full=True, null=True)
    tags = fields.ToManyField(
        'prs2.api.TagResource', attribute='tags', full=True, null=True, blank=True)
    # Update Meta filtering to include M2M fields.
    Meta.filtering.update({
        'tags': ALL_WITH_RELATIONS,
    })


class ClearanceResource(ModelResource):
    Meta = generate_meta(Clearance)
    condition = fields.ToOneField(
        ConditionResource, attribute='condition', full=True)
    task = fields.ToOneField(TaskResource, attribute='task', full=True)


class LocationResource(ModelResource):
    Meta = generate_meta(Location)
    referral = fields.ToOneField(
        ReferralResource, attribute='referral', full=True, null=True,
        blank=True)


class UserProfileResource(ModelResource):
    Meta = generate_meta(UserProfile)
    user = fields.ToOneField(
        'prs2.api.UserResource', attribute='user', full=False, null=True, blank=True)

from django.db.models import signals
from django.contrib.auth import get_user_model
from tastypie import fields
from tastypie.authentication import BasicAuthentication, ApiKeyAuthentication, SessionAuthentication, MultiAuthentication
from tastypie.cache import SimpleCache
from tastypie.models import create_api_key
from tastypie.resources import ModelResource, ALL_WITH_RELATIONS

from referral.models import (
    DopTrigger, Region, OrganisationType, Organisation, TaskState, TaskType,
    ReferralType, NoteType, Agency, Referral, Task, Record, Note, Condition,
    ConditionCategory, Clearance, Location, UserProfile, ModelCondition)


# Set up a signal to auto-create API key values for users.
User = get_user_model()
signals.post_save.connect(create_api_key, sender=User)


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
        'authentication': MultiAuthentication(ApiKeyAuthentication(), BasicAuthentication(), SessionAuthentication()),
        'queryset': klass.objects.all(),
        'resource_name': klass._meta.model_name,
        'filtering': generate_filtering(klass),
        'cache': SimpleCache(),
        'allowed_methods': ['get'],
    }
    metaitems.update(overrides)
    return type('Meta', (object,), metaitems)


class DopTriggerResource(ModelResource):
    Meta = generate_meta(DopTrigger, overrides={'queryset': DopTrigger.objects.current().filter(public=True)})


class RegionResource(ModelResource):
    Meta = generate_meta(Region, overrides={'excludes': ['region_mpoly'], 'queryset': Region.objects.current().filter(public=True)})


class OrganisationTypeResource(ModelResource):
    Meta = generate_meta(OrganisationType, overrides={'queryset': OrganisationType.objects.current().filter(public=True)})


class OrganisationResource(ModelResource):
    Meta = generate_meta(Organisation, overrides={'queryset': Organisation.objects.current().filter(public=True)})
    type = fields.ToOneField(
        OrganisationTypeResource, attribute='type', full=True)


class TaskStateResource(ModelResource):
    Meta = generate_meta(TaskState, overrides={'queryset': TaskState.objects.current().filter(public=True)})
    task_type = fields.ToOneField(
        'referral.api.TaskTypeResource', attribute='task_type', full=True,
        null=True, blank=True)


class TaskTypeResource(ModelResource):
    Meta = generate_meta(TaskType, overrides={'queryset': TaskType.objects.current().filter(public=True)})
    initial_state = fields.ToOneField(
        'referral.api.TaskStateResource', attribute='initial_state', full=True,
        null=True, blank=True)


class ReferralTypeResource(ModelResource):
    Meta = generate_meta(ReferralType, overrides={'queryset': ReferralType.objects.current().filter(public=True)})
    initial_task = fields.ToOneField(
        'referral.api.TaskTypeResource', attribute='initial_task', full=True,
        null=True, blank=True)


class NoteTypeResource(ModelResource):
    Meta = generate_meta(NoteType, overrides={'queryset': NoteType.objects.current().filter(public=True)})


class AgencyResource(ModelResource):
    Meta = generate_meta(Agency, overrides={'queryset': Agency.objects.current().filter(public=True)})


class ReferralResource(ModelResource):
    Meta = generate_meta(Referral, overrides={'queryset': Referral.objects.current()})
    type = fields.ToOneField(ReferralTypeResource, attribute='type', full=True)
    agency = fields.ToOneField(
        AgencyResource, attribute='agency', full=True, null=True, blank=True)
    regions = fields.ToManyField(
        RegionResource, attribute='regions', full=True, null=True, blank=True)
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
        'regions': ALL_WITH_RELATIONS,
        'dop_triggers': ALL_WITH_RELATIONS,
        'tags': ALL_WITH_RELATIONS,
    })


class TaskResource(ModelResource):
    Meta = generate_meta(Task, overrides={'queryset': Task.objects.current()})
    type = fields.ToOneField(TaskTypeResource, attribute='type', full=True)
    referral = fields.ToOneField(
        ReferralResource, attribute='referral', full=True)
    assigned_user = fields.ToOneField(
        'prs2.api.UserResource', attribute='assigned_user', full=True)
    state = fields.ToOneField(TaskStateResource, attribute='state', full=True)


class RecordResource(ModelResource):
    Meta = generate_meta(Record, overrides={'queryset': Record.objects.current()})
    referral = fields.ToOneField(
        ReferralResource, attribute='referral', full=True)
    notes = fields.ToManyField(
        'referral.api.NoteResource', attribute='notes', full=True, null=True,
        blank=True)


class NoteResource(ModelResource):
    Meta = generate_meta(Note, overrides={'queryset': Note.objects.current()})
    referral = fields.ToOneField(
        ReferralResource, attribute='referral', full=True)
    type = fields.ToOneField(
        NoteTypeResource, attribute='type', full=True, null=True, blank=True)
    records = fields.ToManyField(
        'referral.api.RecordResource', attribute='records', full=True,
        null=True, blank=True)


class ConditionCategoryResource(ModelResource):
    Meta = generate_meta(ConditionCategory, overrides={'queryset': ConditionCategory.objects.current().filter(public=True)})


class ModelConditionResource(ModelResource):
    Meta = generate_meta(ModelCondition, overrides={'queryset': ModelCondition.objects.current()})
    category = fields.ToOneField(
        ConditionCategoryResource, attribute='category', full=True, null=True)


class ConditionResource(ModelResource):
    Meta = generate_meta(Condition, overrides={'queryset': Condition.objects.current()})
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
    Meta = generate_meta(Location, overrides={'queryset': Location.objects.current()})
    referral = fields.ToOneField(
        ReferralResource, attribute='referral', full=True, null=True,
        blank=True)


class UserProfileResource(ModelResource):
    Meta = generate_meta(UserProfile)
    user = fields.ToOneField(
        'prs2.api.UserResource', attribute='user', full=False, null=True, blank=True)

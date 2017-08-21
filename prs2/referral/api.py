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
    Meta = generate_meta(
        DopTrigger, overrides={
            'queryset': DopTrigger.objects.current().filter(public=True),
            'excludes': ['created', 'description', 'effective_to', 'modified', 'public']
        })


class RegionResource(ModelResource):
    Meta = generate_meta(
        Region, overrides={'excludes': ['region_mpoly'], 'queryset': Region.objects.current().filter(public=True)})


class OrganisationTypeResource(ModelResource):
    Meta = generate_meta(
        OrganisationType, overrides={'queryset': OrganisationType.objects.current().filter(public=True)})


class OrganisationResource(ModelResource):
    Meta = generate_meta(
        Organisation, overrides={'queryset': Organisation.objects.current().filter(public=True)})


class TaskStateResource(ModelResource):
    Meta = generate_meta(
        TaskState, overrides={'queryset': TaskState.objects.current().filter(public=True)})
    task_type = fields.ToOneField(
        'referral.api.TaskTypeResource', attribute='task_type', full=False,
        null=True, blank=True)


class TaskTypeResource(ModelResource):
    Meta = generate_meta(TaskType, overrides={'queryset': TaskType.objects.current().filter(public=True)})
    initial_state = fields.ToOneField(
        'referral.api.TaskStateResource', attribute='initial_state', full=False,
        null=True, blank=True)


class ReferralTypeResource(ModelResource):
    Meta = generate_meta(
        ReferralType, overrides={'queryset': ReferralType.objects.current().filter(public=True)})


class NoteTypeResource(ModelResource):
    Meta = generate_meta(NoteType, overrides={'queryset': NoteType.objects.current().filter(public=True)})


class AgencyResource(ModelResource):
    Meta = generate_meta(Agency, overrides={'queryset': Agency.objects.current().filter(public=True)})


class ReferralResource(ModelResource):
    Meta = generate_meta(
        Referral, overrides={
            'queryset': Referral.objects.current(),
            'excludes': ['created', 'effective_to', 'modified']
        })
    # Update Meta filtering to include M2M fields.
    Meta.filtering.update({
        'regions': ALL_WITH_RELATIONS,
        'dop_triggers': ALL_WITH_RELATIONS,
        'tags': ALL_WITH_RELATIONS,
    })

    def build_filters(self, filters=None, ignore_bad_filters=False):
        # Because we override the dehydrate for many fields, we need to define the
        # field filtering manually here.
        if filters is None:
            filters = {}
        orm_filters = super(ReferralResource, self).build_filters(filters, ignore_bad_filters)

        if 'regions__id__in' in filters:
            orm_filters['regions__id__in'] = filters['regions__id__in']
        if 'referring_org__id' in filters:
            orm_filters['referring_org__id'] = filters['referring_org__id']
        if 'type__id' in filters:
            orm_filters['type__id'] = filters['type__id']
        if 'tags__id__in' in filters:
            orm_filters['tags__id__in'] = filters['tags__id__in']

        return orm_filters

    def dehydrate(self, bundle):
        bundle.data['type'] = bundle.obj.type.name
        bundle.data['regions'] = [i.name for i in bundle.obj.regions.all()]
        bundle.data['referring_org'] = bundle.obj.referring_org.name
        bundle.data['dop_triggers'] = [i.name for i in bundle.obj.dop_triggers.all()]
        bundle.data['related_refs'] = [i.pk for i in bundle.obj.related_refs.all()]
        bundle.data['tags'] = [i.name for i in bundle.obj.tags.all()]
        return bundle


class TaskResource(ModelResource):
    Meta = generate_meta(Task, overrides={
        'queryset': Task.objects.current(),
        'excludes': ['created', 'effective_to', 'modified']
    })

    def build_filters(self, filters=None, ignore_bad_filters=False):
        # Because we override the dehydrate for many fields, we need to define the
        # field filtering manually here.
        # For 'through' field filters, we need to pop those out of the filters
        # and re-apply them after calling ``super``.
        if 'referral__regions__id__in' in filters:
            ref_region = filters.pop('referral__regions__id__in')
        else:
            ref_region = False

        if filters is None:
            filters = {}
        orm_filters = super(TaskResource, self).build_filters(filters, ignore_bad_filters)

        if ref_region:
            orm_filters['referral__regions__id__in'] = ref_region
        if 'type__id' in filters:
            orm_filters['type__id'] = filters['type__id']
        if 'state__id' in filters:
            orm_filters['state__id'] = filters['state__id']
        if 'assigned_user__id' in filters:
            orm_filters['assigned_user__id'] = filters['assigned_user__id']

        return orm_filters

    def dehydrate(self, bundle):
        bundle.data['referral'] = bundle.obj.referral.pk
        bundle.data['reference'] = bundle.obj.referral.reference
        bundle.data['regions'] = [i.name for i in bundle.obj.referral.regions.all()]
        bundle.data['type'] = bundle.obj.type.name
        bundle.data['assigned_user'] = bundle.obj.assigned_user.get_full_name()
        bundle.data['state'] = bundle.obj.state.name
        return bundle


class RecordResource(ModelResource):
    Meta = generate_meta(Record, overrides={
        'queryset': Record.objects.current(),
        'excludes': ['created', 'effective_to', 'modified']
    })

    def dehydrate(self, bundle):
        bundle.data['referral'] = bundle.obj.referral.pk
        bundle.data['notes'] = [i.pk for i in bundle.obj.notes.all()]
        return bundle


class NoteResource(ModelResource):
    Meta = generate_meta(Note, overrides={
        'queryset': Note.objects.current(),
        'excludes': ['created', 'effective_to', 'modified', 'note_html']
    })

    def dehydrate(self, bundle):
        bundle.data['note'] = bundle.obj.note.strip()
        bundle.data['referral'] = bundle.obj.referral.pk
        bundle.data['type'] = bundle.obj.type.name if bundle.obj.type else ''
        bundle.data['records'] = [i.pk for i in bundle.obj.records.all()]
        return bundle


class ConditionCategoryResource(ModelResource):
    Meta = generate_meta(
        ConditionCategory, overrides={'queryset': ConditionCategory.objects.current().filter(public=True)})


class ModelConditionResource(ModelResource):
    Meta = generate_meta(ModelCondition, overrides={'queryset': ModelCondition.objects.current()})
    category = fields.ToOneField(
        ConditionCategoryResource, attribute='category', full=True, null=True)


class ConditionResource(ModelResource):
    Meta = generate_meta(
        Condition, overrides={
            'queryset': Condition.objects.current(),
            'excludes': ['condition_html', 'created', 'effective_to', 'modified', 'proposed_condition_html']
        })
    # Update Meta filtering to include M2M fields.
    Meta.filtering.update({
        'tags': ALL_WITH_RELATIONS,
    })

    def dehydrate(self, bundle):
        bundle.data['referral'] = bundle.obj.referral.pk
        bundle.data['category'] = bundle.obj.category.name if bundle.obj.category else None
        bundle.data['clearance_tasks'] = [i.pk for i in bundle.obj.clearance_tasks.all()]
        bundle.data['tags'] = [i.name for i in bundle.obj.tags.all()]
        return bundle


class ClearanceResource(ModelResource):
    Meta = generate_meta(Clearance)

    def build_filters(self, filters=None, ignore_bad_filters=False):
        # Because we override the dehydrate for many fields, we need to define the
        # field filtering manually here.
        # For 'through' field filters, we need to pop those out of the filters
        # and re-apply them after calling ``super``.
        if 'task__referral__regions__id__in' in filters:
            task_ref_region = filters.pop('task__referral__regions__id__in')
        else:
            task_ref_region = False
        if 'task__state__id' in filters:
            task_state = filters.pop('task__state__id')[0]
        else:
            task_state = None

        if filters is None:
            filters = {}
        orm_filters = super(ClearanceResource, self).build_filters(filters, ignore_bad_filters)

        if task_ref_region:
            orm_filters['task__referral__regions__id__in'] = task_ref_region
        if task_state:
            orm_filters['task__state__id'] = task_state

        return orm_filters

    def dehydrate(self, bundle):
        bundle.data['task'] = bundle.obj.task.pk
        bundle.data['description'] = bundle.obj.task.description
        bundle.data['assigned_user'] = bundle.obj.task.assigned_user.get_full_name()
        bundle.data['state'] = bundle.obj.task.state.name
        bundle.data['referral'] = bundle.obj.task.referral.pk
        bundle.data['regions'] = [i.name for i in bundle.obj.task.referral.regions.all()]
        bundle.data['condition'] = bundle.obj.condition.condition
        bundle.data['identifier'] = bundle.obj.condition.identifier
        bundle.data['category'] = bundle.obj.condition.category.name if bundle.obj.condition.category else None
        return bundle


class LocationResource(ModelResource):
    Meta = generate_meta(Location, overrides={
        'queryset': Location.objects.current(),
        'excludes': ['created', 'effective_to', 'modified']
    })

    def dehydrate(self, bundle):
        bundle.data['referral'] = bundle.obj.referral.pk
        return bundle


class UserProfileResource(ModelResource):
    Meta = generate_meta(UserProfile)
    user = fields.ToOneField(
        'prs2.api.UserResource', attribute='user', full=False, null=True, blank=True)

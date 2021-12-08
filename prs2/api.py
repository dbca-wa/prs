from django.conf import settings
from django.urls import path
from django.views.decorators.cache import cache_page
from referral import api_v1 as referral_api_v1
from taggit.models import Tag
from tastypie.api import Api
from tastypie.authentication import SessionAuthentication
from tastypie.cache import SimpleCache
from tastypie.resources import ModelResource, ALL
from django.contrib.auth.models import User, Group
from django.db import ProgrammingError
from rest_framework.routers import DefaultRouter

from referral import api_v2
from referral.api_v3 import (
    ReferralTypeAPIResource, RegionAPIResource, OrganisationAPIResource, TaskStateAPIResource,
    TaskTypeAPIResource, UserAPIResource, TagAPIResource, ReferralAPIResource,
)


# v3 API
v3_api = [
    path('organisation/', cache_page(settings.API_RESPONSE_CACHE_SECONDS)(OrganisationAPIResource.as_view()), name='organisation_api_resource'),
    path('organisation/<int:pk>/', cache_page(settings.API_RESPONSE_CACHE_SECONDS)(OrganisationAPIResource.as_view()), name='organisation_api_resource'),
    path('referraltype/', cache_page(settings.API_RESPONSE_CACHE_SECONDS)(ReferralTypeAPIResource.as_view()), name='referraltype_api_resource'),
    path('referraltype/<int:pk>/', cache_page(settings.API_RESPONSE_CACHE_SECONDS)(ReferralTypeAPIResource.as_view()), name='referraltype_api_resource'),
    path('region/', cache_page(settings.API_RESPONSE_CACHE_SECONDS)(RegionAPIResource.as_view()), name='region_api_resource'),
    path('region/<int:pk>/', cache_page(settings.API_RESPONSE_CACHE_SECONDS)(RegionAPIResource.as_view()), name='region_api_resource'),
    path('tag/', cache_page(settings.API_RESPONSE_CACHE_SECONDS)(TagAPIResource.as_view()), name='tag_api_resource'),
    path('tag/<int:pk>/', cache_page(settings.API_RESPONSE_CACHE_SECONDS)(TagAPIResource.as_view()), name='tag_api_resource'),
    path('taskstate/', cache_page(settings.API_RESPONSE_CACHE_SECONDS)(TaskStateAPIResource.as_view()), name='taskstate_api_resource'),
    path('taskstate/<int:pk>/', cache_page(settings.API_RESPONSE_CACHE_SECONDS)(TaskStateAPIResource.as_view()), name='taskstate_api_resource'),
    path('tasktype/', cache_page(settings.API_RESPONSE_CACHE_SECONDS)(TaskTypeAPIResource.as_view()), name='tasktype_api_resource'),
    path('tasktype/<int:pk>/', cache_page(settings.API_RESPONSE_CACHE_SECONDS)(TaskTypeAPIResource.as_view()), name='tasktype_api_resource'),
    path('user/', cache_page(settings.API_RESPONSE_CACHE_SECONDS)(UserAPIResource.as_view()), name='user_api_resource'),
    path('user/<int:pk>/', cache_page(settings.API_RESPONSE_CACHE_SECONDS)(UserAPIResource.as_view()), name='user_api_resource'),
    path('referral/', cache_page(settings.API_RESPONSE_CACHE_SECONDS)(ReferralAPIResource.as_view()), name='referral_api_resource'),
    path('referral/<int:pk>/', cache_page(settings.API_RESPONSE_CACHE_SECONDS)(ReferralAPIResource.as_view()), name='referral_api_resource'),
]

# v2 API
v2_api = DefaultRouter()
v2_api.register('doptrigger', api_v2.DopTriggerView, basename='doptrigger')
v2_api.register('region', api_v2.RegionView, basename='region')
v2_api.register('organisationtype', api_v2.OrganisationTypeView, basename='organisationtype')
v2_api.register('organisation', api_v2.OrganisationView, basename='organisation')
v2_api.register('taskstate', api_v2.TaskStateView, basename='taskstate')
v2_api.register('tasktype', api_v2.TaskTypeView, basename='tasktype')
v2_api.register('referraltype', api_v2.ReferralTypeView, basename='type')
v2_api.register('notetype', api_v2.NoteTypeView, basename='notetype')
v2_api.register('agency', api_v2.AgencyView, basename='agency')
v2_api.register('referral', api_v2.ReferralView, basename='referral')
v2_api.register('task', api_v2.TaskView, basename='task')
v2_api.register('record', api_v2.RecordView, basename='record')
v2_api.register('note', api_v2.NoteView, basename='note')
v2_api.register('conditioncategory', api_v2.ConditionCategoryView, basename='conditioncategory')
v2_api.register('modelcondition', api_v2.ModelConditionView, basename='modelcondition')
v2_api.register('condition', api_v2.ConditionView, basename='condition')
v2_api.register('clearance', api_v2.ClearanceView, basename='clearance')
v2_api.register('location', api_v2.LocationView, basename='location')
v2_api.register('userprofile', api_v2.UserProfileView, basename='userprofile')
v2_api.register('group', api_v2.GroupView, basename='group')
v2_api.register('user', api_v2.UserView, basename='user')
v2_api.register('tag', api_v2.TagView, basename='tag')


# v1 API
v1_api = Api(api_name='v1')
v1_api.register(referral_api_v1.DopTriggerResource())
v1_api.register(referral_api_v1.RegionResource())
v1_api.register(referral_api_v1.OrganisationTypeResource())
v1_api.register(referral_api_v1.OrganisationResource())
v1_api.register(referral_api_v1.TaskStateResource())
v1_api.register(referral_api_v1.TaskTypeResource())
v1_api.register(referral_api_v1.ReferralTypeResource())
v1_api.register(referral_api_v1.NoteTypeResource())
v1_api.register(referral_api_v1.AgencyResource())
v1_api.register(referral_api_v1.ReferralResource())
v1_api.register(referral_api_v1.TaskResource())
v1_api.register(referral_api_v1.RecordResource())
v1_api.register(referral_api_v1.NoteResource())
v1_api.register(referral_api_v1.ConditionCategoryResource())
v1_api.register(referral_api_v1.ModelConditionResource())
v1_api.register(referral_api_v1.ConditionResource())
v1_api.register(referral_api_v1.ClearanceResource())
v1_api.register(referral_api_v1.LocationResource())
v1_api.register(referral_api_v1.UserProfileResource())


# Register the contrib.auth.models models as resources.
class GroupResource(ModelResource):

    class Meta:
        queryset = Group.objects.all()
        ordering = ['name']
        cache = SimpleCache()
        filtering = {'id': ALL, 'name': ALL}
        authentication = SessionAuthentication()


v1_api.register(GroupResource())


class UserResource(ModelResource):
    class Meta:
        try:
            # Queryset should only return active users in the "PRS user" group.
            prs_user = Group.objects.get_or_create(name=settings.PRS_USER_GROUP)[0]
            queryset = User.objects.filter(groups__in=[prs_user], is_active=True)
        except ProgrammingError:
            queryset = User.objects.all()
        ordering = ['username']
        excludes = ['password', 'date_joined', 'is_staff', 'is_superuser', 'last_login']
        filtering = {
            'email': ALL,
            'first_name': ALL,
            'id': ALL,
            'last_name': ALL,
            'username': ALL,
            'is_active': ALL,
        }
        cache = SimpleCache()
        authentication = SessionAuthentication()


v1_api.register(UserResource())


class TagResource(ModelResource):
    class Meta:
        queryset = Tag.objects.all()
        ordering = ['name']
        filtering = {'id': ALL, 'name': ALL, 'slug': ALL}
        cache = SimpleCache()
        authentication = SessionAuthentication()


v1_api.register(TagResource())

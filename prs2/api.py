from django.conf import settings
from django.urls import path
from django.views.decorators.cache import cache_page

from referral.api_v3 import (
    ReferralTypeAPIResource, RegionAPIResource, OrganisationAPIResource, TaskStateAPIResource,
    TaskTypeAPIResource, UserAPIResource, TagAPIResource, ReferralAPIResource, TaskAPIResource, ClearanceAPIResource,
)


# v3 API
v3_api = [
    path('organisation/', cache_page(settings.API_RESPONSE_CACHE_SECONDS)(OrganisationAPIResource.as_view()), name='organisation_api_resource'),
    path('organisation/<int:pk>/', cache_page(settings.API_RESPONSE_CACHE_SECONDS)(OrganisationAPIResource.as_view()), name='organisation_api_resource'),
    path('referraltype/', cache_page(settings.API_RESPONSE_CACHE_SECONDS)(ReferralTypeAPIResource.as_view()), name='referraltype_api_resource'),
    path('referraltype/<int:pk>/', cache_page(settings.API_RESPONSE_CACHE_SECONDS)(ReferralTypeAPIResource.as_view()), name='referraltype_api_resource'),
    path('region/', cache_page(3600)(RegionAPIResource.as_view()), name='region_api_resource'),
    path('region/<int:pk>/', cache_page(3600)(RegionAPIResource.as_view()), name='region_api_resource'),
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
    path('task/', cache_page(settings.API_RESPONSE_CACHE_SECONDS)(TaskAPIResource.as_view()), name='task_api_resource'),
    path('task/<int:pk>/', cache_page(settings.API_RESPONSE_CACHE_SECONDS)(TaskAPIResource.as_view()), name='task_api_resource'),
    path('clearance/', cache_page(settings.API_RESPONSE_CACHE_SECONDS)(ClearanceAPIResource.as_view()), name='clearance_api_resource'),
    path('clearance/<int:pk>/', cache_page(settings.API_RESPONSE_CACHE_SECONDS)(ClearanceAPIResource.as_view()), name='clearance_api_resource'),
]

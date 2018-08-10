from django.urls import include, path
from django.conf import settings
from django.contrib import admin
from django.contrib.auth.views import LoginView, LogoutView
from django.views.generic.base import RedirectView
from rest_framework.routers import DefaultRouter
from api import v1_api
from referral.api_v2 import *

admin.autodiscover()

router = DefaultRouter()
router.register('doptrigger', DopTriggerView, base_name='doptrigger')
router.register('region', RegionView, base_name='region')
router.register('organisationtype', OrganisationTypeView, base_name='organisationtype')
router.register('organisation', OrganisationView, base_name='organisation')
router.register('taskstate', TaskStateView, base_name='taskstate')
router.register('tasktype', TaskTypeView, base_name='tasktype')
router.register('referraltype', ReferralTypeView, base_name='type')
router.register('notetype', NoteTypeView, base_name='notetype')
router.register('agency', AgencyView, base_name='agency')
router.register('referral', ReferralView, base_name='referral')
router.register('task', TaskView, base_name='task')
router.register('record', RecordView, base_name='record')
router.register('note', NoteView, base_name='note')
router.register('conditioncategory', ConditionCategoryView, base_name='conditioncategory')
router.register('modelcondition', ModelConditionView, base_name='modelcondition')
router.register('condition', ConditionView, base_name='condition')
router.register('clearance', ClearanceView, base_name='clearance')
router.register('location', LocationView, base_name='location')
router.register('userprofile', UserProfileView, base_name='userprofile')
router.register('group', GroupView, base_name='group')
router.register('user', UserView, base_name='user')
router.register('tag', TagView, base_name='tag')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/', LoginView.as_view(template_name='login.html'), name='login'),
    path('logout/', LogoutView.as_view(template_name='logged_out.html'), name='logout'),
    path('favicon.ico', RedirectView.as_view(url='{}favicon.ico'.format(settings.STATIC_URL)), name='favicon'),
]

# PRS project URLs
urlpatterns += [
    path('api/', include(v1_api.urls)),  # All API views are registered in api.py
    path('api/v2/', include((router.urls, 'referral_api'), namespace='api_drf')),
    path('reports/', include('reports.urls')),
    path('', include('referral.urls')),
]

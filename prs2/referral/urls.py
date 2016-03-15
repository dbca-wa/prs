from django.conf.urls import patterns, url
from referral.models import Referral, Record, Task
from referral import views

# URL patterns for Referral objects
urlpatterns = patterns(
    '',
    url(r'^referrals/create/$', views.ReferralCreate.as_view(), name='referral_create'),
    url(r'^referrals/recent/$', views.ReferralRecent.as_view(), name='referral_recent'),
    url(r'^referrals/tagged/(?P<slug>[-\w]+)/$', views.ReferralTagged.as_view(), name='referral_tagged'),
    url(r'^referrals/reference-search/$', views.ReferralReferenceSearch.as_view(), name='referral_reference_search'),
    url(r'^referrals/(?P<pk>\d+)/$', views.ReferralDetail.as_view(), name='referral_detail'),
    url(r'^referrals/(?P<pk>\d+)/relate/$', views.ReferralRelate.as_view(), name='referral_relate'),
    url(r'^referrals/(?P<pk>\d+)/history/$', views.PrsObjectHistory.as_view(model=Referral), name='prs_object_history'),
    url(r'^referrals/(?P<pk>\d+)/delete/$', views.ReferralDelete.as_view(), name='referral_delete'),
    url(r'^referrals/(?P<pk>\d+)/upload/$', views.RecordUpload.as_view(), name='referral_record_upload'),
    url(r'^referrals/(?P<pk>\d+)/locations/create/$', views.LocationCreate.as_view(), name='referral_location_create'),
    url(r'^referrals/(?P<pk>\d+)/tag/$', views.PrsObjectTag.as_view(model=Referral), name='referral_tag'),
    url(r'^referrals/(?P<pk>\d+)/(?P<related_model>\w+)/$', views.ReferralDetail.as_view(), name='referral_detail'),
    url(r'^referrals/(?P<pk>\d+)/(?P<model>\w+)/create/$', views.ReferralCreateChild.as_view(), name='referral_create_child'),
    # The following URL allows us to specify the 'type' of child object created (e.g. a clearance request Task)
    url(r'^referrals/(?P<pk>\d+)/(?P<model>\w+)/create/(?P<type>\w+)/$', views.ReferralCreateChild.as_view(), name='referral_create_child_type'),
    url(r'^referrals/(?P<pk>\d+)/(?P<model>\w+)/(?P<id>\d+)/(?P<type>\w+)/$', views.ReferralCreateChild.as_view(), name='referral_create_child_related'),
    url(r'^referrals/(?P<pk>\d+)/locations/intersecting/(?P<loc_ids>\w+)/$', views.LocationIntersects.as_view(), name='referral_intersecting_locations'),
)

# URL patterns for other model types requiring specific views
urlpatterns += patterns(
    '',
    url(r'^bookmarks/$', views.BookmarkList.as_view(), name='bookmark_list'),
    url(r'^tags/$', views.TagList.as_view(), name='tag_list'),
    url(r'^tags/replace/$', views.TagReplace.as_view(), name='tag_replace'),
    url(r'^tasks/(?P<pk>\d+)/history/$', views.PrsObjectHistory.as_view(model=Task), name='prs_object_history'),
    url(r'^tasks/(?P<pk>\d+)/(?P<action>\w+)/$', views.TaskAction.as_view(), name='task_action'),
    url(r'^conditions/(?P<pk>\d+)/clearance/$', views.ConditionClearanceCreate.as_view(), name='condition_clearance_add'),
    url(r'^records/(?P<pk>\d+)/infobase/$', views.InfobaseShortcut.as_view(), name='infobase_shortcut'),
    url(r'^records/(?P<pk>\d+)/download/$', views.ReferralDownloadView.as_view(model=Record, file_field='uploaded_file'), name='download_record'),
)

# Other static/functional URLs
urlpatterns += patterns(
    '',
    url(r'^help/$', views.HelpPage.as_view(), name='help_page'),
    url(r'^search/$', views.GeneralSearch.as_view(), name='prs_general_search'),
    url(r'^stopped-tasks/$', views.SiteHome.as_view(stopped_tasks=True), name='stopped_tasks_list'),
    url(r'^print/$', views.SiteHome.as_view(printable=True), name='site_home_print'),
    url(r'^cronjobs/overdue-tasks-email/$', views.OverdueTasksEmail.as_view(), name='overdue_tasks_email'),
    url(r'^(?P<model>\w+)/$', views.PrsObjectList.as_view(), name='prs_object_list'),
    url(r'^(?P<model>\w+)/create/$', views.PrsObjectCreate.as_view(), name='prs_object_create'),
    url(r'^(?P<model>\w+)/(?P<pk>\d+)/$', views.PrsObjectDetail.as_view(), name='prs_object_detail'),
    url(r'^(?P<model>\w+)/(?P<pk>\d+)/update/$', views.PrsObjectUpdate.as_view(), name='prs_object_update'),
    url(r'^(?P<model>\w+)/(?P<pk>\d+)/history/$', views.PrsObjectHistory.as_view(), name='prs_object_history'),
    url(r'^(?P<model>\w+)/(?P<pk>\d+)/delete/$', views.PrsObjectDelete.as_view(), name='prs_object_delete'),
    url(r'^(?P<model>\w+)/(?P<pk>\d+)/tag/$', views.PrsObjectTag.as_view(), name='prs_object_tag'),
    url(r'^$', views.SiteHome.as_view(printable=False), name='site_home'),
)

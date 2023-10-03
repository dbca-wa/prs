from django.urls import path
from referral.models import Referral, Task
from referral import views


# URL patterns for Referral objects
urlpatterns = [
    path("referrals/create/", views.ReferralCreate.as_view(), name="referral_create"),
    path("referrals/recent/", views.ReferralRecent.as_view(), name="referral_recent"),
    path("referrals/tagged/<str:slug>/", views.ReferralTagged.as_view(), name="referral_tagged"),
    path("referrals/reference-search/", views.ReferralReferenceSearch.as_view(), name="referral_reference_search"),
    path("referrals/<int:pk>/", views.ReferralDetail.as_view(), name="referral_detail"),
    path("referrals/<int:pk>/relate/", views.ReferralRelate.as_view(), name="referral_relate"),
    path("referrals/<int:pk>/history/", views.PrsObjectHistory.as_view(model=Referral), name="prs_object_history"),
    path("referrals/<int:pk>/delete/", views.ReferralDelete.as_view(), name="referral_delete"),
    path("referrals/<int:pk>/upload/", views.RecordUpload.as_view(parent_referral=True), name="referral_record_upload"),
    path("referrals/<int:pk>/locations/create/", views.LocationCreate.as_view(), name="referral_location_create"),
    path("referrals/<int:pk>/tag/", views.PrsObjectTag.as_view(model=Referral), name="referral_tag"),
    path("referrals/<int:pk>/<related_model>/", views.ReferralDetail.as_view(), name="referral_detail"),
    path("referrals/<int:pk>/<str:model>/create/", views.ReferralCreateChild.as_view(), name="referral_create_child"),
    # The following URL allows us to specify the 'type' of child object created (e.g. a clearance request Task)
    path("referrals/<int:pk>/<str:model>/create/<str:type>/", views.ReferralCreateChild.as_view(), name="referral_create_child_type"),
    path("referrals/<int:pk>/<str:model>/<int:id>/<str:type>/", views.ReferralCreateChild.as_view(), name="referral_create_child_related"),
    path("referrals/<int:pk>/locations/intersecting/<str:loc_ids>)/", views.LocationIntersects.as_view(), name="referral_intersecting_locations"),
]

# URL patterns for other model types requiring specific views
urlpatterns += [
    path("bookmarks/", views.BookmarkList.as_view(), name="bookmark_list"),
    path("tags/", views.TagList.as_view(), name="tag_list"),
    path("tags/replace/", views.TagReplace.as_view(), name="tag_replace"),
    path("tasks/<int:pk>/history/", views.PrsObjectHistory.as_view(model=Task), name="prs_object_history"),
    path("tasks/<int:pk>/<str:action>/", views.TaskAction.as_view(), name="task_action"),
    path("conditions/<int:pk>/clearance/", views.ConditionClearanceCreate.as_view(), name="condition_clearance_add"),
    path("records/<int:pk>/infobase/", views.InfobaseShortcut.as_view(), name="infobase_shortcut"),
    path("records/<int:pk>/upload/", views.RecordUpload.as_view(), name="record_upload"),
]

# Other static/functional URLs
urlpatterns += [
    path("help/", views.HelpPage.as_view(), name="help_page"),
    path("search/", views.IndexSearchCombined.as_view(), name="prs_index_search_combined"),
    path("index/", views.IndexSearch.as_view(), name="prs_index_search"),
    path("index/<str:collection>/", views.IndexSearch.as_view(), name="prs_index_search"),
    path("stopped-tasks/", views.SiteHome.as_view(stopped_tasks=True), name="stopped_tasks_list"),
    path("print/", views.SiteHome.as_view(printable=True), name="site_home_print"),
    path("<str:model>/", views.PrsObjectList.as_view(), name="prs_object_list"),
    path("<str:model>/create/", views.PrsObjectCreate.as_view(), name="prs_object_create"),
    path("<str:model>/<int:pk>/", views.PrsObjectDetail.as_view(), name="prs_object_detail"),
    path("<str:model>/<int:pk>/update/", views.PrsObjectUpdate.as_view(), name="prs_object_update"),
    path("<str:model>/<int:pk>/history/", views.PrsObjectHistory.as_view(), name="prs_object_history"),
    path("<str:model>/<int:pk>/delete/", views.PrsObjectDelete.as_view(), name="prs_object_delete"),
    path("<str:model>/<int:pk>/tag/", views.PrsObjectTag.as_view(), name="prs_object_tag"),
    path("", views.SiteHome.as_view(printable=False), name="site_home"),
]

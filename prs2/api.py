from django.urls import path
from referral.api_v3 import (
    ClearanceAPIResource,
    OrganisationAPIResource,
    ReferralAPIResource,
    ReferralTypeAPIResource,
    RegionAPIResource,
    TagAPIResource,
    TaskAPIResource,
    TaskStateAPIResource,
    TaskTypeAPIResource,
    UserAPIResource,
)

# v3 API
v3_api = [
    path("organisation/", OrganisationAPIResource.as_view(), name="organisation_api_resource"),
    path("organisation/<int:pk>/", OrganisationAPIResource.as_view(), name="organisation_api_resource"),
    path("referraltype/", ReferralTypeAPIResource.as_view(), name="referraltype_api_resource"),
    path("referraltype/<int:pk>/", ReferralTypeAPIResource.as_view(), name="referraltype_api_resource"),
    path("region/", RegionAPIResource.as_view(), name="region_api_resource"),
    path("region/<int:pk>/", RegionAPIResource.as_view(), name="region_api_resource"),
    path("tag/", TagAPIResource.as_view(), name="tag_api_resource"),
    path("tag/<int:pk>/", TagAPIResource.as_view(), name="tag_api_resource"),
    path("taskstate/", TaskStateAPIResource.as_view(), name="taskstate_api_resource"),
    path("taskstate/<int:pk>/", TaskStateAPIResource.as_view(), name="taskstate_api_resource"),
    path("tasktype/", TaskTypeAPIResource.as_view(), name="tasktype_api_resource"),
    path("tasktype/<int:pk>/", TaskTypeAPIResource.as_view(), name="tasktype_api_resource"),
    path("user/", UserAPIResource.as_view(), name="user_api_resource"),
    path("user/<int:pk>/", UserAPIResource.as_view(), name="user_api_resource"),
    path("referral/", ReferralAPIResource.as_view(), name="referral_api_resource"),
    path("referral/<int:pk>/", ReferralAPIResource.as_view(), name="referral_api_resource"),
    path("task/", TaskAPIResource.as_view(), name="task_api_resource"),
    path("task/<int:pk>/", TaskAPIResource.as_view(), name="task_api_resource"),
    path("clearance/", ClearanceAPIResource.as_view(), name="clearance_api_resource"),
    path("clearance/<int:pk>/", ClearanceAPIResource.as_view(), name="clearance_api_resource"),
]

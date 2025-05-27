from api import v3_api
from dbca_utils.utils import env
from django.contrib import admin
from django.contrib.auth.views import LoginView, LogoutView
from django.urls import include, path

admin.autodiscover()

urlpatterns = [
    path("admin/", admin.site.urls),
    path("login/", LoginView.as_view(template_name="login.html"), name="login"),
    path("logout/", LogoutView.as_view(template_name="logged_out.html"), name="logout"),
    # PRS project URLs
    path("api/", include((v3_api, "referral"), namespace="api")),
    path("reports/", include("reports.urls")),
    path("", include("referral.urls")),
]

if env("LOCAL_MEDIA_STORAGE", False):
    from django.conf import settings
    from django.conf.urls.static import static

    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

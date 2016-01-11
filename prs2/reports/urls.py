from django.conf.urls import url
from django.contrib.auth.decorators import login_required
from reports.views import ReportView, DownloadView

urlpatterns = [
    url(r'^$', login_required(ReportView.as_view()), name='reports'),
    url(r'^download/$', login_required(DownloadView.as_view()), name='reports_download'),
]

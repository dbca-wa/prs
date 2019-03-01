from django.contrib.auth.decorators import login_required
from django.urls import path
from reports.views import ReportView, DownloadView

urlpatterns = [
    path('', login_required(ReportView.as_view()), name='reports'),
    path('download/', login_required(DownloadView.as_view()), name='reports_download'),
]

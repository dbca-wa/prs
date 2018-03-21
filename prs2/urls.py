from django.conf import settings
from django.conf.urls import include, url
from django.contrib import admin
from django.contrib.auth.views import LoginView, LogoutView
from api import v1_api

admin.autodiscover()

urlpatterns = [
    url(r'^admin/', include(admin.site.urls)),
    url(r'^login/$', LoginView.as_view(template_name='login.html'), name='login'),
    url(r'^logout/$', LogoutView.as_view(template_name='logged_out.html'), name='logout'),
    url(r'^explorer/', include('explorer.urls')),  # django-sql-explorer
]

# PRS project URLs
urlpatterns += [
    url(r'^api/', include(v1_api.urls)),  # All API views are registered in api.py
    url(r'^reports/', include('reports.urls')),
    url(r'^', include('referral.urls')),
]

from django.urls import include, path
from django.conf import settings
from django.contrib import admin
from django.contrib.auth.views import LoginView, LogoutView
from django.views.generic.base import RedirectView
from api import v1_api

admin.autodiscover()

urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/', LoginView.as_view(template_name='login.html'), name='login'),
    path('logout/', LogoutView.as_view(template_name='logged_out.html'), name='logout'),
    path('favicon.ico', RedirectView.as_view(url='{}favicon.ico'.format(settings.STATIC_URL)), name='favicon'),
]

# PRS project URLs
urlpatterns += [
    path('api/', include(v1_api.urls)),  # All API views are registered in api.py
    path('reports/', include('reports.urls')),
    path('', include('referral.urls')),
]

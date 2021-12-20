from django.urls import include, path
from django.contrib import admin
from django.contrib.auth.views import LoginView, LogoutView
from api import v3_api

admin.autodiscover()

urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/', LoginView.as_view(template_name='login.html'), name='login'),
    path('logout/', LogoutView.as_view(template_name='logged_out.html'), name='logout'),
    # PRS project URLs
    path('api/', include((v3_api, 'referral'), namespace='api')),
    path('reports/', include('reports.urls')),
    path('', include('referral.urls')),
]

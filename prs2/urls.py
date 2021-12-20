from django.urls import include, path
from django.contrib import admin
from django.contrib.auth.views import LoginView, LogoutView
from api import v1_api, v2_api, v3_api
from .views import StatusView

admin.autodiscover()

urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/', LoginView.as_view(template_name='login.html'), name='login'),
    path('logout/', LogoutView.as_view(template_name='logged_out.html'), name='logout'),
    # PRS project URLs
    path('api/', include((v3_api, 'referral'), namespace='api')),
    path('api/v3/', include((v3_api, 'referral'), namespace='api_v3')),
    path('api/v2/', include((v2_api.urls, 'referral_api'), namespace='api_drf_v2')),
    path('api/', include(v1_api.urls)),  # Tastypie will prefix '/api/v1/' automatically.
    path('reports/', include('reports.urls')),
    path('status/', StatusView.as_view(), name='status'),
    path('', include('referral.urls')),
]

from base64 import b64encode
from django.conf import settings


def template_context(request):
    """Pass extra context variables to every template.
    """
    context = {
        'site_title': settings.APPLICATION_TITLE,
        'site_acronym': settings.APPLICATION_ACRONYM,
        'version_no': settings.APPLICATION_VERSION_NO,
        'prs_geoserver_url': settings.PRS_GEOSERVER_URL,
        'mapproxy_url': settings.MAPPROXY_URL,
        'geocoder_url': settings.GEOCODER_URL,
        'geoserver_url': settings.GEOSERVER_URL,
        'geoserver_basic_auth': b64encode(f'{settings.GEOSERVER_SSO_USER}:{settings.GEOSERVER_SSO_PASS}'.encode('utf-8')).decode(),
        'cadastre_layer_name': settings.CADASTRE_LAYER_NAME,
        'prs_user_group': settings.PRS_USER_GROUP,
    }
    if request.user.is_authenticated:
        context['prs_user'] = request.user.userprofile.is_prs_user()
        context['prs_power_user'] = request.user.userprofile.is_power_user()
        context['last_referral'] = request.user.userprofile.last_referral()
    context.update(settings.STATIC_CONTEXT_VARS)
    return context

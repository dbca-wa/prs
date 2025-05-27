from django.conf import settings
from django.urls import reverse


def template_context(request):
    """Pass extra context variables to every template."""
    context = {
        "site_title": settings.APPLICATION_TITLE,
        "site_acronym": settings.APPLICATION_ACRONYM,
        "version_no": settings.APPLICATION_VERSION_NO,
        "prs_user_group": settings.PRS_USER_GROUP,
        # Define a dictionary of context variables to supply to JavaScript in view templates.
        "javascript_context": {
            "geoserver_url": settings.GEOSERVER_URL,
            "kmi_geoserver_url": settings.KMI_GEOSERVER_URL,
            "prs_layer_name": settings.PRS_LAYER_NAME,
            "geocoder_url": settings.GEOCODER_URL,
            "cadastre_query_url": reverse("cadastre_query"),
        },
    }
    if request.user.is_authenticated:
        context["prs_user"] = request.user.userprofile.is_prs_user()
        context["prs_power_user"] = request.user.userprofile.is_power_user()
        context["last_referral"] = request.user.userprofile.last_referral()
    context.update(settings.STATIC_CONTEXT_VARS)
    return context

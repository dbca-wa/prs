from django.conf import settings


def template_context(request):
    """Pass extra context variables to every template.
    """
    context = {
        'site_title': settings.APPLICATION_TITLE,
        'site_acronym': settings.APPLICATION_ACRONYM,
        'version_no': settings.APPLICATION_VERSION_NO,
        'geoserver_wms_url': settings.GEOSERVER_WMS_URL,
        'geoserver_wfs_url': settings.GEOSERVER_WFS_URL,
        'prs_user_group': settings.PRS_USER_GROUP,
        'managers': settings.MANAGERS,
    }
    if request.user.is_authenticated():
        context['prs_user'] = request.user.userprofile.is_prs_user()
        context['prs_power_user'] = request.user.userprofile.is_power_user()
        context['last_referral'] = request.user.userprofile.last_referral()
    context.update(settings.STATIC_CONTEXT_VARS)
    return context

from datetime import datetime, date
from dbca_utils.utils import env
from django.apps import apps
from django.conf import settings
from django.contrib import admin
from django.core.mail import EmailMultiAlternatives
from django.db.models import Q
from django.db.models.base import ModelBase
from django.utils.encoding import smart_text
from django.utils.safestring import mark_safe
import json
from reversion.models import Version
import re
import requests
from unidecode import unidecode


def is_model_or_string(model):
    """This function checks if we passed in a Model, or the name of a model as
    a case-insensitive string. The string may also be plural to some extent
    (i.e. ending with "s"). If we passed in a string, return the named Model
    instead using get_model().

    Example::

        from referral.util import is_model_or_string
        is_model_or_string('region')
        is_model_or_string(Region)

    >>> from referral.models import Region
    >>> from django.db.models.base import ModelBase
    >>> from referral.util import is_model_or_string
    >>> isinstance(is_model_or_string('region'), ModelBase)
    True
    >>> isinstance(is_model_or_string(Region), ModelBase)
    True
    """
    if not isinstance(model, ModelBase):
        # Hack: if the last character is "s", remove it before calling get_model
        x = len(model) - 1
        if model[x] == "s":
            model = model[0:x]
        try:
            model = apps.get_model("referral", model)
        except LookupError:
            model = None
    return model


def smart_truncate(content, length=100, suffix="....(more)"):
    """Small function to truncate a string in a sensible way, sourced from:
    http://stackoverflow.com/questions/250357/smart-truncate-in-python
    """
    content = smart_text(content)
    if len(content) <= length:
        return content
    else:
        return " ".join(content[: length + 1].split(" ")[0:-1]) + suffix


def dewordify_text(txt):
    """Function to strip some of the crufty HTML that results from copy-pasting
    MS Word documents/HTML emails into the RTF text fields in this application.
    Should always return a unicode string.

    Source:
    http://stackoverflow.com/questions/1175540/iterative-find-replace-from-a-list-of-tuples-in-python
    """
    REPLACEMENTS = {
        "&nbsp;": " ",
        "&lt;": "<",
        "&gt;": ">",
        ' class="MsoNormal"': "",
        '<span lang="EN-AU">': "",
        "<span>": "",
        "</span>": "",
    }

    def replacer(m):
        return REPLACEMENTS[m.group(0)]

    if txt:
        # Whatever string encoding is passed in,
        # use unidecode to replace non-ASCII characters.
        txt = unidecode(txt)  # Replaces odd characters.
        r = re.compile("|".join(REPLACEMENTS.keys()))
        r = r.sub(replacer, txt)
        return r
    else:
        return ""


def breadcrumbs_li(links):
    """Returns HTML: an unordered list of URLs (no surrounding <ul> tags).
    ``links`` should be a iterable of tuples (URL, text).
    Reference: https://getbootstrap.com/docs/4.1/components/breadcrumb/
    """
    crumbs = ""
    li_str = '<li class="breadcrumb-item"><a href="{}">{}</a></li>'
    li_str_active = '<li class="breadcrumb-item active"><span>{}</span></li>'
    # Iterate over the list, except for the last item.
    if len(links) > 1:
        for i in links[:-1]:
            crumbs += li_str.format(i[0], i[1])
    # Add the final "active" item.
    crumbs += li_str_active.format(links[-1][1])
    return crumbs


def get_query(query_string, search_fields):
    """Returns a query which is a combination of Q objects. That combination
    aims to search keywords within a model by testing the given search fields.

    Splits the query string into individual keywords, getting rid of unecessary
    spaces and grouping quoted words together.
    """
    findterms = re.compile(r'"([^"]+)"|(\S+)').findall
    normspace = re.compile(r"\s{2,}").sub
    query = None  # Query to search for every search term
    terms = [normspace(" ", (t[0] or t[1]).strip()) for t in findterms(query_string)]
    for term in terms:
        or_query = None  # Query to search for a given term in each field
        for field_name in search_fields:
            q = Q(**{"%s__icontains" % field_name: term})
            if or_query is None:
                or_query = q
            else:
                or_query = or_query | q
        if query is None:
            query = or_query
        else:
            query = query & or_query
    return query


def as_row_subtract_referral_cell(html_row):
    """Function to take some HTML of a table row and then remove the cell
    containing the Referral ID (we don't need to display this on the referral details page).
    """
    # Use regex to remove the <TD> tag of class "referral-id-cell".
    html_row = re.sub(r'<td class="referral-id-cell">.+</td>', r"", html_row)
    return mark_safe(html_row)


def user_referral_history(user, referral):
    # Retrieve user profile (create it if it doesn't exist)
    try:
        profile = user.get_profile()
    except Exception:
        profile = user.userprofile
    # If the user has no history, create an empty list
    if not profile.referral_history:
        ref_history = []
    else:
        try:
            # Deserialise the list of lists from the user profile
            ref_history = json.loads(profile.referral_history)
        except Exception:
            # If that failed, assume that the user still has "old style" history in their profile.
            ref_history = profile.referral_history.split(",")
    # Edge-case: single-ref history profiles only.
    if isinstance(ref_history, int):
        ref = ref_history
        ref_history = []
        ref_history.append([ref, datetime.strftime(datetime.today(), "%d-%m-%Y")])
    # We're going to replace the existing list with a new one.
    new_ref_history = []
    # Iterate through the list; it's either a list of unicode strings (old-style)
    # or a list of lists (new-style).
    for i in ref_history:
        # Firstly if the item is a string, convert that to a list ([val, DATE]).
        if isinstance(i, str):
            i = [int(i), datetime.strftime(datetime.today(), "%d-%m-%Y")]
        # If the referral that was passed in exists in the current list, pass (don't append it).
        if referral.id == i[0]:
            pass
        else:
            new_ref_history.append(i)
    # Add the passed-in referral to the end of the new list.
    new_ref_history.append(
        [referral.id, datetime.strftime(datetime.today(), "%d-%m-%Y")]
    )
    # History can be a maximum of 20 referrals; slice the new list accordingly.
    if len(new_ref_history) > 20:
        new_ref_history = new_ref_history[-20:]
    # Save the updated user profile; serialise the new list of lists.
    profile.referral_history = json.dumps(new_ref_history)
    profile.save()


def user_task_history(user, task, comment=None):
    """Utility function to update the task history in a user's profile.
    """
    profile = user.userprofile
    if not profile.task_history:
        task_history = []
    else:
        task_history = json.loads(profile.task_history)
    task_history.append(
        [task.pk, datetime.strftime(datetime.today(), "%d-%m-%Y"), comment]
    )
    profile.task_history = json.dumps(task_history)
    profile.save()


def filter_queryset(request, model, queryset):
    """
    Function to dynamically filter a model queryset, based upon the search_fields defined in
    admin.py for that model. If search_fields is not defined, the queryset is returned unchanged.
    """
    search_string = request.GET["q"]
    # Replace single-quotes with double-quotes
    search_string = search_string.replace("'", r'"')
    if admin.site._registry[model].search_fields:
        search_fields = admin.site._registry[model].search_fields
        entry_query = get_query(search_string, search_fields)
        queryset = queryset.filter(entry_query)
    return queryset, search_string


def is_prs_user(request):
    if "PRS user" not in [group.name for group in request.user.groups.all()]:
        return False
    return True


def is_prs_power_user(request):
    if "PRS power user" not in [group.name for group in request.user.groups.all()]:
        return False
    return True


def prs_user(request):
    return (
        is_prs_user(request) or is_prs_power_user(request) or request.user.is_superuser
    )


def update_revision_history(app_model):
    """Function to bulk-update Version objects where the data model
    is changed. This function is for reference, as these change will tend to
    be one-off and customised.

    Example: the order_date field was added the the Record model, then later
    changed from DateTime to Date. This change caused the deserialisation step
    to fail for Record versions with a serialised DateTime.
    """
    for v in Version.objects.all():
        # Deserialise the object version.
        data = json.loads(v.serialized_data)[0]
        if data["model"] == app_model:  # Example: referral.record
            pass
            """
            # Do something to the deserialised data here, e.g.:
            if 'order_date' in data['fields']:
                if data['fields']['order_date']:
                    data['fields']['order_date'] = data['fields']['order_date'][:10]
                    v.serialized_data = json.dumps([data])
                    v.save()
            else:
                data['fields']['order_date'] = ''
                v.serialized_data = json.dumps([data])
                v.save()
            """


def overdue_task_email():
    """A utility function to send an email to each user with tasks that are overdue.
    """
    from django.contrib.auth.models import Group
    from .models import TaskState, Task

    prs_grp = Group.objects.get(name=settings.PRS_USER_GROUP)
    users = prs_grp.user_set.filter(is_active=True)
    ongoing_states = TaskState.objects.current().filter(is_ongoing=True)

    # For each user, send an email if they have any incomplete tasks that
    # are in an 'ongoing' state (i.e. not stopped).
    subject = "PRS overdue task notification"
    from_email = settings.APPLICATION_ALERTS_EMAIL

    for user in users:
        ongoing_tasks = Task.objects.current().filter(
            complete_date=None,
            state__in=ongoing_states,
            due_date__lt=date.today(),
            assigned_user=user,
        )
        if ongoing_tasks.exists():
            # Send a single email to this user containing the list of tasks
            to_email = [user.email]
            text_content = """This is an automated message to let you know that the following tasks
                assigned to you within PRS are currently overdue:\n"""
            html_content = """<p>This is an automated message to let you know that the following tasks
                assigned to you within PRS are currently overdue:</p>
                <ul>"""
            for t in ongoing_tasks:
                text_content += "* Referral ID {} - {}\n".format(
                    t.referral.pk, t.type.name
                )
                html_content += '<li><a href="{}">Referral ID {} - {}</a></li>'.format(
                    settings.SITE_URL + t.referral.get_absolute_url(),
                    t.referral.pk,
                    t.type.name,
                )
            text_content += (
                "This is an automatically-generated email - please do not reply.\n"
            )
            html_content += (
                "</ul><p>This is an automatically-generated email - please do not reply.</p>"
            )
            msg = EmailMultiAlternatives(subject, text_content, from_email, to_email)
            msg.attach_alternative(html_content, "text/html")
            # Email should fail gracefully - ie no Exception raised on failure.
            msg.send(fail_silently=True)

    return True


def query_cadastre(cql_filter, crs="EPSG:4326"):
    """A utility function to query the internal DBCA Cadastre dataset via the passed-in CQL filter
    and return results as GeoJSON.
    """
    url = env('GEOSERVER_URL', None)
    auth = (env('GEOSERVER_SSO_USER', None), env('GEOSERVER_SSO_PASS', None))
    type_name = env('CADASTRE_LAYER_NAME', '')
    params = {
        'service': 'WFS',
        'version': '2.0.0',
        'typeName': type_name,
        'request': 'getFeature',
        'outputFormat': 'json',
        'SRSName': f'urn:x-ogc:def:crs:{crs}',
        'cql_filter': cql_filter,
    }
    resp = requests.get(url, auth=auth, params=params)
    resp.raise_for_status()
    return resp.json()

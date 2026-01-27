import json
import logging
import re
from datetime import date
from io import BytesIO
from string import punctuation

import docx2txt
import pyproj
import requests
from dbca_utils.utils import env
from django.apps import apps
from django.conf import settings
from django.contrib import admin
from django.core.mail import EmailMultiAlternatives
from django.db.models import Q
from django.db.models.base import ModelBase
from django.utils.encoding import smart_str
from django.utils.safestring import mark_safe
from extract_msg import Message
from fiona.io import ZipMemoryFile
from fudgeo.constant import WGS84
from fudgeo.geopkg import SpatialReferenceSystem
from pdfminer import high_level
from reversion.models import Version
from shapely import force_2d
from shapely.geometry import shape
from shapely.ops import transform
from unidecode import unidecode

LOGGER = logging.getLogger("prs")


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


def smart_truncate(content: str, length: int = 100, suffix: str = "....(more)") -> str:
    """Small function to truncate a string in a sensible way, sourced from:
    http://stackoverflow.com/questions/250357/smart-truncate-in-python
    """
    content = smart_str(content)
    if len(content) <= length:
        return content
    else:
        return " ".join(content[: length + 1].split(" ")[0:-1]) + suffix


def dewordify_text(txt: str) -> str:
    """Function to strip some of the crufty HTML that results from copy-pasting
    MS Word documents/HTML emails into the RTF text fields in this application.

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


def breadcrumbs_li(links: list) -> str:
    """Returns HTML: an unordered list of URLs (no surrounding <ul> tags).
    ``links`` should be a iterable of tuples (URL, text).
    Reference: https://getbootstrap.com/docs/4.1/components/breadcrumb/
    """
    crumbs = ""
    # Iterate over the list, except for the last item.
    if len(links) > 1:
        for i in links[:-1]:
            crumbs += f"<li class='breadcrumb-item'><a href='{i[0]}'>{i[1]}</a></li>"
    # Add the final "active" item.
    crumbs += f"<li class='breadcrumb-item active'><span>{links[-1][1]}</span></li>"
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


def is_prs_user(request) -> bool:
    if "PRS user" not in [group.name for group in request.user.groups.all()]:
        return False
    return True


def is_prs_power_user(request) -> bool:
    if "PRS power user" not in [group.name for group in request.user.groups.all()]:
        return False
    return True


def prs_user(request) -> bool:
    return is_prs_user(request) or is_prs_power_user(request) or request.user.is_superuser


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
    """A utility function to send an email to each user with tasks that are overdue."""
    from django.contrib.auth.models import Group

    from .models import Task, TaskState

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
                text_content += "* Referral ID {} - {}\n".format(t.referral.pk, t.type.name)
                html_content += '<li><a href="{}">Referral ID {} - {}</a></li>'.format(
                    settings.SITE_URL + t.referral.get_absolute_url(),
                    t.referral.pk,
                    t.type.name,
                )
            text_content += "This is an automatically-generated email - please do not reply.\n"
            html_content += "</ul><p>This is an automatically-generated email - please do not reply.</p>"
            msg = EmailMultiAlternatives(subject, text_content, from_email, to_email)
            msg.attach_alternative(html_content, "text/html")
            # Email should fail gracefully - ie no Exception raised on failure.
            msg.send(fail_silently=True)

    return True


def wfs_getfeature(type_name, cql_filter=None, crs="EPSG:4326", max_features=50):
    """A utility function to perform a GetFeature request on a WFS endpoint
    and return results as GeoJSON.
    """
    geoserver_url = env("GEOSERVER_URL", "")
    url = f"{geoserver_url}/ows"
    auth = (env("SSO_USERNAME", None), env("SSO_PASSWORD", None))
    params = {
        "service": "WFS",
        "version": "1.1.0",
        "typeName": type_name,
        "request": "getFeature",
        "outputFormat": "json",
        "SRSName": f"urn:x-ogc:def:crs:{crs}",
        "maxFeatures": max_features,
    }
    if cql_filter:
        params["cql_filter"] = cql_filter
    resp = requests.get(url, auth=auth, params=params)
    try:
        resp.raise_for_status()
        response = resp.json()
    except Exception as e:
        LOGGER.warning(f"Exception during WFS getFeature request to {url}: {params}")
        LOGGER.warning(e)
        # On exception, return an empty dict.
        return {}

    return response


def query_geocoder(q):
    """Utility function to proxy queries to the external geocoder service."""
    url = env("GEOCODER_URL", None)
    auth = (env("SSO_USERNAME", None), env("SSO_PASSWORD", None))
    params = {"q": q}
    resp = requests.get(url, auth=auth, params=params)
    try:
        resp.raise_for_status()
        response = resp.json()
    except Exception as e:
        LOGGER.warning(f"Exception during query: {url}?q={q}")
        LOGGER.warning(e)
        # On exception, return an empty list.
        return []

    return response


def get_previous_pages(page_num, count=5):
    """Convenience function to take a Paginator page object and return the previous `count`
    page numbers, to a minimum of 1.
    """
    prev_page_numbers = []

    if page_num and page_num.has_previous():
        for i in range(page_num.previous_page_number(), page_num.previous_page_number() - count, -1):
            if i >= 1:
                prev_page_numbers.append(i)

    prev_page_numbers.reverse()
    return prev_page_numbers


def get_next_pages(page_num, count=5):
    """Convenience function to take a Paginator page object and return the next `count`
    page numbers, to a maximum of the paginator page count.
    """
    next_page_numbers = []

    if page_num and page_num.has_next():
        for i in range(page_num.next_page_number(), page_num.next_page_number() + count):
            if i <= page_num.paginator.num_pages:
                next_page_numbers.append(i)

    return next_page_numbers


def get_uploaded_file_content(record) -> str:
    """Convenience function that takes in a Record object and returns the uploaded file's text content (for a given set of file types)."""
    if not record.pk or not record.extension or record.extension not in ["PDF", "MSG", "DOCX", "TXT"]:
        return None

    file_content = ""

    # PDF document content.
    if record.extension == "PDF":
        try:
            if settings.LOCAL_MEDIA_STORAGE:
                with open(record.uploaded_file.path, "rb") as f:
                    file_content = high_level.extract_text(f)
            else:
                # Read the upload blob content into an in-memory file.
                tmp = BytesIO()
                tmp.write(record.uploaded_file.read())
                file_content = high_level.extract_text(tmp)
        except:
            pass

    # MSG document content.
    if record.extension == "MSG":
        try:
            if settings.LOCAL_MEDIA_STORAGE:
                message = Message(record.uploaded_file.path)
            else:
                # Read the upload blob content into an in-memory file.
                tmp = BytesIO()
                tmp.write(record.uploaded_file.read())
                message = Message(tmp)
            file_content = f"{message.subject} {message.body}"
        except UnicodeDecodeError:
            LOGGER.warning(f"Record {record.pk} content raised UnicodeDecodeError")
            pass
        except:
            pass

    # DOCX document content.
    if record.extension == "DOCX":
        try:
            if settings.LOCAL_MEDIA_STORAGE:
                file_content = docx2txt.process(record.uploaded_file.path)
            else:
                # Read the upload blob content into an in-memory file.
                tmp = BytesIO()
                tmp.write(record.uploaded_file.read())
                file_content = docx2txt.process(tmp)
        except:
            pass

    # TXT document content.
    if record.extension == "TXT":
        try:
            if settings.LOCAL_MEDIA_STORAGE:
                with open(record.uploaded_file.path, "r") as f:
                    file_content = f.read()
            else:
                # Read the upload blob content directly.
                file_content = record.uploaded_file.read()
        except:
            pass

    # Decode any bytes object to a string and remove leading/trailing whitespace.
    if isinstance(file_content, bytes):
        file_content = file_content.decode("utf-8", errors="ignore").strip()

    # Remove any NUL (0x00) or form feed (0x0c) characters.
    file_content = file_content.replace("\x00", "").replace("\x0c", "")
    return file_content


STOP_WORDS = [
    "about",
    "above",
    "after",
    "again",
    "against",
    "ain",
    "all",
    "am",
    "an",
    "and",
    "any",
    "are",
    "aren",
    "aren't",
    "as",
    "at",
    "be",
    "because",
    "been",
    "before",
    "being",
    "below",
    "between",
    "both",
    "but",
    "by",
    "can",
    "couldn",
    "couldn't",
    "did",
    "didn",
    "didn't",
    "do",
    "does",
    "doesn",
    "doesn't",
    "doing",
    "don",
    "don't",
    "down",
    "during",
    "each",
    "few",
    "for",
    "from",
    "further",
    "had",
    "hadn",
    "hadn't",
    "has",
    "hasn",
    "hasn't",
    "have",
    "haven",
    "haven't",
    "having",
    "he",
    "he'd",
    "he'll",
    "her",
    "here",
    "hers",
    "herself",
    "he's",
    "him",
    "himself",
    "his",
    "how",
    "i'd",
    "if",
    "i'll",
    "i'm",
    "in",
    "into",
    "is",
    "isn",
    "isn't",
    "it",
    "it'd",
    "it'll",
    "it's",
    "its",
    "itself",
    "i've",
    "just",
    "ll",
    "ma",
    "me",
    "mightn",
    "mightn't",
    "more",
    "most",
    "mustn",
    "mustn't",
    "my",
    "myself",
    "needn",
    "needn't",
    "no",
    "nor",
    "not",
    "now",
    "of",
    "off",
    "on",
    "once",
    "only",
    "or",
    "other",
    "our",
    "ours",
    "ourselves",
    "out",
    "over",
    "own",
    "re",
    "same",
    "shan",
    "shan't",
    "she",
    "she'd",
    "she'll",
    "she's",
    "should",
    "shouldn",
    "shouldn't",
    "should've",
    "so",
    "some",
    "such",
    "than",
    "that",
    "that'll",
    "the",
    "their",
    "theirs",
    "them",
    "themselves",
    "then",
    "there",
    "these",
    "they",
    "they'd",
    "they'll",
    "they're",
    "they've",
    "this",
    "those",
    "through",
    "to",
    "too",
    "under",
    "until",
    "up",
    "ve",
    "very",
    "was",
    "wasn",
    "wasn't",
    "we",
    "we'd",
    "we'll",
    "we're",
    "were",
    "weren",
    "weren't",
    "we've",
    "what",
    "when",
    "where",
    "which",
    "while",
    "who",
    "whom",
    "why",
    "will",
    "with",
    "won",
    "won't",
    "wouldn",
    "wouldn't",
    "you",
    "you'd",
    "you'll",
    "your",
    "you're",
    "yours",
    "yourself",
    "yourselves",
    "you've",
]


def search_document_normalise(content):
    """For passed in search_document content, normalise and return."""
    # Make lowercase.
    content = content.lower()

    # Normalise unicode characters.
    content = unidecode(content)

    # Remove any single-character words.
    content = re.sub(r"\b[a-z0-9]\b\s*", "", content)

    # If the content contain line breaks, split and rejoin with spaces.
    content = " ".join([line for line in content.splitlines() if line])

    # Remove stop words.
    content = " ".join([word for word in content.split() if word not in STOP_WORDS])

    # Replace punctuation with a space.
    content = content.translate(content.maketrans(punctuation, " " * len(punctuation)))

    # Replace instances of >1 consecutive spaces with a single space.
    content = re.sub(r"\s{2,}", " ", content)

    # Strip leading/trailing whitespace.
    content = content.strip()

    return content


def parse_shapefile(uploaded_shapefile) -> list | bool:
    """For a passed-in file object, parse it as a zipped shapefile."""
    try:
        zip_file = ZipMemoryFile(uploaded_shapefile)
        shapefile = zip_file.open()
    except:
        # Exception while opening the shapefile - catch and return to the referral view.
        return False

    source_crs = pyproj.CRS(shapefile.crs.to_string())
    dest_crs = pyproj.CRS("EPSG:4283")  # GDA 94
    # Define our projection function.
    project = pyproj.Transformer.from_crs(source_crs, dest_crs, always_xy=True).transform
    features = []

    for feature in shapefile:
        if feature.geometry:
            geometry = shape(feature.geometry)
            projected_geometry = transform(project, geometry)  # Project the geometry to GDA 94.
            features.append(force_2d(projected_geometry))

    return features


SRS_WKT = """GEOGCS["WGS 84",
    DATUM["WGS_1984",
        SPHEROID["WGS 84",6378137,298.257223563,
            AUTHORITY["EPSG","7030"]],
        AUTHORITY["EPSG","6326"]],
    PRIMEM["Greenwich",0,
        AUTHORITY["EPSG","8901"]],
    UNIT["degree",0.0174532925199433,
        AUTHORITY["EPSG","9122"]],
    AUTHORITY["EPSG","4326"]]"""


def get_srs_wgs84() -> SpatialReferenceSystem:
    return SpatialReferenceSystem(name="WGS 84", organization="EPSG", org_coord_sys_id=WGS84, definition=SRS_WKT)

from __future__ import absolute_import, unicode_literals
from confy import env
from datetime import datetime, date
from django.apps import apps
from django.conf import settings
from django.contrib import admin
from django.core.mail import EmailMultiAlternatives
from django.db.models import Q
from django.db.models.base import ModelBase
from django.utils.encoding import smart_text
from django.utils.safestring import mark_safe
from django.utils import six
from dpaw_utils.requests.api import post as post_sso
import json
from reversion.models import Version
import re
from unidecode import unidecode
import os
import sys
from email.parser import Parser as EmailParser
import email.utils
import olefile as OleFile


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
    """
    crumbs = ""
    li_str = '<li><a href="{}">{}</a></li>'
    li_str_last = '<li class="active"><span>{}</span></li>'
    # Iterate over the list, except for the last item.
    if len(links) > 1:
        for i in links[:-1]:
            crumbs += li_str.format(i[0], i[1])
    # Add the last item.
    crumbs += li_str_last.format(links[-1][1])
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
        if isinstance(i, six.text_type):
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


def borgcollector_harvest(request, publishes=["prs_locations"]):
    """Convenience function to manually run a Borg Collector harvest
    job for the PRS locations layer.

    Docs: https://github.com/parksandwildlife/borgcollector
    """
    api_url = env("BORGCOLLECTOR_API", "https://borg.dpaw.wa.gov.au/api/") + "jobs/"
    # Send a POST request to the API endpoint.
    r = post_sso(
        user_request=request, url=api_url, data=json.dumps({"publishes": publishes})
    )
    return r


def overdue_task_email():
    """A utility function to send an email to each user with tasks that are
    overdue.
    """
    from django.contrib.auth.models import Group
    from .models import TaskState, Task

    prs_grp = Group.objects.get(name=settings.PRS_USER_GROUP)
    users = prs_grp.user_set.filter(is_active=True)
    users = users.filter(username="AshleyF")
    ongoing_states = TaskState.objects.current().filter(is_ongoing=True)

    # For each user, send an email if they have any incomplete tasks that
    # are in an 'ongoing' state (i.e. not stopped).
    subject = "PRS overdue task notification"
    from_email = "PRS-Alerts@dpaw.wa.gov.au"

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


"""
ExtractMsg:
    Extracts emails and attachments saved in Microsoft Outlook's .msg files
https://github.com/mattgwwalker/msg-extractor
"""

MSG_PROPERTIES = {
    '001A': 'Message class',
    '0037': 'Subject',
    '003D': 'Subject prefix',
    '0040': 'Received by name',
    '0042': 'Sent repr name',
    '0044': 'Rcvd repr name',
    '004D': 'Org author name',
    '0050': 'Reply rcipnt names',
    '005A': 'Org sender name',
    '0064': 'Sent repr adrtype',
    '0065': 'Sent repr email',
    '0070': 'Topic',
    '0075': 'Rcvd by adrtype',
    '0076': 'Rcvd by email',
    '0077': 'Repr adrtype',
    '0078': 'Repr email',
    '007d': 'Message header',
    '0C1A': 'Sender name',
    '0C1E': 'Sender adr type',
    '0C1F': 'Sender email',
    '0E02': 'Display BCC',
    '0E03': 'Display CC',
    '0E04': 'Display To',
    '0E1D': 'Subject (normalized)',
    '0E28': 'Recvd account1 (uncertain)',
    '0E29': 'Recvd account2 (uncertain)',
    '1000': 'Message body',
    '1008': 'RTF sync body tag',
    '1035': 'Message ID (uncertain)',
    '1046': 'Sender email (uncertain)',
    '3001': 'Display name',
    '3002': 'Address type',
    '3003': 'Email address',
    '39FE': '7-bit email (uncertain)',
    '39FF': '7-bit display name',

    # Attachments (37xx)
    '3701': 'Attachment data',
    '3703': 'Attachment extension',
    '3704': 'Attachment short filename',
    '3707': 'Attachment long filename',
    '370E': 'Attachment mime tag',
    '3712': 'Attachment ID (uncertain)',

    # Address book (3Axx):
    '3A00': 'Account',
    '3A02': 'Callback phone no',
    '3A05': 'Generation',
    '3A06': 'Given name',
    '3A08': 'Business phone',
    '3A09': 'Home phone',
    '3A0A': 'Initials',
    '3A0B': 'Keyword',
    '3A0C': 'Language',
    '3A0D': 'Location',
    '3A11': 'Surname',
    '3A15': 'Postal address',
    '3A16': 'Company name',
    '3A17': 'Title',
    '3A18': 'Department',
    '3A19': 'Office location',
    '3A1A': 'Primary phone',
    '3A1B': 'Business phone 2',
    '3A1C': 'Mobile phone',
    '3A1D': 'Radio phone no',
    '3A1E': 'Car phone no',
    '3A1F': 'Other phone',
    '3A20': 'Transmit dispname',
    '3A21': 'Pager',
    '3A22': 'User certificate',
    '3A23': 'Primary Fax',
    '3A24': 'Business Fax',
    '3A25': 'Home Fax',
    '3A26': 'Country',
    '3A27': 'Locality',
    '3A28': 'State/Province',
    '3A29': 'Street address',
    '3A2A': 'Postal Code',
    '3A2B': 'Post Office Box',
    '3A2C': 'Telex',
    '3A2D': 'ISDN',
    '3A2E': 'Assistant phone',
    '3A2F': 'Home phone 2',
    '3A30': 'Assistant',
    '3A44': 'Middle name',
    '3A45': 'Dispname prefix',
    '3A46': 'Profession',
    '3A48': 'Spouse name',
    '3A4B': 'TTYTTD radio phone',
    '3A4C': 'FTP site',
    '3A4E': 'Manager name',
    '3A4F': 'Nickname',
    '3A51': 'Business homepage',
    '3A57': 'Company main phone',
    '3A58': 'Childrens names',
    '3A59': 'Home City',
    '3A5A': 'Home Country',
    '3A5B': 'Home Postal Code',
    '3A5C': 'Home State/Provnce',
    '3A5D': 'Home Street',
    '3A5F': 'Other adr City',
    '3A60': 'Other adr Country',
    '3A61': 'Other adr PostCode',
    '3A62': 'Other adr Province',
    '3A63': 'Other adr Street',
    '3A64': 'Other adr PO box',

    '3FF7': 'Server (uncertain)',
    '3FF8': 'Creator1 (uncertain)',
    '3FFA': 'Creator2 (uncertain)',
    '3FFC': 'To email (uncertain)',
    '403D': 'To adrtype (uncertain)',
    '403E': 'To email (uncertain)',
    '5FF6': 'To (uncertain)'}


def windowsUnicode(string):
    if string is None:
        return None
    if sys.version_info[0] >= 3:  # Python 3
        return str(string, 'utf_16_le')
    else:  # Python 2
        return unicode(string, 'utf_16_le')


class Attachment:
    def __init__(self, msg, dir_):
        # Get long filename
        self.longFilename = msg._getStringStream([dir_, '__substg1.0_3707'])

        # Get short filename
        self.shortFilename = msg._getStringStream([dir_, '__substg1.0_3704'])

        # Get attachment data
        self.data = msg._getStream([dir_, '__substg1.0_37010102'])

    def save(self):
        # Use long filename as first preference
        filename = self.longFilename
        # Otherwise use the short filename
        if filename is None:
            filename = self.shortFilename
        # Otherwise just make something up!
        if filename is None:
            import random
            import string
            filename = 'UnknownFilename ' + \
                ''.join(random.choice(string.ascii_uppercase + string.digits)
                        for _ in range(5)) + ".bin"
        f = open(filename, 'wb')
        f.write(self.data)
        f.close()
        return filename


class Message(OleFile.OleFileIO):
    def __init__(self, filename):
        OleFile.OleFileIO.__init__(self, filename)

    def _getStream(self, filename):
        if self.exists(filename):
            stream = self.openstream(filename)
            return stream.read()
        else:
            return None

    def _getStringStream(self, filename, prefer='unicode'):
        """Gets a string representation of the requested filename.
        Checks for both ASCII and Unicode representations and returns
        a value if possible.  If there are both ASCII and Unicode
        versions, then the parameter /prefer/ specifies which will be
        returned.
        """

        if isinstance(filename, list):
            # Join with slashes to make it easier to append the type
            filename = "/".join(filename)

        asciiVersion = self._getStream(filename + '001E')
        unicodeVersion = windowsUnicode(self._getStream(filename + '001F'))
        if asciiVersion is None:
            return unicodeVersion
        elif unicodeVersion is None:
            return asciiVersion
        else:
            if prefer == 'unicode':
                return unicodeVersion
            else:
                return asciiVersion

    @property
    def subject(self):
        return self._getStringStream('__substg1.0_0037')

    @property
    def header(self):
        try:
            return self._header
        except Exception:
            headerText = self._getStringStream('__substg1.0_007D')
            if headerText is not None:
                self._header = EmailParser().parsestr(headerText)
            else:
                self._header = None
            return self._header

    @property
    def date(self):
        # Get the message's header and extract the date
        if self.header is None:
            return None
        else:
            return self.header['date']

    @property
    def parsedDate(self):
        return email.utils.parsedate(self.date)

    @property
    def sender(self):
        try:
            return self._sender
        except Exception:
            # Check header first
            if self.header is not None:
                headerResult = self.header["from"]
                if headerResult is not None:
                    self._sender = headerResult
                    return headerResult

            # Extract from other fields
            text = self._getStringStream('__substg1.0_0C1A')
            email = self._getStringStream('__substg1.0_0C1F')
            result = None
            if text is None:
                result = email
            else:
                result = text
                if email is not None:
                    result = result + " <" + email + ">"

            self._sender = result
            return result

    @property
    def to(self):
        try:
            return self._to
        except Exception:
            # Check header first
            if self.header is not None:
                headerResult = self.header["to"]
                if headerResult is not None:
                    self._to = headerResult
                    return headerResult

            # Extract from other fields
            # TODO: This should really extract data from the recip folders,
            # but how do you know which is to/cc/bcc?
            display = self._getStringStream('__substg1.0_0E04')
            self._to = display
            return display

    @property
    def cc(self):
        try:
            return self._cc
        except Exception:
            # Check header first
            if self.header is not None:
                headerResult = self.header["cc"]
                if headerResult is not None:
                    self._cc = headerResult
                    return headerResult

            # Extract from other fields
            # TODO: This should really extract data from the recip folders,
            # but how do you know which is to/cc/bcc?
            display = self._getStringStream('__substg1.0_0E03')
            self._cc = display
            return display

    @property
    def body(self):
        # Get the message body
        return self._getStringStream('__substg1.0_1000')

    @property
    def attachments(self):
        try:
            return self._attachments
        except Exception:
            # Get the attachments
            attachmentDirs = []

            for dir_ in self.listdir():
                if dir_[0].startswith('__attach') and dir_[0] not in attachmentDirs:
                    attachmentDirs.append(dir_[0])

            self._attachments = []

            for attachmentDir in attachmentDirs:
                self._attachments.append(Attachment(self, attachmentDir))

            return self._attachments

    def save(self, toJson=False, useFileName=False, raw=False):
        '''Saves the message body and attachments found in the message.  Setting toJson
        to true will output the message body as JSON-formatted text.  The body and
        attachments are stored in a folder.  Setting useFileName to true will mean that
        the filename is used as the name of the folder; otherwise, the message's date
        and subject are used as the folder name.'''

        if useFileName:
            # strip out the extension
            dirName = filename.split('/').pop().split('.')[0]
        else:
            # Create a directory based on the date and subject of the message
            d = self.parsedDate
            if d is not None:
                dirName = '{0:02d}-{1:02d}-{2:02d}_{3:02d}{4:02d}'.format(*d)
            else:
                dirName = "UnknownDate"

            if self.subject is None:
                subject = "[No subject]"
            else:
                subject = "".join(i for i in self.subject if i not in r'\/:*?"<>|')

            dirName = dirName + " " + subject

        def addNumToDir(dirName):
            # Attempt to create the directory with a '(n)' appended

            for i in range(2, 100):
                try:
                    newDirName = dirName + " (" + str(i) + ")"
                    os.makedirs(newDirName)
                    return newDirName
                except Exception:
                    pass
            return None

        try:
            os.makedirs(dirName)
        except Exception:
            newDirName = addNumToDir(dirName)
            if newDirName is not None:
                dirName = newDirName
            else:
                raise Exception(
                    "Failed to create directory '%s'. Does it already exist?" %
                    dirName
                )

        oldDir = os.getcwd()
        try:
            os.chdir(dirName)

            # Save the message body
            fext = 'json' if toJson else 'text'
            f = open("message." + fext, "w")
            # From, to , cc, subject, date

            def xstr(s):
                return '' if s is None else str(s)

            attachmentNames = []
            # Save the attachments
            for attachment in self.attachments:
                attachmentNames.append(attachment.save())

            if toJson:
                import json
                from imapclient.imapclient import decode_utf7

                emailObj = {'from': xstr(self.sender),
                            'to': xstr(self.to),
                            'cc': xstr(self.cc),
                            'subject': xstr(self.subject),
                            'date': xstr(self.date),
                            'attachments': attachmentNames,
                            'body': decode_utf7(self.body)}

                f.write(json.dumps(emailObj, ensure_ascii=True))
            else:
                f.write("From: " + xstr(self.sender) + "\n")
                f.write("To: " + xstr(self.to) + "\n")
                f.write("CC: " + xstr(self.cc) + "\n")
                f.write("Subject: " + xstr(self.subject) + "\n")
                f.write("Date: " + xstr(self.date) + "\n")
                f.write("-----------------\n\n")
                f.write(self.body)

            f.close()

        except Exception:
            self.saveRaw()
            raise

        finally:
            # Return to previous directory
            os.chdir(oldDir)

    def saveRaw(self):
        # Create a 'raw' folder
        oldDir = os.getcwd()
        try:
            rawDir = "raw"
            os.makedirs(rawDir)
            os.chdir(rawDir)
            sysRawDir = os.getcwd()

            # Loop through all the directories
            for dir_ in self.listdir():
                sysdir = "/".join(dir_)
                code = dir_[-1][-8:-4]
                if code in MSG_PROPERTIES:
                    sysdir = sysdir + " - " + MSG_PROPERTIES[code]
                os.makedirs(sysdir)
                os.chdir(sysdir)

                # Generate appropriate filename
                if dir_[-1].endswith("001E"):
                    filename = "contents.txt"
                else:
                    filename = "contents"

                # Save contents of directory
                f = open(filename, 'wb')
                f.write(self._getStream(dir_))
                f.close()

                # Return to base directory
                os.chdir(sysRawDir)

        finally:
            os.chdir(oldDir)

    def dump(self):
        # Prints out a summary of the message
        print('Message')
        print('Subject:', self.subject)
        print('Date:', self.date)
        print('Body:')
        print(self.body)

    def debug(self):
        for dir_ in self.listdir():
            if dir_[-1].endswith('001E'):  # FIXME: Check for unicode 001F too
                print("Directory: " + str(dir))
                print("Contents: " + self._getStream(dir))

    def save_attachments(self, raw=False):
        """Saves only attachments in the same folder.
        """
        for attachment in self.attachments:
            attachment.save()

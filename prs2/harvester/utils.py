import base64
from dbca_utils.utils import env
from datetime import date, datetime
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.mail import EmailMultiAlternatives
import email
from imaplib import IMAP4_SSL
from io import StringIO
import logging
from lxml.html import fromstring
from lxml_html_clean import clean_html
import re
import requests
import time


LOGGER = logging.getLogger('harvester')


def get_imap(mailbox='INBOX'):
    """Instantiate a new IMAP object, login, and connect to a mailbox.
    """
    imap = IMAP4_SSL(settings.REFERRAL_EMAIL_HOST)
    imap.login(settings.REFERRAL_EMAIL_USER, settings.REFERRAL_EMAIL_PASSWORD)
    imap.select(mailbox)
    return imap


def unread_from_email(imap, from_email):
    """Returns (status, list of UIDs) of unread emails from a sender.
    """
    search = f'(UNSEEN FROM "{from_email}")'
    status, response = imap.search(None, search)
    if status != 'OK':
        return status, response
    # Return status and list of unread email UIDs.
    return status, response[0].split()


def fetch_email(imap, uid):
    """Returns (status, message) for an email by UID.
    Email is returned as an email.Message class object.
    """
    message = None
    status, response = imap.fetch(str(uid), '(BODY.PEEK[])')

    if status != 'OK':
        return status, response

    for i in response:
        if isinstance(i, tuple):
            s = i[1]
            if isinstance(s, bytes):
                s = s.decode('utf-8')
            message = email.message_from_string(s)

    return status, message


def harvest_email(uid, message):
    """Harvest a passed-in UID and email message.
    Abort if UID exists in the database already.
    """
    from .models import EmailedReferral, EmailAttachment

    if message and message.is_multipart():  # Should always be True.
        parts = [i for i in message.walk()]
    else:
        LOGGER.warning(f'Email UID {uid} is not of type multipart')
        return False

    message_body = None
    attachments = []

    for part in parts:
        # 'text/html' or 'text/plain' content should be the email body.
        if part.get_content_type() in ['text/html', 'text/plain']:
            message_body = part
        # Other content types (not multipart/mixed) are attachments (normally application/octet-stream).
        elif part.get_content_type() != 'multipart/mixed':
            attachments.append(part)

    # Create & return EmailedReferral from the email body (if found).
    if message_body:
        try:
            # The "To" or "CC" address might very well be a list of recipients.
            # We'll check them against the list in settings.ASSESSOR_EMAILS,
            # and use the first of those we match with.
            to_emails = message.get('To')  # Might be None.
            if not to_emails:  # Recipient(s) might be CC'd instead.
                to_emails = message.get('CC')
            if not to_emails:  # Still no recipient(s)
                return False
            to_emails = to_emails.split(',')
            pattern = r'\<(.+)\>'
            to_e = ''
            for rec in to_emails:
                m = re.search(pattern, rec.strip())
                if m:
                    email_address = m.group(1).lower()
                    if email_address in settings.ASSESSOR_EMAILS:
                        to_e = email_address

            from_e = email.utils.parseaddr(message.get('From'))[1]
            # Parse the 'sent' date & time (assume AWST).
            ts = time.mktime(email.utils.parsedate(message.get('Date')))
            received = datetime.fromtimestamp(ts).astimezone(settings.TZ)
            # Generate an EmailedReferral object.
            em_new = EmailedReferral(
                received=received, email_uid=str(uid), to_email=to_e,
                from_email=from_e, subject=message.get('Subject'),
            )
            if message_body.get_content_type() == 'text/html':
                # Strip the HTML from the message body and just save the text content.
                t = fromstring(clean_html(message_body.get_payload()))
                em_new.body = t.text_content().replace('=\n', '').strip()
            else:
                em_new.body = message_body.get_payload()  # Plain text body.
            em_new.save()
            LOGGER.info(f'Email UID {uid} harvested: {em_new.subject}')
            for a in attachments:
                att_name = a.get_filename()
                att_new = EmailAttachment(emailed_referral=em_new, name=att_name)
                try:
                    data = a.get_payload(decode=True)
                except Exception:
                    data = StringIO(base64.decodestring(a.get_payload()))
                if att_name and data:  # Some attachments may have no payload.
                    new_file = ContentFile(data)
                    att_new.attachment.save(att_name, new_file)
                    att_new.save()
                    LOGGER.info(f'Email attachment created: {att_new.name}')
        except Exception as e:
            LOGGER.error(f'Email UID {uid} generated exception during harvest')
            LOGGER.exception(e)
            return None
    else:
        LOGGER.error(f'Email UID {uid} had no message body')
        return None

    return True


def email_mark_read(imap, uid):
    """Flag an email as 'Seen' based on passed-in UID.
    """
    status, response = imap.store(str(uid), '+FLAGS', '\Seen')
    return status, response


def email_mark_unread(imap, uid):
    """Remove the 'Seen' flag from an email based on passed-in UID.
    """
    status, response = imap.store(str(uid), '-FLAGS', '\Seen')
    return status, response


def email_delete(imap, uid):
    """Flag an email for deletion.
    """
    status, response = imap.store(str(uid), '+FLAGS', '\Deleted')
    return status, response


def harvest_unread_emails(from_email, purge_email=False):
    """Download a list of unread email from the specified email address and
    harvest each one. Optionally purge harvested emails on completion.
    """
    actions = []
    LOGGER.info(f'Requesting unread emails from {from_email}')

    try:  # Handle IMAP connection error.
        imap = get_imap()
    except:
        LOGGER.warning('IMAP connection error')
        return actions

    actions.append(f'{datetime.now().isoformat()} Requesting unread emails from {from_email}')
    status, uids = unread_from_email(imap, from_email)

    if status != 'OK':
        LOGGER.error(f'Server response failure: {status}')
        actions.append(f'{datetime.now().isoformat()} Server response failure: {status}')
        return actions

    LOGGER.info(f'Server lists {len(uids)} unread emails from {from_email}')
    actions.append(f'{datetime.now().isoformat()} Server lists {len(uids)} unread emails')

    if uids:
        for uid in uids:
            # Decode uid to a string if required.
            if isinstance(uid, bytes):
                uid = uid.decode('utf-8')

            # Fetch email message.
            LOGGER.info(f'Fetching email UID {uid}')
            status, message = fetch_email(imap, uid)
            if status != 'OK':
                LOGGER.error(f'Server response failure on fetching email UID {uid}: {status}')
                continue
            LOGGER.info(f'Harvesting email UID {uid}')
            actions.append(f'{datetime.now().isoformat()} Harvesting email UID {uid}')
            harvest_email(uid, message)

            # Optionally mark email as read and flag it for deletion.
            if purge_email:
                # Mark email as read.
                status, response = email_mark_read(imap, uid)
                if status == 'OK':
                    LOGGER.info(f'Email UID {uid} was marked as "Read"')
                # Mark email for deletion.
                status, response = email_delete(imap, uid)
                if status == 'OK':
                    LOGGER.info(f'Email UID {uid} was marked for deletion')

        LOGGER.info(f'Harvest process completed ({from_email})')
        actions.append(f'{datetime.now().isoformat()} Harvest process completed ({from_email})')

    imap.expunge()
    imap.logout()
    return actions


def import_harvested_refs():
    """Process harvested referrals and generate referrals & records within PRS
    """
    from .models import EmailedReferral

    actions = []
    LOGGER.info('Starting import of harvested referrals')
    actions.append(f'{datetime.now().isoformat()} Starting import of harvested referrals')
    # Process harvested refs that are unprocessed at present.
    for er in EmailedReferral.objects.filter(referral__isnull=True, processed=False):
        actions.append(er.harvest())

    LOGGER.info('Import process completed')
    actions.append(f'{datetime.now().isoformat()} Import process completed')
    return actions


def email_harvest_actions(to_emails, actions):
    """Function to email a log of harvest actions to users.
    Accepts a list of emails and list of actions to append.
    """
    ts = date.today().strftime('%x')
    subject = f'PRS emailed referral harvest log {ts}'
    from_email = 'PRS-Alerts@dbca.wa.gov.au'
    text_content = '''This is an automated message to summarise harvest
    actions undertaken for emailed referrals.\n
    Actions:\n'''
    html_content = '''<p>This is an automated message to summarise harvest
    actions undertaken for emailed referrals.</p>
    <p>Actions:</p>'''
    for l in actions:
        text_content += f'{l}\n'
        html_content += f'{l}<br>'
    msg = EmailMultiAlternatives(subject, text_content, from_email, to_emails)
    msg.attach_alternative(html_content, 'text/html')
    # Email should fail gracefully (no Exception raised on failure).
    msg.send(fail_silently=True)


def query_slip(pin):
    """Function to query the Landgate SLIP service for a cadastral location, by PIN.
    DEPRECATED - use query_slip_esri instead.
    """
    url = env('SLIP_WFS_URL', None)
    auth = (env('SLIP_USERNAME', None), env('SLIP_PASSWORD', None))
    type_name = env('SLIP_DATASET', '')
    params = {
        'service': 'WFS',
        'version': '1.0.0',
        'typeName': type_name,
        'request': 'getFeature',
        'outputFormat': 'json',
        'cql_filter': f'polygon_number={pin}',
    }
    resp = requests.get(url, auth=auth, params=params)
    return resp


def query_slip_esri(pin):
    """Function to query the Landgate SLIP service (Esri REST API) for a cadastral location, by PIN.
    Ref: https://catalogue.data.wa.gov.au/group/about/cadastre
    """
    url = env('SLIP_ESRI_FS_URL', None)
    url = url + '/query'  # Add query suffix to the URL.
    auth = (env('SLIP_USERNAME', None), env('SLIP_PASSWORD', None))
    params = {
        'f': 'json',
        'outSR': 4326,
        'outFields': '*',
        'returnGeometry': 'true',
        'where': f'polygon_number={pin}',
    }
    resp = requests.get(url, auth=auth, params=params)
    resp.raise_for_status()
    return resp.json()

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
from lxml.html import clean, fromstring
from pytz import timezone
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
    search = '(UNSEEN FROM "{}")'.format(from_email)
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

    if message.is_multipart():  # Should always be True.
        parts = [i for i in message.walk()]
    else:
        LOGGER.error('Email UID {} is not of type multipart'.format(uid))
        return False

    message_body = None
    attachments = []

    for p in parts:
        # 'text/html' content is the email body.
        if p.get_content_type() == 'text/html':
            message_body = p
        # Other content types (not multipart/mixed) are attachments (normally application/octet-stream).
        elif p.get_content_type() != 'multipart/mixed':
            attachments.append(p)

    # Create & return EmailedReferral from the email body (if found).
    if message_body:
        try:
            # Check the 'To' address against the whitelist of mailboxes.
            to_e = email.utils.parseaddr(message.get('To'))[1]
            # FIXME: skip the "To" whitelist check at present.
            # if not to_e.lower() in settings.ASSESSOR_EMAILS:
            #     LOGGER.info('Email UID {} to {} harvest was skipped'.format(uid, to_e))
            #     return None  # Not in the whitelist; skip.
            from_e = email.utils.parseaddr(message.get('From'))[1]
            # Parse the 'sent' date & time (assume WST).
            wa_tz = timezone('Australia/Perth')
            ts = time.mktime(email.utils.parsedate(message.get('Date')))
            received = wa_tz.localize(datetime.fromtimestamp(ts))
            # Generate an EmailedReferral object.
            em_new = EmailedReferral(
                received=received, email_uid=str(uid), to_email=to_e,
                from_email=from_e, subject=message.get('Subject'),
            )
            # Strip the HTML from the message body and just save the text content.
            t = fromstring(clean.clean_html(message_body.get_payload()))
            em_new.body = t.text_content().replace('=\n', '').strip()
            em_new.save()
            LOGGER.info('Email UID {} harvested: {}'.format(uid, em_new.subject))
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
                    LOGGER.info('Email attachment created: {}'.format(att_new.name))
        except Exception as e:
            LOGGER.error('Email UID {} generated exception during harvest'.format(uid))
            LOGGER.exception(e)
            return None
    else:
        LOGGER.error('Email UID {} had no message body'.format(uid))
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
    imap = get_imap()

    LOGGER.info('Requesting unread emails from {}'.format(from_email))
    actions.append('{} Requesting unread emails from {}'.format(datetime.now().isoformat(), from_email))
    status, uids = unread_from_email(imap, from_email)

    if status != 'OK':
        LOGGER.error('Server response failure: {}'.status)
        actions.append('{} Server response failure: {}'.format(datetime.now().isoformat(), status))
        return actions

    LOGGER.info('Server lists {} unread emails'.format(len(uids)))
    actions.append('{} Server lists {} unread emails'.format(datetime.now().isoformat(), len(uids)))

    if uids:
        for uid in uids:
            # Decode uid to a string if required.
            if isinstance(uid, bytes):
                uid = uid.decode('utf-8')

            # Fetch email message.
            LOGGER.info('Fetching email UID {}'.format(uid))
            status, message = fetch_email(imap, uid)
            if status != 'OK':
                LOGGER.error('Server response failure on fetching email UID {}: {}'.format(uid, status))
                continue
            LOGGER.info('Harvesting email UID {}'.format(uid))
            actions.append('{} Harvesting email UID {}'.format(datetime.now().isoformat(), uid))
            harvest_email(uid, message)

            # Optionally mark email as read and flag it for deletion.
            if purge_email:
                # Mark email as read.
                status, response = email_mark_read(imap, uid)
                if status == 'OK':
                    LOGGER.info('Email UID {} was marked as "Read"'.format(uid))
                # Mark email for deletion.
                status, response = email_delete(imap, uid)
                if status == 'OK':
                    LOGGER.info('Email UID {} was marked for deletion'.format(uid))

        LOGGER.info('Harvest process completed ({})'.format(from_email))
        actions.append('{} Harvest process completed ({})'.format(datetime.now().isoformat(), from_email))

    imap.expunge()
    imap.logout()
    return actions


def import_harvested_refs():
    """Process harvested referrals and generate referrals & records within PRS
    """
    from .models import EmailedReferral

    actions = []
    LOGGER.info('Starting import of harvested referrals')
    actions.append('{} Starting import of harvested referrals'.format(datetime.now().isoformat()))
    # Process harvested refs that are unprocessed at present.
    for er in EmailedReferral.objects.filter(referral__isnull=True, processed=False):
        try:
            actions.append(er.harvest())
        except Exception:
            actions.append('Emailed referral {} failed to import; notify the custodian to investigate'.format(er))

    LOGGER.info('Import process completed')
    actions.append('{} Import process completed'.format(datetime.now().isoformat()))
    return actions


def email_harvest_actions(to_emails, actions):
    """Function to email a log of harvest actions to users.
    Accepts a list of emails and list of actions to append.
    """
    subject = 'PRS emailed referral harvest log {}'.format(date.today().strftime('%x'))
    from_email = 'PRS-Alerts@dbca.wa.gov.au'
    text_content = '''This is an automated message to summarise harvest
    actions undertaken for emailed referrals.\n
    Actions:\n'''
    html_content = '''<p>This is an automated message to summarise harvest
    actions undertaken for emailed referrals.</p>
    <p>Actions:</p>'''
    for l in actions:
        text_content += '{}\n'.format(l)
        html_content += '{}<br>'.format(l)
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
        'cql_filter': 'polygon_number={}'.format(pin)
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
        'where': 'polygon_number={}'.format(pin)
    }
    resp = requests.get(url, auth=auth, params=params)
    return resp

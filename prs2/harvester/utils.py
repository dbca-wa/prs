from __future__ import absolute_import
import base64
from datetime import date, datetime
from django.conf import settings
from django.core.files import File
from django.core.mail import EmailMultiAlternatives
import email
from imaplib import IMAP4_SSL
import logging
from pytz import timezone
from StringIO import StringIO
import time

from .models import EmailedReferral, EmailAttachment


logger = logging.getLogger('harvester.log')


class DeferredIMAP():
    '''Convenience class for maintaining a bit of state about an IMAP server
    and handling logins/logouts. Note that instances aren't threadsafe.
    '''
    def __init__(self, host, user, password):
        self.deletions = []
        self.flags = []
        self.host = host
        self.user = user
        self.password = password

    def login(self):
        self.imp = IMAP4_SSL(self.host)
        self.imp.login(settings.REFERRAL_EMAIL_USER, settings.REFERRAL_EMAIL_PASSWORD)
        self.imp.select('INBOX')

    def logout(self, expunge=False):
        if expunge:
            self.imp.expunge
        self.imp.close()
        self.imp.logout()

    def __getattr__(self, name):
        def temp(*args, **kwargs):
            self.login()
            result = getattr(self.imp, name)(*args, **kwargs)
            self.logout()
            return result
        return temp


dimap = DeferredIMAP(
    host=settings.REFERRAL_EMAIL_HOST, user=settings.REFERRAL_EMAIL_USER,
    password=settings.REFERRAL_EMAIL_PASSWORD)


def unread_from_email(from_email):
    """Returns (status, list of UIDs) of unread emails from a sender.
    """
    search = '(UNSEEN FROM "{}")'.format(from_email)
    status, response = dimap.search(None, search)
    if status != 'OK':
        return status, response
    # Return status and list of unread email UIDs.
    return status, response[0].split()


def fetch_email(uid):
    """Returns (status, message) for an email by UID.
    Email is returned as an email.Message class object.
    """
    message = None
    status, response = dimap.fetch(str(uid), '(BODY.PEEK[])')

    if status != 'OK':
        return status, response

    for i in response:
        if isinstance(i, tuple):
            message = email.message_from_string(i[1])

    return status, message


def harvest_email(uid, message):
    """Harvest a passed-in UID and email message.
    Abort if UID exists in the database already.
    """
    if EmailedReferral.objects.filter(email_uid=str(uid)).exists():
        logger.warning('Email UID {} already present; aborting'.format(uid))
        return False
    if message.is_multipart():  # Should always be True.
        parts = [i for i in message.walk()]
    else:
        logger.error('Email UID {} is not of type multipart'.format(uid))
        return False

    message_body = None
    attachments = []
    # Build the whitelist of receiving mailboxes (we only harvest messages
    # sent to these addresses).
    # Whitelist should consist of a .txt file, one email per line.
    try:
        f = open('mailbox_whitelist.txt', 'r')
        whitelist = [i.strip() for i in f.readlines()]
    except:
        whitelist = False

    for p in parts:
        # 'text/html' content is the email body.
        if p.get_content_type() == 'text/html':
            message_body = p
        # Other content types (not multipart/mixed) are attachments.
        elif p.get_content_type() != 'multipart/mixed':
            attachments.append(p)

    # Create & return EmailedReferral from the email body (if found).
    if message_body:
        try:
            # Check the 'To' address against the whitelist of mailboxes.
            to_e = email.utils.parseaddr(message.get('To'))[1]
            if whitelist and not to_e.lower() in whitelist:
                logger.info('Email UID {} to {} harvest was skipped'.format(uid, to_e))
                return None  # Not in the whitelist; skip.
            from_e = email.utils.parseaddr(message.get('From'))[1]
            # Parse the 'sent' date & time (assume WST).
            wa_tz = timezone('Australia/Perth')
            ts = time.mktime(email.utils.parsedate(message.get('Date')))
            received = wa_tz.localize(datetime.fromtimestamp(ts))
            # Generate an EmailedReferral object.
            em_new = EmailedReferral(
                received=received, email_uid=str(uid), to_email=to_e,
                from_email=from_e, subject=message.get('Subject'),
                body=message_body.get_payload())
            em_new.save()
            logger.info('Email UID {} harvested: {}'.format(uid, em_new.subject))
            for a in attachments:
                att_new = EmailAttachment(
                    emailed_referral=em_new, name=a.get_filename())
                data = StringIO(base64.decodestring(a.get_payload()))
                new_file = File(data)
                att_new.attachment.save(a.get_filename(), new_file)
                att_new.save()
                data.close()
                logger.info('Email attachment created: {}'.format(att_new.name))
        except Exception as e:
            logger.error('Email UID {} generated exception during harvest'.format(uid))
            logger.exception(e)
            return None
    else:
        logger.error('Email UID {} had no message body'.format(uid))
        return None

    return True


def email_mark_read(uid):
    """Flag an email as 'Seen' based on passed-in UID.
    """
    status, response = dimap.store(str(uid), '+FLAGS', '\Seen')
    return status, response


def email_mark_unread(uid):
    """Remove the 'Seen' flag from an email based on passed-in UID.
    """
    status, response = dimap.store(str(uid), '-FLAGS', '\Seen')
    return status, response


def harvest_unread_emails(from_email):
    """Download a list of unread email from the specified email address and
    harvest each one.
    """
    actions = []
    logger.info('Requesting unread emails from {}'.format(from_email))
    actions.append('{} Requesting unread emails from {}'.format(datetime.now().isoformat(), from_email))
    status, uids = unread_from_email(from_email)

    if status != 'OK':
        logger.error('Server response failure: {}'.status)
        actions.append('{} Server response failure: {}'.format(datetime.now().isoformat(), status))
        return actions

    logger.info('Server lists {} unread emails; harvesting'.format(len(uids)))
    actions.append('{} Server lists {} unread emails; harvesting'.format(datetime.now().isoformat(), len(uids)))

    for uid in uids:
        # Fetch email message.
        if EmailedReferral.objects.filter(email_uid=str(uid)).exists():
            logger.info('Email UID {} already present in database, marking as read'.format(uid))
            status, response = email_mark_read(uid)
            continue
        logger.info('Fetching email UID {}'.format(uid))
        status, message = fetch_email(uid)
        if status != 'OK':
            logger.error('Server response failure on fetching email UID {}: {}'.format(uid, status))
            continue
        logger.info('Harvesting email UID {}'.format(uid))
        actions.append('{} Harvesting email UID {}'.format(datetime.now().isoformat(), uid))
        harvest_email(uid, message)
        # Mark email as read.
        status, response = email_mark_read(uid)
        if status == 'OK':
            logger.info('Email UID {} was marked as "Read"'.format(uid))

    logger.info('Harvest process completed ({})'.format(from_email))
    actions.append('{} Harvest process completed ({})'.format(datetime.now().isoformat(), from_email))
    return actions


def import_harvested_refs():
    """Process harvested referrals and generate referrals & records within PRS
    """
    actions = []
    logger.info('Starting import of harvested referrals')
    actions.append('{} Starting import of harvested referrals'.format(datetime.now().isoformat()))
    # Process harvested refs that are unprocessed at present.
    for er in EmailedReferral.objects.filter(referral__isnull=True, processed=False):
        actions.append(er.harvest())

    logger.info('Import process completed')
    actions.append('{} Import process completed'.format(datetime.now().isoformat()))
    return actions


def email_harvest_actions(to_emails, actions):
    """Function to email a log of harvest actions to users.
    Accepts a list of emails and list of actions to append.
    """
    subject = 'PRS emailed referral harvest log {}'.format(date.today().strftime('%x'))
    from_email = 'PRS-Alerts@dpaw.wa.gov.au'
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

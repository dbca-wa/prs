from __future__ import absolute_import
import arrow
import base64
from datetime import datetime, timedelta
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.core.files import File
import email
from imaplib import IMAP4_SSL
import logging
from StringIO import StringIO
import xmltodict

from referral.models import (
    Region, Referral, ReferralType, Agency, Organisation, DopTrigger, Record,
    TaskType, Task)
from .models import EmailedReferral, EmailAttachment


User = get_user_model()
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

    for p in parts:
        if p.get_content_type() == 'text/html':
            message_body = p
        if p.get_content_type() == 'application/octet-stream':
            attachments.append(p)

    # Create & return EmailedReferral from the email body (if found).
    if message_body:
        try:
            received = arrow.get(message.get('Received').split(';')[1].strip(), 'ddd, D MMM YYYY hh:mm:ss')
            to_e = email.utils.parseaddr(message.get('To'))[1]
            from_e = email.utils.parseaddr(message.get('From'))[1]
            em_new = EmailedReferral(
                received=received.datetime, email_uid=str(uid), to_email=to_e,
                from_email=from_e, subject=message.get('Subject'),
                body=message_body.get_payload())
            em_new.save()
            logger.info('Email UID {} harvested as EmailedReferral {}'.format(uid, em_new.pk))
            for a in attachments:
                att_new = EmailAttachment(
                    emailed_referral=em_new, name=a.get_filename(),
                )
                data = StringIO(base64.decodestring(a.get_payload()))
                new_file = File(data)
                att_new.attachment.save(a.get_filename(), new_file)
                att_new.save()
                data.close()
                logger.info('Email attachment created as EmailAttachment {}'.format(uid, att_new.pk))
        except Exception as e:
            logger.error('Email UID {} generated exception during harvest'.format(uid))
            logger.exception(e)
            return None
    else:
        logger.error('Email UID {} had no message body'.format(uid))
        return None

    return em_new


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


def harvest_unread_emails(from_email=settings.DOP_EMAIL):
    """Download a list of unread email from the specified email address and
    harvest each one.
    """
    logger.info('Requesting unread emails from {}'.format(from_email))
    status, uids = unread_from_email(from_email)

    if status != 'OK':
        logger.error('Server response failure: {}'.status)
        return False

    logger.info('Server listed {} unread emails; harvesting'.format(len(uids)))

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
        em = harvest_email(uid, message)
        if em:  # Mark email as read.
            status, response = email_mark_read(uid)
            if status == 'OK':
                logger.info('Email UID {} was marked as Read'.format(uid))

    return True


def import_harvested_refs():
    """Process harvested referrals and generate referrals & records within PRS
    """
    logger.info('Starting import of harvested referrals')
    dpaw = Agency.objects.get(slug='dpaw')
    wapc = Organisation.objects.get(slug='wapc')
    assess_task = TaskType.objects.get(name='Assess a referral')
    for er in EmailedReferral.objects.filter(referral__isnull=True):
        attachments = er.emailattachment_set.all()
        # Emails without attachments are usually reminder notices.
        if not attachments.exists():
            logger.info('Skipping harvested referral {} (no attachments)'.format(er))
            continue
        # Must be an attachment named 'Application.xml' present to import.
        if not attachments.filter(name__istartswith='application.xml'):
            logger.info('Skipping harvested referral {} (no XML attachment)'.format(er))
            continue
        else:
            xml_file = attachments.get(name__istartswith='application.xml')
        try:
            d = xmltodict.parse(xml_file.attachment.read())
        except Exception as e:
            logger.error('Parsing of application.xml failed')
            logger.exception(e)
            continue
        app = d['APPLICATION']
        ref = app['WAPC_APPLICATION_NO']
        if Referral.objects.current().filter(reference__icontains=ref):
            # Skip harvested referrals if the the reference no. exists.
            logger.info('Referral ref {} is already in database'.format(ref))
            continue
        else:
            # Import the harvested referral.
            logger.info('Importing harvested referral reference {}'.format(ref))
            ref_type = ReferralType.objects.current().get(name__istartswith=app['APP_TYPE'])
            # ADDRESS_DETAIL may or may not be a list :/
            if not isinstance(app['ADDRESS_DETAIL']['DOP_ADDRESS_TYPE'], list):
                addresses = [app['ADDRESS_DETAIL']['DOP_ADDRESS_TYPE']]
            else:
                addresses = app['ADDRESS_DETAIL']['DOP_ADDRESS_TYPE']
            # Business rule cludge: for a referral with multiple addresses, just
            # use the first one to assign the referral to a DPaW region.
            p = Point(x=float(addresses[0]['LONGITUDE']), y=float(addresses[0]['LATITUDE']))
            region = None
            assigned = None
            for reg in Region.objects.all():
                if reg.region_mpoly and reg.region_mpoly.intersects(p):
                    region = reg
                    # TODO: determine the user to assign, by region.
                    # assigned = <SOME USER>
            # Didn't intersect a region? Might be bad geometry in the XML.
            # Default to Swan Region and the designated fallback user.
            if not region:
                region = Region.objects.get(name='Swan')
                # TODO: determine the fallback user.
                # assigned = <FALLBACK USER>
            # Create the referral in PRS.
            new_ref = Referral.objects.create(
                type=ref_type, agency=dpaw, referring_org=wapc,
                reference=ref, description=app['DEVELOPMENT_DESCRIPTION'],
                referral_date=er.received, address=app['LOCATION'], point=p)
            # Assign to a region.
            new_ref.region.add(region)
            logger.info('New PRS referral generated: {}'.format(new_ref))
            # Link the harvested referral to the new, generated referral.
            er.referral = new_ref
            er.save()
            # Add triggers to the new referral.
            triggers = [i.strip() for i in app['MRSZONE_TEXT'].split(',')]
            for i in triggers:
                if DopTrigger.objects.current().filter(name__istartswith=i).exists():
                    new_ref.dop_triggers.add(DopTrigger.objects.current().get(name__istartswith=i))
            # Add records to the new referral (one per attachment).
            for i in attachments:
                new_record = Record.objects.create(name=i.name, referral=new_ref)
                # Duplicate the uploaded file.
                data = StringIO(i.attachment.read())
                new_file = File(data)
                new_record.uploaded_file.save(i.name, new_file)
                new_record.save()
                logger.info('New PRS record generated: {}'.format(new_record))
                # Link the attachment to the new, generated record.
                i.record = new_record
                i.save()
            # Create an "Assess a referral" task and assign it to a user.
            new_task = Task(
                type=assess_task,
                referral=new_ref,
                start_date=new_ref.referral_date,
                description=new_ref.description,
                assigned_user=assigned
            )
            new_task.state = assess_task.initial_state
            new_task.due_date = datetime.today() + timedelta(assess_task.target_days)
            new_task.save()
            logger.info('New PRS task generated: {}'.format(new_task))

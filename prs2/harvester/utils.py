from __future__ import absolute_import
import arrow
import base64
from confy import env
from datetime import date, datetime, timedelta
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.core.files import File
from django.core.mail import EmailMultiAlternatives
import email
from imaplib import IMAP4_SSL
import logging
import requests
from StringIO import StringIO
import xmltodict

from referral.models import (
    Region, Referral, ReferralType, Agency, Organisation, DopTrigger, Record,
    TaskType, Task)
from .models import EmailedReferral, EmailAttachment, RegionAssignee


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
        # 'text/html' content is the email body.
        if p.get_content_type() == 'text/html':
            message_body = p
        # Other content types (not multipart/mixed) are attachments.
        elif p.get_content_type() != 'multipart/mixed':
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
            logger.info('Email UID {} harvested: {}'.format(uid, em_new.subject))
            for a in attachments:
                att_new = EmailAttachment(
                    emailed_referral=em_new, name=a.get_filename(),
                )
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
        em = harvest_email(uid, message)
        if em:  # Mark email as read.
            status, response = email_mark_read(uid)
            if status == 'OK':
                logger.info('Email UID {} was marked as "Read"'.format(uid))

    logger.info('Harvest process completed')
    actions.append('{} Harvest process completed'.format(datetime.now().isoformat()))
    return actions


def import_harvested_refs():
    """Process harvested referrals and generate referrals & records within PRS
    """
    actions = []
    logger.info('Starting import of harvested referrals')
    actions.append('{} Starting import of harvested referrals'.format(datetime.now().isoformat()))
    dpaw = Agency.objects.get(slug='dpaw')
    wapc = Organisation.objects.get(slug='wapc')
    assess_task = TaskType.objects.get(name='Assess a referral')
    assignee_default = User.objects.get(username=settings.REFERRAL_ASSIGNEE_FALLBACK)
    # Process harvested refs that are unprocessed at present.
    for er in EmailedReferral.objects.filter(referral__isnull=True, processed=False):
        attachments = er.emailattachment_set.all()
        # Emails without attachments are usually reminder notices.
        if not attachments.exists():
            logger.info('Skipping harvested referral {} (no attachments)'.format(er))
            actions.append('{} Skipping harvested referral {} (no attachments)'.format(datetime.now().isoformat(), er))
            er.processed = True
            er.save()
            continue
        # Must be an attachment named 'Application.xml' present to import.
        if not attachments.filter(name__istartswith='application.xml'):
            logger.info('Skipping harvested referral {} (no XML attachment)'.format(er))
            actions.append('{} Skipping harvested referral {} (no XML attachment)'.format(datetime.now().isoformat(), er))
            er.processed = True
            er.save()
            continue
        else:
            xml_file = attachments.get(name__istartswith='application.xml')
        try:
            d = xmltodict.parse(xml_file.attachment.read())
        except Exception as e:
            logger.error('Harvested referral {} parsing of application.xml failed'.format(er))
            logger.exception(e)
            actions.append('{} Harvested referral {} parsing of application.xml failed'.format(datetime.now().isoformat(), er))
            er.processed = True
            er.save()
            continue
        app = d['APPLICATION']
        ref = app['WAPC_APPLICATION_NO']
        if Referral.objects.current().filter(reference__icontains=ref):
            # Skip harvested referrals if the the reference no. exists.
            logger.info('Referral ref {} is already in database, skipping'.format(ref))
            actions.append('{} Referral ref {} is already in database, skipping'.format(datetime.now().isoformat(), ref))
            er.processed = True
            er.save()
            continue
        else:
            # Import the harvested referral.
            logger.info('Importing harvested referral ref {}'.format(ref))
            actions.append('{} Importing harvested referral ref {}'.format(datetime.now().isoformat(), ref))
            try:
                ref_type = ReferralType.objects.filter(name__istartswith=app['APP_TYPE'])[0]
            except:
                logger.warning('Referral type {} is not recognised type; skipping'.format(app['APP_TYPE']))
                actions.append('{} Referral type {} is not recognised type; skipping'.format(datetime.now().isoformat(), app['APP_TYPE']))
                er.processed = True
                er.save()
                continue
            # Determine the intersecting region(s).
            regions = []
            assigned = None
            # ADDRESS_DETAIL may or may not be a list :/
            if not isinstance(app['ADDRESS_DETAIL']['DOP_ADDRESS_TYPE'], list):
                addresses = [app['ADDRESS_DETAIL']['DOP_ADDRESS_TYPE']]
            else:
                addresses = app['ADDRESS_DETAIL']['DOP_ADDRESS_TYPE']
            # Address geometry:
            url = env('SLIP_WFS_URL', None)
            auth = (env('SLIP_USERNAME', None), env('SLIP_PASSWORD', None))
            type_name = env('SLIP_DATASET', '')
            locations = []
            for a in addresses:
                # Use the long/lat info to intersect DPaW regions.
                try:
                    p = Point(x=float(a['LONGITUDE']), y=float(a['LATITUDE']))
                    for r in Region.objects.all():
                        if r.region_mpoly and r.region_mpoly.intersects(p):
                            regions.append(r)
                except:
                    logger.warning('Address long/lat could not be parsed ({}, {})'.format(a['LONGITUDE'], a['LATITUDE']))
                    actions.append('{} Address long/lat could not be parsed ({}, {})'.format(datetime.now().isoformat(), a['LONGITUDE'], a['LATITUDE']))
                # Use the PIN field to try returning geometry from SLIP.
                if 'PIN' in a:
                    try:
                        pin = int(a['PIN'])
                        if pin > 0:
                            params = {
                                'service': 'WFS',
                                'version': '1.0.0',
                                'typeName': type_name,
                                'request': 'getFeature',
                                'outputFormat': 'json',
                                'cql_filter': 'polygon_number={}'.format(pin)
                            }
                            resp = requests.get(url, auth=auth, params=params)
                            if resp.json()['features']:  # GeoJSON
                                a['FEATURES'] = resp.json()['features']
                                locations.append(a)  # A dict for each address location.
                    except:
                        logger.warning('Address PIN could not be parsed ({})'.format(a['PIN']))
                        actions.append('{} Address PIN could not be parsed ({})'.format(datetime.now().isoformat(), a['PIN']))

            # Business rules:
            # Didn't intersect a region? Might be bad geometry in the XML.
            # Likewise if >1 region was intersected, default to Swan Region
            # and the designated fallback user.
            if len(regions) == 0 or len(regions) > 1:
                region = Region.objects.get(name='Swan')
                assigned = assignee_default
            else:
                region = regions[0]
                try:
                    assigned = RegionAssignee.objects.get(region=region).user
                except:
                    logger.warning('No default assignee set for {}, defaulting to {}'.format(region, assignee_default))
                    actions.append('{} No default assignee set for {}, defaulting to {}'.format(datetime.now().isoformat(), region, assignee_default))
                    assigned = assignee_default
            # Create the referral in PRS.
            new_ref = Referral.objects.create(
                type=ref_type, agency=dpaw, referring_org=wapc,
                reference=ref, description=app['DEVELOPMENT_DESCRIPTION'],
                referral_date=er.received, address=app['LOCATION'])
            # Assign to a region.
            new_ref.region.add(region)
            logger.info('New PRS referral generated: {}'.format(new_ref))
            actions.append('{} New PRS referral generated: {}'.format(datetime.now().isoformat(), new_ref))
            # Link the harvested referral to the new, generated referral.
            er.referral = new_ref
            er.processed = True
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
                actions.append('{} New PRS record generated: {}'.format(datetime.now().isoformat(), new_record))
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
            logger.info('New PRS task generated: {} assigned to {}'.format(new_task, assigned))
            actions.append('{} New PRS task generated: {} assigned to {}'.format(datetime.now().isoformat(), new_task, assigned))

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

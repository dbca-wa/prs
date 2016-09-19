from __future__ import absolute_import
import base64
from confy import env
from datetime import date, datetime, timedelta
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import GEOSGeometry, Point
from django.core.files import File
from django.core.mail import EmailMultiAlternatives
import email
from imaplib import IMAP4_SSL
import json
import logging
from pytz import timezone
import requests
from StringIO import StringIO
import time
import xmltodict

from referral.models import (
    Region, Referral, ReferralType, Agency, Organisation, DopTrigger, Record,
    TaskType, Task, Location, LocalGovernment)
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
            # Note if the the reference no. exists in PRS already.
            logger.info('Referral ref {} is already in database'.format(ref))
            actions.append('{} Referral ref {} is already in database'.format(datetime.now().isoformat(), ref))
            referral_preexists = True
            new_ref = Referral.objects.current().filter(reference__icontains=ref).order_by('-pk').first()
        else:
            referral_preexists = False

        if not referral_preexists:
            # No match with existing references; import the harvested referral.
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
                        if r.region_mpoly and r.region_mpoly.intersects(p) and r not in regions:
                            regions.append(r)
                except:
                    logger.warning('Address long/lat could not be parsed ({}, {})'.format(a['LONGITUDE'], a['LATITUDE']))
                    actions.append('{} Address long/lat could not be parsed ({}, {})'.format(datetime.now().isoformat(), a['LONGITUDE'], a['LATITUDE']))
                # Use the PIN field to try returning geometry from SLIP.
                if 'PIN' in a:
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
                        if resp.json()['features']:  # Features are Multipolygons.
                            a['FEATURES'] = resp.json()['features']  # List of MP features.
                            locations.append(a)  # A dict for each address location.
                        logger.info('Address PIN {} returned geometry from SLIP'.format(pin))
                    else:
                        logger.warning('Address PIN could not be parsed ({})'.format(a['PIN']))
            # Business rules:
            # Didn't intersect a region? Might be bad geometry in the XML.
            # Likewise if >1 region was intersected, default to Swan Region
            # and the designated fallback user.
            if len(regions) == 0:
                region = Region.objects.get(name='Swan')
                assigned = assignee_default
                logger.warning('No regions were intersected, defaulting to {} ({})'.format(region, assigned))
            elif len(regions) > 1:
                region = Region.objects.get(name='Swan')
                assigned = assignee_default
                logger.warning('>1 regions were intersected ({}), defaulting to {} ({})'.format(regions, region, assigned))
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
            logger.info('New PRS referral generated: {}'.format(new_ref))
            actions.append('{} New PRS referral generated: {}'.format(datetime.now().isoformat(), new_ref))
            # Assign to a region.
            new_ref.region.add(region)
            # Assign an LGA.
            try:
                new_ref.lga = LocalGovernment.objects.get(name=app['LOCAL_GOVERNMENT'])
                new_ref.save()
            except:
                logger.warning('LGA {} was not recognised'.format(app['LOCAL_GOVERNMENT']))
                actions.append('{} LGA {} was not recognised'.format(datetime.now().isoformat(), app['LOCAL_GOVERNMENT']))
            # Add triggers to the new referral.
            triggers = [i.strip() for i in app['MRSZONE_TEXT'].split(',')]
            added_trigger = False
            for i in triggers:
                if DopTrigger.objects.current().filter(name__istartswith=i).exists():
                    added_trigger = True
                    new_ref.dop_triggers.add(DopTrigger.objects.current().get(name__istartswith=i))
                elif i.startswith('BUSH FOREVER SITE'):
                    added_trigger = True
                    new_ref.dop_triggers.add(DopTrigger.objects.get(name='Bush Forever site'))
            # If we didn't link any DoP triggers, link the "No Parks and Wildlife trigger" tag.
            if not added_trigger:
                new_ref.dop_triggers.add(DopTrigger.objects.get(name='No Parks and Wildlife trigger'))
            # Add locations to the new referral (one per polygon in each MP geometry).
            new_locations = []
            for l in locations:
                for f in l['FEATURES']:
                    geom = GEOSGeometry(json.dumps(f['geometry']))
                    for p in geom:
                        new_loc = Location.objects.create(
                            address_no=int(a['NUMBER_FROM']) if a['NUMBER_FROM'] else None,
                            address_suffix=a['NUMBER_FROM_SUFFIX'],
                            road_name=a['STREET_NAME'],
                            road_suffix=a['STREET_SUFFIX'],
                            locality=a['SUBURB'],
                            postcode=a['POSTCODE'],
                            referral=new_ref,
                            poly=p
                        )
                        new_locations.append(new_loc)
                        logger.info('New PRS location generated: {}'.format(new_loc))
                        actions.append('{} New PRS location generated: {}'.format(datetime.now().isoformat(), new_loc))
            # Check to see if new locations intersect with any existing locations.
            intersecting = []
            for l in new_locations:
                other_l = Location.objects.current().exclude(pk=l.pk).filter(poly__isnull=False, poly__intersects=l.poly)
                if other_l.exists():
                    intersecting += list(other_l)
            # For any intersecting locations, relate the new and existing referrals.
            for l in intersecting:
                new_ref.add_relationship(l.referral)
                logger.info('New referral {} related to existing referral {}'.format(new_ref.pk, l.referral.pk))
                actions.append('{} New referral {} related to existing referral {}'.format(datetime.now().isoformat(), new_ref.pk, l.referral.pk))
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
            logger.info('New PRS task generated: {} assigned to {}'.format(new_task, assigned.get_full_name()))
            actions.append('{} New PRS task generated: {} assigned to {}'.format(datetime.now().isoformat(), new_task, assigned.get_full_name()))
            # Email the assigned user about the new task.
            new_task.email_user()
            logger.info('Task assignment email sent to {}'.format(assigned.email))
            actions.append('{} Task assignment email sent to {}'.format(datetime.now().isoformat(), assigned.email))

        # Save the EmailedReferral as a record on the referral.
        new_record = Record.objects.create(name=er.subject, referral=new_ref)
        file_name = 'emailed_referral_{}.html'.format(ref)
        new_file = File(StringIO(er.body))
        new_record.uploaded_file.save(file_name, new_file)
        new_record.save()
        logger.info('New PRS record generated: {}'.format(new_record))
        actions.append('{} New PRS record generated: {}'.format(datetime.now().isoformat(), new_record))

        # Add records to the referral (one per attachment).
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

        # Link the emailed referral to the new or existing referral.
        er.referral = new_ref
        er.processed = True
        er.save()

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

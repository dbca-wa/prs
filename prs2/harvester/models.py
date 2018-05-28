from __future__ import unicode_literals, absolute_import
from datetime import datetime, timedelta
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import GEOSGeometry, Point
from django.core.files.base import ContentFile
from django.db import models
from django.utils.encoding import python_2_unicode_compatible
import logging
from shapely.geometry import Polygon
import xmltodict

from referral.models import (
    Referral, Record, Region, ReferralType, Agency, Organisation, DopTrigger,
    TaskType, Task, Location, LocalGovernment)

logger = logging.getLogger('harvester.log')


@python_2_unicode_compatible
class EmailedReferral(models.Model):
    """A model to record details about emailed planning referrals.
    """
    harvested = models.DateTimeField(auto_now_add=True)
    received = models.DateTimeField(blank=True, null=True, editable=False)
    email_uid = models.CharField(max_length=256)
    to_email = models.CharField(max_length=256)
    from_email = models.CharField(max_length=256)
    subject = models.CharField(max_length=512)
    body = models.TextField()
    referral = models.ForeignKey(
        Referral, null=True, blank=True, on_delete=models.PROTECT)
    processed = models.BooleanField(default=False)

    def __str__(self):
        return self.subject

    def harvest(self, create_tasks=True, create_locations=True, create_records=True, assignee=False):
        """Undertake the harvest process for this emailed referral.
        """
        from .utils import query_slip_esri

        if self.processed:
            return

        User = get_user_model()
        dbca = Agency.objects.get(slug='dbca')
        wapc = Organisation.objects.get(slug='wapc')
        assess_task = TaskType.objects.get(name='Assess a referral')
        if not assignee:
            assignee_default = User.objects.get(username=settings.REFERRAL_ASSIGNEE_FALLBACK)
        else:
            assignee_default = assignee
        actions = []
        attachments = self.emailattachment_set.all()
        # Emails without attachments are usually reminder notices.
        if not attachments.exists():
            logger.info('Skipping harvested referral {} (no attachments)'.format(self))
            self.processed = True
            self.save()
            actions.append('{} Skipping harvested referral {} (no attachments)'.format(datetime.now().isoformat(), self))
            return actions
        # Must be an attachment named 'Application.xml' present to import.
        if not attachments.filter(name__istartswith='application.xml'):
            logger.info('Skipping harvested referral {} (no XML attachment)'.format(self))
            self.processed = True
            self.save()
            actions.append('{} Skipping harvested referral {} (no XML attachment)'.format(datetime.now().isoformat(), self))
            return actions
        else:
            xml_file = attachments.get(name__istartswith='application.xml')
        try:
            d = xmltodict.parse(xml_file.attachment.read())
        except Exception as e:
            logger.error('Harvested referral {} parsing of application.xml failed'.format(self))
            logger.exception(e)
            self.processed = True
            self.save()
            actions.append('{} Harvested referral {} parsing of application.xml failed'.format(datetime.now().isoformat(), self))
        app = d['APPLICATION']
        reference = app['WAPC_APPLICATION_NO']

        # New/existing referral object.
        if Referral.objects.current().filter(reference__iexact=reference):
            # Note if the the reference no. exists in PRS already.
            logger.info('Referral ref. {} is already in database'.format(reference))
            actions.append('{} Referral ref. {} is already in database; using existing referral'.format(datetime.now().isoformat(), reference))
            new_ref = Referral.objects.current().filter(reference__iexact=reference).order_by('-pk').first()
            referral_preexists = True
        else:
            # No match with existing references.
            logger.info('Importing harvested referral ref. {} as new entity'.format(reference))
            actions.append('{} Importing harvested referral ref. {} as new entity'.format(datetime.now().isoformat(), reference))
            new_ref = Referral(reference=reference)
            referral_preexists = False

        # Referral type
        try:
            ref_type = ReferralType.objects.filter(name__istartswith=app['APP_TYPE'])[0]
        except Exception:
            logger.warning('Referral type {} is not recognised type; skipping'.format(app['APP_TYPE']))
            actions.append('{} Referral type {} is not recognised type; skipping'.format(datetime.now().isoformat(), app['APP_TYPE']))
            self.processed = True
            self.save()
            return actions

        # Determine the intersecting region(s).
        regions = []
        assigned = None
        # ADDRESS_DETAIL may or may not be a list :/
        if not isinstance(app['ADDRESS_DETAIL']['DOP_ADDRESS_TYPE'], list):
            addresses = [app['ADDRESS_DETAIL']['DOP_ADDRESS_TYPE']]
        else:
            addresses = app['ADDRESS_DETAIL']['DOP_ADDRESS_TYPE']
        # Address geometry:
        locations = []
        if create_locations:
            for a in addresses:
                # Use the long/lat info to intersect DBCA regions.
                try:
                    p = Point(x=float(a['LONGITUDE']), y=float(a['LATITUDE']))
                    for r in Region.objects.all():
                        if r.region_mpoly and r.region_mpoly.intersects(p) and r not in regions:
                            regions.append(r)
                    intersected_region = True
                except Exception:
                    logger.warning('Address long/lat could not be parsed ({}, {})'.format(a['LONGITUDE'], a['LATITUDE']))
                    actions.append('{} Address long/lat could not be parsed ({}, {})'.format(datetime.now().isoformat(), a['LONGITUDE'], a['LATITUDE']))
                    intersected_region = False
                # Use the PIN field to try returning geometry from SLIP.
                if 'PIN' in a and a['PIN']:
                    try:
                        resp = query_slip_esri(a['PIN'])
                        features = resp.json()['features']  # List of spatial features.
                        if len(features) > 0:
                            a['FEATURES'] = features
                            locations.append(a)  # A dict for each address location.
                            # If we haven't yet, use the feature geom to intersect DBCA regions.
                            if not intersected_region:
                                for f in features:
                                    att = f['attributes']
                                    if 'centroid_longitude' in att and 'centroid_latitude' in att:
                                        p = Point(x=att['centroid_longitude'], y=att['centroid_latitude'])
                                        for r in Region.objects.all():
                                            if r.region_mpoly and r.region_mpoly.intersects(p) and r not in regions:
                                                regions.append(r)
                        logger.info('Address PIN {} returned geometry from SLIP'.format(a['PIN']))
                    except Exception as e:
                        logger.error('Error querying Landgate SLIP for spatial data (referral ref. {})'.format(reference))
                        logger.error(resp.content)
                        logger.exception(e)
                else:
                    logger.warning('Address PIN could not be parsed ({})'.format(a['PIN']))
        regions = set(regions)
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
            region = regions.pop()
            try:
                assigned = RegionAssignee.objects.get(region=region).user
            except Exception:
                logger.warning('No default assignee set for {}, defaulting to {}'.format(region, assignee_default))
                actions.append('{} No default assignee set for {}, defaulting to {}'.format(datetime.now().isoformat(), region, assignee_default))
                assigned = assignee_default

        # Create/update the referral in PRS.
        new_ref.type = ref_type
        new_ref.agency = dbca
        new_ref.referring_org = wapc
        new_ref.reference = reference
        new_ref.description = app['DEVELOPMENT_DESCRIPTION'] if 'DEVELOPMENT_DESCRIPTION' in app else ''
        new_ref.referral_date = self.received
        new_ref.address = app['LOCATION'] if 'LOCATION' in app else ''
        new_ref.save()

        if referral_preexists:
            logger.info('PRS referral updated: {}'.format(new_ref))
            actions.append('{} PRS referral updated: {}'.format(datetime.now().isoformat(), new_ref))
        else:
            logger.info('New PRS referral generated: {}'.format(new_ref))
            actions.append('{} New PRS referral generated: {}'.format(datetime.now().isoformat(), new_ref))

        # Assign to a region.
        new_ref.regions.add(region)
        # Assign an LGA.
        try:
            new_ref.lga = LocalGovernment.objects.get(name=app['LOCAL_GOVERNMENT'])
            new_ref.save()
        except Exception:
            logger.warning('LGA {} was not recognised'.format(app['LOCAL_GOVERNMENT']))
            actions.append('{} LGA {} was not recognised'.format(datetime.now().isoformat(), app['LOCAL_GOVERNMENT']))

        # Add triggers to the new referral.
        if 'MRSZONE_TEXT' in app:
            triggers = [i.strip() for i in app['MRSZONE_TEXT'].split(',')]
        else:
            triggers = []
        added_trigger = False
        for i in triggers:
            # A couple of exceptions for DoP triggers follow (specific -> general trigger).
            if i.startswith('BUSH FOREVER SITE'):
                added_trigger = True
                new_ref.dop_triggers.add(DopTrigger.objects.get(name='Bush Forever site'))
            elif i.startswith('DPW ESTATE'):
                added_trigger = True
                new_ref.dop_triggers.add(DopTrigger.objects.get(name='Parks and Wildlife estate'))
            elif i.find('REGIONAL PARK') > -1:
                added_trigger = True
                new_ref.dop_triggers.add(DopTrigger.objects.get(name='Regional Park'))
            # All other triggers (don't use exists() in case of duplicates).
            elif DopTrigger.objects.current().filter(name__istartswith=i).count() == 1:
                added_trigger = True
                new_ref.dop_triggers.add(DopTrigger.objects.current().get(name__istartswith=i))
        # If we didn't link any DoP triggers, link the "No Parks and Wildlife trigger" tag.
        if not added_trigger:
            new_ref.dop_triggers.add(DopTrigger.objects.get(name='No Parks and Wildlife trigger'))

        # Add locations to the new referral (one per polygon in each MP geometry).
        if create_locations:
            new_locations = []
            for l in locations:
                for f in l['FEATURES']:
                    poly = Polygon(f['geometry']['rings'][0])
                    geom = GEOSGeometry(poly.wkt)
                    new_loc = Location(
                        address_no=int(a['NUMBER_FROM']) if a['NUMBER_FROM'] else None,
                        address_suffix=a['NUMBER_FROM_SUFFIX'],
                        road_name=a['STREET_NAME'],
                        road_suffix=a['STREET_SUFFIX'],
                        locality=a['SUBURB'],
                        postcode=a['POSTCODE'],
                        referral=new_ref,
                        poly=geom
                    )
                    new_loc.save()
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
                if l.referral.pk != new_ref.pk:
                    new_ref.add_relationship(l.referral)
                    logger.info('New referral {} related to existing referral {}'.format(new_ref.pk, l.referral.pk))
                    actions.append('{} New referral {} related to existing referral {}'.format(datetime.now().isoformat(), new_ref.pk, l.referral.pk))

        # Create an "Assess a referral" task and assign it to a user.
        if create_tasks:
            new_task = Task(
                type=assess_task,
                referral=new_ref,
                start_date=new_ref.referral_date,
                description=new_ref.description,
                assigned_user=assigned
            )
            new_task.state = assess_task.initial_state
            if 'DUE_DATE' in app and app['DUE_DATE']:
                try:
                    due = datetime.strptime(app['DUE_DATE'], '%d-%b-%y')
                except Exception:
                    due = datetime.today() + timedelta(assess_task.target_days)
            else:
                due = datetime.today() + timedelta(assess_task.target_days)
            new_task.due_date = due
            new_task.save()
            logger.info('New PRS task generated: {} assigned to {}'.format(new_task, assigned.get_full_name()))
            actions.append('{} New PRS task generated: {} assigned to {}'.format(datetime.now().isoformat(), new_task, assigned.get_full_name()))

            # Email the assigned user about the new task.
            new_task.email_user()
            logger.info('Task assignment email sent to {}'.format(assigned.email))
            actions.append('{} Task assignment email sent to {}'.format(datetime.now().isoformat(), assigned.email))

        # Save the EmailedReferral as a record on the referral.
        if create_records:
            new_record = Record.objects.create(
                name=self.subject, referral=new_ref, order_date=datetime.today())
            file_name = 'emailed_referral_{}.html'.format(reference)
            new_file = ContentFile(self.body)
            new_record.uploaded_file.save(file_name, new_file)
            new_record.save()
            logger.info('New PRS record generated: {}'.format(new_record))
            actions.append('{} New PRS record generated: {}'.format(datetime.now().isoformat(), new_record))

            # Add records to the referral (one per attachment).
            for i in attachments:
                new_record = Record.objects.create(
                    name=i.name, referral=new_ref, order_date=datetime.today())
                # Duplicate the uploaded file.
                new_file = ContentFile(i.attachment.read())
                new_record.uploaded_file.save(i.name, new_file)
                new_record.save()
                logger.info('New PRS record generated: {}'.format(new_record))
                actions.append('{} New PRS record generated: {}'.format(datetime.now().isoformat(), new_record))
                # Link the attachment to the new, generated record.
                i.record = new_record
                i.save()

        # Link the emailed referral to the new or existing referral.
        self.referral = new_ref
        self.processed = True
        self.save()

        return actions


@python_2_unicode_compatible
class EmailAttachment(models.Model):
    """A saved email file attachment.
    """
    emailed_referral = models.ForeignKey(EmailedReferral, on_delete=models.PROTECT)
    name = models.CharField(max_length=512)
    attachment = models.FileField(
        max_length=255, upload_to='email_attachments/%Y/%m/%d')
    record = models.ForeignKey(
        Record, null=True, blank=True, on_delete=models.PROTECT)

    def __str__(self):
        return self.name

    def get_xml_data(self):
        """Convenience function to conditionally return XML data from the
        attachment (returns None if not an XML file).
        """
        d = None
        if self.name.startswith('Application.xml'):
            self.attachment.seek(0)
            d = xmltodict.parse(self.attachment.read())
        return d


@python_2_unicode_compatible
class RegionAssignee(models.Model):
    """A model to define which user will be assigned any generated referrals
    for a region.
    """
    region = models.OneToOneField(Region, on_delete=models.PROTECT)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        limit_choices_to={'groups__name__in': ['PRS user'], 'is_active': True},
        help_text='Default assigned user for this region.')

    def __str__(self):
        return '{} -> {}'.format(self.region, self.user.get_full_name())

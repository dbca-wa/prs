from django.contrib.gis.geos import GEOSGeometry
from django.core.management.base import BaseCommand, CommandError
import json
from referral.models import Region


class Command(BaseCommand):
    help = 'Loads Region geometry from serialised GeoJSON (dpaw_regions.json)'

    def handle(self, *args, **options):
        try:
            regions_json = json.load(open('dpaw_regions.json', 'r'))
        except IOError:
            raise CommandError('dpaw_regions.json file not present')

        for f in regions_json['features']:
            region = Region.objects.get(name__istartswith=f['properties']['region'])
            region.region_mpoly = GEOSGeometry(json.dumps(f['geometry']))
            region.save()
            self.stdout.write('{} geometry updated'.format(region))

        self.stdout.write('Done!')

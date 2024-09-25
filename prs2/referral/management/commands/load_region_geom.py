from django.contrib.gis.geos import GEOSGeometry
from django.core.management.base import BaseCommand
from referral.models import Region
from referral.utils import wfs_getfeature


class Command(BaseCommand):
    help = "Loads Region geometry from a Geoserver layer WFS"

    def add_arguments(self, parser):
        parser.add_argument(
            "--typename",
            action="store",
            required=True,
            type=str,
            dest="typename",
            help="typeName value for WFS GetFeature request (namespace:featuretype)",
        )
        parser.add_argument(
            "--field",
            action="store",
            required=True,
            type=str,
            dest="field",
            help="GeoJSON property key containing the region name",
        )

    def handle(self, *args, **options):
        type_name = options["typename"]
        field = options["field"]
        regions_data = wfs_getfeature(type_name)

        for feature in regions_data["features"]:
            region = Region.objects.get(name__iexact=feature["properties"][field])
            region.region_mpoly = GEOSGeometry(str(feature["geometry"]))
            region.save()
            self.stdout.write("{} region geometry updated".format(region))

        self.stdout.write("Completed")

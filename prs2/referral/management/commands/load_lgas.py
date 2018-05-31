import csv
from django.core.management.base import BaseCommand, CommandError
from referral.models import LocalGovernment


class Command(BaseCommand):
    help = 'Loads LGA names from a CSV (lga.csv)'

    def handle(self, *args, **options):
        try:
            lga_file = open('lga.csv', 'r')
        except IOError:
            raise CommandError('lga.csv file not present')

        lga_reader = csv.reader(lga_file)
        for row in lga_reader:
            LocalGovernment.objects.create(name=row[0])

        self.stdout.write('Done!')

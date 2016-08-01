from django.core.management.base import BaseCommand
from harvester.utils import harvest_unread_emails, import_harvested_refs


class Command(BaseCommand):
    help = 'Harvest emailed referrals into the database.'

    def handle(self, *args, **options):
        harvest_unread_emails()
        import_harvested_refs()
        self.stdout.write('Done')

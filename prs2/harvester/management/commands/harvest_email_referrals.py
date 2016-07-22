from django.core.management.base import BaseCommand

from harvester.harvest import harvest_unread_emails


class Command(BaseCommand):
    help = 'Harvest emailed referrals into the database.'

    def handle(self, *args, **options):
        harvest_unread_emails()
        self.stdout.write('Done')

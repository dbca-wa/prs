from django.core.management.base import BaseCommand, CommandError
from referral.utils import overdue_task_email


class Command(BaseCommand):
    help = 'Send email to users notifying about overdue tasks'

    def handle(self, *args, **options):
        try:
            overdue_task_email()
            self.stdout.write('Done')
        except:
            raise CommandError('Unable to send overdue tasks email to users')

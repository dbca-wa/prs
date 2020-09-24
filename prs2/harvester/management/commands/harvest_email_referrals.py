from django.conf import settings
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from django.core.mail import EmailMessage
from django.utils import timezone
from harvester.utils import harvest_unread_emails, import_harvested_refs, email_harvest_actions


class Command(BaseCommand):
    help = 'Harvest emailed referrals into the database.'

    def add_arguments(self, parser):
        # Named (optional) arguments
        parser.add_argument(
            '--email',
            action='store_true',
            dest='email',
            default=False,
            help='Email a report of harvest actions to PRS power user group',
        )

    def handle(self, *args, **options):
        try:
            actions = []
            for email in settings.PLANNING_EMAILS:
                actions += harvest_unread_emails(email)
            actions += import_harvested_refs()
            if options['email']:
                # Send an email to users in the 'PRS power users' group.
                pu_group = Group.objects.get(name=settings.PRS_POWER_USER_GROUP)
                p_users = pu_group.user_set.filter(is_active=True)
                to_emails = [u.email for u in p_users]
                email_harvest_actions(to_emails, actions)
                self.stdout.write('Done, email sent')
            else:
                self.stdout.write('Done')
        except Exception as ex:
            error = 'PRS harvest of emailed referrals raised an exception at {}'.format(timezone.localtime().isoformat())
            text_content = 'Exception:\n\n{}'.format(ex)
            if not settings.DEBUG:
                # Send an email to ADMINS.
                msg = EmailMessage(
                    subject=error,
                    body=text_content,
                    from_email=settings.APPLICATION_ALERTS_EMAIL,
                    to=settings.ADMINS,
                )
                msg.send()
            raise CommandError(error)

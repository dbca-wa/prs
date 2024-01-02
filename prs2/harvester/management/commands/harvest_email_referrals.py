from django.conf import settings
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand
import logging
from harvester.utils import harvest_unread_emails, import_harvested_refs, email_harvest_actions


class Command(BaseCommand):
    help = "Harvest emailed referrals into the database."

    def add_arguments(self, parser):
        # Named (optional) arguments
        parser.add_argument(
            "--email",
            action="store_true",
            dest="email",
            default=False,
            help="Email a report of harvest actions to PRS power user group",
        )
        parser.add_argument(
            "--purge-email",
            action="store_true",
            dest="purge_email",
            required=False,
            help="Mark processed email as read and flag for deletion",
        )

    def handle(self, *args, **options):
        logger = logging.getLogger("harvester")
        actions = []
        for email in settings.PLANNING_EMAILS:
            if "purge_email" in options and options["purge_email"]:
                actions += harvest_unread_emails(from_email=email, purge_email=True)
            else:
                actions += harvest_unread_emails(from_email=email)
        actions += import_harvested_refs()
        if options["email"]:
            # Send an email to users in the "PRS power users" group.
            pu_group = Group.objects.get(name=settings.PRS_POWER_USER_GROUP)
            p_users = pu_group.user_set.filter(is_active=True)
            to_emails = [u.email for u in p_users]
            email_harvest_actions(to_emails, actions)
            logger.info("Completed, email sent")
        else:
            logger.info("Completed")

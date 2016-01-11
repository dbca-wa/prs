from tqdm import tqdm
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import Group, User
from django.conf import settings
import os
from referral.models import ConditionCategory, Condition, ModelCondition, Note, Task
from taggit.models import Tag


class Command(BaseCommand):
    help = 'Performs PRS v2.0 post-update tasks'

    def handle(self, *args, **options):
        # Only run this command if PRS is v2.0.
        if settings.APPLICATION_VERSION_NO != '2.0':
            raise CommandError('PRS application version is not 2.0')

        # Ensure that only the required groups exist.
        self.check_groups()

        # Place required users in groups and update emails.
        self.add_users_to_groups()
        self.update_user_emails()

        # Add new ConditionCategory objects.
        self.add_categories()

        # Migrate Conditions: attach categories matching existing tags.
        self.migrate_categories()

        # Migrate ModelConditions: attach conditions matching is_null Referrals.
        self.populate_modelconditions()

        # Cleanse fields containing unicode by calling save() on each object.
        self.cleanse_unicode()

        # Ensure that all required Tags exist.
        self.get_or_create_tags()

        # End.
        self.stdout.write('Done')

    def check_groups(self):
        self.stdout.write('Ensuring that required groups exist')
        g1, g2 = 'PRS user', 'PRS power user'
        users, c = Group.objects.get_or_create(name=g1)
        p_users, c = Group.objects.get_or_create(name=g2)

        # Delete all existing groups except for the two above.
        groups_old = Group.objects.all().exclude(name__in=[g1, g2])
        self.stdout.write('Deleting {} old groups'.format(groups_old.count()))
        for group in groups_old:
            group.delete()

    def add_users_to_groups(self):
        # Requires a file in the base project directory called usernames.txt
        # File should list one username per line to add to the 'PRS user' group
        self.stdout.write('Adding existing PRS users to the required groups')
        fp = os.path.join(settings.BASE_DIR, 'usernames.txt')

        if not os.path.exists(fp):
            self.stdout.write('usernames.txt not found, skipping')
            return

        f = open(fp, 'r')
        grp = Group.objects.get(name='PRS user')

        for i in f.readlines():
            username = i.strip()
            user = User.objects.get(username=username)
            user.groups.add(grp)

    def update_user_emails(self):
        self.stdout.write('Updating dec emails to dpaw.wa.gov.au')
        for i in User.objects.all():
            if 'dec.wa.gov.au' in i.email:
                i.email = i.email.replace('dec.wa.gov.au', 'dpaw.wa.gov.au')
                i.save()

    def add_categories(self):
        self.stdout.write('Ensuring that required condition categories exist')
        for cc in [
                'Conservation covenant', 'DPaW managed area', 'Wetlands',
                'Regional Park', 'TEC', 'Flora', 'Fauna', 'Fire', 'Other']:
            cat, c = ConditionCategory.objects.get_or_create(name=cc)

    def migrate_categories(self):
        conditions = Condition.objects.filter(tags__isnull=False)
        self.stdout.write('Migrating categories for {} conditions'.format(conditions.count()))
        for i in tqdm(range(conditions.count())):
            # Should only be one tag; use category with same name.
            c = conditions[i]
            tag = c.tags.first()
            if ConditionCategory.objects.filter(name=tag.name).exists():
                c.category = ConditionCategory.objects.get(name=tag.name)
                c.save()

    def populate_modelconditions(self):
        conditions = Condition.objects.current().filter(referral__isnull=True)
        self.stdout.write(
            'Migrating ModelConditions for {} model conditions'.format(
                conditions.count()))
        for i in tqdm(range(conditions.count())):
            c = conditions[i]
            ModelCondition.objects.get_or_create(
                creator_id=c.creator.id,
                modifier_id=c.modifier.id,
                category=c.category,
                condition=c.condition,
                identifier=c.identifier)
        # Set 'effective_to' on all ModelConditions that aren't the new ones.
        for m in ModelCondition.objects.all():
            if not m.identifier.startswith('EN'):
                m.delete()

    def cleanse_unicode(self):
        self.stdout.write('Cleansing unicode for notes')
        for i in tqdm(Note.objects.all()):
            i.save()
        self.stdout.write('Cleansing unicode for conditions')
        for i in tqdm(Condition.objects.all()):
            i.save()
        self.stdout.write('Cleansing unicode for tasks')
        for i in tqdm(Task.objects.all()):
            i.save()

    def get_or_create_tags(self):
        self.stdout.write('Ensuring that all required tags exist')
        tag_list = [
            'DPaW managed area',
            'Near DPaW managed area',
            'Regional Park',
            'Bush Forever site',
            'Remnant vegetation',
            'Threatened ecological community',
            'Priority ecological community',
            'Declared rare flora',
            'Priority flora',
            'Native flora',
            'Wetlands',
            'Ecological linkage',
            'Covenant',
            'Fire',
            'Weeds',
            'Disease risk',
            ]
        for t in tag_list:
            tag, c = Tag.objects.get_or_create(name=t)

# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import taggit.managers
import django.contrib.gis.db.models.fields
import storages.backends.overwrite
import autoslug.fields
import referral.base
import django.utils.timezone
from django.conf import settings
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('taggit', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Agency',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', models.DateTimeField(default=django.utils.timezone.now, editable=False)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('effective_to', models.DateTimeField(null=True, blank=True)),
                ('name', models.CharField(max_length=200)),
                ('description', models.CharField(blank=True, max_length=200, null=True, validators=[django.core.validators.MaxLengthValidator(200)])),
                ('slug', autoslug.fields.AutoSlugField(editable=False, populate_from='name', help_text='Must be unique. Automatically generated from name.', unique=True)),
                ('public', models.BooleanField(default=True, help_text='Is this lookup selection available to all users?')),
                ('code', models.CharField(max_length=16)),
                ('creator', models.ForeignKey(related_name='referral_agency_created', editable=False, to=settings.AUTH_USER_MODEL)),
                ('modifier', models.ForeignKey(related_name='referral_agency_modified', editable=False, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name_plural': 'agencies',
            },
        ),
        migrations.CreateModel(
            name='Bookmark',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', models.DateTimeField(default=django.utils.timezone.now, editable=False)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('effective_to', models.DateTimeField(null=True, blank=True)),
                ('description', models.CharField(blank=True, max_length=200, null=True, help_text='Maximum 200 characters.', validators=[django.core.validators.MaxLengthValidator(200)])),
                ('creator', models.ForeignKey(related_name='referral_bookmark_created', editable=False, to=settings.AUTH_USER_MODEL)),
                ('modifier', models.ForeignKey(related_name='referral_bookmark_modified', editable=False, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Clearance',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('date_created', models.DateField(auto_now_add=True)),
                ('deposited_plan', models.CharField(blank=True, max_length=200, null=True, validators=[django.core.validators.MaxLengthValidator(200)])),
            ],
        ),
        migrations.CreateModel(
            name='Condition',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', models.DateTimeField(default=django.utils.timezone.now, editable=False)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('effective_to', models.DateTimeField(null=True, blank=True)),
                ('condition', models.TextField(editable=False)),
                ('condition_html', models.TextField()),
                ('proposed_condition', models.TextField(null=True, editable=False, blank=True)),
                ('proposed_condition_html', models.TextField(null=True, blank=True)),
                ('identifier', models.CharField(blank=True, max_length=100, null=True, help_text="The decision-making authority's identifying number or code for this condition.", validators=[django.core.validators.MaxLengthValidator(100)])),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='DopTrigger',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', models.DateTimeField(default=django.utils.timezone.now, editable=False)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('effective_to', models.DateTimeField(null=True, blank=True)),
                ('name', models.CharField(max_length=200)),
                ('description', models.CharField(blank=True, max_length=200, null=True, validators=[django.core.validators.MaxLengthValidator(200)])),
                ('slug', autoslug.fields.AutoSlugField(editable=False, populate_from='name', help_text='Must be unique. Automatically generated from name.', unique=True)),
                ('public', models.BooleanField(default=True, help_text='Is this lookup selection available to all users?')),
                ('creator', models.ForeignKey(related_name='referral_doptrigger_created', editable=False, to=settings.AUTH_USER_MODEL)),
                ('modifier', models.ForeignKey(related_name='referral_doptrigger_modified', editable=False, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'DoP trigger',
            },
        ),
        migrations.CreateModel(
            name='Location',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', models.DateTimeField(default=django.utils.timezone.now, editable=False)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('effective_to', models.DateTimeField(null=True, blank=True)),
                ('address_no', models.IntegerField(null=True, verbose_name='address number', blank=True)),
                ('address_suffix', models.CharField(blank=True, max_length=10, null=True, validators=[django.core.validators.MaxLengthValidator(10)])),
                ('road_name', models.CharField(blank=True, max_length=100, null=True, validators=[django.core.validators.MaxLengthValidator(100)])),
                ('road_suffix', models.CharField(blank=True, max_length=100, null=True, validators=[django.core.validators.MaxLengthValidator(100)])),
                ('locality', models.CharField(blank=True, max_length=100, null=True, validators=[django.core.validators.MaxLengthValidator(100)])),
                ('postcode', models.CharField(blank=True, max_length=6, null=True, validators=[django.core.validators.MaxLengthValidator(6)])),
                ('landuse', models.TextField(null=True, blank=True)),
                ('lot_no', models.CharField(blank=True, max_length=100, null=True, verbose_name='lot number', validators=[django.core.validators.MaxLengthValidator(100)])),
                ('lot_desc', models.TextField(null=True, blank=True)),
                ('strata_lot_no', models.CharField(blank=True, max_length=100, null=True, validators=[django.core.validators.MaxLengthValidator(100)])),
                ('strata_lot_desc', models.TextField(null=True, blank=True)),
                ('reserve', models.TextField(null=True, blank=True)),
                ('cadastre_obj_id', models.IntegerField(null=True, blank=True)),
                ('poly', django.contrib.gis.db.models.fields.PolygonField(help_text='Optional.', srid=4283, null=True, blank=True)),
                ('address_string', models.TextField(null=True, blank=True)),
                ('creator', models.ForeignKey(related_name='referral_location_created', editable=False, to=settings.AUTH_USER_MODEL)),
                ('modifier', models.ForeignKey(related_name='referral_location_modified', editable=False, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Note',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', models.DateTimeField(default=django.utils.timezone.now, editable=False)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('effective_to', models.DateTimeField(null=True, blank=True)),
                ('note_html', models.TextField()),
                ('note', models.TextField(editable=False)),
                ('order_date', models.DateField(null=True, blank=True)),
                ('creator', models.ForeignKey(related_name='referral_note_created', editable=False, to=settings.AUTH_USER_MODEL)),
                ('modifier', models.ForeignKey(related_name='referral_note_modified', editable=False, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['order_date', 'id'],
            },
        ),
        migrations.CreateModel(
            name='NoteType',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', models.DateTimeField(default=django.utils.timezone.now, editable=False)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('effective_to', models.DateTimeField(null=True, blank=True)),
                ('name', models.CharField(max_length=200)),
                ('description', models.CharField(blank=True, max_length=200, null=True, validators=[django.core.validators.MaxLengthValidator(200)])),
                ('slug', autoslug.fields.AutoSlugField(editable=False, populate_from='name', help_text='Must be unique. Automatically generated from name.', unique=True)),
                ('public', models.BooleanField(default=True, help_text='Is this lookup selection available to all users?')),
                ('icon', models.ImageField(null=True, upload_to='img', blank=True)),
                ('creator', models.ForeignKey(related_name='referral_notetype_created', editable=False, to=settings.AUTH_USER_MODEL)),
                ('modifier', models.ForeignKey(related_name='referral_notetype_modified', editable=False, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['name'],
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Organisation',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', models.DateTimeField(default=django.utils.timezone.now, editable=False)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('effective_to', models.DateTimeField(null=True, blank=True)),
                ('name', models.CharField(max_length=200)),
                ('description', models.CharField(blank=True, max_length=200, null=True, validators=[django.core.validators.MaxLengthValidator(200)])),
                ('slug', autoslug.fields.AutoSlugField(editable=False, populate_from='name', help_text='Must be unique. Automatically generated from name.', unique=True)),
                ('public', models.BooleanField(default=True, help_text='Is this lookup selection available to all users?')),
                ('list_name', models.CharField(help_text='Name as it will appear in the alphabetised selection lists (e.g. "Broome,\n            Shire of"). Put acronyms (e.g. OEPA) at the end.', max_length=100, validators=[django.core.validators.MaxLengthValidator(100)])),
                ('telephone', models.CharField(help_text='Include the area code.', max_length=20, null=True, blank=True)),
                ('fax', models.CharField(blank=True, max_length=20, null=True, help_text='Include the area code.', validators=[django.core.validators.MaxLengthValidator(20)])),
                ('email', models.EmailField(max_length=254, null=True, blank=True)),
                ('address1', models.CharField(validators=[django.core.validators.MaxLengthValidator(100)], max_length=100, blank=True, help_text='Postal address (optional). Maximum 100 characters.', null=True, verbose_name='Address line 1')),
                ('address2', models.CharField(validators=[django.core.validators.MaxLengthValidator(100)], max_length=100, blank=True, help_text='Postal address line 2 (optional). Maximum 100 characters.', null=True, verbose_name='Address line 2')),
                ('suburb', models.CharField(blank=True, max_length=100, null=True, validators=[django.core.validators.MaxLengthValidator(100)])),
                ('state', models.IntegerField(default=8, choices=[(1, 'ACT'), (2, 'NSW'), (3, 'NT'), (4, 'QLD'), (5, 'SA'), (6, 'TAS'), (7, 'VIC'), (8, 'WA')])),
                ('postcode', models.CharField(blank=True, max_length=4, null=True, validators=[django.core.validators.MaxLengthValidator(4)])),
                ('creator', models.ForeignKey(related_name='referral_organisation_created', editable=False, to=settings.AUTH_USER_MODEL)),
                ('modifier', models.ForeignKey(related_name='referral_organisation_modified', editable=False, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['name'],
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='OrganisationType',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', models.DateTimeField(default=django.utils.timezone.now, editable=False)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('effective_to', models.DateTimeField(null=True, blank=True)),
                ('name', models.CharField(max_length=200)),
                ('description', models.CharField(blank=True, max_length=200, null=True, validators=[django.core.validators.MaxLengthValidator(200)])),
                ('slug', autoslug.fields.AutoSlugField(editable=False, populate_from='name', help_text='Must be unique. Automatically generated from name.', unique=True)),
                ('public', models.BooleanField(default=True, help_text='Is this lookup selection available to all users?')),
                ('creator', models.ForeignKey(related_name='referral_organisationtype_created', editable=False, to=settings.AUTH_USER_MODEL)),
                ('modifier', models.ForeignKey(related_name='referral_organisationtype_modified', editable=False, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['name'],
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Record',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', models.DateTimeField(default=django.utils.timezone.now, editable=False)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('effective_to', models.DateTimeField(null=True, blank=True)),
                ('name', models.CharField(help_text='The name/description of the record (max 200 characters).', max_length=200, validators=[django.core.validators.MaxLengthValidator(200)])),
                ('uploaded_file', referral.base.ContentTypeRestrictedFileField(upload_to='uploads/%Y/%m/%d', storage=storages.backends.overwrite.OverwriteStorage(), max_length=255, blank=True, help_text='Allowed file types: TIF,JPG,GIF,PNG,DOC,DOCX,XLS,XLSX,CSV,PDF or ZIP (max 20mb).', null=True)),
                ('infobase_id', models.SlugField(blank=True, help_text='Infobase object ID. Optional.', null=True, verbose_name='Infobase ID')),
                ('description', models.TextField(help_text='Optional.', null=True, blank=True)),
                ('order_date', models.DateField(null=True, blank=True)),
                ('creator', models.ForeignKey(related_name='referral_record_created', editable=False, to=settings.AUTH_USER_MODEL)),
                ('modifier', models.ForeignKey(related_name='referral_record_modified', editable=False, to=settings.AUTH_USER_MODEL)),
                ('notes', models.ManyToManyField(to='referral.Note', blank=True)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Referral',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', models.DateTimeField(default=django.utils.timezone.now, editable=False)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('effective_to', models.DateTimeField(null=True, blank=True)),
                ('reference', models.CharField(help_text="[Searchable] Referrer's reference no. Maximum 100 characters.", max_length=100, validators=[django.core.validators.MaxLengthValidator(100)])),
                ('file_no', models.CharField(blank=True, max_length=100, null=True, help_text='[Searchable] The DEC file this referral is filed within. Maximum 100 characters.', validators=[django.core.validators.MaxLengthValidator(100)])),
                ('description', models.TextField(help_text='[Searchable] Optional.', null=True, blank=True)),
                ('referral_date', models.DateField(help_text='Date that the referral was received.', verbose_name='received date')),
                ('address', models.CharField(blank=True, max_length=200, null=True, help_text='[Searchable] Physical address of the planning proposal. Maximum 200 characters.', validators=[django.core.validators.MaxLengthValidator(200)])),
                ('point', django.contrib.gis.db.models.fields.PointField(help_text='Optional.', srid=4283, null=True, editable=False, blank=True)),
                ('agency', models.ForeignKey(blank=True, to='referral.Agency', help_text='[Searchable] The agency to which this referral relates.', null=True)),
                ('creator', models.ForeignKey(related_name='referral_referral_created', editable=False, to=settings.AUTH_USER_MODEL)),
                ('dop_triggers', models.ManyToManyField(help_text='[Searchable] The Department of Planning trigger(s) for this referral.', related_name='dop_triggers', verbose_name='DoP triggers', to='referral.DopTrigger', blank=True)),
                ('modifier', models.ForeignKey(related_name='referral_referral_modified', editable=False, to=settings.AUTH_USER_MODEL)),
                ('referring_org', models.ForeignKey(verbose_name='referring organisation', to='referral.Organisation', help_text='[Searchable] The referring organisation or individual.')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='ReferralType',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', models.DateTimeField(default=django.utils.timezone.now, editable=False)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('effective_to', models.DateTimeField(null=True, blank=True)),
                ('name', models.CharField(max_length=200)),
                ('description', models.CharField(blank=True, max_length=200, null=True, validators=[django.core.validators.MaxLengthValidator(200)])),
                ('slug', autoslug.fields.AutoSlugField(editable=False, populate_from='name', help_text='Must be unique. Automatically generated from name.', unique=True)),
                ('public', models.BooleanField(default=True, help_text='Is this lookup selection available to all users?')),
                ('creator', models.ForeignKey(related_name='referral_referraltype_created', editable=False, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['name'],
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Region',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', models.DateTimeField(default=django.utils.timezone.now, editable=False)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('effective_to', models.DateTimeField(null=True, blank=True)),
                ('name', models.CharField(max_length=200)),
                ('description', models.CharField(blank=True, max_length=200, null=True, validators=[django.core.validators.MaxLengthValidator(200)])),
                ('slug', autoslug.fields.AutoSlugField(editable=False, populate_from='name', help_text='Must be unique. Automatically generated from name.', unique=True)),
                ('public', models.BooleanField(default=True, help_text='Is this lookup selection available to all users?')),
                ('region_mpoly', django.contrib.gis.db.models.fields.MultiPolygonField(help_text='Optional.', srid=4283, null=True, blank=True)),
                ('creator', models.ForeignKey(related_name='referral_region_created', editable=False, to=settings.AUTH_USER_MODEL)),
                ('modifier', models.ForeignKey(related_name='referral_region_modified', editable=False, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['name'],
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='RelatedReferral',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('from_referral', models.ForeignKey(related_name='from_referral', to='referral.Referral')),
                ('to_referral', models.ForeignKey(related_name='to_referral', to='referral.Referral')),
            ],
        ),
        migrations.CreateModel(
            name='Task',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', models.DateTimeField(default=django.utils.timezone.now, editable=False)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('effective_to', models.DateTimeField(null=True, blank=True)),
                ('description', models.TextField(help_text='Please describe the task requirements (optional).', null=True, blank=True)),
                ('start_date', models.DateField(help_text='Date on which this task was started.', null=True, blank=True)),
                ('due_date', models.DateField(help_text='Date by which the task must be completed.', null=True, blank=True)),
                ('complete_date', models.DateField(help_text='Date that the task was completed.', null=True, blank=True)),
                ('stop_date', models.DateField(help_text='Date that the task was stopped.', null=True, blank=True)),
                ('restart_date', models.DateField(help_text='Date that a stopped task was restarted.', null=True, blank=True)),
                ('stop_time', models.IntegerField(default=0, help_text='Cumulative time stopped in days.', editable=False)),
                ('assigned_user', models.ForeignKey(related_name='refer_task_assigned_user', to=settings.AUTH_USER_MODEL, help_text='The officer responsible for completing the task.')),
                ('creator', models.ForeignKey(related_name='referral_task_created', editable=False, to=settings.AUTH_USER_MODEL)),
                ('modifier', models.ForeignKey(related_name='referral_task_modified', editable=False, to=settings.AUTH_USER_MODEL)),
                ('notes', models.ManyToManyField(to='referral.Note', blank=True)),
                ('records', models.ManyToManyField(to='referral.Record', blank=True)),
                ('referral', models.ForeignKey(to='referral.Referral')),
            ],
            options={
                'ordering': ['due_date'],
            },
        ),
        migrations.CreateModel(
            name='TaskState',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', models.DateTimeField(default=django.utils.timezone.now, editable=False)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('effective_to', models.DateTimeField(null=True, blank=True)),
                ('name', models.CharField(max_length=200)),
                ('description', models.CharField(blank=True, max_length=200, null=True, validators=[django.core.validators.MaxLengthValidator(200)])),
                ('slug', autoslug.fields.AutoSlugField(editable=False, populate_from='name', help_text='Must be unique. Automatically generated from name.', unique=True)),
                ('public', models.BooleanField(default=True, help_text='Is this lookup selection available to all users?')),
                ('is_ongoing', models.BooleanField(default=True, help_text='Does this task state indicate that the task remains active?')),
                ('is_assessment', models.BooleanField(default=False, help_text='Does this task state represent an assessment by staff?')),
                ('creator', models.ForeignKey(related_name='referral_taskstate_created', editable=False, to=settings.AUTH_USER_MODEL)),
                ('modifier', models.ForeignKey(related_name='referral_taskstate_modified', editable=False, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['name'],
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='TaskType',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', models.DateTimeField(default=django.utils.timezone.now, editable=False)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('effective_to', models.DateTimeField(null=True, blank=True)),
                ('name', models.CharField(max_length=200)),
                ('description', models.CharField(blank=True, max_length=200, null=True, validators=[django.core.validators.MaxLengthValidator(200)])),
                ('slug', autoslug.fields.AutoSlugField(editable=False, populate_from='name', help_text='Must be unique. Automatically generated from name.', unique=True)),
                ('public', models.BooleanField(default=True, help_text='Is this lookup selection available to all users?')),
                ('target_days', models.IntegerField(default=35, help_text='Time limit to fall back on if there is no user-supplied due date.')),
                ('creator', models.ForeignKey(related_name='referral_tasktype_created', editable=False, to=settings.AUTH_USER_MODEL)),
                ('initial_state', models.ForeignKey(help_text='The initial state for this task type.', to='referral.TaskState')),
                ('modifier', models.ForeignKey(related_name='referral_tasktype_modified', editable=False, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['name'],
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='UserProfile',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('referral_history', models.TextField(null=True, blank=True)),
                ('task_history', models.TextField(null=True, blank=True)),
                ('agency', models.ForeignKey(blank=True, to='referral.Agency', null=True)),
                ('user', models.OneToOneField(to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddField(
            model_name='taskstate',
            name='task_type',
            field=models.ForeignKey(blank=True, to='referral.TaskType', help_text='Optional - does this state relate to a single task type only?', null=True),
        ),
        migrations.AddField(
            model_name='task',
            name='state',
            field=models.ForeignKey(verbose_name='task state', to='referral.TaskState', help_text='The status of the task.'),
        ),
        migrations.AddField(
            model_name='task',
            name='type',
            field=models.ForeignKey(verbose_name='task type', to='referral.TaskType', help_text='The task type.'),
        ),
        migrations.AddField(
            model_name='referraltype',
            name='initial_task',
            field=models.ForeignKey(blank=True, to='referral.TaskType', help_text='Optional, but highly recommended.', null=True),
        ),
        migrations.AddField(
            model_name='referraltype',
            name='modifier',
            field=models.ForeignKey(related_name='referral_referraltype_modified', editable=False, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='referral',
            name='region',
            field=models.ManyToManyField(help_text='[Searchable] The region(s) in which this referral belongs.', related_name='regions', to='referral.Region', blank=True),
        ),
        migrations.AddField(
            model_name='referral',
            name='related_refs',
            field=models.ManyToManyField(related_name='related_referrals', editable=False, through='referral.RelatedReferral', to='referral.Referral'),
        ),
        migrations.AddField(
            model_name='referral',
            name='tags',
            field=taggit.managers.TaggableManager(to='taggit.Tag', through='taggit.TaggedItem', blank=True, help_text='A comma-separated list of tags.', verbose_name='Tags'),
        ),
        migrations.AddField(
            model_name='referral',
            name='type',
            field=models.ForeignKey(verbose_name='referral type', to='referral.ReferralType', help_text='[Searchable] The referral type; explanation of these categories is also found\n            in the <a href="/help/">PRS User documentation</a>.'),
        ),
        migrations.AddField(
            model_name='record',
            name='referral',
            field=models.ForeignKey(to='referral.Referral'),
        ),
        migrations.AddField(
            model_name='organisation',
            name='type',
            field=models.ForeignKey(help_text='The organisation type.', to='referral.OrganisationType'),
        ),
        migrations.AddField(
            model_name='note',
            name='records',
            field=models.ManyToManyField(to='referral.Record', blank=True),
        ),
        migrations.AddField(
            model_name='note',
            name='referral',
            field=models.ForeignKey(to='referral.Referral'),
        ),
        migrations.AddField(
            model_name='note',
            name='type',
            field=models.ForeignKey(blank=True, to='referral.NoteType', help_text='The type of note (optional).', null=True, verbose_name='note type'),
        ),
        migrations.AddField(
            model_name='location',
            name='referral',
            field=models.ForeignKey(to='referral.Referral'),
        ),
        migrations.AddField(
            model_name='condition',
            name='clearance_tasks',
            field=models.ManyToManyField(related_name='clearance_requests', editable=False, through='referral.Clearance', to='referral.Task'),
        ),
        migrations.AddField(
            model_name='condition',
            name='creator',
            field=models.ForeignKey(related_name='referral_condition_created', editable=False, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='condition',
            name='modifier',
            field=models.ForeignKey(related_name='referral_condition_modified', editable=False, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='condition',
            name='referral',
            field=models.ForeignKey(blank=True, to='referral.Referral', null=True),
        ),
        migrations.AddField(
            model_name='condition',
            name='tags',
            field=taggit.managers.TaggableManager(to='taggit.Tag', through='taggit.TaggedItem', blank=True, help_text='A comma-separated list of tags.', verbose_name='Tags'),
        ),
        migrations.AddField(
            model_name='clearance',
            name='condition',
            field=models.ForeignKey(to='referral.Condition'),
        ),
        migrations.AddField(
            model_name='clearance',
            name='task',
            field=models.ForeignKey(to='referral.Task'),
        ),
        migrations.AddField(
            model_name='bookmark',
            name='referral',
            field=models.ForeignKey(to='referral.Referral'),
        ),
        migrations.AddField(
            model_name='bookmark',
            name='user',
            field=models.ForeignKey(related_name='referral_user_bookmark', to=settings.AUTH_USER_MODEL),
        ),
    ]

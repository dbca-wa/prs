# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import autoslug.fields
import django.utils.timezone
from django.conf import settings
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('referral', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ConditionCategory',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', models.DateTimeField(default=django.utils.timezone.now, editable=False)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('effective_to', models.DateTimeField(null=True, blank=True)),
                ('name', models.CharField(max_length=200)),
                ('description', models.CharField(blank=True, max_length=200, null=True, validators=[django.core.validators.MaxLengthValidator(200)])),
                ('slug', autoslug.fields.AutoSlugField(editable=False, populate_from='name', help_text='Must be unique. Automatically generated from name.', unique=True)),
                ('public', models.BooleanField(default=True, help_text='Is this lookup selection available to all users?')),
                ('creator', models.ForeignKey(related_name='referral_conditioncategory_created', editable=False, to=settings.AUTH_USER_MODEL)),
                ('modifier', models.ForeignKey(related_name='referral_conditioncategory_modified', editable=False, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['name'],
                'abstract': False,
                'verbose_name_plural': 'condition categories',
            },
        ),
        migrations.AlterModelOptions(
            name='agency',
            options={'ordering': ['name'], 'verbose_name_plural': 'agencies'},
        ),
        migrations.AlterModelOptions(
            name='doptrigger',
            options={'ordering': ['name'], 'verbose_name': 'DoP trigger'},
        ),
        migrations.AddField(
            model_name='condition',
            name='category',
            field=models.ForeignKey(blank=True, to='referral.ConditionCategory', null=True),
        ),
    ]

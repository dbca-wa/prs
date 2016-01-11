# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.utils.timezone
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('referral', '0002_auto_20150819_1116'),
    ]

    operations = [
        migrations.CreateModel(
            name='ModelCondition',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', models.DateTimeField(default=django.utils.timezone.now, editable=False)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('effective_to', models.DateTimeField(null=True, blank=True)),
                ('condition', models.TextField()),
                ('category', models.ForeignKey(blank=True, to='referral.ConditionCategory', null=True)),
                ('creator', models.ForeignKey(related_name='referral_modelcondition_created', editable=False, to=settings.AUTH_USER_MODEL)),
                ('modifier', models.ForeignKey(related_name='referral_modelcondition_modified', editable=False, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.AddField(
            model_name='condition',
            name='model_condition',
            field=models.ForeignKey(related_name='model_condition', blank=True, to='referral.ModelCondition', help_text=b'Model text on which this condition is based', null=True),
        ),
    ]

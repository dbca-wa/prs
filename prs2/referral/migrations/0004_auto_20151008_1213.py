# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('referral', '0003_auto_20150916_1135'),
    ]

    operations = [
        migrations.AddField(
            model_name='modelcondition',
            name='identifier',
            field=models.CharField(blank=True, max_length=100, null=True, help_text=b"The decision-making authority's identifying number or code for this condition.", validators=[django.core.validators.MaxLengthValidator(100)]),
        ),
        migrations.AlterField(
            model_name='condition',
            name='condition',
            field=models.TextField(help_text=b'Approved condition', editable=False),
        ),
        migrations.AlterField(
            model_name='modelcondition',
            name='condition',
            field=models.TextField(help_text=b'Model condition'),
        ),
    ]

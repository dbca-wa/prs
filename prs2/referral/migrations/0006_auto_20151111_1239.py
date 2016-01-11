# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('referral', '0005_auto_20151020_1042'),
    ]

    operations = [
        migrations.AlterField(
            model_name='condition',
            name='condition',
            field=models.TextField(help_text='Approved condition', null=True, editable=False, blank=True),
        ),
        migrations.AlterField(
            model_name='condition',
            name='condition_html',
            field=models.TextField(null=True, blank=True),
        ),
    ]

# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import referral.base


class Migration(migrations.Migration):

    dependencies = [
        ('referral', '0004_auto_20151008_1213'),
    ]

    operations = [
        migrations.AlterField(
            model_name='record',
            name='uploaded_file',
            field=referral.base.ContentTypeRestrictedFileField(help_text=b'Allowed file types: TIF,JPG,GIF,PNG,DOC,DOCX,XLS,XLSX,CSV,PDF or ZIP (max 20mb).', max_length=255, null=True, upload_to=b'uploads/%Y/%m/%d', blank=True),
        ),
    ]

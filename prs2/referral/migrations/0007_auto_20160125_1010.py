# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django.core.validators
import taggit.managers


class Migration(migrations.Migration):

    dependencies = [
        ('referral', '0006_auto_20151111_1239'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='bookmark',
            options={'ordering': ['-created']},
        ),
        migrations.AlterModelOptions(
            name='condition',
            options={'ordering': ['-created']},
        ),
        migrations.AlterModelOptions(
            name='location',
            options={'ordering': ['-created']},
        ),
        migrations.AlterModelOptions(
            name='modelcondition',
            options={'ordering': ['-created']},
        ),
        migrations.AlterModelOptions(
            name='note',
            options={'ordering': ['order_date']},
        ),
        migrations.AlterModelOptions(
            name='record',
            options={'ordering': ['-created']},
        ),
        migrations.AlterModelOptions(
            name='referral',
            options={'ordering': ['-created']},
        ),
        migrations.AlterModelOptions(
            name='task',
            options={'ordering': ['-pk', 'due_date']},
        ),
        migrations.AlterField(
            model_name='condition',
            name='condition',
            field=models.TextField(null=True, editable=False, blank=True),
        ),
        migrations.AlterField(
            model_name='condition',
            name='condition_html',
            field=models.TextField(help_text="Insert words exactly as in the decision-maker's letter\n        of approval, and add any advice notes relating to DPaW.", null=True, verbose_name='approved condition', blank=True),
        ),
        migrations.AlterField(
            model_name='condition',
            name='proposed_condition_html',
            field=models.TextField(help_text='Condition text proposed by DPaW.', null=True, verbose_name='proposed condition', blank=True),
        ),
        migrations.AlterField(
            model_name='note',
            name='note_html',
            field=models.TextField(verbose_name='note'),
        ),
        migrations.AlterField(
            model_name='note',
            name='order_date',
            field=models.DateField(help_text='Optional date (for sorting purposes).', null=True, verbose_name='date', blank=True),
        ),
        migrations.AlterField(
            model_name='record',
            name='description',
            field=models.TextField(null=True, blank=True),
        ),
        migrations.AlterField(
            model_name='record',
            name='infobase_id',
            field=models.SlugField(blank=True, help_text='Infobase object ID (optional).', null=True, verbose_name='Infobase ID'),
        ),
        migrations.AlterField(
            model_name='record',
            name='order_date',
            field=models.DateField(help_text='Optional date (for sorting purposes).', null=True, verbose_name='date', blank=True),
        ),
        migrations.AlterField(
            model_name='record',
            name='uploaded_file',
            field=models.FileField(help_text='Allowed file types: TIF,JPG,GIF,PNG,DOC,DOCX,XLS,XLSX,CSV,PDF,TXT,ZIP,MSG,QGS', max_length=255, null=True, upload_to='uploads/%Y/%m/%d', blank=True),
        ),
        migrations.AlterField(
            model_name='referral',
            name='file_no',
            field=models.CharField(blank=True, max_length=100, null=True, help_text='[Searchable] The DPaW file this referral is filed within. Maximum 100 characters.', validators=[django.core.validators.MaxLengthValidator(100)]),
        ),
        migrations.AlterField(
            model_name='referral',
            name='tags',
            field=taggit.managers.TaggableManager(to='taggit.Tag', through='taggit.TaggedItem', blank=True, help_text='[Searchable] A list of issues or tags.', verbose_name='Issues/tags'),
        ),
        migrations.AlterField(
            model_name='task',
            name='complete_date',
            field=models.DateField(help_text='Date that the task was completed.', null=True, verbose_name='completed date', blank=True),
        ),
        migrations.AlterField(
            model_name='task',
            name='description',
            field=models.TextField(help_text='Description of the task requirements.', null=True, blank=True),
        ),
        migrations.AlterField(
            model_name='task',
            name='state',
            field=models.ForeignKey(verbose_name='status', to='referral.TaskState', help_text='The status of the task.'),
        ),
    ]

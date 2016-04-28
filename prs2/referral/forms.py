from datetime import datetime

# Django imports
from django import forms
from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.urlresolvers import reverse
from django.db.models import Q

# Other app imports
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, HTML, Div
from crispy_forms.bootstrap import PrependedText
from taggit.models import Tag

# PRS app imports
from referral.models import (
    Region, Task, Referral, Condition, Note, Record, Location,
    Bookmark, TaskState, Organisation, TaskType, DopTrigger,
    ReferralType, ConditionCategory, ModelCondition)


class OrganisationChoiceField(forms.ModelChoiceField):
    '''
    ModelChoiceField that renders using each Organisation's list_name.
    '''

    def __init__(self, *args, **kwargs):
        qs = Organisation.objects.current().filter(public=True)
        kwargs['queryset'] = qs.order_by('list_name')
        kwargs['help_text'] = 'The referring organisation or individual.'
        kwargs['label'] = 'Referrer'
        super(OrganisationChoiceField, self).__init__(*args, **kwargs)

    def label_from_instance(self, obj):
        return obj.list_name


class RecordChoiceField(forms.ModelMultipleChoiceField):

    def __init__(self, *args, **kwargs):
        kwargs['queryset'] = Record.objects.none()
        super(RecordChoiceField, self).__init__(*args, **kwargs)

    def label_from_instance(self, obj):
        if obj.infobase_id:
            label = '{0} ({1})'.format(obj.name, obj.infobase_id)
        elif obj.uploaded_file:
            label = '{0} ({1}, {2})'.format(obj.name, obj.extension, obj.filesize_str)
        else:
            label = '{0}'.format(obj.name)

        return label


class RegionMultipleChoiceField(forms.ModelMultipleChoiceField):

    def __init__(self, *args, **kwargs):
        kwargs['queryset'] = Region.objects.current()
        kwargs['label'] = 'Region(s)'
        kwargs['widget'] = forms.SelectMultiple(
            attrs={'data-placeholder': 'Select region(s)...'})
        super(RegionMultipleChoiceField, self).__init__(*args, **kwargs)


class DopTriggerMultipleChoiceField(forms.ModelMultipleChoiceField):

    def __init__(self, *args, **kwargs):
        qs = DopTrigger.objects.current().order_by('name')
        kwargs['queryset'] = qs
        kwargs['label'] = 'DoP trigger(s)'
        kwargs['widget'] = forms.SelectMultiple(
            attrs={'data-placeholder': 'Select trigger(s)...'})
        super(DopTriggerMultipleChoiceField, self).__init__(*args, **kwargs)


class TaskTypeChoiceField(forms.ModelChoiceField):

    def __init__(self, *args, **kwargs):
        kwargs['label'] = 'Task type'
        kwargs['queryset'] = TaskType.objects.current().filter(public=True)
        super(TaskTypeChoiceField, self).__init__(*args, **kwargs)


class PRSUserChoiceField(forms.ModelChoiceField):
    """Returns a ModelChoiceField of all current users in the PRS user group.
    """

    def __init__(self, *args, **kwargs):
        users = User.objects.filter(groups__name__in=['PRS user'], is_active=True)
        kwargs['queryset'] = users.order_by('username')
        super(PRSUserChoiceField, self).__init__(*args, **kwargs)

    def label_from_instance(self, obj):
        if obj.get_full_name():
            return obj.get_full_name()
        else:
            return obj.username


class PRSUserMultipleChoiceField(forms.ModelMultipleChoiceField):
    """Returns a ModelMultipleChoiceField of all current users in the PRS user group.
    """

    def __init__(self, *args, **kwargs):
        users = User.objects.filter(
            groups__name__in=['PRS user', 'PRS power user'], is_active=True)
        kwargs['queryset'] = users.order_by('username')
        super(PRSUserMultipleChoiceField, self).__init__(*args, **kwargs)

    def label_from_instance(self, obj):
        if obj.get_full_name():
            return obj.get_full_name()
        else:
            return obj.username


class TaskOutcomeField(forms.ModelChoiceField):

    def __init__(self, task_type, *args, **kwargs):
        kwargs['label'] = 'Task outcome'
        state_qs = TaskState.objects.current()
        state_qs = state_qs.filter(
            Q(is_assessment=True),
            Q(task_type=task_type) | Q(task_type=None)
        )
        state_qs = state_qs.order_by('name')
        kwargs['queryset'] = state_qs
        kwargs['help_text'] = 'The final outcome for this task.'
        super(TaskOutcomeField, self).__init__(*args, **kwargs)


class BaseFormHelper(FormHelper):
    """Base FormHelper class, with common options set.
    """

    def __init__(self, *args, **kwargs):
        super(BaseFormHelper, self).__init__(*args, **kwargs)
        self.form_class = 'form-horizontal'
        self.form_method = 'POST'
        self.label_class = 'col-xs-12 col-sm-4 col-md-3 col-lg-2'
        self.field_class = 'col-xs-12 col-sm-8 col-md-6 col-lg-4'
        self.help_text_inline = True


class BaseForm(forms.ModelForm):
    """Base ModelForm class for referral models.
    """
    save_button = Submit('save', 'Save', css_class='btn-lg')
    cancel_button = Submit('cancel', 'Cancel')

    def __init__(self, *args, **kwargs):
        self.helper = BaseFormHelper()
        super(BaseForm, self).__init__(*args, **kwargs)

    class Meta:
        exclude = ['created', 'modified', 'creator', 'modifier', 'effective_to']


class ReferralForm(BaseForm):
    """Base form class, extended by the ReferralCreate and ReferralUpdate forms.
    """
    referring_org = OrganisationChoiceField()
    region = RegionMultipleChoiceField(
        help_text='''[Searchable] The region(s) in which this referral belongs.
        Hold control to select multiple options.''')
    dop_triggers = DopTriggerMultipleChoiceField(
        required=False,
        help_text='''[Searchable] The DoP trigger(s) for this referral.
        Hold control to select multiple options.''')
    referral_date = forms.DateField(
        widget=forms.DateInput(format='%d/%m/%Y'),
        input_formats=settings.DATE_INPUT_FORMATS)

    def __init__(self, *args, **kwargs):
        super(ReferralForm, self).__init__(*args, **kwargs)
        self.fields['type'].queryset = ReferralType.objects.current()
        self.fields['reference'].label = 'Referrers reference'
        self.fields['file_no'].label = 'File no.'

    class Meta(BaseForm.Meta):
        model = Referral
        exclude = BaseForm.Meta.exclude + ['point']

    def clean(self):
        """Validate the "referral type" and "DoP trigger" fields; if the
        referral type is "Subdivision" or "Development application" then at
        least one DoP trigger must be input.
        For other referral types, the Dop trigger field can be left blank.
        """
        if not self.cleaned_data['dop_triggers'] and self.cleaned_data.get('type', None):
            t = self.cleaned_data['type']
            if t.slug == 'development-application' or t.slug == 'subdivision':
                msg = '''Subdivision/development application: you must choose
                    applicable DoP triggers for this referral type.'''
                self._errors['dop_triggers'] = self.error_class([msg])
        return self.cleaned_data


class ReferralCreateForm(ReferralForm):
    due_date = forms.DateField(
        required=False,
        help_text='''Optional. Date that the referral must be actioned by (
            system will set a due date of 42 days if no date is chosen).''',
        widget=forms.DateInput(format='%d/%m/%Y'),
        input_formats=settings.DATE_INPUT_FORMATS)
    task_type = TaskTypeChoiceField()
    assigned_user = PRSUserChoiceField(
        help_text='''The user to which to assign the initial task. '''
        '''To become a PRS user, please email the PRS application '''
        '''owner(s): {}.'''.format(', '.join([i[0] for i in settings.MANAGERS])))
    email_user = forms.BooleanField(
        label='Email user',
        required=False,
        help_text='Email the assigned user a notification about this referral.')

    def __init__(self, *args, **kwargs):
        super(ReferralCreateForm, self).__init__(*args, **kwargs)
        self.fields['referring_org'].help_text = '''The referring organisation
            or individual. Fill in the Referrer first. <a href="{}">Click here
            </a> to create a new referrer (you will be taken to a new screen
            and any data already input will be lost).'''.format(
            reverse('prs_object_create', kwargs={'model': 'organisation'}))
        self.fields['description'].required = True
        self.fields['description'].help_text = '''[Searchable] Insert the name
            given by the referrer and distingushing details. Other key info may
            be added.'''
        self.fields['address'].help_text = '''[Searchable] Insert physical
            address of the proposal.'''
        self.fields['type'].label = '''<a class="btn btn-info"
            data-toggle="modal" data-target="#refTypeModal">
            <span class="glyphicon glyphicon-info-sign"></span>
            Referral type</a>'''
        self.fields['task_type'].help_text = '''Select a task from the list.
            Normally, the default task 'Assess a referral' is appropriate.
            Please note that to enter a clearance request, a referral will first
            need to be entered in PRS with a task from this list assigned. Then
            the task 'Add a clearance request' can be added via the options menu
            on the referral detail page.'''
        # Define the form layout.
        self.helper.layout = Layout(
            'referring_org', 'reference', 'description', 'address',
            'referral_date', 'due_date', 'type', 'task_type', 'assigned_user',
            # Hack to make crispy_forms output proper HTML for Bootstrap 3:
            PrependedText('email_user', ''),
            'region', 'dop_triggers', 'file_no',
            Div(
                self.save_button,
                self.cancel_button,
                Submit('saveaddlocation', 'Save and add a location'),
                css_class='col-sm-offset-4 col-md-offset-3 col-lg-offset-2')
        )


class ReferralUpdateForm(ReferralForm):

    def __init__(self, *args, **kwargs):
        super(ReferralUpdateForm, self).__init__(*args, **kwargs)
        # Define the form layout.
        self.helper.layout = Layout(
            'referring_org', 'reference', 'description', 'address',
            'referral_date', 'type', 'region', 'dop_triggers',
            'file_no',
            Div(
                self.save_button, self.cancel_button,
                css_class='col-sm-offset-4 col-md-offset-3 col-lg-offset-2')
        )


class OrganisationForm(BaseForm):

    def __init__(self, *args, **kwargs):
        super(OrganisationForm, self).__init__(*args, **kwargs)
        self.fields['name'].help_text = 'The name of the referrer.'
        # Define the form layout.
        layout = Layout(
            'name', 'description', 'type', 'list_name', 'telephone', 'fax',
            'email', 'address1', 'address2', 'suburb', 'state', 'postcode',
            Div(
                self.save_button, self.cancel_button,
                css_class='col-sm-offset-4 col-md-offset-3 col-lg-offset-2')
        )
        self.helper.add_layout(layout)

    class Meta:
        model = Organisation
        exclude = BaseForm.Meta.exclude + ['slug', 'public']

    def clean(self):
        '''Validate the name field; cannot have any (new) duplicates.
        '''
        cleaned_data = super(OrganisationForm, self).clean()
        if not self.instance.pk and 'name' in cleaned_data:  # Adding/changing the name
            if Organisation.objects.current().filter(name=cleaned_data['name']).exists():
                raise ValidationError({'name': 'An organisation with that name already exists!'})


class NoteForm(BaseForm):
    """Basic form layout for creating/updating notes.
    """

    def __init__(self, *args, **kwargs):
        super(NoteForm, self).__init__(*args, **kwargs)
        self.fields['order_date'].initial = datetime.today().strftime('%d/%m/%Y')
        self.fields['order_date'].widget = forms.DateInput(format='%d/%m/%Y')
        self.fields['order_date'].input_formats = settings.DATE_INPUT_FORMATS
        # Define the form layout.
        layout = Layout(
            'note_html', 'type', 'order_date',
            Div(
                self.save_button, self.cancel_button,
                css_class='col-sm-offset-4 col-md-offset-3 col-lg-offset-2')
        )
        self.helper.add_layout(layout)

    class Meta:
        model = Note
        exclude = BaseForm.Meta.exclude + ['referral']


class NoteAddExistingForm(BaseForm):
    """Form for associating existing note(s) to a task
    """
    notes = forms.ModelMultipleChoiceField(queryset=None)

    def __init__(self, referral, *args, **kwargs):
        super(NoteAddExistingForm, self).__init__(*args, **kwargs)
        self.fields['notes'].queryset = Note.objects.current().filter(referral=referral)
        self.helper = BaseFormHelper()
        layout = Layout(
            'notes',
            Div(
                self.save_button, self.cancel_button,
                css_class='col-sm-offset-4 col-md-offset-3 col-lg-offset-2')
        )
        self.helper.add_layout(layout)

    class Meta:
        model = Note
        fields = ['notes']


class RecordForm(BaseForm):
    '''
    * Name
    * File upload field
    * Infobase ID
    * Description
    * Date
    * Save/Cancel buttons
    '''

    def __init__(self, *args, **kwargs):
        super(RecordForm, self).__init__(*args, **kwargs)
        self.fields['order_date'].widget = forms.DateInput(format='%d/%m/%Y')
        self.fields['order_date'].input_formats = settings.DATE_INPUT_FORMATS
        self.fields['uploaded_file'].max_length = 220  # Allow 35 characters for the filepath
        layout = Layout(
            'name', 'uploaded_file', 'infobase_id', 'description', 'order_date',
            Div(
                self.save_button, self.cancel_button,
                css_class='col-sm-offset-4 col-md-offset-3 col-lg-offset-2')
        )
        self.helper.add_layout(layout)

    class Meta:
        model = Record
        exclude = BaseForm.Meta.exclude + ['referral']

    def clean(self):
        cleaned_data = super(RecordForm, self).clean()
        u = cleaned_data.get('uploaded_file')
        if u and hasattr(u, 'content_type') and u.content_type not in settings.ALLOWED_UPLOAD_TYPES:
            self._errors['uploaded_file'] = self.error_class(['File type is not permitted.'])
        return cleaned_data


class RecordCreateForm(RecordForm):
    '''
    * Name
    * File upload field
    * Infobase ID
    * Description
    * Date
    * Save, Save & Another, Cancel buttons
    '''

    def __init__(self, *args, **kwargs):
        super(RecordCreateForm, self).__init__(*args, **kwargs)
        self.fields['order_date'].initial = datetime.today().strftime('%d/%m/%Y')
        self.fields['infobase_id'].help_text = '''To link to an Infobase record,
            enter the Infobase object ID exactly as it appears in Infobase (i.e.
            case-sensitive, no spaces). E.g.: eA498596'''
        # Add in a "Save and add another" button.
        save_another_button = Submit('save-another', 'Save and add another')
        save_another_button.field_classes = ' btn btn-default'
        layout = Layout(
            'name', 'uploaded_file', 'infobase_id', 'description', 'order_date',
            Div(
                self.save_button, save_another_button, self.cancel_button,
                css_class='col-sm-offset-4 col-md-offset-3 col-lg-offset-2')
        )
        self.helper.add_layout(layout)

    def clean(self):
        '''
        Custom validation: User must choose upload file or input infobase id.
        One or both MUST be present.
        '''
        cleaned_data = super(RecordCreateForm, self).clean()
        uploaded_file = cleaned_data.get('uploaded_file')
        infobase_id = cleaned_data.get('infobase_id')
        msg = 'Please choose a file to upload AND/OR input an Infobase ID.'
        if not uploaded_file and not infobase_id:
            self._errors['uploaded_file'] = self.error_class([msg])
            self._errors['infobase_id'] = self.error_class([msg])
        return cleaned_data

    class Meta:
        model = Record
        exclude = BaseForm.Meta.exclude + ['referral', 'notes']


class RecordAddExistingForm(BaseForm):
    '''
    Form for associating existing record(s) to a task
    '''
    records = forms.ModelMultipleChoiceField(queryset=None)

    def __init__(self, referral, *args, **kwargs):
        super(RecordAddExistingForm, self).__init__(*args, **kwargs)
        self.fields['records'].queryset = Record.objects.current().filter(referral=referral)
        self.helper = BaseFormHelper()
        layout = Layout(
            'records',
            Div(
                self.save_button, self.cancel_button,
                css_class='col-sm-offset-4 col-md-offset-3 col-lg-offset-2')
        )
        self.helper.add_layout(layout)

    class Meta:
        model = Record
        fields = ['records']


class TaskCompleteForm(BaseForm):
    '''
    * Task outcome
    * Completed date
    * Description
    * Tags
    '''
    tags = forms.CharField(
        required=False,
        help_text='''Select all tags relevant to the advice supplied (required
        for response with advice / condition / objection).''')

    def __init__(self, *args, **kwargs):
        super(TaskCompleteForm, self).__init__(*args, **kwargs)
        self.fields['state'] = TaskOutcomeField(task_type=self.instance.type)
        self.fields['complete_date'].input_formats = settings.DATE_INPUT_FORMATS
        self.fields['complete_date'].required = True
        self.fields['complete_date'].help_text += ''' Usually the date that the
            Region mailed or emailed advice. If the task has just been stopped
            by the referrer/proponent, do not use this screen. Go back to the
            'Referral details' and select the red 'Stop' icon for this task
            instead.'''
        self.fields['description'].help_text = '''To comment on the completion
            stage of the task, ADD details to this description.'''
        layout = Layout(
            'state', 'complete_date', 'description', 'tags',
            Div(
                self.save_button, self.cancel_button,
                css_class='col-sm-offset-4 col-md-offset-3 col-lg-offset-2')
        )
        self.helper.add_layout(layout)

    class Meta:
        model = Task
        exclude = BaseForm.Meta.exclude + [
            'type', 'referral', 'assigned_user', 'start_date', 'due_date',
            'stop_date', 'restart_date']


class TaskStopForm(BaseForm):
    '''
    * Stop date
    * Description
    * Save/Cancel buttons

    NOTE: we instantiate a "stopped_date" field (instead of using the model
    field) to avoid interference by existing values in stop_date.
    '''
    stopped_date = forms.DateField(
        initial=datetime.today().strftime('%d/%m/%Y'), required=True,
        input_formats=settings.DATE_INPUT_FORMATS,
        help_text='Date on which this task was stopped.')

    def __init__(self, *args, **kwargs):
        super(TaskStopForm, self).__init__(*args, **kwargs)
        self.fields['description'].required = True
        self.fields['description'].help_text = '''Please describe why the
            task was stopped.'''
        layout = Layout(
            'stopped_date', 'description',
            Div(
                self.save_button, self.cancel_button,
                css_class='col-sm-offset-4 col-md-offset-3 col-lg-offset-2')
        )
        self.helper.add_layout(layout)

    class Meta:
        model = Task
        exclude = BaseForm.Meta.exclude + [
            'type', 'referral', 'assigned_user', 'start_date', 'due_date',
            'complete_date', 'restart_date', 'state']


class TaskStartForm(BaseForm):
    '''
    * Due date
    * Date of task restart
    * Description
    * Save/Cancel buttons
    '''

    def __init__(self, *args, **kwargs):
        super(TaskStartForm, self).__init__(*args, **kwargs)
        self.fields['due_date'].widget = forms.DateInput(format='%d/%m/%Y')
        self.fields['due_date'].input_formats = settings.DATE_INPUT_FORMATS
        self.fields['due_date'].required = True
        self.fields['due_date'].label = 'Revised due date'
        self.fields['restart_date'].required = True
        self.fields['restart_date'].input_formats = settings.DATE_INPUT_FORMATS
        self.fields['description'].help_text += ''' ADD to the description a
            brief explanation for restarting the task.'''
        layout = Layout(
            'due_date', 'restart_date', 'description',
            Div(
                self.save_button, self.cancel_button,
                css_class='col-sm-offset-4 col-md-offset-3 col-lg-offset-2')
        )
        self.helper.add_layout(layout)

    class Meta:
        model = Task
        exclude = BaseForm.Meta.exclude + [
            'type', 'referral', 'assigned_user', 'start_date', 'complete_date',
            'stop_date', 'state']


class TaskReassignForm(BaseForm):
    '''
    * Assigned user
    * Due date
    * Description
    * "Email user" checkbox
    * Save/Cancel buttons
    '''
    email_user = forms.BooleanField(
        required=False,
        help_text='Email the assigned user a notification about this task.')

    def __init__(self, *args, **kwargs):
        super(TaskReassignForm, self).__init__(*args, **kwargs)
        self.fields['assigned_user'] = PRSUserChoiceField()
        self.fields['due_date'].widget = forms.DateInput(format='%d/%m/%Y')
        self.fields['due_date'].input_formats = settings.DATE_INPUT_FORMATS
        self.fields['due_date'].required = True
        layout = Layout(
            'assigned_user', 'due_date', 'description',
            PrependedText('email_user', ''),
            Div(
                self.save_button, self.cancel_button,
                css_class='col-sm-offset-4 col-md-offset-3 col-lg-offset-2')
        )
        self.helper.add_layout(layout)

    class Meta:
        model = Task
        exclude = BaseForm.Meta.exclude + [
            'type', 'referral', 'start_date', 'complete_date', 'stop_date',
            'restart_date', 'state']


class TaskCancelForm(BaseForm):
    '''
    * Description
    * Save/Cancel buttons
    '''

    def __init__(self, *args, **kwargs):
        super(TaskCancelForm, self).__init__(*args, **kwargs)
        self.fields['description'].help_text = '''Please record why the task
            was cancelled (optional).'''
        layout = Layout(
            'description',
            Div(
                self.save_button, self.cancel_button,
                css_class='col-sm-offset-4 col-md-offset-3 col-lg-offset-2')
        )
        self.helper.add_layout(layout)

    class Meta:
        model = Task
        exclude = BaseForm.Meta.exclude + [
            'type', 'referral', 'start_date', 'complete_date', 'state',
            'assigned_user', 'due_date', 'stop_date', 'restart_date']


class TaskForm(BaseForm):
    '''
    * Assigned user
    * Task state
    * Start date
    * Due date
    * Completion date
    * Description
    * Stop date
    * Restart date
    * Save/Cancel buttons
    '''

    def __init__(self, *args, **kwargs):
        super(TaskForm, self).__init__(*args, **kwargs)
        self.fields['assigned_user'] = PRSUserChoiceField()
        self.fields['type'].queryset = TaskType.objects.current()
        self.fields['start_date'].required = True
        self.fields['start_date'].help_text = '''The date on which the Department
            received the request to do this task.'''
        self.fields['start_date'].widget = forms.DateInput(format='%d/%m/%Y')
        self.fields['start_date'].input_formats = settings.DATE_INPUT_FORMATS
        self.fields['due_date'].required = True
        self.fields['due_date'].widget = forms.DateInput(format='%d/%m/%Y')
        self.fields['due_date'].input_formats = settings.DATE_INPUT_FORMATS
        self.fields['complete_date'].widget = forms.DateInput(format='%d/%m/%Y')
        self.fields['complete_date'].input_formats = settings.DATE_INPUT_FORMATS
        self.fields['stop_date'].widget = forms.DateInput(format='%d/%m/%Y')
        self.fields['stop_date'].input_formats = settings.DATE_INPUT_FORMATS
        self.fields['restart_date'].widget = forms.DateInput(format='%d/%m/%Y')
        self.fields['restart_date'].input_formats = settings.DATE_INPUT_FORMATS
        self.fields['state'].queryset = TaskState.objects.current().filter(
            Q(task_type=self.instance.type) |
            Q(task_type=None)
        )

        layout = Layout(
            'assigned_user', 'type', 'state', 'start_date', 'due_date',
            'complete_date', 'stop_date', 'restart_date', 'description',
            Div(
                self.save_button, self.cancel_button,
                css_class='col-sm-offset-4 col-md-offset-3 col-lg-offset-2')
        )
        self.helper.add_layout(layout)

    def clean(self):
        """Validate the complete_date field; cannot have a complete_date and a stop_date.
        Edge case only: users shouldn't be able to edit a stopped task.
        """
        d = self.cleaned_data
        if 'complete_date' in d and d['complete_date']:
            # Can't have a complete date and a stop date.
            if 'stop_date' in d and d['stop_date']:
                msg = 'You cannot save the task with both a completed date AND a stop date!'
                self._errors['complete_date'] = self.error_class([msg])
                self._errors['stop_date'] = self.error_class([msg])
            # Start date can't be later than complete date.
            if 'start_date' in d and d['start_date'] and d['start_date'] > d['complete_date']:
                self._errors['start_date'] = self.error_class(['Cannot be after complete date!'])
                self._errors['complete_date'] = self.error_class(['Cannot be before start date!'])
            # Can't record a complete date and leave the task state "In progress".
            if 'state' in d and d['state'].is_ongoing:
                self._errors['complete_date'] = self.error_class(
                    ['Cannot record a complete date for an ongoing task!'])
                self._errors['state'] = self.error_class(
                    ['Cannot record a complete date for an ongoing task!'])

        return self.cleaned_data

    class Meta:
        model = Task
        exclude = BaseForm.Meta.exclude + ['referral']


class TaskInheritForm(BaseForm):
    '''
    * Description
    * Save/Cancel buttons
    '''

    def __init__(self, *args, **kwargs):
        super(TaskInheritForm, self).__init__(*args, **kwargs)
        layout = Layout('description')
        layout = Layout(
            'description',
            Div(
                self.save_button, self.cancel_button,
                css_class='col-sm-offset-4 col-md-offset-3 col-lg-offset-2')
        )
        self.helper.add_layout(layout)

    class Meta:
        model = Task
        exclude = BaseForm.Meta.exclude + [
            'type', 'referral', 'start_date', 'complete_date', 'state',
            'assigned_user', 'due_date', 'stop_date', 'restart_date']


class TaskCreateForm(BaseForm):
    '''
    * Assigned officer
    * Task type
    * Start date
    * Due date (optional, because we handle this in the view)
    * Description
    * "Email user" checkbox
    * Save/Cancel buttons
    '''
    email_user = forms.BooleanField(
        required=False,
        help_text='Email the assigned user a notification about this referral.')

    def __init__(self, *args, **kwargs):
        super(TaskCreateForm, self).__init__(*args, **kwargs)
        self.fields['assigned_user'] = PRSUserChoiceField()
        self.fields['start_date'].required = True
        self.fields['start_date'].input_formats = settings.DATE_INPUT_FORMATS
        self.fields['due_date'].required = True
        self.fields['due_date'].input_formats = settings.DATE_INPUT_FORMATS
        self.fields['type'].queryset = TaskType.objects.current().filter(public=True)
        self.fields['type'].help_text = '''Please note that "Information only"
            and "Provide pre-referral/preliminary advice" tasks will be
            auto-completed if no due date is recorded.'''
        self.fields['description'].required = True
        layout = Layout(
            'assigned_user', 'type', 'start_date', 'due_date', 'description',
            PrependedText('email_user', ''),
            Div(
                self.save_button, self.cancel_button,
                css_class='col-sm-offset-4 col-md-offset-3 col-lg-offset-2')
        )
        self.helper.add_layout(layout)

    class Meta:
        model = Task
        exclude = BaseForm.Meta.exclude + [
            'state', 'referral', 'complete_date', 'stop_date', 'restart_date']


class LocationForm(BaseForm):

    def __init__(self, *args, **kwargs):
        super(LocationForm, self).__init__(*args, **kwargs)
        layout = Layout(
            'address_no', 'address_suffix', 'road_name', 'road_suffix',
            'locality', 'postcode', 'lot_no',
            Div(
                self.save_button, self.cancel_button,
                css_class='col-sm-offset-4 col-md-offset-3 col-lg-offset-2')
        )
        self.helper.add_layout(layout)

    class Meta:
        model = Location
        exclude = BaseForm.Meta.exclude + [
            'landuse', 'lot_desc', 'strata_lot_no', 'strata_lot_desc',
            'reserve', 'cadastre_obj_id', 'referral', 'poly', 'address_string']


class ConditionForm(BaseForm):
    '''
    * Proposed condition
    * Approved condition
    * Condition number
    * Save/Cancel buttons
    '''

    def __init__(self, *args, **kwargs):
        super(ConditionForm, self).__init__(*args, **kwargs)
        self.fields['category'].queryset = ConditionCategory.objects.current()
        self.fields['identifier'].label = 'Condition no.'
        layout = Layout(
            'proposed_condition_html', 'condition_html', 'identifier',
            Div(
                self.save_button, self.cancel_button,
                css_class='col-sm-offset-4 col-md-offset-3 col-lg-offset-2')
        )
        self.helper.add_layout(layout)

    class Meta:
        model = Condition
        exclude = BaseForm.Meta.exclude + ['referral', 'tags']


class ModelConditionChoiceField(forms.ModelChoiceField):
    '''Select widget for model conditions with custom queryset and labels.
    '''

    def __init__(self, *args, **kwargs):
        kwargs['queryset'] = ModelCondition.objects.current().order_by('identifier')
        super(ModelConditionChoiceField, self).__init__(*args, **kwargs)

    def label_from_instance(self, obj):
        return '{} {}'.format(obj.identifier, obj.condition)


class ConditionCreateForm(ConditionForm):
    '''
    * Condition proposed by DPaW (optional)
    * Approved Condition text
    * Identifier/number
    * Save, Cancel, Save and add another buttons
    '''
    model_condition = ModelConditionChoiceField(
        required=False,
        help_text='''To enter a condition based on a model condition, click on
        the relevant condition in the select list. This will appear in the next
        field where it may be edited as required.''')

    def __init__(self, *args, **kwargs):
        super(ConditionCreateForm, self).__init__(*args, **kwargs)
        help_html = HTML('''<p>Add a subdivision or development condition that
            requires a clearance. Add additional conditions separately by
            clicking <strong>Save and add another</strong>.</p>''')
        # Add in a "Save and add another" button.
        save_another_button = Submit('save-another', 'Save and add another')
        save_another_button.field_classes = 'btn btn-default'
        layout = Layout(
            help_html, 'model_condition', 'proposed_condition_html',
            'condition_html', 'identifier',
            Div(
                self.save_button, self.cancel_button, save_another_button,
                css_class='col-sm-offset-4 col-md-offset-3 col-lg-offset-2')
        )
        self.helper.add_layout(layout)


class TaskClearanceCreateForm(BaseForm):
    '''
    Form to create a|several clearance request task(s).

    * Condition(s) checkboxes
    * Assigned user
    * Deposited plan no.
    * Due date
    * Description
    * "Email user" checkbox
    * Save/Cancel buttons
    '''
    conditions = forms.MultipleChoiceField(
        choices=[], required=True,
        help_text='Hold control to select more than one condition.')
    deposited_plan = forms.CharField(
        required=False,
        help_text='Optional. The deposited plan attached to the clearance request.')
    email_user = forms.BooleanField(
        required=False,
        help_text='Email the assigned user a notification about this task.')
    start_date = forms.DateField(
        initial=datetime.today().strftime('%d/%m/%Y'), required=True,
        input_formats=settings.DATE_INPUT_FORMATS,
        help_text='Date on which this clearance request was received.')
    due_date = forms.DateField(
        input_formats=settings.DATE_INPUT_FORMATS, required=False,
        help_text='''Optional date by which the clearance(s) are required.
            Will default to 45 days from today if no date is specifed.''')

    def __init__(self, condition_choices, *args, **kwargs):
        super(TaskClearanceCreateForm, self).__init__(*args, **kwargs)
        self.fields['conditions'].choices = condition_choices
        self.fields['assigned_user'] = PRSUserChoiceField()
        self.fields['assigned_user'].help_text = 'User to which to assign the clearance task(s).'
        self.fields['description'].required = True
        self.fields['description'].help_text = '''Please describe the
            requirements to provide clearance (max 200 characters). Include the
            stage number, all condition numbers applicable to this clearance
            request and any other useful information.'''
        layout = Layout(
            'conditions', 'assigned_user', 'deposited_plan', 'start_date',
            'due_date', 'description',
            PrependedText('email_user', ''),
            Div(
                self.save_button, self.cancel_button,
                css_class='col-sm-offset-4 col-md-offset-3 col-lg-offset-2')
        )
        self.helper.add_layout(layout)

    class Meta:
        model = Task
        exclude = BaseForm.Meta.exclude + [
            'referral', 'type', 'complete_date', 'stop_date', 'state']


class ClearanceCreateForm(BaseForm):
    '''
    Form to create a clearance requests on a single condition.

    * Assigned user
    * Deposited plan no.
    * Due date
    * Description
    * "Email user" checkbox
    * Save/Cancel buttons
    '''
    deposited_plan = forms.CharField(
        required=False,
        help_text='Optional. The deposited plan attached to the clearance request.')
    email_user = forms.BooleanField(
        required=False,
        help_text='Email the assigned user a notification about this referral.')
    start_date = forms.DateField(
        initial=datetime.today().strftime('%d/%m/%Y'), required=True,
        input_formats=settings.DATE_INPUT_FORMATS,
        help_text='Date on which this clearance request was received.')
    due_date = forms.DateField(
        input_formats=settings.DATE_INPUT_FORMATS, required=False,
        help_text='''Optional date by which the clearance is required.
            Will default to 45 days from today if no date is specifed.''')

    def __init__(self, condition=None, *args, **kwargs):
        super(ClearanceCreateForm, self).__init__(*args, **kwargs)
        cond_text_html = HTML('''
            <div id="div_id_condition_text" class="form-group">
                <label for="id_condition_text" class="control-label col-xs-12 col-sm-4 col-md-3 col-lg-2">Approved condition</label>
                <div class="controls col-xs-12 col-sm-8 col-md-6 col-lg-4"><p>{}</p></div>
            </div>
            <div id="div_id_condition_no" class="form-group">
                <label for="id_condition_no" class="control-label col-xs-12 col-sm-4 col-md-3 col-lg-2">Condition no.</label>
                <div class="controls col-xs-12 col-sm-8 col-md-6 col-lg-4"><p>{}</p></div>
            </div>
            '''.format(condition.condition_html, condition.identifier or '(none)'))
        self.fields['assigned_user'] = PRSUserChoiceField()
        self.fields['assigned_user'].help_text = 'User to which to assign the clearance task.'
        self.fields['description'].help_text = '''Please describe the requirements to provide clearance
            (max 200 characters). Include the stage number, all condition numbers applicable to this
            clearance request and any other useful information.'''
        layout = Layout(
            cond_text_html, 'assigned_user', 'deposited_plan', 'start_date',
            'due_date', 'description',
            # Hack to make crispy_forms output proper HTML for Bootstrap 3:
            PrependedText('email_user', ''),
            Div(
                self.save_button, self.cancel_button,
                css_class='col-sm-offset-4 col-md-offset-3 col-lg-offset-2')
        )
        self.helper.add_layout(layout)

    class Meta:
        model = Task
        exclude = BaseForm.Meta.exclude + [
            'referral', 'type', 'complete_date', 'stop_date', 'state']


class BookmarkForm(BaseForm):
    '''
    * Description
    * Save/Cancel buttons
    '''

    def __init__(self, *args, **kwargs):
        super(BookmarkForm, self).__init__(*args, **kwargs)
        self.fields['description'].required = True
        layout = Layout(
            'description',
            Div(
                self.save_button, self.cancel_button,
                css_class='col-sm-offset-4 col-md-offset-3 col-lg-offset-2')
        )
        self.helper.add_layout(layout)

    class Meta:
        model = Bookmark
        exclude = BaseForm.Meta.exclude + ['referral', 'user']


class ReferralModelMultipleChoiceField(forms.ModelMultipleChoiceField):

    def label_from_instance(self, obj):
        label = '{0} ({1})'.format(obj.id, obj.type.name)
        if obj.address:
            label += ' ' + obj.address
        elif obj.description:
            label += ' ' + obj.description
        return label


class IntersectingReferralForm(BaseForm):
    related_refs = ReferralModelMultipleChoiceField(
        queryset=Referral.objects.none(),
        label='Related referrals',
        help_text='Hold down control to select more than one item from this list.',
        required=False)

    def __init__(self, referral, referrals, *args, **kwargs):
        super(IntersectingReferralForm, self).__init__(*args, **kwargs)
        self.fields['related_refs'].queryset = referrals
        html = HTML('''<p>The new location intersects other locations associated with different referrals.
            Please select any referrals that you want to relate to referral {0} ({1}):</p>'''.format(referral.id, referral.type))
        layout = Layout(
            html, 'related_refs',
            Div(
                self.save_button, self.cancel_button,
                css_class='col-sm-offset-4 col-md-offset-3 col-lg-offset-2')
        )
        self.helper.add_layout(layout)

    class Meta:
        model = Referral
        exclude = BaseForm.Meta.exclude + [
            'type', 'referring_org', 'reference', 'file_no', 'description',
            'referral_date', 'address', 'region', 'tags', 'agency']


class TagReplaceForm(forms.Form):
    old_tag = forms.ModelChoiceField(queryset=Tag.objects.all().order_by('name'))
    replace_with = forms.ModelChoiceField(queryset=Tag.objects.all().order_by('name'))
    save_button = Submit('save', 'Save', css_class='btn-lg')
    cancel_button = Submit('cancel', 'Cancel')

    def __init__(self, *args, **kwargs):
        self.helper = BaseFormHelper()
        # Define the form layout.
        self.helper.layout = Layout(
            'old_tag', 'replace_with',
            Div(
                self.save_button, self.cancel_button,
                css_class='col-sm-offset-4 col-md-offset-3 col-lg-offset-2')
        )
        super(TagReplaceForm, self).__init__(*args, **kwargs)


# The following dictionary contains info about customised forms for editing different model types.
FORMS_MAP = {
    Referral: {'create': ReferralCreateForm, 'update': ReferralUpdateForm},
    Organisation: {'create': OrganisationForm, 'update': OrganisationForm},
    Condition: {'create': ConditionCreateForm, 'update': ConditionForm},
    Note: {
        'create': NoteForm,
        'update': NoteForm,
        'addnewrecord': RecordCreateForm,
        'addrecord': RecordAddExistingForm},
    Record: {
        'create': RecordCreateForm,
        'update': RecordForm,
        'addnote': NoteAddExistingForm,
        'addnewnote': NoteForm},
    Bookmark: {'create': BookmarkForm, 'has_file_field': False},
    Task: {
        'create': TaskCreateForm,
        'stop': TaskStopForm,
        'start': TaskStartForm,
        'reassign': TaskReassignForm,
        'cancel': TaskCancelForm,
        'complete': TaskCompleteForm,
        'addrecord': RecordAddExistingForm,
        'addnewrecord': RecordCreateForm,
        'addnote': NoteAddExistingForm,
        'addnewnote': NoteForm,
        'edit': TaskForm,
        'inherit': TaskInheritForm,
        'clearance': TaskClearanceCreateForm,
        'has_file_field': False
    },
    Location: {'update': LocationForm},
}

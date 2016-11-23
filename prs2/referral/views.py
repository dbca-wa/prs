from __future__ import unicode_literals
from braces.views import LoginRequiredMixin
from copy import copy
from datetime import date, datetime, timedelta
from django.conf import settings
from django.contrib import admin, messages
from django.contrib.auth.models import Group
from django.contrib.gis.geos import GEOSGeometry, MultiPolygon
from django.core.mail import EmailMultiAlternatives
from django.core.serializers import serialize
from django.core.urlresolvers import reverse
from django.db.models import Q
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect
from django.utils.decorators import method_decorator
from django.utils.safestring import mark_safe
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import View, ListView, TemplateView, FormView
from django_downloadview import ObjectDownloadView
import json
import logging
import re
from taggit.models import Tag

from referral.models import (
    Task, Clearance, Referral, Condition, Note, Record, Location,
    Bookmark, RelatedReferral, TaskState, Organisation, TaskType,
    Agency, ReferralType)
from referral.utils import (
    is_model_or_string, breadcrumbs_li, smart_truncate, get_query,
    user_task_history, user_referral_history, filter_queryset,
    prs_user, is_prs_power_user, borgcollector_harvest)
from referral.forms import (
    ReferralCreateForm, NoteForm, NoteAddExistingForm,
    RecordCreateForm, RecordAddExistingForm, TaskCreateForm,
    ConditionCreateForm,
    TaskClearanceCreateForm, ClearanceCreateForm, LocationForm,
    BookmarkForm, ConditionForm, RecordForm, FORMS_MAP,
    TaskForm, TaskCompleteForm, TaskStopForm, TaskStartForm,
    TaskReassignForm, TaskCancelForm, TaskInheritForm,
    IntersectingReferralForm, TagReplaceForm)
from referral.views_base import (
    PrsObjectDetail, PrsObjectList, PrsObjectCreate,
    PrsObjectUpdate, PrsObjectDelete, PrsObjectHistory, PrsObjectTag)

logger = logging.getLogger('prs.log')


class SiteHome(LoginRequiredMixin, ListView):
    """Site home page view. Returns an object list of tasks (ongoing or stopped).
    """
    stopped_tasks = False
    printable = False

    def get_queryset(self):
        qs = Task.objects.current().filter(assigned_user=self.request.user)
        if self.stopped_tasks:
            qs = qs.filter(state__name='Stopped').order_by('stop_date')
        else:
            qs = qs.filter(state__is_ongoing=True)
        return qs

    def get_template_names(self):
        if 'print' in self.request.GET or self.printable:
            return 'site_home_print.html'
        else:
            return'site_home.html'

    def get_context_data(self, **kwargs):
        context = super(SiteHome, self).get_context_data(**kwargs)
        context['stopped_tasks'] = self.stopped_tasks
        context['headers'] = copy(Task.headers_site_home)
        if not self.stopped_tasks:
            context['stopped_tasks_exist'] = Task.objects.current().filter(
                assigned_user=self.request.user, state__name='Stopped').exists()
        # Printable view only: pop the last element from 'headers'
        if 'print' in self.request.GET or self.printable:
            context['headers'].pop()
        context['page_title'] = settings.APPLICATION_ACRONYM
        context['breadcrumb_trail'] = breadcrumbs_li([(None, 'Home')])
        return context


class HelpPage(TemplateView):
    """Help page (static template view).
    """
    template_name = 'help_page.html'

    def get_context_data(self, **kwargs):
        context = super(HelpPage, self).get_context_data(**kwargs)
        context['page_title'] = ' | '.join([settings.APPLICATION_ACRONYM, 'Help'])
        links = [(reverse('site_home'), 'Home'), (None, 'Help')]
        context['breadcrumb_trail'] = breadcrumbs_li(links)
        return context


class GeneralSearch(PrsObjectList):
    """A search view that filters multiple object types: Referrals, Notes,
    Records, Conditions and Tasks.
    """
    model = Referral
    template_name = 'referral/prs_general_search.html'

    def get_context_data(self, **kwargs):
        context = super(GeneralSearch, self).get_context_data(**kwargs)
        context['page_title'] = ' | '.join([settings.APPLICATION_ACRONYM, 'Search'])
        links = [(reverse('site_home'), 'Home'), (None, 'Search')]
        context['breadcrumb_trail'] = breadcrumbs_li(links)
        # Add search results for models other than Referral.
        if 'q' in self.request.GET and self.request.GET['q']:
            context['query'] = True
            query_str = self.request.GET['q'].replace("'", r'"')
            context['search_string_norm'] = query_str
            for m, k in [
                    (Note, 'notes'), (Record, 'records'),
                    (Condition, 'conditions'), (Task, 'tasks')]:
                search_fields = admin.site._registry[m].search_fields
                entry_query = get_query(query_str, search_fields)
                # Only inlude up to 5 results for each model type.
                context[k] = m.objects.current().distinct().order_by(
                    '-modified').filter(entry_query)[:5]
            context['referrals'] = self.get_queryset()[:5]
            context['referral_headers'] = Referral.headers
            context['note_headers'] = Note.headers
            context['record_headers'] = Record.headers
            context['condition_headers'] = Condition.headers
            context['task_headers'] = Task.headers
        return context


class ReferralCreate(PrsObjectCreate):
    """Dedicated create view for new referrals.
    """
    model = Referral
    form_class = ReferralCreateForm
    template_name = 'referral/referral_create.html'

    def get_context_data(self, **kwargs):
        context = super(ReferralCreate, self).get_context_data(**kwargs)
        links = [
            (reverse('site_home'), 'Home'),
            (reverse('prs_object_list', kwargs={'model': 'referrals'}), 'Referrals'),
            (None, 'Create')
        ]
        context['breadcrumb_trail'] = breadcrumbs_li(links)
        context['title'] = 'CREATE A NEW REFERRAL'
        context['page_title'] = 'PRS | Referrals | Create'
        # Pass in a serialised list of tag names.
        context['tags'] = json.dumps([t.name for t in Tag.objects.all().order_by('name')])
        return context

    def get_initial(self):
        initial = super(ReferralCreate, self).get_initial()
        initial['assigned_user'] = self.request.user
        try:
            initial['referring_org'] = Organisation.objects.current().get(
                name__iexact='western australian planning commission')
            initial['task_type'] = TaskType.objects.get(name='Assess a referral')
            initial['agency'] = Agency.objects.get(code='DPaW')
        except:
            initial['referring_org'] = Organisation.objects.current()[0]
            initial['task_type'] = TaskType.objects.all()[0]
            initial['agency'] = Agency.objects.all()[0]
        return initial

    def form_valid(self, form):
        req = self.request
        d = form.cleaned_data
        new_ref = form.save(commit=False)
        new_ref.creator, new_ref.modifier = req.user, req.user
        new_ref.save()
        form.save_m2m()  # Save any DoP Triggers.
        # All new referrals get a default task, chosen from the select list.
        new_task = Task(
            type=d['task_type'],
            referral=new_ref,
            start_date=new_ref.referral_date,
            description=new_ref.address or '',
            assigned_user=d['assigned_user']
        )
        new_task.state = new_task.type.initial_state
        if new_ref.description:
            new_task.description += ' ' + new_ref.description
        # Check if a due date was provided. If not, fall back to the
        # target days defined for the Task Type.
        if d['due_date']:
            new_task.due_date = d['due_date']
        else:
            new_task.due_date = datetime.today() + timedelta(new_task.type.target_days)
        new_task.creator, new_task.modifier = req.user, req.user
        new_task.save()
        # If the user checked the "Email user" box, send an email notification.
        if req.POST.get('email_user'):
            subject = 'PRS new referral notification ({0}), reference: {1}'
            subject = subject.format(new_ref.id, new_ref.reference)
            from_email = req.user.email
            to_email = new_task.assigned_user.email
            ref_url = settings.SITE_URL + new_ref.get_absolute_url()
            address = new_ref.address or '(not recorded)'
            text_content = '''This is an automated message to let you know that
                you have been assigned a PRS task by the sending user.\n
                This task is attached to referral ID {0}.\n
                The referrer's reference is {1}.\n
                The referral address is {2}\n
                '''.format(new_ref.id, new_ref.reference, address)
            html_content = '''<p>This is an automated message to let you know
                that you have been assigned a PRS task by the sending user.</p>
                <p>This task is attached to referral ID {0}</a>, at this URL:</p>
                <p>{1}</p>
                <p>The referrer's reference is: {2}.</p>
                <p>The referral address is {3}.</p>
                '''.format(new_ref.pk, ref_url, new_ref.reference, address)
            msg = EmailMultiAlternatives(subject, text_content, from_email, [to_email])
            msg.attach_alternative(html_content, 'text/html')
            # Email should fail gracefully - ie no Exception raised on failure.
            msg.send(fail_silently=True)

        messages.success(req, 'New referral created successfully.')
        # If the user clicked 'Save', redirect to the new referral detail view.
        # Otherwise, assume that they clicked 'Save and add location'.
        if req.POST.get('save'):
            return redirect(new_ref.get_absolute_url())
        else:
            return redirect(
                reverse(
                    'referral_location_create',
                    kwargs={'pk': new_ref.pk})
            )


class ReferralDetail(PrsObjectDetail):
    """Detail view for a single referral. Also includes a queryset of related/
    child objects in context.
    """
    model = Referral
    related_model = None
    template_name = 'referral/referral_detail.html'

    def dispatch(self, request, *args, **kwargs):
        # related_model is an optional 'child' of referral (e.g. task, note, etc).
        # Defaults to 'task'.
        if 'related_model' in kwargs:
            self.related_model = kwargs['related_model']
        else:
            self.related_model = 'tasks'
        return super(ReferralDetail, self).dispatch(request, *args, **kwargs)

    def get_template_names(self):
        if 'print' in self.request.GET:
            if self.request.GET['print'] == 'notes':
                return ['referral/referral_notes_print.html']
        return super(ReferralDetail, self).get_template_names()

    def get(self, request, *args, **kwargs):
        ref = self.get_object()
        # Deleted? Redirect home.
        if ref.is_deleted():
            messages.warning(self.request, 'Referral {} not found.'.format(ref.id))
            return HttpResponseRedirect(reverse('site_home'))
        # Override the get() to optionally return a QGIS layer definition.
        if 'generate_qgis' in request.GET and ref.location_set.current().exists():
            if 'qgis_ver' in request.GET and request.GET['qgis_ver'] == '2_16':
                content = ref.generate_qgis_layer('qgis_layer_v2-16')
            else:
                content = ref.generate_qgis_layer()
            fn = 'prs_referral_{}.qlr'.format(ref.pk)
            resp = HttpResponse(content, content_type='application/x-qgis-project')
            resp['Content-Disposition'] = 'attachment; filename="{}"'.format(fn)
            return resp
        # Call user_referral_history with the current referral.
        user_referral_history(request.user, ref)

        return super(ReferralDetail, self).get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(ReferralDetail, self).get_context_data(**kwargs)
        ref = self.get_object()
        context['title'] = 'REFERRAL DETAILS: {}'.format(ref.pk)
        context['page_title'] = 'PRS | Referrals | {}'.format(ref.pk)
        context['rel_model'] = self.related_model
        # Test if the user has bookmarked this referral.
        if Bookmark.objects.filter(referral=ref, user=self.request.user).exists():
            context['bookmark'] = Bookmark.objects.filter(referral=ref, user=self.request.user)[0]

        # Add context for each child model type: task_list, note_list, etc.
        table = '''<table class="table table-striped table-bordered table-condensed prs-object-table">
        <thead><tr>{}</tr></thead><tbody>{}<tbody></table>'''
        for m in [Task, Note, Record, Location, Condition]:
            obj_tab = 'tab_{}'.format(m._meta.model_name)
            obj_list = '{}_list'.format(m._meta.model_name)
            if m.objects.current().filter(referral=ref):
                context['{}_count'.format(m._meta.object_name.lower())] = m.objects.current().filter(referral=ref).count()
                obj_qs = m.objects.current().filter(referral=ref)
                headers = copy(m.headers)
                headers.remove('Referral ID')
                headers.append('Actions')
                thead = ''.join(['<th>{}</th>'.format(h) for h in headers])
                rows = [u'<tr>{}{}</tr>'.format(o.as_row_minus_referral(),
                                               o.as_row_actions()) for o in obj_qs]
                tbody = ''.join(rows)
                obj_tab_html = table.format(thead, tbody)
                if m == Location:  # Append a div for the map viewer.
                    obj_tab_html += '<div id="ref_locations"></div>'
                context[obj_tab] = mark_safe(obj_tab_html)
                context[obj_list] = obj_qs
            else:
                context['{}_count'.format(m._meta.object_name.lower())] = 0
                context[obj_tab] = 'No {} found for this referral'.format(
                    m._meta.verbose_name_plural)
                context[obj_list] = None

        # Add child locations serialised as GeoJSON (if geometry exists).
        if any([l.poly for l in ref.location_set.current()]):
            context['geojson_locations'] = serialize(
                'geojson', ref.location_set.current(), geometry_field='poly', srid=4283)

        context['has_conditions'] = ref.condition_set.exists()
        return context


class ReferralCreateChild(PrsObjectCreate):
    """View to create 'child' objects for a referral, e.g. a Task or Note.
    Also allows the creation of relationships between children (e.g relating
    a Note to a Record).
    """

    def get_context_data(self, **kwargs):
        context = super(ReferralCreateChild, self).get_context_data(**kwargs)
        referral_id = self.parent_referral.pk
        child_model = is_model_or_string(self.kwargs['model'].capitalize())
        if 'id' in self.kwargs:  # Relating to existing object.
            child_obj = child_model.objects.get(pk=self.kwargs['id'])
            if self.kwargs['type'] == 'addnote':
                context['title'] = 'ADD EXISTING NOTE(S) TO {}'.format(child_obj).upper()
                context['page_title'] = 'PRS | Add note(s) to {}'.format(child_obj)
                last_breadcrumb = 'Add note(s) to {}'.format(child_obj)
            elif 'addrecord' in self.kwargs.values():
                context['title'] = 'ADD EXISTING RECORD(S) TO {}'.format(child_obj).upper()
                context['page_title'] = 'PRS | Add record(s) to {}'.format(child_obj)
                last_breadcrumb = 'Add record(s) to {}'.format(child_obj)
            elif 'addnewnote' in self.kwargs.values():
                context['title'] = 'ADD NOTE TO {}'.format(child_obj).upper()
                context['page_title'] = 'PRS | Add note to {}'.format(child_obj)
                last_breadcrumb = 'Add note to {}'.format(child_obj)
            elif 'addnewrecord' in self.kwargs.values():
                context['title'] = 'ADD RECORD TO {}'.format(child_obj).upper()
                context['page_title'] = 'PRS | Add record to {}'.format(child_obj)
                last_breadcrumb = 'Add record to {}'.format(child_obj)
        else:  # New child object.
            # Special case: clearance request task
            if 'type' in self.kwargs and self.kwargs['type'] == 'clearance':
                child_model = 'Clearance Request'
            else:
                child_model = self.kwargs['model'].capitalize()
            context['title'] = 'CREATE A NEW {}'.format(child_model).upper()
            context['page_title'] = 'PRS | Create {}'.format(child_model)
            last_breadcrumb = 'Create {}'.format(child_model)
        links = [
            (reverse('site_home'), 'Home'),
            (reverse('prs_object_list', kwargs={'model': 'referrals'}), 'Referrals'),
            (reverse('referral_detail', kwargs={'pk': referral_id}), referral_id),
            (None, last_breadcrumb)
        ]
        context['breadcrumb_trail'] = breadcrumbs_li(links)
        if child_model == 'Location':
            context['include_map'] = True
        return context

    def get_form_kwargs(self):
        kwargs = super(ReferralCreateChild, self).get_form_kwargs()
        referral = self.parent_referral
        if 'clearance' in self.kwargs.values():
            kwargs['condition_choices'] = self.get_condition_choices()
            kwargs['initial'] = {'assigned_user': self.request.user}
        if 'addrecord' in self.kwargs.values() or 'addnote' in self.kwargs.values():
            kwargs['referral'] = referral
        return kwargs

    @property
    def parent_referral(self):
        return Referral.objects.get(pk=self.kwargs['pk'])

    def get(self, request, *args, **kwargs):
        # Sanity check: disallow addition of clearance tasks where no approved
        # conditions exist on the referral.
        if 'clearance' in self.kwargs.values() and not self.get_condition_choices():
            messages.error(self.request, 'This referral has no approval conditions!')
            return HttpResponseRedirect(self.get_success_url())
        return super(ReferralCreateChild, self).get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        # If the user clicked Cancel, redirect to the referral detail page.
        if request.POST.get('cancel'):
            return HttpResponseRedirect(self.parent_referral.get_absolute_url())
        return super(ReferralCreateChild, self).post(request, *args, **kwargs)

    def form_valid(self, form):
        self.object = form.save(commit=False)
        self.object.referral = self.parent_referral
        self.object.user = self.request.user
        self.object.creator, self.object.modifier = self.request.user, self.request.user
        redirect_url = None

        if form.Meta.model._meta.model_name == 'task':
            # Create a clearance request task:
            if 'type' in self.kwargs and self.kwargs['type'] == 'clearance':
                self.create_clearance(form)
            # Create a task, type unspecified:
            elif 'type' not in self.kwargs:
                self.create_task(self.object)
        elif form.Meta.model._meta.model_name == 'record':
            # Creating a new record and relating it to another object:
            if 'type' in self.kwargs and self.kwargs['type'] == 'addnewrecord':
                redirect_url = self.create_new_record(form)
            # Using an existing record and relating it to another object:
            elif 'type' in self.kwargs and self.kwargs['type'] == 'addrecord':
                self.create_existing_record(form)
            # Creating a new record:
            elif 'type' not in self.kwargs:
                self.object.save()
        elif form.Meta.model._meta.model_name == 'note':
            # Creating a new note and relating it to another object:
            if 'type' in self.kwargs and self.kwargs['type'] == 'addnewnote':
                redirect_url = self.create_new_note(form)
            # Using an existing note and relating it to another object:
            elif 'type' in self.kwargs and self.kwargs['type'] == 'addnote':
                self.create_existing_note(form)
            # Creating a new note:
            elif 'type' not in self.kwargs:
                self.object.save()
        elif form.Meta.model._meta.model_name == 'condition':
            redirect_url = self.create_condition(self.object)
        else:
            self.object.save()

        if not messages.get_messages(self.request):
            messages.success(self.request, '{} has been created.'.format(self.object))

        redirect_url = redirect_url if redirect_url else self.get_success_url()
        return HttpResponseRedirect(redirect_url)

    def get_success_url(self):
        if 'id' in self.kwargs:  # Relating to existing object.
            child_model = is_model_or_string(self.kwargs['model'].capitalize())
            child_obj = child_model.objects.get(pk=self.kwargs['id'])
            return child_obj.get_absolute_url()
        return self.parent_referral.get_absolute_url()

    def create_existing_note(self, form):
        pk = self.kwargs['id']
        model_name = self.model._meta.model_name  # same as self.kwargs['model']
        obj = get_object_or_404(self.model, pk=pk)  # task, note, record obj etc

        # Relate existing note(s) to the task.
        d = form.cleaned_data
        for note in d['notes']:
            obj.notes.add(note)
            # Create the reverse relationship too.
            if model_name == 'task':
                note.task_set.add(obj)
            else:
                note.records.add(obj)
        messages.success(self.request, 'The note has been added to {} {}.'.format(
            self.kwargs['model'].capitalize(), self.kwargs['id']))

    def create_new_note(self, form):
        request = self.request

        pk = self.kwargs['id']
        model_name = self.model._meta.model_name  # same as self.kwargs['model']
        obj = get_object_or_404(self.model, pk=pk)  # task, note, record obj etc
        referral = obj.referral

        new_note = form.save(commit=False)
        # Create a new note and relate it to the task.
        new_note.referral = referral  # Use the parent referral for the record.
        new_note.creator, new_note.modifier = request.user, request.user
        new_note.save()
        obj.notes.add(new_note)
        obj.modifier = request.user
        obj.save()
        # Create the reverse relationship too.
        if model_name == 'task':
            new_note.task_set.add(obj)

        messages.success(self.request, 'New note successfully added to task.')
        redirect_url = None
        if (request.POST.get('save-another')):
            redirect_url = reverse('referral_create_child_related', kwargs={
                'pk': referral.pk, 'id': pk, 'model': 'task', 'type': 'addnewnote'})
        return redirect_url

    def create_existing_record(self, form):
        pk = self.kwargs['id']
        model_name = self.model._meta.model_name  # same as self.kwargs['model']
        obj = get_object_or_404(self.model, pk=pk)  # task, note, record obj etc

        # Relate existing record(s) to the obj.
        d = form.cleaned_data
        for record in d['records']:
            obj.records.add(record)
            # Create the reverse relationship too.
            if model_name == 'task':
                record.task_set.add(obj)
            else:
                record.note_set.add(obj)
        messages.success(self.request, 'The record has been added to {} {}.'.format(
            self.kwargs['model'].capitalize(), self.kwargs['id']))

    def create_new_record(self, form):
        request = self.request
        pk = self.kwargs['id']
        model_name = self.model._meta.model_name  # same as self.kwargs['model']
        obj = get_object_or_404(self.model, pk=pk)  # task, note, record obj etc
        referral = obj.referral
        new_record = form.save(commit=False)
        # Create a new record and relate it to the obj.
        new_record.referral = referral  # Use the parent referral for the record.
        new_record.creator, new_record.modifier = request.user, request.user
        new_record.save()
        obj.records.add(new_record)
        obj.modifier = request.user
        obj.save()
        # Create the reverse relationship too.
        if model_name == 'task':
            new_record.task_set.add(obj)

        redirect_url = None
        if (request.POST.get('save-another')):
            redirect_url = reverse(
                'referral_create_child_related',
                kwargs={
                    'pk': referral.pk,
                    'id': pk,
                    'model': model_name,
                    'type': 'addnewrecord'})
        return redirect_url

    def get_condition_choices(self):
        """Return conditions with 'approved' text only.
        """
        condition_qs = Condition.objects.current().filter(referral=self.parent_referral).exclude(condition='')
        condition_choices = []
        for i in condition_qs:
            condition_choices.append(
                (i.id, '{0} - {1}'.format(i.identifier or '', smart_truncate(i.condition, 100)))
            )
        return condition_choices

    def create_clearance(self, form):
        request = self.request
        # For each of the chosen conditions, create a clearance task using the form data.
        tasks = []
        for i in form.cleaned_data['conditions']:
            condition = Condition.objects.get(pk=i)
            clearance_task = Task()
            clearance_task.type = TaskType.objects.get(name='Conditions clearance request')
            clearance_task.referral = condition.referral
            clearance_task.assigned_user = form.cleaned_data['assigned_user']
            clearance_task.start_date = form.cleaned_data['start_date']
            clearance_task.description = form.cleaned_data['description']
            clearance_task.state = clearance_task.type.initial_state
            if form.cleaned_data['due_date']:
                clearance_task.due_date = form.cleaned_data['due_date']
            else:
                clearance_task.due_date = datetime.date(datetime.today())
                clearance_task.due_date += timedelta(clearance_task.type.target_days)
            clearance_task.creator, clearance_task.modifier = request.user, request.user
            clearance_task.save()
            condition.add_clearance(
                task=clearance_task,
                deposited_plan=form.cleaned_data['deposited_plan'])
            # If the user checked the "Email user" box, send them a notification.
            if request.POST.get('email_user'):
                subject = 'PRS referral {0} - new clearance request notification'.format(
                    clearance_task.referral.pk)
                from_email = request.user.email
                to_email = clearance_task.assigned_user.email
                referral_url = settings.SITE_URL + clearance_task.referral.get_absolute_url()
                text_content = '''This is an automated message to let you know that you have
                    been assigned PRS clearance request {0} by the sending user.\n
                    This clearance request is attached to referral ID {1}.\n
                    '''.format(clearance_task.pk, clearance_task.referral.pk)
                html_content = '''<p>This is an automated message to let you know that you have
                    been assigned PRS clearance request {0} by the sending user.</p>
                    <p>This task is attached to referral ID {1}</a>, at this URL:</p>
                    <p>{2}</p>'''.format(clearance_task.pk, clearance_task.referral.pk, referral_url)
                msg = EmailMultiAlternatives(subject, text_content, from_email, [to_email])
                msg.attach_alternative(html_content, 'text/html')
                # Email should fail gracefully - ie no Exception raised on failure.
                msg.send(fail_silently=True)
            tasks.append(clearance_task.pk)

        messages.success(
            self.request,
            'New Clearance {0} has been created.'.format(
                str(tasks).strip('[]')))

    def create_condition(self, obj):
        obj.save()
        messages.success(self.request, '{} has been created.'.format(obj))
        # If no model condition was chosen, email users in the 'PRS power user' group.
        pu_group = Group.objects.get(name=settings.PRS_POWER_USER_GROUP)
        users = pu_group.user_set.filter(is_active=True)
        subject = 'PRS condition created notification'
        from_email = 'PRS-Alerts@dpaw.wa.gov.au'
        for user in users:
            # Send a single email to this user
            to_email = [user.email]
            text_content = '''This is an automated message to let you know
                that the following condition was just created by:\n'''
            html_content = '''<p>This is an automated message to let you know
                that the following condition was just created:</p>'''
            text_content += '* Condition ID {}\n'.format(obj.pk)
            html_content += '<p><a href="{}">Condition ID {}</a></p>'.format(
                settings.SITE_URL + obj.get_absolute_url(), obj.pk)
            text_content += 'The condition was created by {}.\n'.format(obj.creator.get_full_name())
            html_content += '<p>The condition was created by {}.</p>'.format(obj.creator.get_full_name())
            text_content += 'This is an automatically-generated email - please do not reply.\n'
            html_content += '<p>This is an automatically-generated email - please do not reply.</p>'
            msg = EmailMultiAlternatives(subject, text_content, from_email, to_email)
            msg.attach_alternative(html_content, 'text/html')
            # Email should fail gracefully - ie no Exception raised on failure.
            msg.send(fail_silently=True)
        redirect_url = None
        if self.request.POST.get('save-another'):
            referral = obj.referral
            redirect_url = reverse('referral_create_child', kwargs={'pk': referral.pk, 'model': 'condition'})
        return redirect_url

    def create_task(self, obj):
        # Set the default initial state for the task type.
        obj.state = obj.type.initial_state

        # Auto-complete certain task types.
        if obj.type.name in ['Information only', 'Provide pre-referral/preliminary advice']:
            obj.due_date = datetime.date(datetime.today())
            obj.complete_date = datetime.date(datetime.today())
            obj.state = TaskState.objects.get(name='Complete')

        obj.save()

        # If "email user" was checked, do so now.
        if self.request.POST.get('email_user'):
            obj.email_user(from_email=self.request.user.email)


class LocationCreate(ReferralCreateChild):
    """Specialist view to allow selection of locations from cadastre, or
    digitisation of a spatial area.
    """
    model = Location
    form_class = LocationForm
    template_name = 'referral/location_create.html'

    @property
    def parent_referral(self):
        return get_object_or_404(Referral, pk=self.kwargs['pk'])

    def get_context_data(self, **kwargs):
        # Standard view context data.
        self.kwargs['model'] = 'location'  # Append to kwargs
        context = super(LocationCreate, self).get_context_data(**kwargs)
        ref = self.parent_referral
        links = [
            (reverse('site_home'), 'Home'),
            (reverse('prs_object_list', kwargs={'model': 'referrals'}), 'Referrals'),
            (reverse('referral_detail', kwargs={'pk': ref.pk}), ref.pk),
            (None, 'Create locations(s)')
        ]
        context['breadcrumb_trail'] = breadcrumbs_li(links)
        context['title'] = 'CREATE LOCATION(S)'
        context['address'] = ref.address
        # Add any existing referral locations serialised as GeoJSON.
        if any([l.poly for l in ref.location_set.current()]):
            context['geojson_locations'] = serialize(
                'geojson', ref.location_set.current(), geometry_field='poly', srid=4283)
        return context

    def get_success_url(self):
        return reverse('referral_detail', kwargs={'pk': self.parent_referral.pk})

    def post(self, request, *args, **kwargs):
        if request.POST.get('cancel'):
            return HttpResponseRedirect(self.get_success_url())
        ref = self.parent_referral

        # Aggregate the submitted form values into a dict of dicts.
        forms = {}
        for key, val in request.POST.iteritems():
            if key.startswith('form-'):
                form = re.findall('^form-[0-9]+', key)[0]
                field = re.sub('^form-[0-9]+-', '', key)
                if form in forms:  # Form dict already started.
                    pass
                else:  # Start a new form dict.
                    forms[form] = {}
                forms[form][field] = val

        # Iterate through forms, create new location for each.
        locations = []
        for form in forms.values():
            wkt = form.pop('wkt')
            poly = GEOSGeometry(wkt)
            # Set any blank form field values to None (digitised features)
            for k, v in form.iteritems():
                if not v:
                    form[k] = None
            l = Location(**form)
            if isinstance(poly, MultiPolygon):
                l.poly = poly[0]
            else:
                l.poly = poly
            l.referral = ref
            l.save()
            locations.append(l)

        messages.success(request, '{} location(s) created.'.format(len(forms)))

        # Call the Borg Collector publish API endpoint to create a manual job
        # to update the prs_locations layer.
        resp = borgcollector_harvest(self.request)
        logger.info('Borg Collector API response status was {}'.format(resp.status_code))
        logger.info('Borg Collector API response: {}'.format(resp.content))

        # Test for intersecting locations.
        intersecting_locations = self.polygon_intersects(locations)
        if intersecting_locations:
            # Redirect to a view where users can create relationships between referrals.
            locs_str = '_'.join(map(str, intersecting_locations))
            return HttpResponseRedirect(
                reverse(
                    'referral_intersecting_locations',
                    kwargs={
                        'pk': ref.id,
                        'loc_ids': locs_str}))
        else:
            return HttpResponseRedirect(self.get_success_url())

    def polygon_intersects(self, locations):
        """ Check to see if the location polygon intersects with any other locations.
        """
        intersecting_locations = []
        for location in locations:
            if location.poly:
                other_locs = Location.objects.current().exclude(pk=location.pk).filter(poly__isnull=False, poly__intersects=location.poly)
                if other_locs.exists():
                    intersecting_locations.append(location.pk)
        return intersecting_locations


class LocationIntersects(PrsObjectCreate):
    model = Referral
    form_class = IntersectingReferralForm

    @property
    def parent_referral(self):
        return self.get_object()

    def get_success_url(self):
        return reverse('referral_detail', kwargs={'pk': self.parent_referral.pk})

    def get_form_kwargs(self):
        kwargs = super(LocationIntersects, self).get_form_kwargs()
        kwargs['referral'] = self.parent_referral
        kwargs['referrals'] = self.referral_intersecting_locations()
        return kwargs

    def get_context_data(self, **kwargs):
        context = super(LocationIntersects, self).get_context_data(**kwargs)
        referral = self.parent_referral
        links = [
            (reverse('site_home'), 'Home'),
            (reverse('prs_object_list', kwargs={'model': 'referrals'}), 'Referrals'),
            (reverse('referral_detail', kwargs={'pk': referral.pk}), referral.pk),
            (None, 'Referrals with intersect(s)')
        ]
        context['breadcrumb_trail'] = breadcrumbs_li(links)
        context['title'] = 'REFERRALS WITH INTERSECTING LOCATION(S)'
        return context

    def post(self, request, *args, **kwargs):
        # If the user clicked Cancel, redirect to the referral detail page.
        if request.POST.get('cancel'):
            return HttpResponseRedirect(self.get_success_url())
        return super(LocationIntersects, self).post(request, *args, **kwargs)

    def form_valid(self, form):
        # For each intersecting referral chosen, add a relationship
        for ref in form.cleaned_data['related_refs']:
            self.parent_referral.add_relationship(ref)

        messages.success(self.request, '{} Referral relationship(s) created.'.format(
            len(form.cleaned_data['related_refs']))
        )
        return redirect(self.get_success_url())

    def referral_intersecting_locations(self):
        # get the loc_ids string and convert to list of int's
        loc_ids = map(int, self.kwargs['loc_ids'].split('_'))

        referral_ids = []
        for loc_id in loc_ids:
            location = get_object_or_404(Location, pk=loc_id)
            geom = location.poly.wkt
            intersects = Location.objects.current().exclude(id=location.id).filter(poly__isnull=False)
            # Get a qs of intersecting locations
            intersects = intersects.filter(poly__intersects=geom)
            # Get a qs of referrals
            for i in intersects:
                # Don't add the passed-in referral to the list.
                if i.referral.id != self.parent_referral.id:
                    referral_ids.append(i.referral.id)

        unique_referral_ids = list(set(referral_ids))
        return Referral.objects.current().filter(id__in=unique_referral_ids)


class RecordUpload(LoginRequiredMixin, View):
    """Minimal view to handle POST of form-encoded uploaded files.
    Note that this view is CSRF-exempt, though auth is still required.
    TODO: unit test for this view.
    """
    http_method_names = ['post']

    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        return super(RecordUpload, self).dispatch(request, *args, **kwargs)

    def parent_referral(self):
        return Referral.objects.get(pk=self.kwargs['pk'])

    def post(self, request, *args, **kargs):
        f = request.FILES['file']
        rec = Record(
            name=f.name, referral=self.parent_referral(), uploaded_file=f,
            order_date=datetime.now(), creator=request.user, modifier=request.user)
        rec.save()
        return HttpResponse(json.dumps({'success': True}))


class TaskAction(PrsObjectUpdate):
    """
    A customised view is used for editing Tasks because of the additional business logic.
    ``action`` includes add, stop, start, reassign, complete, cancel, inherit, update,
    addrecord, addnewrecord, addnote, addnewnote
    NOTE: does not include the 'delete' action (handled by separate view).
    """
    model = Task
    template_name = 'referral/change_form.html'
    action = None

    def get(self, request, *args, **kwargs):
        """Business rule/sanity check on task state (disallow some state
        changes for tasks). Ensures that actions that shouldn't be able t
        occur, don't occur. E.g. can't stop a task that is already stopped
        or already completed.
        """
        action = self.kwargs['action']
        task = self.get_object()

        if action == 'update' and task.stop_date and not task.restart_date:
            messages.error(request, "You can't edit a stopped task - restart the task first!")
            return redirect(task.get_absolute_url())
        if action == 'stop' and task.complete_date:
            messages.error(request, "You can't stop a completed task!")
            return redirect(task.get_absolute_url())
        if action == 'start' and not task.stop_date:
            messages.error(request, "You can't restart a non-stopped task!")
            return redirect(task.get_absolute_url())
        if action == 'inherit' and task.assigned_user == request.user:
            messages.info(request, 'That task is already assigned to you.')
            return redirect(task.get_absolute_url())
        if action in ['reassign', 'complete', 'cancel'] and task.complete_date:
            messages.info(request, 'That task is already completed.')
            return redirect(task.get_absolute_url())
        # We can't (yet) add a task to a task.
        if action == 'add':
            return redirect(task.get_absolute_url())
        # Business rule: adding a location is mandatory before completing some
        # 'Assess' tasks.
        trigger_ref_type = ReferralType.objects.filter(name__in=[
            'Development application',
            'Drain/pump/take water, watercourse works',
            'Extractive industry / mining',
            'GBRS amendment',
            'Land tenure change',
            'Management plan / technical report',
            'MRS amendment',
            'Pastoral lease permit to diversify',
            'Planning scheme / amendment',
            'PRS amendment',
            'Structure Plan',
            'Subdivision',
            'Utilities infrastructure & roads'])
        if action == 'complete' and task.referral.type in trigger_ref_type and not task.referral.has_location:
            msg = '''You are unable to complete this task without first
                recording location(s) on the referral.
                <a href="{}">Click here to create location(s).</a>'''.format(
                    reverse('referral_location_create', kwargs={'pk': task.referral.pk}))
            messages.warning(self.request, msg)
            return redirect(task.get_absolute_url())
        return super(TaskAction, self).get(request, *args, **kwargs)

    def get_form_class(self):
        action = self.kwargs['action']
        if action == 'stop':
            return TaskStopForm
        elif action == 'start':
            return TaskStartForm
        elif action == 'inherit':
            return TaskInheritForm
        elif action == 'complete':
            return TaskCompleteForm
        elif action == 'cancel':
            return TaskCancelForm
        elif action == 'reassign':
            return TaskReassignForm
        elif action == 'add':
            return TaskCreateForm
        else:
            return TaskForm

    def get_context_data(self, **kwargs):
        context = super(TaskAction, self).get_context_data(**kwargs)
        # Create a breadcrumb trail: Home[URL] > Tasks[URL] > ID[URL] > Action
        action = self.kwargs['action']
        obj = self.get_object()
        context['page_title'] = 'PRS | Tasks | {} | {}'.format(
            obj.pk, action.capitalize())
        links = [
            (reverse('site_home'), 'Home'),
            (reverse('prs_object_list', kwargs={'model': 'tasks'}), 'Tasks'),
            (reverse('prs_object_detail', kwargs={'pk': obj.pk, 'model': 'tasks'}), obj.pk),
            (None, action.capitalize())
        ]
        context['breadcrumb_trail'] = breadcrumbs_li(links)
        context['title'] = action.upper() + ' TASK'
        # Pass in a serialised list of tag names.
        context['tags'] = json.dumps([t.name for t in Tag.objects.all().order_by('name')])
        return context

    def get_success_url(self):
        task = self.get_object()
        return task.referral.get_absolute_url()

    def post(self, request, *args, **kwargs):
        # If the user clicked Cancel, redirect back to the site home page.
        if request.POST.get('cancel'):
            return redirect('site_home')
        return super(TaskAction, self).post(request, *args, **kwargs)

    def form_valid(self, form):
        action = self.kwargs['action']
        obj = form.save(commit=False)
        d = form.cleaned_data

        # This is where custom logic for the different actions takes place (if required).
        if action == 'stop':
            obj.stop_date = d['stopped_date']
            obj.state = TaskState.objects.all().get(name='Stopped')
            obj.restart_date = None
        elif action == 'start':
            obj.state = obj.type.initial_state
            obj.stop_time = obj.stop_time + (obj.restart_date - obj.stop_date).days
        elif action == 'inherit':
            user_task_history(
                self.request.user, obj, 'Inherited from {0} by {1}'.format(
                    obj.assigned_user.get_full_name(),
                    self.request.user.get_full_name())
            )
            obj.assigned_user = self.request.user
        elif action == 'cancel':
            obj.state = TaskState.objects.all().get(name='Cancelled')
            obj.complete_date = datetime.now()
        elif action == 'reassign':
            # Don't capture "self reassignment" in task history.
            if obj.assigned_user != self.request.user:
                user_task_history(
                    self.request.user, obj, 'Reassigned to {0} by {1}'.format(
                        obj.assigned_user.get_full_name(),
                        self.request.user.get_full_name())
                )
            if self.request.POST.get('email_user'):
                obj.email_user(self.request.user.email)
        elif action == 'update':
            if obj.restart_date and obj.stop_date:
                obj.stop_time = (obj.restart_date - obj.stop_date).days
        elif action == 'complete':
            if obj.type.name == 'Assess a referral':
                # Rule: proposed condition is mandatory for some 'Assess' task outcomes.
                # Ref PPRS-127.
                trigger_outcome = TaskState.objects.filter(name__in=[
                    'Response with condition'])
                trigger_ref_type = ReferralType.objects.filter(name__in=[
                    'Development application',
                    'Extractive industry / mining',
                    'Subdivision'])
                if (
                    obj.state in trigger_outcome
                    and obj.referral.type in trigger_ref_type
                    and not obj.referral.has_proposed_condition
                ):
                    msg = '''You are unable to complete this task as 'Response
                        with condition' without first recording proposed
                        condition(s) on the referral.
                        <a href="{}">Click here to create a condition.</a>'''.format(
                            reverse('referral_create_child', kwargs={'pk': obj.referral.pk, 'model': 'condition'}))
                    messages.warning(self.request, mark_safe(msg))
                    return redirect(obj.get_absolute_url())
                # Rule: >0 Tags are mandatory for some 'Assess' task outcomes.
                # Ref PPRS-103.
                trigger_outcome = TaskState.objects.filter(name__in=[
                    'Insufficient information provided',
                    'Response with advice',
                    'Response with condition',
                    'Response with objection'])
                form_data = form.cleaned_data
                if obj.state in trigger_outcome and not form_data['tags']:
                    msg = '''You are unable to select that task outcome without
                        recording tags that are relevant to advice provided.'''
                    messages.warning(self.request, msg)
                    return self.form_invalid(form)
                # Save selected tags on the task's parent referral.
                if form_data['tags']:
                    for tag in form_data['tags']:
                        obj.referral.tags.add(tag)

        obj.modifier = self.request.user
        obj.save()
        return super(TaskAction, self).form_valid(form)


class ReferralDownloadView(ObjectDownloadView):

    # override the file_not_found method in django-downloadview module
    def file_not_found_response(self):
        # check if the infobase field is set
        pk = self.kwargs['pk']
        record = Record.objects.get(pk=pk)
        if record.infobase_id:
            infobase_url = reverse('infobase_shortcut', kwargs={'pk': pk})
            infobase_id = record.infobase_id
            messages.warning(self.request, 'No file available. Try via Infobase ID <a href={}>{}</a>'.format(
                infobase_url, infobase_id))
        else:
            messages.warning(self.request, 'No file available.')

        return redirect(reverse('record_detail', kwargs={'pk': pk}))


class ReferralRecent(PrsObjectList):
    """Override the general-purpose list view to return only referrals in the
    user's recent history.
    """
    model = Referral
    paginate_by = None
    template_name = 'referral/referral_recent.html'

    def get_queryset(self):
        # UserProfile referral_history is a list of lists ([pk, date]).
        try:  # Empty history fails.
            history_list = json.loads(self.request.user.userprofile.referral_history)
            return Referral.objects.current().filter(pk__in=[i[0] for i in history_list])
        except:
            return Referral.objects.none()

    def get_context_data(self, **kwargs):
        context = super(ReferralRecent, self).get_context_data(**kwargs)
        title = 'Recent referrals'
        context['page_title'] = ' | '.join([settings.APPLICATION_ACRONYM, title])
        links = [
            (reverse('site_home'), 'Home'),
            (reverse('prs_object_list', kwargs={'model': 'referrals'}), 'Referrals'),
            (None, 'Recent referrals')
        ]
        context['breadcrumb_trail'] = breadcrumbs_li(links)
        return context


class ReferralReferenceSearch(PrsObjectList):
    """
    This is a small utility view that returns a small template meant to inserted
    inline to a form during an AJAX call when adding a new referral.
    The template is rendered with an object list of referrals returned whose
    reference matches that input for the new referral

    E.g. if the new referrals reference in "1234", this view will return all
    existing referrals with "1234" inside their reference too.
    """
    model = Referral
    template_name = 'referral/referral_reference_search.html'

    def get_queryset(self):
        object_count = 0
        if self.request.is_ajax():
            q = self.request.GET.get('q')
            queryset = Referral.objects.current().filter(Q(reference__contains=q))
            object_count = queryset.count()
            # If we have a lot of results, slice and return the first twenty only.
            if object_count > 20:
                queryset = queryset[0:19]
            return queryset
        return Referral.objects.none()

    def get_context_data(self, **kwargs):
        context = super(ReferralReferenceSearch, self).get_context_data(**kwargs)
        context['object_count'] = self.object_list.count()
        return context


class TagList(PrsObjectList):
    """Custom view to return a readonly list of tags (rendered HTML or JSON).
    """
    model = Tag
    template_name = 'referral/tag_list.html'
    http_method_names = ['get', 'options']

    def get(self, request, *args, **kwargs):
        """For an AJAX request or one containing a ``json`` request parameter,
        return a JSON response (list of tag names).
        """
        if request.is_ajax() or 'json' in request.GET:
            l = [str(i) for i in self.get_queryset().values_list('name', flat=True)]
            return JsonResponse(l, safe=False)
        return super(TagList, self).get(request, *args, **kwargs)

    def get_queryset(self):
        return Tag.objects.all().order_by('name')


class TagReplace(LoginRequiredMixin, FormView):
    """Custom view to replace all instances of a tag with another.
    NOTE: only users in the 'PRS power user' group can access this view.
    """
    form_class = TagReplaceForm
    template_name = 'referral/change_form.html'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_superuser and not is_prs_power_user(request):
            return HttpResponseForbidden('You do not have permission to use this function.')
        return super(TagReplace, self).dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(TagReplace, self).get_context_data(**kwargs)
        context['page_title'] = ' | '.join([settings.APPLICATION_ACRONYM, 'Replace tag'])
        context['title'] = 'REPLACE TAG'
        return context

    def post(self, request, *args, **kwargs):
        # If the user clicks "Cancel", redirect to the tags list view.
        if request.POST.get('cancel'):
            return HttpResponseRedirect(reverse('tag_list'))
        return super(TagReplace, self).post(request, *args, **kwargs)

    def form_valid(self, form):
        d = form.cleaned_data
        old, new = d['old_tag'], d['replace_with']
        # Iterate through all model classes that use tags.
        # Replace old tags with new tags.
        for model in [Referral, Condition]:
            tagged = model.objects.filter(tags__name__in=[old.name])
            for obj in tagged:
                obj.tags.remove(old)
                obj.tags.add(new)
        # Finally, delete the old tag
        old.delete()
        messages.success(self.request, 'All "{}" tags have been replaced by "{}"'.format(old, new))
        return HttpResponseRedirect(reverse('tag_list'))


class ReferralTagged(PrsObjectList):
    """Override the Referral model list view to filter tagged objects.
    """
    model = Referral

    def get_queryset(self):
        qs = super(ReferralTagged, self).get_queryset()
        # Filter queryset by the tag.
        tag = Tag.objects.get(slug=self.kwargs['slug'])
        qs = qs.filter(tags__in=[tag]).distinct()
        return qs

    def get_context_data(self, **kwargs):
        context = super(ReferralTagged, self).get_context_data(**kwargs)
        tag = Tag.objects.get(slug=self.kwargs['slug'])
        title = 'Referrals tagged: {}'.format(tag.name)
        context['page_title'] = ' | '.join([settings.APPLICATION_ACRONYM, title])
        links = [
            (reverse('site_home'), 'Home'),
            (reverse('prs_object_list', kwargs={'model': 'referral'}), 'Referrals'),
            (None, title)]
        context['breadcrumb_trail'] = breadcrumbs_li(links)
        context['object_type_plural'] = title
        return context


class BookmarkList(PrsObjectList):
    """Override to default object list to only show current user bookmarks.
    """
    model = Bookmark

    def get_queryset(self):
        qs = super(BookmarkList, self).get_queryset()
        qs = qs.filter(user=self.request.user)
        return qs


class ReferralDelete(PrsObjectDelete):
    model = Referral
    template_name = 'referral/prs_object_delete.html'

    def get_success_url(self):
        return reverse('site_home')

    def get_context_data(self, **kwargs):
        ref = self.get_object()

        context = super(ReferralDelete, self).get_context_data(**kwargs)
        context['object'] = ref
        context['object_type_plural'] = self.model._meta.verbose_name_plural
        context['object_type'] = self.model._meta.verbose_name
        return context

    def post(self, request, *args, **kwargs):
        ref = self.get_object()
        if request.POST.get('cancel'):
            return redirect('site_home')

        # Delete referral relationships
        # We can just call delete on this queryset.
        RelatedReferral.objects.filter(Q(from_referral=ref) | Q(to_referral=ref)).delete()
        # Delete any tags on the referral
        ref.tags.clear()
        # Delete tasks
        # Need iterate this queryset to call the object delete() method
        tasks = Task.objects.current().filter(referral=ref)
        for i in tasks:
            i.delete()
        # Delete records
        records = Record.objects.current().filter(referral=ref)
        for i in records:
            i.delete()
        # Delete notes
        notes = Note.objects.current().filter(referral=ref)
        for i in notes:
            i.delete()
        # Delete conditions
        conditions = Condition.objects.current().filter(referral=ref)
        for i in conditions:
            # Delete any clearances on each condition
            # We can just call delete on this queryset.
            Clearance.objects.current().filter(condition=i).delete()
            i.delete()
        # Delete locations
        locations = Location.objects.current().filter(referral=ref)
        for i in locations:
            i.delete()
        # Delete bookmarks
        bookmarks = Bookmark.objects.current().filter(referral=ref)
        for i in bookmarks:
            i.delete()
        ref.delete()
        messages.success(request, '{0} deleted.'.format(self.model._meta.object_name))
        # Call the Borg Collector publish API endpoint to create a manual job
        # to update the prs_locations layer.
        resp = borgcollector_harvest(self.request)
        logger.info('Borg Collector API response status was {}'.format(resp.status_code))
        logger.info('Borg Collector API response: {}'.format(resp.content))
        return redirect('site_home')


class ReferralRelate(PrsObjectList):
    """Custom list view to search referrals to relate together.
    """
    model = Referral
    template_name = 'referral/referral_relate.html'

    def get_object(self):
        return Referral.objects.get(pk=self.kwargs['pk'])

    def get_queryset(self):
        # Exclude parent object from queryset.
        qs = super(ReferralRelate, self).get_queryset()
        return qs.exclude(pk=self.get_object().pk)

    def get_context_data(self, **kwargs):
        context = super(ReferralRelate, self).get_context_data(**kwargs)
        title = 'Add a related referral'
        context['object_type_plural'] = title.upper()
        context['page_title'] = ' | '.join([settings.APPLICATION_ACRONYM, title])
        context['referral'] = self.get_object()
        return context

    def post(self, request, *args, **kwargs):
        """Handle POST requests to create or delete referral relationships.
        Expects a kwarg ``pk`` to define the 'first' referral, plus query
        parameters ``ref_pk`` and EITHER ``create`` or ``delete``.

        ``ref_pk``: PK of the 'second' referral.
        ``create``: create a relationship
        ``delete``: delete the relationship
        """
        # NOTE: query parameters always live in request.GET.
        if not self.request.GET.get('ref_pk', None):
            raise AttributeError('Relate view {} must be called with a '
                                 'ref_pk query parameter.'.format(self.__class__.__name__))

        if 'create' not in self.request.GET and 'delete' not in self.request.GET:
            raise AttributeError(
                'Relate view {} must be called with either '
                'create or delete query parameters.'.format(
                    self.__class__.__name__))

        ref1 = self.get_object()
        ref2 = get_object_or_404(Referral, pk=self.request.GET.get('ref_pk'))

        if prs_user(request):
            if 'create' in self.request.GET:
                ref1.add_relationship(ref2)
                messages.success(request, 'Referral relation created')
            elif 'delete' in self.request.GET:
                ref1.remove_relationship(ref2)
                messages.success(request, 'Referral relation removed')

        return redirect(ref1.get_absolute_url())


class ConditionClearanceCreate(PrsObjectCreate):
    '''
    View to add a clearance request to a single condition object.
    This view opens the form for adding a new condition clearance to the database.
    ``pk`` is the PK of the Condition to which the clearance request is being made.
    '''
    model = Condition
    form_class = ClearanceCreateForm
    template_name = 'referral/change_form.html'

    def get_form_kwargs(self):
        kwargs = super(ConditionClearanceCreate, self).get_form_kwargs()
        condition = get_object_or_404(Condition, pk=self.kwargs['pk'])
        kwargs.update({'condition': condition})
        return kwargs

    def get_object(self):
        return Condition.objects.current().get(pk=self.kwargs.get('pk'))

    def get_context_data(self, **kwargs):
        context = super(ConditionClearanceCreate, self).get_context_data(**kwargs)
        obj = self.get_object()
        context['title'] = 'CREATE A CLEARANCE REQUEST'
        title = 'Create clearance request'
        context['page_title'] = ' | '.join([settings.APPLICATION_ACRONYM, title])
        model_list_url = reverse('prs_object_list', kwargs={'model': 'conditions'})
        context['breadcrumb_trail'] = breadcrumbs_li([
            (reverse('site_home'), 'Home'),
            (model_list_url, 'Conditions'),
            (obj.get_absolute_url, str(obj.pk)),
            (None, 'Create a clearance request')])
        return context

    def get_initial(self):
        initial = super(ConditionClearanceCreate, self).get_initial()
        obj = self.get_object()
        initial['assigned_user'] = self.request.user
        initial['description'] = obj.condition
        return initial

    def post(self, request, *args, **kwargs):
        # On Cancel, redirect to the Condition URL.
        if request.POST.get('cancel'):
            obj = self.get_object()
            return HttpResponseRedirect(
                reverse('prs_object_detail', kwargs={'pk': obj.pk, 'model': 'conditions'}))
        return super(ConditionClearanceCreate, self).post(request, *args, **kwargs)

    def form_valid(self, form):
        obj = self.get_object()
        clearance_task = form.save(commit=False)
        clearance_task.type = TaskType.objects.get(name='Conditions clearance request')
        clearance_task.referral = obj.referral
        clearance_task.state = clearance_task.type.initial_state
        if form.cleaned_data['due_date']:
            clearance_task.due_date = form.cleaned_data['due_date']
        else:
            clearance_task.due_date = datetime.date(datetime.today())
            clearance_task.due_date += timedelta(clearance_task.type.target_days)
        clearance_task.creator, clearance_task.modifier = self.request.user, self.request.user
        clearance_task.save()
        obj.add_clearance(
            task=clearance_task,
            deposited_plan=form.cleaned_data['deposited_plan'])
        messages.success(self.request, 'New clearance request created successfully.')

        # If the user check the "Email user" box, send them a notification.
        if self.request.POST.get('email_user'):
            subject = 'PRS referral {0} - new clearance request notification'.format(
                clearance_task.referral.pk)
            from_email = self.request.user.email
            to_email = clearance_task.assigned_user.email
            referral_url = settings.SITE_URL + clearance_task.referral.get_absolute_url()
            text_content = '''This is an automated message to let you know that you have
                been assigned PRS clearance request {0} by the sending user.\n
                This clearance request is attached to referral ID {1}.\n
                '''.format(clearance_task.pk, clearance_task.referral.pk)
            html_content = '''<p>This is an automated message to let you know that you have
                been assigned PRS clearance request {0} by the sending user.</p>
                <p>This task is attached to referral ID {1}, at this URL:</p>
                <p>{2}</p>'''.format(clearance_task.pk, clearance_task.referral.pk, referral_url)
            msg = EmailMultiAlternatives(subject, text_content, from_email, [to_email])
            msg.attach_alternative(html_content, 'text/html')
            # Email should fail gracefully - ie no Exception raised on failure.
            msg.send(fail_silently=True)
        return redirect(clearance_task.get_absolute_url())


class InfobaseShortcut(View):
    """Basic view to generate a shortcut file to an Infobase object
    The file is a one-line text file containing the Infobase ID, with a .obr
    file extension.
    """

    def get(self, request, *args, **kwargs):
        record = get_object_or_404(Record, pk=self.kwargs['pk'])
        if record.infobase_id:
            response = HttpResponse(content_type='application/octet-stream')
            response[
                'Content-Disposition'] = 'attachment; filename=infobase_{}.obr'.format(record.infobase_id)
            # The HttpResponse is a file-like object; write the Infobase ID and return it.
            response.write(record.infobase_id)
            return response
        else:
            messages.warning(request, 'That record is not associated with an InfoBase object ID.')
            return HttpResponseRedirect(record.get_absolute_url())

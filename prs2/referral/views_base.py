from braces.views import LoginRequiredMixin
from django.conf import settings
from django.contrib import messages
from django.contrib.admin import site
from django.core.serializers import serialize
from django.core.urlresolvers import reverse
from django.http import (
    HttpResponse, HttpResponseBadRequest, HttpResponseRedirect, Http404)
from django.shortcuts import redirect
from django.template.defaultfilters import slugify
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import (
    View, ListView, DetailView, CreateView, UpdateView, DeleteView)
import json
from reversion import revisions
from taggit.models import Tag

from .forms import FORMS_MAP, ReferralForm
from .utils import is_model_or_string, breadcrumbs_li, get_query, prs_user


class PrsObjectList(LoginRequiredMixin, ListView):
    """A general-purpose view class to use for listing and searching PRS
    objects. Extend this class to customise the view for each model type.
    """
    paginate_by = 20
    template_name = 'referral/prs_object_list.html'

    def dispatch(self, request, *args, **kwargs):
        # kwargs must include a Model class, or a string.
        if 'model' in kwargs:
            self.model = is_model_or_string(kwargs['model'])
        # is_model_or_string() returns None if the model doesn't exist.
        if not self.model:
            return HttpResponseBadRequest('Not a model.')
        return super(PrsObjectList, self).dispatch(request, *args, **kwargs)

    def get_queryset(self):
        '''
        Define the queryset of objects to return.
        By default, the queryset return recently-modified ones objects first.
        '''
        qs = super(PrsObjectList, self).get_queryset()
        if 'effective_to' in self.model._meta.get_all_field_names():
            qs = qs.filter(effective_to=None)
        # Did we pass in a search string? If so, filter the queryset and
        # return it.
        if 'q' in self.request.GET and self.request.GET['q']:
            query_str = self.request.GET['q']
            # Replace single-quotes with double-quotes
            query_str = query_str.replace("'", r'"')
            # If the model is registered with in admin.py, filter it using
            # registered search_fields.
            if site._registry[self.model].search_fields:
                search_fields = site._registry[self.model].search_fields
                entry_query = get_query(query_str, search_fields)
                qs = qs.filter(entry_query)
        return qs.distinct()

    def get_context_data(self, **kwargs):
        context = super(PrsObjectList, self).get_context_data(**kwargs)
        # Pass model headers.
        if hasattr(self.model, 'headers'):
            context['object_list_headers'] = self.model.headers
        # Pass in any query string
        if ('q' in self.request.GET):
            context['query_string'] = self.request.GET['q']
        title = self.model._meta.verbose_name_plural.capitalize()
        object_type_plural = self.model._meta.verbose_name_plural
        context['object_type_plural'] = object_type_plural
        context['page_title'] = ' | '.join([settings.APPLICATION_ACRONYM, title])
        links = [(reverse('site_home'), 'Home'), (None, title)]
        context['breadcrumb_trail'] = breadcrumbs_li(links)
        return context


class PrsObjectCreate(LoginRequiredMixin, CreateView):
    """A general-purpose view class for creating new PRS objects. Extend this
    class to customise the 'create' view for each model type.
    Note that most PRS objects are associated with Referral models, thus they
    use the ``ReferralChildObjectCreate`` view instead.
    """
    template_name = 'referral/change_form.html'

    def dispatch(self, request, *args, **kwargs):
        if not prs_user(request):
            messages.warning(request, '''You do not have permission to edit data.
            Please contact the application owner(s): {}'''.format(', '.join([i[0] for i in settings.MANAGERS])))
            return HttpResponseRedirect(reverse('site_home'))

        # kwargs must include a Model class, or a string.
        if 'model' in kwargs:
            self.model = is_model_or_string(kwargs['model'])
        return super(PrsObjectCreate, self).dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        # Standard view context data.
        context = super(PrsObjectCreate, self).get_context_data(**kwargs)
        m = self.model._meta
        model_type = m.verbose_name.capitalize()
        context['model_type'] = model_type
        context['title'] = 'CREATE {}'.format(self.model._meta.object_name.upper())
        context['page_title'] = ' | '.join([
            settings.APPLICATION_ACRONYM, 'Create ' + model_type])
        context['page_heading'] = 'CREATE ' + model_type.upper()
        model_list_url = reverse(
            'prs_object_list',
            kwargs={'model': self.model._meta.verbose_name_plural.replace(' ', '-')})
        context['breadcrumb_trail'] = breadcrumbs_li([
            (reverse('site_home'), 'Home'),
            (model_list_url, m.verbose_name_plural.capitalize()),
            (None, 'Create')])
        return context

    def get_form_class(self):
        # If we haven't defined form_class, use the class in FORMS_MAP.
        if not self.form_class:
            if 'type' in self.kwargs:
                _type = self.kwargs['type']
                return FORMS_MAP[self.model][_type]
            else:
                return FORMS_MAP[self.model]['create']
        return self.form_class

    def post(self, request, *args, **kwargs):
        # If the user clicked Cancel, redirect back to the site home page.
        if request.POST.get('cancel'):
            return redirect('site_home')
        return super(PrsObjectCreate, self).post(request, *args, **kwargs)

    def form_valid(self, form):
        # Saves the form instance, sets the current object for the view,
        # and redirects to get_success_url().
        self.object = form.save(commit=False)
        # Handle models that inherit from Audit abstract model.
        f = self.model._meta.get_all_field_names()
        if 'creator' in f and 'modifier' in f:
            self.object.creator, self.object.modifier = self.request.user, self.request.user
        # Handle slug fields.
        if 'slug' in f and 'slug' not in form.cleaned_data:
            self.object.slug = slugify(self.object.name)
        self.object.save()
        messages.success(
            self.request, '{0} has been created.'.format(self.object))
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        # Allow success_url to be defined.
        if not self.success_url:
            return reverse('prs_object_detail', kwargs={
                'model': self.model._meta.object_name, 'pk': self.object.pk})
        return self.success_url


class PrsObjectDetail(LoginRequiredMixin, DetailView):
    """A general-purpose view class to use for displaying a single PRS object.
    """
    template_name = 'referral/prs_object_detail.html'

    def dispatch(self, request, *args, **kwargs):
        # kwargs must include a Model class, or a string.
        if 'model' in kwargs:
            self.model = is_model_or_string(kwargs['model'])
        return super(PrsObjectDetail, self).dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        from referral.models import Task, Record, Note, Location
        context = super(PrsObjectDetail, self).get_context_data(**kwargs)
        context['object_type'] = self.model._meta.verbose_name
        context['object_type_plural'] = self.model._meta.verbose_name_plural
        # Does this model type have a tools template?
        if hasattr(self.model, 'tools_template'):
            context['object_tools_template'] = self.model.tools_template
        # Does this model type use tags?
        if hasattr(self.model, 'tags'):
            context['object_has_tags'] = True
        obj = self.get_object()
        context['page_title'] = ' | '.join([
            settings.APPLICATION_ACRONYM,
            self.model._meta.verbose_name_plural.capitalize(),
            unicode(obj.pk)])
        context['page_heading'] = self.model._meta.verbose_name.upper() + ' DETAILS'
        # Create a breadcrumb trail: Home[URL] > Model[URL] > ID
        context['breadcrumb_trail'] = breadcrumbs_li([
            (reverse('site_home'), 'Home'),
            (reverse(
                'prs_object_list',
                kwargs={'model': self.model._meta.object_name.lower()}),
                self.model._meta.verbose_name_plural.capitalize()),
            (None, unicode(obj.pk))])
        # Related model table headers.
        context['note_headers'] = Note.headers
        context['record_headers'] = Record.headers
        context['task_headers'] = Task.headers
        # Additional context for specific model types.
        if self.model == Task:
            if obj.records.current():  # Related records.
                context['related_records'] = obj.records.current()
            if obj.notes.current():  # Related records.
                context['related_notes'] = obj.notes.current()
            context['task_stopped'] = True if obj.state.name == 'Stopped' else False
            context['can_complete'] = True
            if not obj.referral.has_proposed_condition:
                context['can_complete_msg'] = '''You are unable to complete this task
                as 'Response with advice' without first recording proposed condition(s)
                on the referral.'''
                context['can_complete'] = False
            if not obj.referral.has_location:
                context['can_complete_msg'] = '''You are unable to complete this task
                as 'Assess a referral' without first recording at least one location
                on the referral.'''
                context['can_complete'] = False
        if self.model == Record:
            if Task.objects.current().filter(records=obj):  # Related tasks.
                context['related_tasks'] = Task.objects.current().filter(records=obj)
            if obj.notes.exists():  # Related notes.
                context['related_notes'] = obj.notes.current()
        if self.model == Note:
            if Task.objects.current().filter(notes=obj):  # Related tasks.
                context['related_tasks'] = Task.objects.current().filter(notes=obj)
            if obj.records.exists():  # Related records.
                context['related_records'] = obj.records.current()
        if self.model == Location:
            # Add child locations serialised as GeoJSON (if geometry exists).
            if obj:
                context['geojson_locations'] = serialize(
                    'geojson', [obj], geometry_field='poly')
        return context


class PrsObjectUpdate(LoginRequiredMixin, UpdateView):
    """A general-purpose detail view class to use for updating a PRS object
    using a form.
    Extend this class to customise the view for each model type.
    """
    template_name = 'referral/change_form.html'

    def dispatch(self, request, *args, **kwargs):
        if not prs_user(request):
            messages.warning(request, '''You do not have permission to edit data.
            Please contact the application owner(s): {}'''.format(', '.join([i[0] for i in settings.MANAGERS])))
            return HttpResponseRedirect(reverse('site_home'))

        # kwargs must include a Model class, or a string.
        if 'model' in kwargs:
            self.model = is_model_or_string(kwargs['model'])
        return super(PrsObjectUpdate, self).dispatch(request, *args, **kwargs)

    def get_form_class(self):
        # If we haven't defined form_class, use the class in FORMS_MAP.
        if not self.form_class:
            return FORMS_MAP[self.model]['update']
        return self.form_class

    def get_context_data(self, **kwargs):
        context = super(PrsObjectUpdate, self).get_context_data(**kwargs)
        obj = self.get_object()
        context['title'] = 'UPDATE {}'.format(obj._meta.object_name).upper()
        context['page_title'] = 'PRS | {} | {} | Update'.format(
            obj._meta.verbose_name_plural.capitalize(),
            obj.pk)
        context['page_heading'] = 'UPDATE ' + obj._meta.verbose_name.upper()
        # Create a breadcrumb trail: Home[URL] > Model[URL] > ID > History
        context['breadcrumb_trail'] = breadcrumbs_li([
            (reverse('site_home'), 'Home'),
            (reverse(
                'prs_object_list',
                kwargs={'model': obj._meta.object_name.lower()}),
                obj._meta.verbose_name_plural.capitalize()),
            (obj.get_absolute_url(), str(obj.pk)),
            (None, 'Update')])
        # If the model type uses tags, pass in a serialised list of tag names.
        if hasattr(self.model, 'tags'):
            context['tags'] = json.dumps([t.name for t in Tag.objects.all()])
        return context

    def post(self, request, *args, **kwargs):
        # If the user clicks "Cancel", redirect back to the object URL.
        if request.POST.get('cancel'):
            return redirect(self.get_object().get_absolute_url())
        return super(PrsObjectUpdate, self).post(request, *args, **kwargs)

    def form_valid(self, form):
        form.save()
        messages.success(
            self.request, '{0} has been updated.'.format(self.get_object()))
        return super(PrsObjectUpdate, self).form_valid(form)


class PrsObjectHistory(PrsObjectDetail):
    """A general-purpose detail view class to use for displaying the revision
    history of a PRS object.
    Extend this class to customise the view for each model type.
    """
    template_name = 'referral/prs_object_history.html'

    def dispatch(self, request, *args, **kwargs):
        # kwargs must include a Model class, or a string.
        if 'model' in kwargs:
            self.model = is_model_or_string(kwargs['model'])
        return super(PrsObjectHistory, self).dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(PrsObjectHistory, self).get_context_data(**kwargs)
        obj = self.get_object()
        context['title'] = 'CHANGE HISTORY: {}'.format(obj)
        context['page_title'] = ' | '.join([
            settings.APPLICATION_ACRONYM, self.get_object().__unicode__(),
            'History'])
        context['page_heading'] = self.model._meta.verbose_name.upper() + ' CHANGE HISTORY'
        # Create a breadcrumb trail: Home[URL] > Model[URL] > ID > History
        context['breadcrumb_trail'] = breadcrumbs_li([
            (reverse('site_home'), 'Home'),
            (reverse(
                'prs_object_list',
                kwargs={'model': self.model._meta.object_name.lower()}),
                self.model._meta.verbose_name_plural.capitalize()),
            (obj.get_absolute_url(), str(obj.pk)),
            (None, 'History')])
        # Get all object versions
        versions = revisions.get_for_object(obj).order_by('-id')
        context['obj_versions'] = versions
        context['multi_versions'] = len(versions) > 1  # True/False
        return context


class PrsObjectDelete(LoginRequiredMixin, DeleteView):
    """A general-purpose view for confirming the deletion of a PRS object.
    Extend this class to customise the view for each model type.
    """
    template_name = 'referral/prs_object_delete.html'

    def dispatch(self, request, *args, **kwargs):
        if not prs_user(request):
            messages.warning(request, '''You do not have permission to edit data.
            Please contact the application owner(s): {}'''.format(', '.join([i[0] for i in settings.MANAGERS])))
            return HttpResponseRedirect(reverse('site_home'))

        # kwargs must include a Model class, or a string.
        if 'model' in kwargs:
            self.model = is_model_or_string(kwargs['model'])
        return super(PrsObjectDelete, self).dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(PrsObjectDelete, self).get_context_data(**kwargs)
        context['object_type'] = self.model._meta.verbose_name
        obj = self.get_object()
        context['title'] = 'DELETE: {}'.format(obj)
        context['page_title'] = ' | '.join([
            settings.APPLICATION_ACRONYM,
            'Delete {}'.format(self.get_object().__unicode__())])
        context['page_heading'] = 'DELETE ' + self.model._meta.verbose_name.upper()
        # Create a breadcrumb trail: Home[URL] > Model[URL] > ID > History
        context['breadcrumb_trail'] = breadcrumbs_li([
            (reverse('site_home'), 'Home'),
            (reverse(
                'prs_object_list',
                kwargs={'model': self.model._meta.object_name.lower()}),
                self.model._meta.verbose_name_plural.capitalize()),
            (obj.get_absolute_url(), str(obj.pk)),
            (None, 'Delete')])
        # If the object is a 'child' of a referral, set the referral's
        # absolute_url as the redirect URL
        if hasattr(obj, 'referral'):
            context['next_redirect'] = obj.referral.get_absolute_url()
        return context

    def get_success_url(self):
        # The success URL can be passed in as a kwarg to this view.
        if not self.success_url:
            return reverse('site_home')
        return self.success_url

    def post(self, request, *args, **kwargs):
        # If the user clicked "Cancel", redirect to the object's URL.
        if request.POST.get('cancel'):
            return redirect(self.get_object().get_absolute_url())
        return super(PrsObjectDelete, self).post(request, *args, **kwargs)

    def delete(self, request, *args, **kwargs):
        """
        Calls the delete() method on the fetched object and then
        redirects to the success URL.
        """
        obj = self.get_object()
        if request.POST.get('next', None):
            success_url = request.POST['next']
        else:
            success_url = self.get_success_url()
        obj.delete()
        messages.success(self.request, '{0} has been deleted.'.format(obj))
        return HttpResponseRedirect(success_url)


class PrsObjectTag(View):
    """Utility view to create/delete a tag on an object (typically via AJAX).
    Expects a POST request containing a ``tag`` query param with the value of
    the tag to add.
    A ``model`` and ``pk`` kwarg should be passed in via the URL.
    Default to adding the tag, unless the ``delete`` query param is also
    passed in.
    """
    http_method_names = [u'post']
    model = None
    pk_url_kwarg = 'pk'

    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        # kwargs must include a Model class, or a string.
        if 'model' in kwargs:
            self.model = is_model_or_string(kwargs['model'])
        # is_model_or_string() returns None if the model doesn't exist.
        if not self.model:
            raise AttributeError('Object tag view {} must be called with an '
                                 'model.'.format(self.__class__.__name__))
        return super(PrsObjectTag, self).dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return self.model._default_manager.all()

    def get_object(self, queryset=None):
        if queryset is None:
            queryset = self.get_queryset()
        # Look up the object by primary key.
        pk = self.kwargs.get(self.pk_url_kwarg, None)
        if pk is not None:
            queryset = queryset.filter(pk=pk)
        else:
            raise AttributeError('Object tag view {} must be called with an '
                                 'object pk.'.format(self.__class__.__name__))
        try:
            obj = queryset.get()
        except queryset.model.DoesNotExist:
            raise Http404('No {} found matching the query'.format(
                queryset.model._meta.verbose_name_plural))
        return obj

    def post(self, request, *args, **kwargs):
        """Handles POST requests, and adds or remove a tag on an object.
        """
        obj = self.get_object()
        tag = request.POST.get('tag', None)
        if not tag:
            return HttpResponseBadRequest('No tag supplied.')
        if 'delete' in request.POST:
            # Remove the tag from the object.
            obj.tags.remove(tag)
            return HttpResponse('Tag deleted')
        else:
            # Add the tag to the object.
            obj.tags.add(tag)
            return HttpResponse('Tag created')

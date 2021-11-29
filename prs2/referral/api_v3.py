from django.conf import settings
from django.contrib.auth.models import User, Group
from django.http import JsonResponse
from django.views.generic import View
from taggit.models import Tag

from .models import ReferralType, Region, Organisation, TaskState, TaskType


class ReferralTypeAPIResource(View):
    """An API view that returns JSON of current, active referral types.
    """
    http_method_names = ['get', 'options', 'head', 'trace']

    def get(self, request, *args, **kwargs):
        queryset = ReferralType.objects.current()

        # Queryset filtering.
        if 'pk' in kwargs and kwargs['pk']:  # Allow filtering by object PK.
            queryset = queryset.filter(pk=kwargs['pk'])
        if 'q' in self.request.GET:  # Allow basic filtering on name.
            queryset = queryset.filter(name__icontains=self.request.GET['q'])

        # Tailor the API response.
        if 'selectlist' in request.GET:  # Smaller response, for use in HTML select lists.
            objects = [{'id': obj.pk, 'text': obj.name} for obj in queryset]
        else:
            objects = [
                {
                    'id': obj.pk,
                    'name': obj.name,
                    'slug': obj.slug,
                    'description': obj.description,
                    'initial_task': obj.initial_task.pk if obj.initial_task else None,
                } for obj in queryset
            ]

        return JsonResponse(objects, safe=False)


class RegionAPIResource(View):
    """An API view that returns JSON of current, active department regions.
    """
    http_method_names = ['get', 'options', 'head', 'trace']

    def get(self, request, *args, **kwargs):
        queryset = Region.objects.current()

        # Queryset filtering.
        if 'pk' in kwargs and kwargs['pk']:  # Allow filtering by object PK.
            queryset = queryset.filter(pk=kwargs['pk'])
        if 'q' in self.request.GET:  # Allow basic filtering on name.
            queryset = queryset.filter(name__icontains=self.request.GET['q'])

        # Tailor the API response.
        if 'selectlist' in request.GET:  # Smaller response, for use in HTML select lists.
            objects = [{'id': obj.pk, 'text': obj.name} for obj in queryset]
        else:
            objects = [
                {
                    'id': obj.pk,
                    'name': obj.name,
                    'slug': obj.slug,
                } for obj in queryset
            ]

        return JsonResponse(objects, safe=False)


class OrganisationAPIResource(View):
    """An API view that returns JSON of current, active referring organisations.
    """
    http_method_names = ['get', 'options', 'head', 'trace']

    def get(self, request, *args, **kwargs):
        queryset = Organisation.objects.current()

        # Queryset filtering.
        if 'pk' in kwargs and kwargs['pk']:  # Allow filtering by object PK.
            queryset = queryset.filter(pk=kwargs['pk'])
        if 'q' in self.request.GET:  # Allow basic filtering on name.
            queryset = queryset.filter(name__icontains=self.request.GET['q'])

        # Tailor the API response.
        if 'selectlist' in request.GET:  # Smaller response, for use in HTML select lists.
            objects = [{'id': obj.pk, 'text': obj.name} for obj in queryset]
        else:
            objects = [
                {
                    'id': obj.pk,
                    'name': obj.name,
                    'type': obj.type.name,
                    'description': obj.description,
                    'slug': obj.slug,
                    'telephone': obj.telephone,
                    'fax': obj.fax,
                    'email': obj.email,
                    'address1': obj.address1,
                    'suburb': obj.suburb,
                    'state': obj.get_state_display(),
                    'postcode': obj.postcode,
                } for obj in queryset
            ]

        return JsonResponse(objects, safe=False)


class TaskStateAPIResource(View):
    """An API view that returns JSON of current, active task states.
    """
    http_method_names = ['get', 'options', 'head', 'trace']

    def get(self, request, *args, **kwargs):
        queryset = TaskState.objects.current()

        # Queryset filtering.
        if 'pk' in kwargs and kwargs['pk']:  # Allow filtering by object PK.
            queryset = queryset.filter(pk=kwargs['pk'])
        if 'q' in self.request.GET:  # Allow basic filtering on name.
            queryset = queryset.filter(name__icontains=self.request.GET['q'])

        # Tailor the API response.
        if 'selectlist' in request.GET:  # Smaller response, for use in HTML select lists.
            objects = [{'id': obj.pk, 'text': obj.name} for obj in queryset]
        else:
            objects = [
                {
                    'id': obj.pk,
                    'name': obj.name,
                    'slug': obj.slug,
                    'is_ongoing': obj.is_ongoing,
                    'is_assessment': obj.is_assessment,
                    'task_type': obj.task_type.name if obj.task_type else '',
                } for obj in queryset
            ]

        return JsonResponse(objects, safe=False)


class TaskTypeAPIResource(View):
    """An API view that returns JSON of current, active referral types.
    """
    http_method_names = ['get', 'options', 'head', 'trace']

    def get(self, request, *args, **kwargs):
        queryset = TaskType.objects.current()

        # Queryset filtering.
        if 'pk' in kwargs and kwargs['pk']:  # Allow filtering by object PK.
            queryset = queryset.filter(pk=kwargs['pk'])
        if 'q' in self.request.GET:  # Allow basic filtering on name.
            queryset = queryset.filter(name__icontains=self.request.GET['q'])

        # Tailor the API response.
        if 'selectlist' in request.GET:  # Smaller response, for use in HTML select lists.
            objects = [{'id': obj.pk, 'text': obj.name} for obj in queryset]
        else:
            objects = [
                {
                    'id': obj.pk,
                    'name': obj.name,
                    'description': obj.description,
                    'slug': obj.slug,
                    'initial_state': obj.initial_state.pk,
                    'target_days': obj.target_days,
                } for obj in queryset
            ]

        return JsonResponse(objects, safe=False)


class UserAPIResource(View):
    """An API view that returns JSON of current, active users.
    """
    http_method_names = ['get', 'options', 'head', 'trace']

    def get(self, request, *args, **kwargs):
        # Queryset should only return active users in the "PRS user" group.
        prs_user = Group.objects.get_or_create(name=settings.PRS_USER_GROUP)[0]
        queryset = User.objects.filter(groups__in=[prs_user], is_active=True).order_by('email')

        # Queryset filtering.
        if 'pk' in kwargs and kwargs['pk']:  # Allow filtering by object PK.
            queryset = queryset.filter(pk=kwargs['pk'])
        if 'q' in self.request.GET:  # Allow basic filtering on email.
            queryset = queryset.filter(email__icontains=self.request.GET['q'])

        # Tailor the API response.
        if 'selectlist' in request.GET:  # Smaller response, for use in HTML select lists.
            objects = [{'id': obj.pk, 'text': obj.get_full_name()} for obj in queryset]
        else:
            objects = [
                {
                    'id': obj.pk,
                    'name': obj.get_full_name(),
                    'email': obj.email,
                } for obj in queryset
            ]

        return JsonResponse(objects, safe=False)


class TagAPIResource(View):
    """An API view that returns JSON of current, active users.
    """
    http_method_names = ['get', 'options', 'head', 'trace']

    def get(self, request, *args, **kwargs):
        queryset = Tag.objects.all().order_by('name')

        # Queryset filtering.
        if 'pk' in kwargs and kwargs['pk']:  # Allow filtering by object PK.
            queryset = queryset.filter(pk=kwargs['pk'])
        if 'q' in self.request.GET:  # Allow basic filtering on name.
            queryset = queryset.filter(name__icontains=self.request.GET['q'])

        # Tailor the API response.
        if 'selectlist' in request.GET:  # Smaller response, for use in HTML select lists.
            objects = [{'id': obj.pk, 'text': obj.name} for obj in queryset]
        else:
            objects = [
                {
                    'id': obj.pk,
                    'name': obj.name,
                    'slug': obj.slug,
                } for obj in queryset
            ]

        return JsonResponse(objects, safe=False)

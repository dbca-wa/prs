from django.conf import settings
from django.contrib.auth.models import User, Group
from django.http import JsonResponse
from django.views.generic import View
from taggit.models import Tag

from .models import ReferralType, Region, Organisation, TaskState, TaskType, Referral


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


class ReferralAPIResource(View):
    """An API view that returns JSON of current, active referrals.
    This API resource is more elaborate than those above, including pagination and filtering.
    """
    http_method_names = ['get', 'options', 'head', 'trace']

    def get(self, request, *args, **kwargs):
        queryset = Referral.objects.current().prefetch_related('type', 'regions', 'referring_org', 'dop_triggers', 'tags', 'lga')

        # Queryset filtering.
        if 'pk' in kwargs and kwargs['pk']:  # Allow filtering by object PK.
            queryset = queryset.filter(pk=kwargs['pk'])
        if 'region__id' in self.request.GET and self.request.GET['region__id']:
            queryset = queryset.filter(regions__pk__in=[self.request.GET['region__id']])
        if 'referring_org__id' in self.request.GET and self.request.GET['referring_org__id']:
            queryset = queryset.filter(referring_org__pk=self.request.GET['referring_org__id'])
        if 'type__id' in self.request.GET and self.request.GET['type__id']:
            queryset = queryset.filter(type__pk=self.request.GET['type__id'])
        if 'referral_date__gte' in self.request.GET and self.request.GET['referral_date__gte']:
            queryset = queryset.filter(referral_date__gte=self.request.GET['referral_date__gte'])
        if 'referral_date__lte' in self.request.GET and self.request.GET['referral_date__lte']:
            queryset = queryset.filter(referral_date__lte=self.request.GET['referral_date__lte'])
        if 'tag__id' in self.request.GET and self.request.GET['tag__id']:
            queryset = queryset.filter(tags__pk__in=[self.request.GET['tag__id']])

        obj_count = queryset.count()  # Count the filtered results.

        # Paginate the queryset.
        offset = 0
        if 'offset' in self.request.GET and self.request.GET['offset']:
            offset = int(self.request.GET['offset'])
            # Ignore any offset which is greater than the result count.
            if offset >= obj_count:
                offset = 0

        # Django's queryset slicing is smart enough that we don't need to worry about "wrapping around".
        if 'limit' in self.request.GET and self.request.GET['limit']:
            limit = offset + int(self.request.GET['limit'])
        else:
            limit = offset + 50  # Default to a maximum of 50 objects in the response.

        queryset = queryset[offset:limit]
        resp = {
            'count': obj_count,
            'objects': [
                {
                    'id': obj.pk,
                    'type': obj.type.name,
                    'regions': ', '.join([i.name for i in obj.regions.current()]),
                    'referring_org': obj.referring_org.name,
                    'reference': obj.reference,
                    'file_no': obj.file_no,
                    'description': obj.description,
                    'referral_date': obj.referral_date.strftime('%Y-%m-%d'),
                    'address': obj.address,
                    'point': obj.point.wkt if obj.point else None,
                    'dop_triggers': [i.name for i in obj.dop_triggers.current()],
                    'tags': [i.name for i in obj.tags.all()],
                    'related_refs': [i.pk for i in obj.related_refs.current()],
                    'lga': obj.lga.name if obj.lga else None,
                } for obj in queryset
            ],
        }

        return JsonResponse(resp)

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import Group, User
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_control
from django.views.decorators.vary import vary_on_cookie
from django.views.generic import View
from django.views.generic.detail import SingleObjectMixin
from django.views.generic.list import MultipleObjectMixin
from taggit.models import Tag

from .models import Clearance, Organisation, Referral, ReferralType, Region, Task, TaskState, TaskType

# Pagination defaults for the API resources that support it.
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 500


class ApiResourceMixin(LoginRequiredMixin):
    """Mixin class for all v3 API resources.

    Every API response contains PRS data, so each resource requires an
    authenticated user; anonymous requests are redirected to the login page.
    This mixin must precede ``View`` in the MRO of each concrete resource.
    """

    http_method_names = ["get", "options", "head"]

    def get_page_bounds(self, count):
        """Return validated ``(start, stop)`` slice bounds for a response.

        ``limit`` is the maximum number of objects to return, counting from
        ``offset``. It defaults to DEFAULT_PAGE_SIZE and is clamped to
        MAX_PAGE_SIZE. Raises ValueError for malformed values, so callers can
        return an HTTP 400 rather than raising a server error.
        """
        try:
            offset = int(self.request.GET.get("offset", 0))
            limit = int(self.request.GET.get("limit", DEFAULT_PAGE_SIZE))
        except (TypeError, ValueError):
            raise ValueError("Pagination values 'offset' and 'limit' must be integers.")
        if offset < 0 or limit < 1:
            raise ValueError("Pagination values 'offset' and 'limit' must be positive integers.")
        # Ignore any offset which is greater than the result count.
        if offset >= count:
            offset = 0
        # Django's queryset slicing is smart enough that we don't need to
        # worry about "wrapping around".
        return offset, offset + min(limit, MAX_PAGE_SIZE)


class ListApiResource(ApiResourceMixin, View, MultipleObjectMixin):
    pass


class DetailApiResource(ApiResourceMixin, View, SingleObjectMixin):
    pass


class ReferralTypeAPIResource(ApiResourceMixin, View):
    """An API view that returns JSON of current, active referral types."""

    @method_decorator(cache_control(max_age=settings.API_RESPONSE_CACHE_SECONDS, private=True))
    @method_decorator(vary_on_cookie)
    def get(self, request, *args, **kwargs):
        queryset = ReferralType.objects.current()

        # Queryset filtering.
        if kwargs.get("pk"):  # Allow filtering by object PK.
            queryset = queryset.filter(pk=kwargs["pk"])
        if "q" in self.request.GET:  # Allow basic filtering on name.
            queryset = queryset.filter(name__icontains=self.request.GET["q"])

        # Tailor the API response.
        if "selectlist" in request.GET:  # Smaller response, for use in HTML select lists.
            objects = [{"id": obj.pk, "text": obj.name} for obj in queryset]
        else:
            objects = [
                {
                    "id": obj.pk,
                    "name": obj.name,
                    "slug": obj.slug,
                    "description": obj.description,
                    "initial_task": obj.initial_task.pk if obj.initial_task else None,
                }
                for obj in queryset
            ]

        return JsonResponse(objects, safe=False)


class RegionAPIResource(ApiResourceMixin, View):
    """An API view that returns JSON of current, active department regions."""

    @method_decorator(cache_control(max_age=settings.API_RESPONSE_CACHE_SECONDS, private=True))
    @method_decorator(vary_on_cookie)
    def get(self, request, *args, **kwargs):
        queryset = Region.objects.current()

        # Queryset filtering.
        if kwargs.get("pk"):  # Allow filtering by object PK.
            queryset = queryset.filter(pk=kwargs["pk"])
        if "q" in self.request.GET:  # Allow basic filtering on name.
            queryset = queryset.filter(name__icontains=self.request.GET["q"])

        # Tailor the API response.
        if "selectlist" in request.GET:  # Smaller response, for use in HTML select lists.
            objects = [{"id": obj.pk, "text": obj.name} for obj in queryset]
        else:
            objects = [
                {
                    "id": obj.pk,
                    "name": obj.name,
                    "slug": obj.slug,
                }
                for obj in queryset
            ]

        return JsonResponse(objects, safe=False)


class OrganisationAPIResource(ApiResourceMixin, View):
    """An API view that returns JSON of current, active referring organisations."""

    @method_decorator(cache_control(max_age=settings.API_RESPONSE_CACHE_SECONDS, private=True))
    @method_decorator(vary_on_cookie)
    def get(self, request, *args, **kwargs):
        queryset = Organisation.objects.current()

        # Queryset filtering.
        if kwargs.get("pk"):  # Allow filtering by object PK.
            queryset = queryset.filter(pk=kwargs["pk"])
        if "q" in self.request.GET:  # Allow basic filtering on name.
            queryset = queryset.filter(name__icontains=self.request.GET["q"])

        # Tailor the API response.
        if "selectlist" in request.GET:  # Smaller response, for use in HTML select lists.
            objects = [{"id": obj.pk, "text": obj.name} for obj in queryset]
        else:
            objects = [
                {
                    "id": obj.pk,
                    "name": obj.name,
                    "type": obj.type.name,
                    "description": obj.description,
                    "slug": obj.slug,
                    "telephone": obj.telephone,
                    "fax": obj.fax,
                    "email": obj.email,
                    "address1": obj.address1,
                    "suburb": obj.suburb,
                    "state": obj.get_state_display(),
                    "postcode": obj.postcode,
                }
                for obj in queryset
            ]

        return JsonResponse(objects, safe=False)


class TaskStateAPIResource(ApiResourceMixin, View):
    """An API view that returns JSON of current, active task states."""

    @method_decorator(cache_control(max_age=settings.API_RESPONSE_CACHE_SECONDS, private=True))
    @method_decorator(vary_on_cookie)
    def get(self, request, *args, **kwargs):
        queryset = TaskState.objects.current()

        # Queryset filtering.
        if kwargs.get("pk"):  # Allow filtering by object PK.
            queryset = queryset.filter(pk=kwargs["pk"])
        if "q" in self.request.GET:  # Allow basic filtering on name.
            queryset = queryset.filter(name__icontains=self.request.GET["q"])

        # Tailor the API response.
        if "selectlist" in request.GET:  # Smaller response, for use in HTML select lists.
            objects = [{"id": obj.pk, "text": obj.name} for obj in queryset]
        else:
            objects = [
                {
                    "id": obj.pk,
                    "name": obj.name,
                    "slug": obj.slug,
                    "is_ongoing": obj.is_ongoing,
                    "is_assessment": obj.is_assessment,
                    "task_type": obj.task_type.name if obj.task_type else "",
                }
                for obj in queryset
            ]

        return JsonResponse(objects, safe=False)


class TaskTypeAPIResource(ApiResourceMixin, View):
    """An API view that returns JSON of current, active referral types."""

    @method_decorator(cache_control(max_age=settings.API_RESPONSE_CACHE_SECONDS, private=True))
    @method_decorator(vary_on_cookie)
    def get(self, request, *args, **kwargs):
        queryset = TaskType.objects.current()

        # Queryset filtering.
        if kwargs.get("pk"):  # Allow filtering by object PK.
            queryset = queryset.filter(pk=kwargs["pk"])
        if "q" in self.request.GET:  # Allow basic filtering on name.
            queryset = queryset.filter(name__icontains=self.request.GET["q"])

        # Tailor the API response.
        if "selectlist" in request.GET:  # Smaller response, for use in HTML select lists.
            objects = [{"id": obj.pk, "text": obj.name} for obj in queryset]
        else:
            objects = [
                {
                    "id": obj.pk,
                    "name": obj.name,
                    "description": obj.description,
                    "slug": obj.slug,
                    "initial_state": obj.initial_state.pk,
                    "target_days": obj.target_days,
                }
                for obj in queryset
            ]

        return JsonResponse(objects, safe=False)


class UserAPIResource(ApiResourceMixin, View):
    """An API view that returns JSON of current, active users."""

    @method_decorator(cache_control(max_age=settings.API_RESPONSE_CACHE_SECONDS, private=True))
    @method_decorator(vary_on_cookie)
    def get(self, request, *args, **kwargs):
        # Queryset should only return active users in the "PRS user" group.
        prs_user = Group.objects.get_or_create(name=settings.PRS_USER_GROUP)[0]
        queryset = User.objects.filter(groups__in=[prs_user], is_active=True).order_by("email")

        # Queryset filtering.
        if kwargs.get("pk"):  # Allow filtering by object PK.
            queryset = queryset.filter(pk=kwargs["pk"])
        if "q" in self.request.GET:  # Allow basic filtering on email.
            queryset = queryset.filter(email__icontains=self.request.GET["q"])

        # Tailor the API response.
        if "selectlist" in request.GET:  # Smaller response, for use in HTML select lists.
            objects = [{"id": obj.pk, "text": obj.get_full_name()} for obj in queryset]
        else:
            objects = [
                {
                    "id": obj.pk,
                    "name": obj.get_full_name(),
                    "email": obj.email,
                }
                for obj in queryset
            ]

        return JsonResponse(objects, safe=False)


class TagAPIResource(ApiResourceMixin, View):
    """An API view that returns JSON of current, active users."""

    @method_decorator(cache_control(max_age=settings.API_RESPONSE_CACHE_SECONDS, private=True))
    @method_decorator(vary_on_cookie)
    def get(self, request, *args, **kwargs):
        queryset = Tag.objects.all().order_by("name")

        # Queryset filtering.
        if kwargs.get("pk"):  # Allow filtering by object PK.
            queryset = queryset.filter(pk=kwargs["pk"])
        if "q" in self.request.GET:  # Allow basic filtering on name.
            queryset = queryset.filter(name__icontains=self.request.GET["q"])

        # Tailor the API response.
        if "selectlist" in request.GET:  # Smaller response, for use in HTML select lists.
            objects = [{"id": obj.pk, "text": obj.name} for obj in queryset]
        else:
            objects = [
                {
                    "id": obj.pk,
                    "name": obj.name,
                    "slug": obj.slug,
                }
                for obj in queryset
            ]

        return JsonResponse(objects, safe=False)


class ReferralAPIResource(ApiResourceMixin, View):
    """An API view that returns JSON of current, active referrals.
    This API resource is more elaborate than those above, including pagination and filtering.
    """

    @method_decorator(cache_control(max_age=settings.API_RESPONSE_CACHE_SECONDS, private=True))
    @method_decorator(vary_on_cookie)
    def get(self, request, *args, **kwargs):
        queryset = Referral.objects.current().prefetch_related("type", "regions", "referring_org", "dop_triggers", "tags", "lga")

        # Queryset filtering.
        if kwargs.get("pk"):  # Allow filtering by object PK.
            queryset = queryset.filter(pk=kwargs["pk"])
        if self.request.GET.get("region__id"):
            queryset = queryset.filter(regions__pk__in=[self.request.GET["region__id"]])
        if self.request.GET.get("referring_org__id"):
            queryset = queryset.filter(referring_org__pk=self.request.GET["referring_org__id"])
        if self.request.GET.get("type__id"):
            queryset = queryset.filter(type__pk=self.request.GET["type__id"])
        if self.request.GET.get("referral_date__gte"):
            queryset = queryset.filter(referral_date__gte=self.request.GET["referral_date__gte"])
        if self.request.GET.get("referral_date__lte"):
            queryset = queryset.filter(referral_date__lte=self.request.GET["referral_date__lte"])
        if self.request.GET.get("tag__id"):
            queryset = queryset.filter(tags__pk__in=[self.request.GET["tag__id"]])

        obj_count = queryset.count()  # Count the filtered results.
        try:
            start, stop = self.get_page_bounds(obj_count)
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)
        queryset = queryset[start:stop]
        resp = {
            "count": obj_count,
            "objects": [
                {
                    "id": obj.pk,
                    "type": obj.type.name,
                    "regions": ", ".join([i.name for i in obj.regions.current()]),
                    "referring_org": obj.referring_org.name,
                    "reference": obj.reference,
                    "file_no": obj.file_no,
                    "description": obj.description,
                    "referral_date": obj.referral_date.strftime("%Y-%m-%d"),
                    "address": obj.address,
                    "point": obj.point.wkt if obj.point else None,
                    "dop_triggers": [i.name for i in obj.dop_triggers.current()],
                    "tags": [i.name for i in obj.tags.all()],
                    "related_refs": [i.pk for i in obj.related_refs.current()],
                    "lga": obj.lga.name if obj.lga else None,
                }
                for obj in queryset
            ],
        }

        return JsonResponse(resp)


class TaskAPIResource(ApiResourceMixin, View):
    """An API view that returns JSON of current, active tasks.
    This API resource is more elaborate than those above, including pagination and filtering.
    """

    @method_decorator(cache_control(max_age=settings.API_RESPONSE_CACHE_SECONDS, private=True))
    @method_decorator(vary_on_cookie)
    def get(self, request, *args, **kwargs):
        queryset = Task.objects.current().prefetch_related("type", "referral", "assigned_user", "state")

        # Queryset filtering.
        if kwargs.get("pk"):  # Allow filtering by object PK.
            queryset = queryset.filter(pk=kwargs["pk"])
        if self.request.GET.get("region__id"):
            queryset = queryset.filter(referral__regions__pk__in=[self.request.GET["region__id"]])
        if self.request.GET.get("state__id"):
            queryset = queryset.filter(state__pk=self.request.GET["state__id"])
        if self.request.GET.get("assigned_user__id"):
            queryset = queryset.filter(assigned_user__pk=self.request.GET["assigned_user__id"])
        if self.request.GET.get("type__id"):
            queryset = queryset.filter(type__pk=self.request.GET["type__id"])
        if self.request.GET.get("start_date__gte"):
            queryset = queryset.filter(start_date__gte=self.request.GET["start_date__gte"])
        if self.request.GET.get("start_date__lte"):
            queryset = queryset.filter(start_date__lte=self.request.GET["start_date__lte"])

        obj_count = queryset.count()  # Count the filtered results.
        try:
            start, stop = self.get_page_bounds(obj_count)
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)
        queryset = queryset[start:stop]
        resp = {
            "count": obj_count,
            "objects": [
                {
                    "id": obj.pk,
                    "referral_id": obj.referral.pk,
                    "referral_reference": obj.referral.reference,
                    "regions": ", ".join([i.name for i in obj.referral.regions.current()]),
                    "assigned_user": obj.assigned_user.get_full_name(),
                    "type": obj.type.name,
                    "description": obj.description,
                    "state": obj.state.name,
                    "start_date": obj.start_date.strftime("%Y-%m-%d") if obj.start_date else None,
                    "due_date": obj.due_date.strftime("%Y-%m-%d") if obj.due_date else None,
                    "complete_date": obj.complete_date.strftime("%Y-%m-%d") if obj.complete_date else None,
                    "stop_date": obj.stop_date.strftime("%Y-%m-%d") if obj.stop_date else None,
                    "restart_date": obj.restart_date.strftime("%Y-%m-%d") if obj.restart_date else None,
                    "stop_time": obj.stop_time,
                }
                for obj in queryset
            ],
        }

        return JsonResponse(resp)


class ClearanceAPIResource(ApiResourceMixin, View):
    """An API view that returns JSON of current, active clearance requests.
    This API resource is more elaborate than those above, including pagination and filtering.
    """

    @method_decorator(cache_control(max_age=settings.API_RESPONSE_CACHE_SECONDS, private=True))
    @method_decorator(vary_on_cookie)
    def get(self, request, *args, **kwargs):
        queryset = Clearance.objects.current().prefetch_related("task", "condition")

        # Queryset filtering.
        if kwargs.get("pk"):  # Allow filtering by object PK.
            queryset = queryset.filter(pk=kwargs["pk"])
        if self.request.GET.get("region__id"):
            queryset = queryset.filter(task__referral__regions__pk__in=[self.request.GET["region__id"]])
        if self.request.GET.get("referring_org__id"):
            queryset = queryset.filter(task__referral__referring_org__pk=self.request.GET["referring_org__id"])
        if self.request.GET.get("state__id"):
            queryset = queryset.filter(task__state__pk=self.request.GET["state__id"])
        if self.request.GET.get("start_date__gte"):
            queryset = queryset.filter(task__start_date__gte=self.request.GET["start_date__gte"])
        if self.request.GET.get("start_date__lte"):
            queryset = queryset.filter(task__start_date__lte=self.request.GET["start_date__lte"])

        obj_count = queryset.count()  # Count the filtered results.
        try:
            start, stop = self.get_page_bounds(obj_count)
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)
        queryset = queryset[start:stop]
        resp = {
            "count": obj_count,
            "objects": [
                {
                    "id": obj.pk,
                    "referral_id": obj.task.referral.pk,
                    "task_id": obj.task.pk,
                    "condition_id": obj.condition.pk,
                    "condition": obj.condition.condition,
                    "identifier": obj.condition.identifier,
                    "category": obj.condition.tags.first().name if obj.condition.tags.exists() else None,
                    "regions": ", ".join([i.name for i in obj.task.referral.regions.current()]),
                    "assigned_user": obj.task.assigned_user.get_full_name(),
                    "description": obj.task.description,
                    "state": obj.task.state.name,
                    "start_date": obj.task.start_date.strftime("%Y-%m-%d") if obj.task.start_date else None,
                    "due_date": obj.task.due_date.strftime("%Y-%m-%d") if obj.task.due_date else None,
                    "complete_date": obj.task.complete_date.strftime("%Y-%m-%d") if obj.task.complete_date else None,
                    "stop_date": obj.task.stop_date.strftime("%Y-%m-%d") if obj.task.stop_date else None,
                    "restart_date": obj.task.restart_date.strftime("%Y-%m-%d") if obj.task.restart_date else None,
                    "stop_time": obj.task.stop_time,
                    "deposited_plan": obj.deposited_plan,
                }
                for obj in queryset
            ],
        }

        return JsonResponse(resp)

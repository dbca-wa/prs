from django.contrib.auth import get_user_model
from datetime import datetime
from rest_framework import viewsets, permissions
from .serializer import *
from taggit.managers import TaggableManager
from taggit.models import Tag
from rest_framework.pagination import LimitOffsetPagination

from referral.models import (
    DopTrigger, Region, OrganisationType, Organisation, TaskState, TaskType,
    ReferralType, NoteType, Agency, Referral, Task, Record, Note, Condition,
    ConditionCategory, Clearance, Location, UserProfile, ModelCondition)

"""
Pagination class
"""
class StandardResultsSetPagination(LimitOffsetPagination):
    page_size = 25
    page_size_query_param = 'limit'
    max_page_size = 100


"""
Viewsets for models, all readonly. 
"""

class DopTriggerView(viewsets.ReadOnlyModelViewSet):
    permission_classes = (permissions.IsAuthenticated,)
    queryset = DopTrigger.objects.current().filter(public=True)
    serializer_class = DopTriggerSerializer

class RegionView(viewsets.ReadOnlyModelViewSet):
    permission_classes = (permissions.IsAuthenticated,)
    queryset = Region.objects.current().filter(public=True)
    serializer_class = RegionSerializer

class OrganisationTypeView(viewsets.ReadOnlyModelViewSet):
    permission_classes = (permissions.IsAuthenticated,)
    queryset = OrganisationType.objects.current().filter(public=True)
    serializer_class = OrganisationTypeSerializer

class OrganisationView(viewsets.ReadOnlyModelViewSet):
    permission_classes = (permissions.IsAuthenticated,)
    queryset = Organisation.objects.current().filter(public=True)
    serializer_class = OrganisationSerializer

class TaskStateView(viewsets.ReadOnlyModelViewSet):
    permission_classes = (permissions.IsAuthenticated,)
    queryset = TaskState.objects.current().filter(public=True)
    serializer_class = TaskStateSerializer

class TaskTypeView(viewsets.ReadOnlyModelViewSet):
    permission_classes = (permissions.IsAuthenticated,)
    queryset = TaskType.objects.current()
    serializer_class = TaskTypeSerializer

class ReferralTypeView(viewsets.ReadOnlyModelViewSet):
    permission_classes = (permissions.IsAuthenticated,)
    queryset = ReferralType.objects.current().filter(public=True)
    serializer_class = ReferralTypeSerializer

class NoteTypeView(viewsets.ReadOnlyModelViewSet):
    permission_classes = (permissions.IsAuthenticated,)
    queryset = NoteType.objects.current().filter(public=True)
    serializer_class = NoteTypeSerializer

class AgencyView(viewsets.ReadOnlyModelViewSet):
    permission_classes = (permissions.IsAuthenticated,)
    queryset = Agency.objects.current().filter(public=True)
    serializer_class = AgencySerializer

class ReferralView(viewsets.ReadOnlyModelViewSet):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = ReferralSerializer
    pagination_class = StandardResultsSetPagination
    def get_queryset(self):
        queryset = Referral.objects.all()
        dop_trigger = self.request.query_params.get('dop_trigger', None)
        region = self.request.query_params.get('regions__id__in', None)
        referring_org = self.request.query_params.get('referring_org__id', None)
        type_id = self.request.query_params.get('type__id', None)
        referral_date_gte = self.request.query_params.get('referral_date__gte', None)
        referral_date_lte = self.request.query_params.get('referral_date__lte', None)
        tags = self.request.query_params.get('tags__id__in', None)
        start = self.request.query_params.get('start', None)
        length = self.request.query_params.get('length',None)
        if dop_trigger is not None:
            queryset = queryset.filter(dop_trigger=dop_trigger)
        if region is not None:
            queryset = queryset.filter(regions__id__in=region)
        if referring_org is not None:
            queryset = queryset.filter(referring_org__id=referring_org)
        if type_id is not None:
            queryset = queryset.filter(type__id=type_id)
        if referral_date_gte is not None:
            date_after = datetime.strptime(referral_date_gte, "%Y-%m-%d").date()
            queryset = queryset.filter(referral_date__gte=date_after)
        if referral_date_lte is not None:
            date_before = datetime.strptime(referral_date_lte, "%Y-%m-%d").date()
            queryset = queryset.filter(referral_date__lte=date_before)
        if tags is not None:
            for tag in tags.split(","):
                queryset = queryset.filter(tags__id=tag)
        queryset = self.get_serializer_class().setup_eager_loading(queryset)
        return queryset

class TaskView(viewsets.ReadOnlyModelViewSet):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = TaskSerializer
    pagination_class = StandardResultsSetPagination
    def get_queryset(self):
        queryset = Task.objects.current()
        region = self.request.query_params.get('referral__regions__id__in', None)
        user = self.request.query_params.get('assigned_user__id', None)
        type_id = self.request.query_params.get('type__id', None)
        state = self.request.query_params.get('state__id', None)
        start_date_gte = self.request.query_params.get('start_date__gte', None)
        start_date_lte = self.request.query_params.get('start_date__lte', None)
        start = self.request.query_params.get('start', None)
        length = self.request.query_params.get('length',None)
        if region is not None:
            queryset = queryset.filter(referral__regions__id__in=region)
        if user is not None:
            queryset = queryset.filter(assigned_user__id=user)
        if type_id is not None:
            queryset = queryset.filter(type__id=type_id)
        if state is not None:
            queryset = queryset.filter(state__id=state)
        if start_date_gte is not None:
            date_after = datetime.strptime(start_date_gte, "%Y-%m-%d").date()
            queryset = queryset.filter(start_date__gte=date_after)
        if start_date_lte is not None:
            date_before = datetime.strptime(start_date_lte, "%Y-%m-%d").date()
            queryset = queryset.filter(start_date__lte=date_before)
        queryset = self.get_serializer_class().setup_eager_loading(queryset)
        return queryset

class RecordView(viewsets.ReadOnlyModelViewSet):
    permission_classes = (permissions.IsAuthenticated,)
    queryset = Record.objects.current()
    serializer_class = RecordSerializer

class NoteView(viewsets.ReadOnlyModelViewSet):
    permission_classes = (permissions.IsAuthenticated,)
    queryset = Note.objects.current()
    serializer_class = NoteSerializer

class ConditionCategoryView(viewsets.ReadOnlyModelViewSet):
    permission_classes = (permissions.IsAuthenticated,)
    queryset = ConditionCategory.objects.current().filter(public=True)
    serializer_class = ConditionCategorySerializer

class ModelConditionView(viewsets.ReadOnlyModelViewSet):
    permission_classes = (permissions.IsAuthenticated,)
    queryset = ModelCondition.objects.current()
    serializer_class = ModelConditionSerializer

class ConditionView(viewsets.ReadOnlyModelViewSet):
    permission_classes = (permissions.IsAuthenticated,)
    queryset = Condition.objects.current()
    serializer_class = ConditionSerializer
    

class ClearanceView(viewsets.ReadOnlyModelViewSet):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = ClearanceSerializer
    pagination_class = StandardResultsSetPagination
    def get_queryset(self):
        queryset = Clearance.objects.all()
        region = self.request.query_params.get('task__referral__regions__id__in', None)
        referring_org = self.request.query_params.get('task__referral__referring_org__id', None)
        status = self.request.query_params.get('task__state__id', None)
        start_date_gte = self.request.query_params.get('task__start_date__gte', None)
        start_date_lte = self.request.query_params.get('task__start_date__lte', None)
        start = self.request.query_params.get('start', None)
        length = self.request.query_params.get('length',None)
        if region is not None:
            queryset = queryset.filter(task__referral__regions__id__in=region)
        if referring_org is not None:
            queryset = queryset.filter(task__referral__referring_org__id=referring_org)
        if status is not None:
            queryset = queryset.filter(task__state__id__in=status)
        if start_date_gte is not None:
            date_after = datetime.strptime(start_date_gte, "%Y-%m-%d").date()
            queryset = queryset.filter(date_created__gte=date_after)
        if start_date_lte is not None:
            date_before = datetime.strptime(start_date_lte, "%Y-%m-%d").date()
            queryset = queryset.filter(date_created__lte=date_before)
        queryset = self.get_serializer_class().setup_eager_loading(queryset)
        return queryset

class LocationView(viewsets.ReadOnlyModelViewSet):
    permission_classes = (permissions.IsAuthenticated,)
    queryset = Location.objects.current()
    serializer_class = LocationSerializer

class UserProfileView(viewsets.ReadOnlyModelViewSet):
    permission_classes = (permissions.IsAuthenticated,)
    queryset = UserProfile.objects.all()
    serializer_class = UserProfileSerializer

class GroupView(viewsets.ReadOnlyModelViewSet):
    permission_classes = (permissions.IsAuthenticated,)
    queryset = Group.objects.all()
    serializer_class = GroupSerializer

class UserView(viewsets.ReadOnlyModelViewSet):
    permission_classes = (permissions.IsAuthenticated,)
    try:
        # Queryset should only return active users in the "PRS user" group.
        prs_user = Group.objects.get_or_create(name=settings.PRS_USER_GROUP)[0]
        queryset = User.objects.filter(groups__in=[prs_user], is_active=True)
    except:
        queryset = User.objects.all()
    serializer_class = UserSerializer

class TagView(viewsets.ReadOnlyModelViewSet):
    permission_classes = (permissions.IsAuthenticated,)
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
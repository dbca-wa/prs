from rest_framework import serializers
from referral.models import (
    DopTrigger, Region, OrganisationType, Organisation, TaskState, TaskType,
    ReferralType, NoteType, Agency, Referral, Task, Record, Note, Condition,
    ConditionCategory, Clearance, Location, UserProfile, ModelCondition)
from taggit.models import Tag
from django.contrib.auth.models import User, Group


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        exclude = (
            'password', 'date_joined', 'is_staff', 'is_superuser', 'last_login', 'groups',
            'user_permissions')


class DopTriggerSerializer(serializers.ModelSerializer):
    class Meta:
        model = DopTrigger
        exclude = (
            'created', 'effective_to', 'modified', 'creator', 'modifier', 'public', 'description')


class RegionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Region
        exclude = (
            'created', 'effective_to', 'modified', 'creator', 'modifier', 'public', 'region_mpoly')


class OrganisationTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrganisationType
        exclude = ('created', 'effective_to', 'modified', 'creator', 'modifier', 'public')


class OrganisationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organisation
        exclude = ('created', 'effective_to', 'modified', 'creator', 'modifier', 'public')


class TaskStateSerializer(serializers.ModelSerializer):

    class Meta:
        model = TaskState
        exclude = ('created', 'effective_to', 'modified', 'creator', 'modifier', 'public')


class TaskTypeSerializer(serializers.ModelSerializer):
    initial_state = TaskStateSerializer(read_only=True)

    class Meta:
        model = TaskType
        exclude = ('created', 'effective_to', 'modified', 'creator', 'modifier', 'public')


class ReferralTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReferralType
        exclude = ('created', 'effective_to', 'modified', 'creator', 'modifier', 'public')


class NoteTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = NoteType
        exclude = ('created', 'effective_to', 'modified', 'creator', 'modifier', 'public')


class AgencySerializer(serializers.ModelSerializer):
    class Meta:
        model = Agency
        exclude = ('created', 'effective_to', 'modified', 'creator', 'modifier', 'public')


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        exclude = ()  # Required.


class TagListSerializer(serializers.Field):
    def to_representation(Self, data):
        return data.names()


class ReferralSerializer(serializers.ModelSerializer):
    tags = TagListSerializer(read_only=True)
    regions_str = serializers.ReadOnlyField()
    referring_org = serializers.StringRelatedField()
    type = serializers.StringRelatedField()

    class Meta:
        model = Referral
        exclude = ('created', 'effective_to', 'modified', 'creator', 'modifier')

    @staticmethod
    def setup_eager_loading(queryset):
        """
        Loads related items to speed up search"""
        queryset = queryset.prefetch_related('tags')
        queryset = queryset.select_related('referring_org')
        queryset = queryset.select_related('type')
        return queryset


class FullNameUserField(serializers.StringRelatedField):
    def to_representation(self, data):
        return data.first_name + " " + data.last_name


class TaskSerializer(serializers.ModelSerializer):
    referral = ReferralSerializer(read_only=True)
    assigned_user = FullNameUserField()
    state = serializers.StringRelatedField()
    type = serializers.StringRelatedField()

    class Meta:
        model = Task
        exclude = ('created', 'effective_to', 'modified', 'creator', 'modifier')

    @staticmethod
    def setup_eager_loading(queryset):
        queryset = queryset.prefetch_related('referral')
        queryset = queryset.select_related('state')
        queryset = queryset.select_related('type')
        return queryset


class RecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = Record
        exclude = ('created', 'effective_to', 'modified', 'creator', 'modifier')


class NoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Note
        exclude = ('created', 'effective_to', 'modified', 'creator', 'modifier', 'note_html')
        exclude = ('created', 'effective_to', 'modified', 'note_html')


class ConditionCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ConditionCategory
        exclude = ('created', 'effective_to', 'modified', 'creator', 'modifier')


class ModelConditionSerializer(serializers.ModelSerializer):
    category = ConditionCategorySerializer(read_only=True)

    class Meta:
        model = ModelCondition
        exclude = ('created', 'effective_to', 'modified', 'creator', 'modifier')


class ConditionSerializer(serializers.ModelSerializer):
    category = serializers.StringRelatedField()

    class Meta:
        model = Condition
        exclude = (
            'created', 'effective_to', 'modified', 'creator', 'modifier',
            'proposed_condition_html', 'condition_html')


class ClearanceSerializer(serializers.ModelSerializer):
    task = TaskSerializer(read_only=True)
    condition = ConditionSerializer(read_only=True)

    class Meta:
        model = Clearance
        exclude = ()

    @staticmethod
    def setup_eager_loading(queryset):
        queryset = queryset.prefetch_related('task')
        queryset = queryset.prefetch_related('condition')
        return queryset


class LocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Location
        exclude = ('created', 'effective_to', 'modified', 'creator', 'modifier')


class UserProfileSerializer(serializers.ModelSerializer):
    user = 'referral.serializer.UserSerializer(read_only=True)'

    class Meta:
        model = UserProfile
        exclude = ()


class GroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        exclude = ('permissions',)

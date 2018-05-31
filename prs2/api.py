from django.conf import settings
from referral import api as referral_api
from taggit.models import Tag
from tastypie.api import Api
from tastypie.authentication import SessionAuthentication
from tastypie.cache import SimpleCache
from tastypie.resources import ModelResource, ALL
from django.contrib.auth.models import User, Group
from django.db import ProgrammingError

v1_api = Api(api_name='v1')
v1_api.register(referral_api.DopTriggerResource())
v1_api.register(referral_api.RegionResource())
v1_api.register(referral_api.OrganisationTypeResource())
v1_api.register(referral_api.OrganisationResource())
v1_api.register(referral_api.TaskStateResource())
v1_api.register(referral_api.TaskTypeResource())
v1_api.register(referral_api.ReferralTypeResource())
v1_api.register(referral_api.NoteTypeResource())
v1_api.register(referral_api.AgencyResource())
v1_api.register(referral_api.ReferralResource())
v1_api.register(referral_api.TaskResource())
v1_api.register(referral_api.RecordResource())
v1_api.register(referral_api.NoteResource())
v1_api.register(referral_api.ConditionCategoryResource())
v1_api.register(referral_api.ModelConditionResource())
v1_api.register(referral_api.ConditionResource())
v1_api.register(referral_api.ClearanceResource())
v1_api.register(referral_api.LocationResource())
v1_api.register(referral_api.UserProfileResource())


# Register the contrib.auth.models models as resources.
class GroupResource(ModelResource):

    class Meta:
        queryset = Group.objects.all()
        ordering = ['name']
        cache = SimpleCache()
        filtering = {'id': ALL, 'name': ALL}
        authentication = SessionAuthentication()


v1_api.register(GroupResource())


class UserResource(ModelResource):
    class Meta:
        try:
            # Queryset should only return active users in the "PRS user" group.
            prs_user = Group.objects.get_or_create(name=settings.PRS_USER_GROUP)[0]
            queryset = User.objects.filter(groups__in=[prs_user], is_active=True)
        except ProgrammingError:
            queryset = User.objects.all()
        ordering = ['username']
        excludes = ['password', 'date_joined', 'is_staff', 'is_superuser', 'last_login']
        filtering = {
            'email': ALL,
            'first_name': ALL,
            'id': ALL,
            'last_name': ALL,
            'username': ALL,
            'is_active': ALL,
        }
        cache = SimpleCache()
        authentication = SessionAuthentication()


v1_api.register(UserResource())


class TagResource(ModelResource):
    class Meta:
        queryset = Tag.objects.all()
        ordering = ['name']
        filtering = {'id': ALL, 'name': ALL, 'slug': ALL}
        cache = SimpleCache()
        authentication = SessionAuthentication()


v1_api.register(TagResource())

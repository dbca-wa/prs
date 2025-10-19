from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from referral.models import UserProfile


@receiver(user_logged_in)
def user_create_userprofile(sender, **kwargs):
    # Ensure that a UserProfile object exists for a user.
    UserProfile.objects.get_or_create(user=kwargs["user"])

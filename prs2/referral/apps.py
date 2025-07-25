from django.apps import AppConfig


class ReferralConfig(AppConfig):
    default_auto_field = "django.db.models.AutoField"
    name = "referral"

    def ready(self):
        # Import module signals.
        from referral import signals

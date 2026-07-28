import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class Subscription(models.Model):
    TRIALING = "trialing"
    ACTIVE = "active"
    CANCELED = "canceled"
    EXPIRED = "expired"

    PLAN_CHOICES = [("monthly", "Monthly"), ("yearly", "Yearly")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="subscription"
    )
    status = models.CharField(
        max_length=20,
        default=TRIALING,
        choices=[(TRIALING, "Trialing"), (ACTIVE, "Active"), (CANCELED, "Canceled")],
    )
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES, blank=True, null=True)
    trial_end = models.DateTimeField(blank=True, null=True)
    current_period_end = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def effective_status(self):
        if self.status == self.TRIALING and self.trial_end and self.trial_end < timezone.now():
            return self.EXPIRED
        return self.status

    def activate(self, plan, period_end):
        self.status = self.ACTIVE
        self.plan = plan
        self.current_period_end = period_end
        self.save()

    def cancel(self):
        self.status = self.CANCELED
        self.save()

    def extend_trial(self, days):
        baseline = self.trial_end if self.trial_end and self.trial_end > timezone.now() else timezone.now()
        self.status = self.TRIALING
        self.trial_end = baseline + timezone.timedelta(days=days)
        self.save()

    def __str__(self):
        return f"{self.user.email} — {self.effective_status}"

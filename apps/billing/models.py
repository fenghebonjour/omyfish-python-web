import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class Subscription(models.Model):
    TRIALING = "trialing"
    ACTIVE = "active"
    PAST_DUE = "past_due"
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
        choices=[
            (TRIALING, "Trialing"),
            (ACTIVE, "Active"),
            (PAST_DUE, "Past due"),
            (CANCELED, "Canceled"),
        ],
    )
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES, blank=True, null=True)
    trial_end = models.DateTimeField(blank=True, null=True)
    current_period_end = models.DateTimeField(blank=True, null=True)
    # Named after Stripe for historical reasons (this field existed before multi-processor
    # support), but holds whichever processor's customer/subscription id per payment_processor.
    stripe_customer_id = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    stripe_subscription_id = models.CharField(max_length=255, blank=True, null=True)
    payment_processor = models.CharField(max_length=20, blank=True, null=True)  # stripe|paypal|adyen
    # Adyen has no subscription object, so refunding it needs the pspReference of the last
    # captured payment rather than a subscription id — unused by Stripe/PayPal, which look up
    # the latest payment from their own subscription object instead.
    last_payment_reference = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def effective_status(self):
        if self.status == self.TRIALING and self.trial_end and self.trial_end < timezone.now():
            return self.EXPIRED
        return self.status

    def activate(self, plan, period_end, stripe_subscription_id=None):
        self.status = self.ACTIVE
        self.plan = plan
        self.current_period_end = period_end
        if stripe_subscription_id:
            self.stripe_subscription_id = stripe_subscription_id
        self.save()

    def attach_processor(self, processor, customer_id, subscription_id):
        """Records a processor's ids as soon as they're known, without changing status."""
        self.payment_processor = processor
        self.stripe_customer_id = customer_id
        self.stripe_subscription_id = subscription_id
        self.save()

    def attach_processor_customer_id(self, processor, customer_id):
        """Records the processor customer id alone, e.g. after tokenizing a payment method
        pre-checkout, when there's no subscription id yet.
        """
        self.payment_processor = processor
        self.stripe_customer_id = customer_id
        self.save()

    def record_last_payment_reference(self, reference):
        self.last_payment_reference = reference
        self.save()

    def mark_past_due(self):
        """Stripe keeps retrying a failed renewal for days before actually canceling —
        collapsing straight to cancel() here would cut off a still-maybe-paying customer
        too early.
        """
        self.status = self.PAST_DUE
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


class IdempotencyRecord(models.Model):
    """Guards checkout/refund against a retried request (the same Idempotency-Key header)
    re-entering the service and calling the payment processor again. Mirrors the Java/dotnet
    siblings' IdempotencyRecord — a row reserved before calling the processor, completed (or
    deleted) after, with a stale/incomplete reservation retried rather than orphaned forever
    (see services.is_orphaned).
    """

    CHECKOUT = "checkout"
    REFUND = "refund"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    key = models.CharField(max_length=255)
    endpoint = models.CharField(max_length=20, choices=[(CHECKOUT, "Checkout"), (REFUND, "Refund")])
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    # Checkout result
    customer_id = models.CharField(max_length=255, blank=True, null=True)
    subscription_id = models.CharField(max_length=255, blank=True, null=True)
    client_secret = models.TextField(blank=True, null=True)
    checkout_status = models.CharField(max_length=40, blank=True, null=True)

    # Refund result
    refund_id = models.CharField(max_length=255, blank=True, null=True)
    refund_status = models.CharField(max_length=40, blank=True, null=True)
    amount_cents = models.BigIntegerField(blank=True, null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["key", "endpoint"], name="uniq_idempotency_key_endpoint")
        ]

    def is_stale(self, max_age):
        return timezone.now() - self.created_at > max_age

    def complete_checkout(self, customer_id, subscription_id, client_secret, checkout_status):
        self.customer_id = customer_id
        self.subscription_id = subscription_id
        self.client_secret = client_secret
        self.checkout_status = checkout_status
        self.completed = True
        self.save()

    def complete_refund(self, refund_id, refund_status, amount_cents):
        self.refund_id = refund_id
        self.refund_status = refund_status
        self.amount_cents = amount_cents
        self.completed = True
        self.save()


class ProcessedWebhookEvent(models.Model):
    """Dedups a redelivered webhook — keyed by the provider's own event id, checked before
    re-applying an event's effects so a redelivery is a no-op.
    """

    event_id = models.CharField(max_length=255, primary_key=True)
    created_at = models.DateTimeField(auto_now_add=True)

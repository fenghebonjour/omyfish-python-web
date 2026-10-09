from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.models import User

from . import services
from .gateways import registry
from .gateways.base import PaymentEvent, ReconciliationCandidate, RefundResult, SetupIntentResult, SubscriptionIntent
from .models import IdempotencyRecord, ProcessedWebhookEvent, Subscription


class FakeGateway:
    """A PaymentGateway test double — mirrors the NSubstitute/Mockito mocks the Java/dotnet
    siblings use for IPaymentGateway/PaymentPort, since this project has no Stripe/PayPal/Adyen
    test credentials to exercise the real gateways against.
    """

    def __init__(self, name="stripe", configured=True):
        self.name = name
        self._configured = configured
        self.subscription_intent = None
        self.setup_intent = None
        self.refund_result = None
        self.portal_url = None
        self.recent_subscriptions = []
        self.set_default_payment_method_calls = []
        self.create_subscription_intent_calls = []
        self.refund_subscription_calls = []

    def is_configured(self):
        return self._configured

    def create_subscription_intent(self, user, plan, idempotency_key):
        self.create_subscription_intent_calls.append((user, plan, idempotency_key))
        return self.subscription_intent

    def create_setup_intent(self, user):
        return self.setup_intent

    def set_default_payment_method(self, customer_id, payment_method_id):
        self.set_default_payment_method_calls.append((customer_id, payment_method_id))

    def refund_subscription(self, subscription_id, amount_cents, idempotency_key, last_payment_reference=None):
        self.refund_subscription_calls.append(
            (subscription_id, amount_cents, idempotency_key, last_payment_reference)
        )
        return self.refund_result

    def verify_webhook(self, payload, headers):
        return None

    def list_recent_subscriptions(self, since):
        return self.recent_subscriptions

    def create_portal_session(self, customer_id, return_url):
        return self.portal_url


class BillingServiceTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="billing-test@example.com", password="x")
        self.gateway = FakeGateway()


class StartCheckoutTests(BillingServiceTestCase):
    def test_no_gateway_configured_returns_none(self):
        with patch.object(registry, "default_gateway", return_value=None):
            result = services.start_checkout(self.user, "monthly", "idem-1")
        self.assertIsNone(result)

    def test_valid_plan_attaches_processor_without_activating(self):
        self.gateway.subscription_intent = SubscriptionIntent("stripe", "cus_123", "sub_456", "secret_abc", "incomplete")
        with patch.object(registry, "default_gateway", return_value=self.gateway):
            intent = services.start_checkout(self.user, "yearly", "idem-1")

        self.assertEqual(intent.client_secret, "secret_abc")
        subscription = Subscription.objects.get(user=self.user)
        self.assertEqual(subscription.stripe_customer_id, "cus_123")
        self.assertEqual(subscription.stripe_subscription_id, "sub_456")
        self.assertEqual(subscription.effective_status, "trialing")

    def test_gateway_returning_none_deletes_reservation(self):
        self.gateway.subscription_intent = None
        with patch.object(registry, "default_gateway", return_value=self.gateway):
            result = services.start_checkout(self.user, "monthly", "idem-1")

        self.assertIsNone(result)
        self.assertFalse(IdempotencyRecord.objects.filter(key="idem-1").exists())

    def test_completed_idempotency_key_replays_without_calling_gateway(self):
        record = IdempotencyRecord.objects.create(key="idem-1", endpoint=IdempotencyRecord.CHECKOUT, user=self.user)
        record.complete_checkout("cus_123", "sub_456", "secret_abc", "incomplete")

        with patch.object(registry, "default_gateway", return_value=self.gateway):
            intent = services.start_checkout(self.user, "yearly", "idem-1")

        self.assertEqual(intent.client_secret, "secret_abc")
        self.assertEqual(self.gateway.create_subscription_intent_calls, [])

    def test_in_progress_idempotency_key_raises_conflict(self):
        IdempotencyRecord.objects.create(key="idem-1", endpoint=IdempotencyRecord.CHECKOUT, user=self.user)

        with self.assertRaises(services.IdempotencyConflictError):
            services.start_checkout(self.user, "yearly", "idem-1")

    def test_idempotency_key_used_by_another_user_raises(self):
        other_user = User.objects.create_user(email="other@example.com", password="x")
        record = IdempotencyRecord.objects.create(key="idem-1", endpoint=IdempotencyRecord.CHECKOUT, user=other_user)
        record.complete_checkout("cus_123", "sub_456", "secret_abc", "incomplete")

        with self.assertRaises(ValueError):
            services.start_checkout(self.user, "yearly", "idem-1")

    def test_already_active_subscription_raises_without_calling_gateway(self):
        subscription = services.get_or_start_trial(self.user)
        subscription.attach_processor("stripe", "cus_123", "sub_456")
        subscription.activate("monthly", timezone.now() + timezone.timedelta(days=30))

        with patch.object(registry, "default_gateway", return_value=self.gateway):
            with self.assertRaises(services.AlreadySubscribedError):
                services.start_checkout(self.user, "yearly", "idem-1")
        self.assertEqual(self.gateway.create_subscription_intent_calls, [])

    def test_already_past_due_subscription_raises(self):
        subscription = services.get_or_start_trial(self.user)
        subscription.attach_processor("stripe", "cus_123", "sub_456")
        subscription.activate("monthly", timezone.now() + timezone.timedelta(days=30))
        subscription.mark_past_due()

        with self.assertRaises(services.AlreadySubscribedError):
            services.start_checkout(self.user, "yearly", "idem-1")

    def test_trialing_with_no_processor_attached_is_unaffected(self):
        services.get_or_start_trial(self.user)
        self.gateway.subscription_intent = SubscriptionIntent("stripe", "cus_123", "sub_456", "secret_abc", "incomplete")

        with patch.object(registry, "default_gateway", return_value=self.gateway):
            intent = services.start_checkout(self.user, "monthly", "idem-1")

        self.assertIsNotNone(intent)


class StartPaymentMethodSetupTests(BillingServiceTestCase):
    def test_no_gateway_configured_returns_none(self):
        with patch.object(registry, "default_gateway", return_value=None):
            self.assertIsNone(services.start_payment_method_setup(self.user))

    def test_attaches_customer_id(self):
        self.gateway.setup_intent = SetupIntentResult("stripe", "cus_123", "secret_abc")
        with patch.object(registry, "default_gateway", return_value=self.gateway):
            intent = services.start_payment_method_setup(self.user)

        self.assertEqual(intent.client_secret, "secret_abc")
        subscription = Subscription.objects.get(user=self.user)
        self.assertEqual(subscription.stripe_customer_id, "cus_123")


class RefundServiceTests(BillingServiceTestCase):
    def test_no_subscription_raises_does_not_exist(self):
        with self.assertRaises(Subscription.DoesNotExist):
            services.refund(self.user, 500, "idem-1")

    def test_no_processor_subscription_id_raises(self):
        services.get_or_start_trial(self.user)
        with self.assertRaises(services.NoProcessorCustomerError):
            services.refund(self.user, 500, "idem-1")

    def test_passes_last_payment_reference_to_gateway(self):
        subscription = services.get_or_start_trial(self.user)
        subscription.attach_processor("adyen", "cus_123", "ref_456")
        subscription.record_last_payment_reference("psp_789")
        self.gateway.name = "adyen"
        self.gateway.refund_result = RefundResult("re_1", "succeeded", 500)

        with patch.object(registry, "by_name", return_value=self.gateway):
            result = services.refund(self.user, 500, "idem-1")

        self.assertEqual(result.refund_id, "re_1")
        self.assertEqual(self.gateway.refund_subscription_calls, [("ref_456", 500, "idem-1", "psp_789")])

    def test_gateway_returning_none_deletes_reservation(self):
        subscription = services.get_or_start_trial(self.user)
        subscription.attach_processor("stripe", "cus_123", "sub_456")
        self.gateway.refund_result = None

        with patch.object(registry, "by_name", return_value=self.gateway):
            result = services.refund(self.user, 500, "idem-1")

        self.assertIsNone(result)
        self.assertFalse(IdempotencyRecord.objects.filter(key="idem-1").exists())

    def test_completed_idempotency_key_replays_without_calling_gateway(self):
        subscription = services.get_or_start_trial(self.user)
        subscription.attach_processor("stripe", "cus_123", "sub_456")
        record = IdempotencyRecord.objects.create(key="idem-1", endpoint=IdempotencyRecord.REFUND, user=self.user)
        record.complete_refund("re_1", "succeeded", 500)

        with patch.object(registry, "by_name", return_value=self.gateway):
            result = services.refund(self.user, 500, "idem-1")

        self.assertEqual(result.refund_id, "re_1")
        self.assertEqual(self.gateway.refund_subscription_calls, [])


class CreatePortalSessionTests(BillingServiceTestCase):
    def test_no_subscription_raises_does_not_exist(self):
        with self.assertRaises(Subscription.DoesNotExist):
            services.create_portal_session(self.user, "https://app.example.com/account")

    def test_no_customer_id_on_file_raises(self):
        services.get_or_start_trial(self.user)
        with self.assertRaises(services.NoProcessorCustomerError):
            services.create_portal_session(self.user, "https://app.example.com/account")

    def test_delegates_to_gateway(self):
        subscription = services.get_or_start_trial(self.user)
        subscription.attach_processor("stripe", "cus_123", "sub_456")
        self.gateway.portal_url = "https://billing.stripe.com/session/abc"

        with patch.object(registry, "by_name", return_value=self.gateway):
            url = services.create_portal_session(self.user, "https://app.example.com/account")

        self.assertEqual(url, "https://billing.stripe.com/session/abc")


class ApplyEventTests(BillingServiceTestCase):
    def test_subscription_deleted_cancels(self):
        subscription = services.get_or_start_trial(self.user)
        subscription.attach_processor("stripe", "cus_123", "sub_456")
        subscription.activate("monthly", None)

        handled = services.apply_event(PaymentEvent(
            type="subscription_deleted", customer_id="cus_123", subscription_id="sub_456"
        ))

        subscription.refresh_from_db()
        self.assertTrue(handled)
        self.assertEqual(subscription.effective_status, "canceled")

    def test_subscription_updated_plan_on_event_overwrites_stored_plan(self):
        # A Portal-initiated upgrade must actually change the stored plan — Java found this bug
        # in two separate adapters (the event carried the new plan but nothing read it).
        subscription = services.get_or_start_trial(self.user)
        subscription.attach_processor("stripe", "cus_123", "sub_456")
        subscription.activate("monthly", None)

        services.apply_event(PaymentEvent(
            type="subscription_updated", customer_id="cus_123", subscription_id="sub_456",
            plan="yearly", provider_status="active",
        ))

        subscription.refresh_from_db()
        self.assertEqual(subscription.plan, "yearly")

    def test_subscription_updated_no_plan_on_event_keeps_stored_plan(self):
        subscription = services.get_or_start_trial(self.user)
        subscription.attach_processor("stripe", "cus_123", "sub_456")
        subscription.activate("monthly", None)

        services.apply_event(PaymentEvent(
            type="subscription_updated", customer_id="cus_123", subscription_id="sub_456",
            provider_status="active",
        ))

        subscription.refresh_from_db()
        self.assertEqual(subscription.plan, "monthly")

    def test_payment_method_attached_delegates_to_gateway(self):
        with patch.object(registry, "by_name", return_value=self.gateway):
            handled = services.apply_event(PaymentEvent(
                type="payment_method_attached", customer_id="cus_123",
                payment_method_id="pm_456", processor="stripe",
            ))

        self.assertTrue(handled)
        self.assertEqual(self.gateway.set_default_payment_method_calls, [("cus_123", "pm_456")])

    def test_payment_captured_records_last_payment_reference(self):
        subscription = services.get_or_start_trial(self.user)
        subscription.attach_processor("adyen", "cus_123", "ref_456")

        handled = services.apply_event(PaymentEvent(
            type="payment_captured", customer_id="cus_123", processor="adyen", payment_reference="psp_789"
        ))

        subscription.refresh_from_db()
        self.assertTrue(handled)
        self.assertEqual(subscription.last_payment_reference, "psp_789")

    def test_payment_captured_unknown_customer_returns_false(self):
        handled = services.apply_event(PaymentEvent(
            type="payment_captured", customer_id="cus_unknown", processor="adyen", payment_reference="psp_789"
        ))
        self.assertFalse(handled)

    def test_payment_failed_marks_past_due(self):
        subscription = services.get_or_start_trial(self.user)
        subscription.attach_processor("stripe", "cus_123", "sub_456")
        subscription.activate("monthly", None)

        handled = services.apply_event(PaymentEvent(type="payment_failed", customer_id="cus_123", subscription_id="sub_456"))

        subscription.refresh_from_db()
        self.assertTrue(handled)
        self.assertEqual(subscription.effective_status, "past_due")

    def test_duplicate_event_id_skips_reprocessing(self):
        ProcessedWebhookEvent.objects.create(event_id="evt_dup")

        with patch.object(registry, "by_name", return_value=self.gateway):
            handled = services.apply_event(PaymentEvent(
                type="payment_method_attached", customer_id="cus_123",
                payment_method_id="pm_456", event_id="evt_dup",
            ))

        self.assertTrue(handled)
        self.assertEqual(self.gateway.set_default_payment_method_calls, [])

    def test_new_event_id_recorded_after_handling(self):
        with patch.object(registry, "by_name", return_value=self.gateway):
            services.apply_event(PaymentEvent(
                type="payment_method_attached", customer_id="cus_123",
                payment_method_id="pm_456", event_id="evt_new",
            ))

        self.assertTrue(ProcessedWebhookEvent.objects.filter(event_id="evt_new").exists())

    def test_unknown_customer_returns_false(self):
        handled = services.apply_event(PaymentEvent(type="subscription_updated", customer_id="cus_ghost"))
        self.assertFalse(handled)


class ReconcileServiceTests(BillingServiceTestCase):
    def test_relinks_mismatched_row_and_resyncs_status(self):
        subscription = services.get_or_start_trial(self.user)
        self.gateway.recent_subscriptions = [
            ReconciliationCandidate(
                processor="stripe", user_id=str(self.user.id), customer_id="cus_123",
                subscription_id="sub_456", plan="monthly", provider_status="active", period_end=None,
            )
        ]

        with patch.object(registry, "configured", return_value=[self.gateway]):
            result = services.reconcile(timezone.now() - timezone.timedelta(hours=24))

        subscription.refresh_from_db()
        self.assertEqual(result["checked"], 1)
        self.assertEqual(len(result["repaired"]), 1)
        self.assertEqual(subscription.stripe_customer_id, "cus_123")
        self.assertEqual(subscription.effective_status, "active")

    def test_candidate_with_no_user_id_is_skipped_with_error(self):
        self.gateway.recent_subscriptions = [
            ReconciliationCandidate(
                processor="stripe", user_id=None, customer_id="cus_123",
                subscription_id="sub_456", plan="monthly", provider_status="active", period_end=None,
            )
        ]

        with patch.object(registry, "configured", return_value=[self.gateway]):
            result = services.reconcile(timezone.now() - timezone.timedelta(hours=24))

        self.assertEqual(result["checked"], 1)
        self.assertEqual(result["repaired"], [])
        self.assertEqual(len(result["errors"]), 1)

    def test_gateway_list_failure_recorded_as_error_not_raised(self):
        class BrokenGateway(FakeGateway):
            def list_recent_subscriptions(self, since):
                raise RuntimeError("boom")

        with patch.object(registry, "configured", return_value=[BrokenGateway()]):
            result = services.reconcile(timezone.now() - timezone.timedelta(hours=24))

        self.assertEqual(result["checked"], 0)
        self.assertEqual(len(result["errors"]), 1)

    def test_already_linked_row_is_not_reported_as_repaired(self):
        subscription = services.get_or_start_trial(self.user)
        subscription.attach_processor("stripe", "cus_123", "sub_456")
        self.gateway.recent_subscriptions = [
            ReconciliationCandidate(
                processor="stripe", user_id=str(self.user.id), customer_id="cus_123",
                subscription_id="sub_456", plan="monthly", provider_status="active", period_end=None,
            )
        ]

        with patch.object(registry, "configured", return_value=[self.gateway]):
            result = services.reconcile(timezone.now() - timezone.timedelta(hours=24))

        self.assertEqual(result["repaired"], [])


class CheckoutViewTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="checkout-view@example.com", password="TestPass123!")
        login = self.client.post(
            "/api/v1/auth/login", {"email": "checkout-view@example.com", "password": "TestPass123!"}, format="json"
        )
        self.token = login.data["token"]

    def _auth(self):
        return {"HTTP_AUTHORIZATION": f"Bearer {self.token}"}

    def test_missing_idempotency_key_is_rejected(self):
        response = self.client.post(
            "/api/v1/billing/checkout", {"plan": "monthly"}, format="json", **self._auth()
        )
        self.assertEqual(response.status_code, 400)

    def test_no_processor_configured_returns_503(self):
        response = self.client.post(
            "/api/v1/billing/checkout", {"plan": "monthly"}, format="json",
            HTTP_IDEMPOTENCY_KEY="idem-1", **self._auth()
        )
        self.assertEqual(response.status_code, 503)

    def test_requires_auth(self):
        response = self.client.post(
            "/api/v1/billing/checkout", {"plan": "monthly"}, format="json", HTTP_IDEMPOTENCY_KEY="idem-1"
        )
        self.assertEqual(response.status_code, 401)


class WebhookViewTests(APITestCase):
    def test_unknown_processor_returns_404(self):
        response = self.client.post("/api/v1/billing/webhook/bogus", {}, format="json")
        self.assertEqual(response.status_code, 404)

    def test_unconfigured_processor_returns_503(self):
        # No test credentials for any processor are set, so every known processor name is
        # reachable (AllowAny) but unconfigured.
        response = self.client.post("/api/v1/billing/webhook/stripe", {}, format="json")
        self.assertEqual(response.status_code, 503)


class PortalSessionViewTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="portal-view@example.com", password="TestPass123!")
        login = self.client.post(
            "/api/v1/auth/login", {"email": "portal-view@example.com", "password": "TestPass123!"}, format="json"
        )
        self.token = login.data["token"]

    def test_no_subscription_returns_404(self):
        response = self.client.post(
            "/api/v1/billing/portal-session", {"returnUrl": "https://app.example.com/account"},
            format="json", HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 404)

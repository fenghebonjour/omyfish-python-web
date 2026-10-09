import threading
from datetime import datetime, timedelta, timezone

import requests
from django.conf import settings

from .base import PaymentEvent, RefundResult, SetupIntentResult, SubscriptionIntent


class PayPalGateway:
    """Direct PayPal integration (Subscriptions + Vault APIs) via plain `requests` — PayPal has
    no first-party Python SDK worth depending on for this, same reasoning as the Java/dotnet
    siblings' hand-rolled REST adapters. A sibling gateway to StripeGateway behind the same
    PaymentGateway shape, not a Stripe payment method.

    Model differences from Stripe, by necessity rather than by choice:
     - No client-secret concept: SubscriptionIntent/SetupIntentResult's client_secret slot
       instead carries the "approve" link the frontend must redirect the shopper to.
     - customer_id is unknown at subscription-creation time (PayPal only assigns a payer_id
       once the shopper approves) — it starts empty and is filled in by the ACTIVATED webhook,
       the same way Stripe's own webhook refines state after creation.
     - set_default_payment_method is a no-op: PayPal's Vault API has no customer-level "default
       payment method" pointer the way Stripe does.
    """

    name = "paypal"

    def __init__(self):
        self._session = requests.Session()
        self._token_lock = threading.Lock()
        self._cached_token = None
        self._token_expiry = None

    def is_configured(self):
        return bool(settings.PAYPAL_CLIENT_ID) and bool(settings.PAYPAL_CLIENT_SECRET)

    def _plan_ids(self):
        return {"monthly": settings.PAYPAL_PLAN_MONTHLY, "yearly": settings.PAYPAL_PLAN_YEARLY}

    def _access_token(self):
        with self._token_lock:
            if self._cached_token and datetime.now(timezone.utc) < self._token_expiry:
                return self._cached_token

        response = self._session.post(
            f"{settings.PAYPAL_BASE_URL}/v1/oauth2/token",
            data={"grant_type": "client_credentials"},
            auth=(settings.PAYPAL_CLIENT_ID, settings.PAYPAL_CLIENT_SECRET),
            timeout=15,
        )
        response.raise_for_status()
        body = response.json()

        with self._token_lock:
            self._cached_token = body["access_token"]
            self._token_expiry = datetime.now(timezone.utc) + timedelta(
                seconds=max(0, body["expires_in"] - 60)
            )
            return self._cached_token

    def create_subscription_intent(self, user, plan, idempotency_key):
        plan_id = self._plan_ids().get(plan)
        if not plan_id or not self.is_configured() or not settings.PAYPAL_RETURN_URL or not settings.PAYPAL_CANCEL_URL:
            return None

        response = self._session.post(
            f"{settings.PAYPAL_BASE_URL}/v1/billing/subscriptions",
            json={
                "plan_id": plan_id,
                "subscriber": {"email_address": user.email},
                "application_context": {
                    "return_url": settings.PAYPAL_RETURN_URL,
                    "cancel_url": settings.PAYPAL_CANCEL_URL,
                },
            },
            headers={
                "Authorization": f"Bearer {self._access_token()}",
                "PayPal-Request-Id": idempotency_key,
            },
            timeout=15,
        )
        response.raise_for_status()
        body = response.json()
        # customer_id left blank: PayPal only assigns a payer_id once the shopper approves;
        # the ACTIVATED webhook fills it in.
        return SubscriptionIntent(
            self.name, "", body["id"], self._approve_link(body.get("links")), body["status"]
        )

    def create_setup_intent(self, user):
        if not self.is_configured():
            return None

        # Creates a Vault setup token for the PayPal wallet; the frontend's PayPal JS SDK
        # completes it (exchanges it for a reusable payment token) after the shopper approves,
        # the same way Stripe.js completes a SetupIntent client-side.
        response = self._session.post(
            f"{settings.PAYPAL_BASE_URL}/v3/vault/setup-tokens",
            json={
                "payment_source": {
                    "paypal": {
                        "usage_pattern": "IMMEDIATE",
                        "usage_type": "MERCHANT",
                        "customer_type": "CONSUMER",
                        "permit_multiple_payment_tokens": False,
                        "experience_context": {
                            "return_url": settings.PAYPAL_RETURN_URL,
                            "cancel_url": settings.PAYPAL_CANCEL_URL,
                        },
                    }
                }
            },
            headers={"Authorization": f"Bearer {self._access_token()}"},
            timeout=15,
        )
        response.raise_for_status()
        body = response.json()
        return SetupIntentResult(self.name, "", self._approve_link(body.get("links")) or "")

    def set_default_payment_method(self, customer_id, payment_method_id):
        # No-op: PayPal's Vault API has no customer-level "default payment method" the way
        # Stripe does — the payment-token id is referenced directly on each future charge.
        pass

    def refund_subscription(self, subscription_id, amount_cents, idempotency_key, last_payment_reference=None):
        if not self.is_configured() or not subscription_id:
            return None

        token = self._access_token()
        now = datetime.now(timezone.utc)
        transactions_response = self._session.get(
            f"{settings.PAYPAL_BASE_URL}/v1/billing/subscriptions/{subscription_id}/transactions",
            params={
                "start_time": (now - timedelta(days=366)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "end_time": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        transactions_response.raise_for_status()
        transactions = transactions_response.json().get("transactions") or []

        # The latest COMPLETED transaction's id doubles as the capture id for refund purposes,
        # per PayPal's Subscriptions transactions endpoint.
        completed = [t for t in transactions if t.get("status") == "COMPLETED"]
        if not completed:
            return None
        capture_id = completed[-1]["id"]

        refund_body = {} if amount_cents is None else {
            "amount": {"value": _cents_to_amount(amount_cents), "currency_code": "USD"}
        }
        refund_response = self._session.post(
            f"{settings.PAYPAL_BASE_URL}/v2/payments/captures/{capture_id}/refund",
            json=refund_body,
            headers={"Authorization": f"Bearer {token}", "PayPal-Request-Id": idempotency_key},
            timeout=15,
        )
        refund_response.raise_for_status()
        refund_body_resp = refund_response.json()
        return RefundResult(refund_body_resp["id"], refund_body_resp["status"], amount_cents)

    def verify_webhook(self, payload, headers):
        if not self.is_configured() or not settings.PAYPAL_WEBHOOK_ID:
            return None

        import json
        try:
            event = json.loads(payload)
        except (ValueError, TypeError):
            return None

        try:
            response = self._session.post(
                f"{settings.PAYPAL_BASE_URL}/v1/notifications/verify-webhook-signature",
                json={
                    "auth_algo": headers.get("paypal-auth-algo"),
                    "cert_url": headers.get("paypal-cert-url"),
                    "transmission_id": headers.get("paypal-transmission-id"),
                    "transmission_sig": headers.get("paypal-transmission-sig"),
                    "transmission_time": headers.get("paypal-transmission-time"),
                    "webhook_id": settings.PAYPAL_WEBHOOK_ID,
                    "webhook_event": event,
                },
                headers={"Authorization": f"Bearer {self._access_token()}"},
                timeout=15,
            )
            response.raise_for_status()
            if response.json().get("verification_status") != "SUCCESS":
                return None
        except requests.RequestException:
            return None

        event_id = event.get("id")
        event_type = event.get("event_type") or ""
        resource = event.get("resource") or {}

        if event_type in ("BILLING.SUBSCRIPTION.ACTIVATED", "BILLING.SUBSCRIPTION.UPDATED"):
            billing_info = resource.get("billing_info") or {}
            return PaymentEvent(
                type="subscription_updated",
                customer_id=(resource.get("subscriber") or {}).get("payer_id"),
                subscription_id=resource.get("id"),
                plan=self._plan_for_plan_id(resource.get("plan_id")),
                provider_status=resource.get("status"),
                period_end=_parse_date(billing_info.get("next_billing_time")),
                event_id=event_id,
                processor=self.name,
            )
        if event_type in ("BILLING.SUBSCRIPTION.CANCELLED", "BILLING.SUBSCRIPTION.EXPIRED", "BILLING.SUBSCRIPTION.SUSPENDED"):
            return PaymentEvent(
                type="subscription_deleted",
                customer_id=(resource.get("subscriber") or {}).get("payer_id"),
                subscription_id=resource.get("id"),
                event_id=event_id,
                processor=self.name,
            )
        if event_type == "VAULT.PAYMENT-TOKEN.CREATED":
            return PaymentEvent(
                type="payment_method_attached",
                customer_id=(resource.get("customer") or {}).get("id"),
                payment_method_id=resource.get("id"),
                event_id=event_id,
                processor=self.name,
            )
        return None

    def list_recent_subscriptions(self, since):
        # Not implemented: PayPal's own reconciliation support is a known, separately-tracked
        # gap (same as the Java/dotnet siblings) — add this once it's actually needed.
        return []

    def create_portal_session(self, customer_id, return_url):
        # PayPal has no hosted self-service portal equivalent to Stripe's — cancel/upgrade for
        # PayPal subscribers is admin-assisted for now.
        return None

    @staticmethod
    def _approve_link(links):
        if not links:
            return None
        for link in links:
            if link.get("rel") == "approve":
                return link.get("href")
        return None

    def _plan_for_plan_id(self, plan_id):
        """Reverses _plan_ids() to recover our plan name from a PayPal plan id on a webhook event."""
        if not plan_id:
            return None
        for plan, pid in self._plan_ids().items():
            if pid == plan_id:
                return plan
        return None


def _cents_to_amount(amount_cents):
    return f"{amount_cents // 100}.{amount_cents % 100:02d}"


def _parse_date(iso_string):
    if not iso_string:
        return None
    try:
        return datetime.fromisoformat(iso_string.replace("Z", "+00:00"))
    except ValueError:
        return None


paypal_gateway = PayPalGateway()

import json
import uuid

import Adyen
from django.conf import settings

from .base import PaymentEvent, RefundResult, SetupIntentResult, SubscriptionIntent


class AdyenGateway:
    """Adyen Checkout Sessions — a sibling acquirer to StripeGateway, not a Stripe payment
    method. Uses the official `Adyen` PyPI package for request dispatch and HMAC webhook
    validation (`Adyen.util.is_valid_hmac_notification`), rather than hand-rolled REST — same
    discipline as the Java sibling (which also uses Adyen's official library), confirmed to be
    actively maintained before depending on it (regular releases, owned by Adyen).

    Model differences from Stripe, by necessity rather than by choice (same as the Java/dotnet
    siblings):
     - Adyen has no subscription object at all. The first payment stores a payment method
       (recurringProcessingModel=Subscription, storePaymentMethodMode=enabled); actually
       renewing on a monthly/yearly schedule requires charging that stored payment method on a
       schedule — a separate follow-up feature, not built here. subscription_id is therefore our
       own generated reference, not Adyen's; customer_id is the user id, not a real Adyen
       customer id.
     - client_secret holds a small JSON blob {"sessionId":...,"sessionData":...} — Adyen's web
       Components need both values, not one string.
     - create_setup_intent uses a zero-amount session as a known rough edge: a true zero-amount
       verification isn't uniformly supported across every card network/region.
     - set_default_payment_method is a documented no-op (same reasoning as the PayPal sibling)
       — and Adyen's webhook mapping here never emits payment_method_attached anyway, so it's
       genuinely unreachable, not a hidden gap.
     - refund_subscription requires last_payment_reference (Adyen's pspReference of the last
       captured payment) since Adyen has no subscription object to look it up from.
    """

    name = "adyen"

    def is_configured(self):
        return bool(settings.ADYEN_API_KEY) and bool(settings.ADYEN_MERCHANT_ACCOUNT)

    def _client(self):
        return Adyen.Adyen(
            xapikey=settings.ADYEN_API_KEY,
            platform="live" if settings.ADYEN_ENVIRONMENT.lower() == "live" else "test",
            merchant_account=settings.ADYEN_MERCHANT_ACCOUNT,
            hmac=settings.ADYEN_HMAC_KEY,
            http_timeout=15,
        )

    def create_subscription_intent(self, user, plan, idempotency_key):
        if not self.is_configured() or not settings.ADYEN_RETURN_URL:
            return None
        price_cents = settings.ADYEN_PRICE_YEARLY_CENTS if plan == "yearly" else settings.ADYEN_PRICE_MONTHLY_CENTS
        reference = f"{user.id}:{plan}:{uuid.uuid4()}"

        result = self._client().checkout.payments_api.sessions(
            {
                "merchantAccount": settings.ADYEN_MERCHANT_ACCOUNT,
                "reference": reference,
                "amount": {"currency": settings.ADYEN_CURRENCY, "value": price_cents},
                "returnUrl": settings.ADYEN_RETURN_URL,
                "shopperReference": str(user.id),
                "shopperEmail": user.email,
                "recurringProcessingModel": "Subscription",
                "storePaymentMethodMode": "enabled",
            },
            idempotency_key=idempotency_key,
        )
        client_secret = _client_secret(result.message)
        return SubscriptionIntent(self.name, str(user.id), reference, client_secret, "pending")

    def create_setup_intent(self, user):
        if not self.is_configured() or not settings.ADYEN_RETURN_URL:
            return None
        reference = f"{user.id}:setup:{uuid.uuid4()}"

        result = self._client().checkout.payments_api.sessions({
            "merchantAccount": settings.ADYEN_MERCHANT_ACCOUNT,
            "reference": reference,
            # Known rough edge: a true zero-amount verification isn't uniformly supported
            # across every card network/region — validate against the schemes actually in play
            # before relying on this in production.
            "amount": {"currency": settings.ADYEN_CURRENCY, "value": 0},
            "returnUrl": settings.ADYEN_RETURN_URL,
            "shopperReference": str(user.id),
            "shopperEmail": user.email,
            "recurringProcessingModel": "Subscription",
            "storePaymentMethodMode": "enabled",
        })
        return SetupIntentResult(self.name, str(user.id), _client_secret(result.message))

    def set_default_payment_method(self, customer_id, payment_method_id):
        # No-op: Adyen has no customer-level "default payment method" pointer, and this
        # gateway's webhook mapping never emits payment_method_attached for Adyen anyway.
        pass

    def refund_subscription(self, subscription_id, amount_cents, idempotency_key, last_payment_reference=None):
        if not self.is_configured() or not last_payment_reference:
            return None

        request = {"merchantAccount": settings.ADYEN_MERCHANT_ACCOUNT, "reference": idempotency_key}
        if amount_cents is not None:
            request["amount"] = {"currency": settings.ADYEN_CURRENCY, "value": amount_cents}

        result = self._client().checkout.modifications_api.refund_captured_payment(
            request, last_payment_reference, idempotency_key=idempotency_key
        )
        return RefundResult(result.message["pspReference"], result.message["status"], amount_cents)

    def verify_webhook(self, payload, headers):
        if not self.is_configured() or not settings.ADYEN_HMAC_KEY:
            return None

        try:
            notification = json.loads(payload)
        except (ValueError, TypeError):
            return None

        items = notification.get("notificationItems") or []
        if not items:
            return None
        item = items[0].get("NotificationRequestItem") or {}

        if not Adyen.util.is_valid_hmac_notification(notification, settings.ADYEN_HMAC_KEY):
            return None

        # Adyen has no subscription-lifecycle events to speak of since it never hosts the
        # subscription itself — only a successful capture is meaningful to us here.
        if item.get("eventCode") != "AUTHORISATION" or not item.get("success"):
            return None

        # merchantReference is our own "userId:plan:uuid" reference (see
        # create_subscription_intent) — there's no shopperReference on a notification item, so
        # the customer id is recovered from the reference we control instead.
        reference = item.get("merchantReference")
        customer_id = reference.split(":")[0] if reference and ":" in reference else reference

        return PaymentEvent(
            type="payment_captured",
            customer_id=customer_id,
            event_id=item.get("pspReference"),
            processor=self.name,
            payment_reference=item.get("pspReference"),
        )

    def list_recent_subscriptions(self, since):
        # Not implemented: Adyen isn't live yet (same known gap as the Java/dotnet siblings) —
        # it would also need Adyen's own notion of "recent" (no subscription object to list;
        # this would have to query captured payments by shopperReference/merchantReference
        # instead).
        return []

    def create_portal_session(self, customer_id, return_url):
        # Adyen has no hosted self-service portal equivalent to Stripe's — cancel/upgrade for
        # Adyen subscribers is admin-assisted for now.
        return None


def _client_secret(message):
    return json.dumps({"sessionId": message["id"], "sessionData": message["sessionData"]})


adyen_gateway = AdyenGateway()

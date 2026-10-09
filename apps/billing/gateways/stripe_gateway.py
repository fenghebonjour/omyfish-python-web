import stripe
from django.conf import settings

from .base import PaymentEvent, ReconciliationCandidate, RefundResult, SetupIntentResult, SubscriptionIntent, epoch_to_datetime


class StripeGateway:
    name = "stripe"

    def is_configured(self):
        return bool(settings.STRIPE_SECRET_KEY)

    def _prices(self):
        return {"monthly": settings.STRIPE_PRICE_MONTHLY, "yearly": settings.STRIPE_PRICE_YEARLY}

    def create_subscription_intent(self, user, plan, idempotency_key):
        price_id = self._prices().get(plan)
        if not self.is_configured() or not price_id:
            return None

        customer_id = self._find_or_create_customer(user)
        subscription = stripe.Subscription.create(
            customer=customer_id,
            items=[{"price": price_id}],
            payment_behavior="default_incomplete",
            expand=["latest_invoice.confirmation_secret"],
            metadata={"user_id": str(user.id), "plan": plan},
            idempotency_key=idempotency_key,
            api_key=settings.STRIPE_SECRET_KEY,
        )
        client_secret = None
        invoice = subscription.latest_invoice
        if invoice is not None and invoice.confirmation_secret is not None:
            client_secret = invoice.confirmation_secret.client_secret
        return SubscriptionIntent(
            self.name, subscription.customer, subscription.id, client_secret, subscription.status
        )

    def create_setup_intent(self, user):
        if not self.is_configured():
            return None
        customer_id = self._find_or_create_customer(user)
        setup_intent = stripe.SetupIntent.create(
            customer=customer_id, usage="off_session", api_key=settings.STRIPE_SECRET_KEY
        )
        return SetupIntentResult(self.name, customer_id, setup_intent.client_secret)

    def set_default_payment_method(self, customer_id, payment_method_id):
        if not self.is_configured():
            return
        stripe.Customer.modify(
            customer_id,
            invoice_settings={"default_payment_method": payment_method_id},
            api_key=settings.STRIPE_SECRET_KEY,
        )

    def refund_subscription(self, subscription_id, amount_cents, idempotency_key, last_payment_reference=None):
        if not self.is_configured() or not subscription_id:
            return None

        subscription = stripe.Subscription.retrieve(subscription_id, api_key=settings.STRIPE_SECRET_KEY)
        invoice_id = subscription.latest_invoice
        if not invoice_id:
            return None

        payments = stripe.InvoicePayment.list(
            invoice=invoice_id, status="paid", limit=1, api_key=settings.STRIPE_SECRET_KEY
        )
        if not payments.data:
            return None
        payment_intent_id = payments.data[0].payment.payment_intent
        if not payment_intent_id:
            return None

        refund_kwargs = {
            "payment_intent": payment_intent_id,
            "idempotency_key": idempotency_key,
            "api_key": settings.STRIPE_SECRET_KEY,
        }
        if amount_cents is not None:
            refund_kwargs["amount"] = amount_cents
        refund = stripe.Refund.create(**refund_kwargs)
        return RefundResult(refund.id, refund.status, amount_cents)

    def verify_webhook(self, payload, headers):
        if not settings.STRIPE_WEBHOOK_SECRET:
            return None
        signature = headers.get("stripe-signature", "")
        try:
            event = stripe.Webhook.construct_event(payload, signature, settings.STRIPE_WEBHOOK_SECRET)
        except stripe.SignatureVerificationError:
            return None

        if event.type in ("customer.subscription.updated", "customer.subscription.deleted"):
            return self._from_subscription_event(event)
        if event.type == "setup_intent.succeeded":
            return self._from_setup_intent(event)
        if event.type == "invoice.payment_failed":
            return self._from_invoice_payment_failed(event)
        return None

    def _from_subscription_event(self, event):
        sub = event.data.object
        items = sub.items.data if sub.items else []
        period_end = items[0].current_period_end if items else None
        price_id = items[0].price.id if items else None
        event_type = "subscription_deleted" if event.type.endswith("deleted") else "subscription_updated"
        return PaymentEvent(
            type=event_type,
            customer_id=sub.customer,
            subscription_id=sub.id,
            plan=self._plan_for_price_id(price_id),
            provider_status=sub.status,
            period_end=epoch_to_datetime(period_end),
            event_id=event.id,
            processor=self.name,
        )

    def _from_setup_intent(self, event):
        setup_intent = event.data.object
        return PaymentEvent(
            type="payment_method_attached",
            customer_id=setup_intent.customer,
            payment_method_id=setup_intent.payment_method,
            event_id=event.id,
            processor=self.name,
        )

    def _from_invoice_payment_failed(self, event):
        invoice = event.data.object
        subscription_id = None
        if invoice.parent is not None and invoice.parent.subscription_details is not None:
            subscription_id = invoice.parent.subscription_details.subscription
        if not subscription_id:
            return None
        return PaymentEvent(
            type="payment_failed",
            customer_id=invoice.customer,
            subscription_id=subscription_id,
            event_id=event.id,
            processor=self.name,
        )

    def _plan_for_price_id(self, price_id):
        """Reverses _prices() to recover our plan name from a Stripe price id on a webhook event."""
        if not price_id:
            return None
        for plan, pid in self._prices().items():
            if pid == price_id:
                return plan
        return None

    def list_recent_subscriptions(self, since):
        if not self.is_configured():
            return []
        candidates = []
        subscriptions = stripe.Subscription.list(
            created={"gte": int(since.timestamp())}, limit=100, api_key=settings.STRIPE_SECRET_KEY
        )
        for sub in subscriptions.auto_paging_iter():
            metadata = sub.metadata
            user_id = metadata["user_id"] if metadata and "user_id" in metadata else None
            plan = metadata["plan"] if metadata and "plan" in metadata else None
            items = sub.items.data if sub.items else []
            period_end = items[0].current_period_end if items else None
            candidates.append(ReconciliationCandidate(
                processor=self.name,
                user_id=user_id,
                customer_id=sub.customer,
                subscription_id=sub.id,
                plan=plan,
                provider_status=sub.status,
                period_end=epoch_to_datetime(period_end),
            ))
        return candidates

    def create_portal_session(self, customer_id, return_url):
        if not self.is_configured():
            return None
        session = stripe.billing_portal.Session.create(
            customer=customer_id, return_url=return_url, api_key=settings.STRIPE_SECRET_KEY
        )
        return session.url

    def _find_or_create_customer(self, user):
        existing = stripe.Customer.list(email=user.email, limit=1, api_key=settings.STRIPE_SECRET_KEY)
        if existing.data:
            return existing.data[0].id
        created = stripe.Customer.create(
            email=user.email, metadata={"user_id": str(user.id)}, api_key=settings.STRIPE_SECRET_KEY
        )
        return created.id


stripe_gateway = StripeGateway()

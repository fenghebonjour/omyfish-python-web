"""Payment provider boundary (Stripe, PayPal, Adyen) — a Protocol since Python has no formal
interfaces, mirroring the Java/dotnet siblings' PaymentPort/IPaymentGateway. Empty/None results
mean "not configured". A gateway module exposes a module-level instance implementing this shape;
see registry.py for how one is selected by name.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Protocol


def epoch_to_datetime(epoch_seconds):
    return None if epoch_seconds is None else datetime.fromtimestamp(epoch_seconds, tz=timezone.utc)


@dataclass(frozen=True)
class SubscriptionIntent:
    processor: str
    customer_id: str
    subscription_id: str
    client_secret: Optional[str]
    status: str


@dataclass(frozen=True)
class SetupIntentResult:
    processor: str
    customer_id: str
    client_secret: str


@dataclass(frozen=True)
class RefundResult:
    refund_id: str
    status: str
    amount_cents: Optional[int]


@dataclass(frozen=True)
class ReconciliationCandidate:
    processor: str
    user_id: Optional[str]  # None if the processor-side metadata is missing/unparseable
    customer_id: str
    subscription_id: str
    plan: Optional[str]
    provider_status: Optional[str]
    period_end: Optional[datetime]


@dataclass(frozen=True)
class PaymentEvent:
    type: str  # subscription_updated | subscription_deleted | payment_method_attached | payment_captured | payment_failed
    customer_id: Optional[str]
    subscription_id: Optional[str] = None
    plan: Optional[str] = None  # "monthly" | "yearly", when the event's processor can tell; None otherwise
    provider_status: Optional[str] = None
    period_end: Optional[datetime] = None
    payment_method_id: Optional[str] = None  # set for payment_method_attached
    event_id: Optional[str] = None  # provider's event id, used to dedup redelivered webhooks
    # Defaults to "stripe" since every event constructed before multi-processor support existed
    # was implicitly Stripe's; new gateways should pass this explicitly.
    processor: str = "stripe"
    payment_reference: Optional[str] = None  # set for payment_captured (e.g. Adyen's pspReference)


class PaymentGateway(Protocol):
    name: str

    def is_configured(self) -> bool: ...

    def create_subscription_intent(
        self, user, plan: str, idempotency_key: str
    ) -> Optional[SubscriptionIntent]: ...

    def create_setup_intent(self, user) -> Optional[SetupIntentResult]: ...

    def set_default_payment_method(self, customer_id: str, payment_method_id: str) -> None: ...

    def refund_subscription(
        self,
        subscription_id: str,
        amount_cents: Optional[int],
        idempotency_key: str,
        last_payment_reference: Optional[str] = None,
    ) -> Optional[RefundResult]: ...

    def verify_webhook(self, payload: bytes, headers: dict) -> Optional[PaymentEvent]: ...

    def list_recent_subscriptions(self, since: datetime) -> list[ReconciliationCandidate]: ...

    def create_portal_session(self, customer_id: str, return_url: str) -> Optional[str]: ...

from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from .gateways import registry
from .gateways.base import PaymentEvent, RefundResult, SubscriptionIntent
from .models import IdempotencyRecord, ProcessedWebhookEvent, Subscription

TRIAL_DAYS = 7
MONTHLY_CAD = 5
YEARLY_CAD = 29

# How long an incomplete checkout/refund reservation sits before it's treated as orphaned
# rather than "still in progress" — comfortably past the gateway's own worst-case call time; a
# reservation only outlives that if the process died before it could complete.
STALE_RESERVATION_AGE = timedelta(minutes=1)


class AlreadySubscribedError(Exception):
    """The user is asking to create a subscription they already have — a business invariant
    distinct from a replayed idempotency key (IdempotencyConflictError) or "no such thing"
    (Subscription.DoesNotExist/NoProcessorCustomerError). ->409 at the view.
    """


class IdempotencyConflictError(Exception):
    """A request with this idempotency key is already in progress. ->409 at the view."""


class NoProcessorCustomerError(Exception):
    """The user has a subscription row but no payment-processor id on file yet. ->404 at the
    view, same bucket as "no subscription at all" (Subscription.DoesNotExist).
    """


def get_or_start_trial(user):
    subscription, _ = Subscription.objects.get_or_create(
        user=user,
        defaults={"trial_end": timezone.now() + timezone.timedelta(days=TRIAL_DAYS)},
    )
    return subscription


def start_checkout(user, plan, idempotency_key):
    """None when no payment processor is configured."""
    existing = IdempotencyRecord.objects.filter(key=idempotency_key, endpoint=IdempotencyRecord.CHECKOUT).first()
    if existing is not None and not _is_orphaned(existing):
        return _replayed_checkout(_require_owner(existing, user))

    # A second checkout call with a genuinely different idempotency key (e.g. a double click,
    # or a retest against an account that's already paying) must not create a second live
    # subscription for the same user — the idempotency-key check above only catches a retry of
    # the *same* key. Found live in the Java sibling: two separate "active" Stripe
    # subscriptions, both billing the same user every month.
    current = Subscription.objects.filter(user=user).first()
    if (current is not None and current.stripe_subscription_id
            and current.effective_status in (Subscription.ACTIVE, Subscription.PAST_DUE)):
        raise AlreadySubscribedError("Already subscribed")

    gateway = registry.default_gateway()
    if gateway is None:
        return None

    reservation = (
        _require_owner(existing, user) if existing is not None
        else _reserve(idempotency_key, IdempotencyRecord.CHECKOUT, user)
    )
    try:
        intent = gateway.create_subscription_intent(user, plan, idempotency_key)
        if intent is None:
            reservation.delete()
            return None

        subscription = get_or_start_trial(user)
        subscription.attach_processor(intent.processor, intent.customer_id, intent.subscription_id)

        reservation.complete_checkout(intent.customer_id, intent.subscription_id, intent.client_secret, intent.status)
        return intent
    except Exception:
        reservation.delete()
        raise


def _replayed_checkout(record):
    if not record.completed:
        raise IdempotencyConflictError("A checkout with this idempotency key is already in progress")
    subscription = Subscription.objects.filter(user=record.user).first()
    processor = subscription.payment_processor if subscription and subscription.payment_processor else "stripe"
    return SubscriptionIntent(processor, record.customer_id, record.subscription_id, record.client_secret, record.checkout_status)


def start_payment_method_setup(user):
    """None when no payment processor is configured."""
    gateway = registry.default_gateway()
    if gateway is None:
        return None

    intent = gateway.create_setup_intent(user)
    if intent is None:
        return None

    subscription = get_or_start_trial(user)
    subscription.attach_processor_customer_id(intent.processor, intent.customer_id)
    return intent


def refund(user, amount_cents, idempotency_key):
    """Raises Subscription.DoesNotExist (->404) if the user has no subscription on file, or
    NoProcessorCustomerError (->404) if it has one but no processor subscription id yet.
    Returns None (->503, a different failure mode) when the processor isn't configured or
    there's nothing to refund.
    """
    existing = IdempotencyRecord.objects.filter(key=idempotency_key, endpoint=IdempotencyRecord.REFUND).first()
    if existing is not None and not _is_orphaned(existing):
        return _replayed_refund(_require_owner(existing, user))

    subscription = Subscription.objects.get(user=user)
    if not subscription.stripe_subscription_id:
        raise NoProcessorCustomerError("No payment processor subscription on file")

    gateway = registry.by_name(subscription.payment_processor or "stripe")

    reservation = (
        _require_owner(existing, user) if existing is not None
        else _reserve(idempotency_key, IdempotencyRecord.REFUND, user)
    )
    try:
        result = gateway.refund_subscription(
            subscription.stripe_subscription_id, amount_cents, idempotency_key,
            last_payment_reference=subscription.last_payment_reference,
        )
        if result is None:
            reservation.delete()
            return None

        reservation.complete_refund(result.refund_id, result.status, result.amount_cents)
        return result
    except Exception:
        reservation.delete()
        raise


def _replayed_refund(record):
    if not record.completed:
        raise IdempotencyConflictError("A refund with this idempotency key is already in progress")
    return RefundResult(record.refund_id, record.refund_status, record.amount_cents)


def create_portal_session(user, return_url):
    """Raises Subscription.DoesNotExist (->404) / NoProcessorCustomerError (->404) the same way
    refund() does. Returns None (->503) when the processor has no portal equivalent (PayPal,
    Adyen) or isn't configured.
    """
    subscription = Subscription.objects.get(user=user)
    if not subscription.stripe_customer_id:
        raise NoProcessorCustomerError("No payment processor customer on file")

    gateway = registry.by_name(subscription.payment_processor or "stripe")
    return gateway.create_portal_session(subscription.stripe_customer_id, return_url)


def apply_event(event: PaymentEvent) -> bool:
    if event.event_id and ProcessedWebhookEvent.objects.filter(event_id=event.event_id).exists():
        return True

    handled = _apply_event_effects(event)
    if handled and event.event_id:
        ProcessedWebhookEvent.objects.get_or_create(event_id=event.event_id)
    return handled


def _apply_event_effects(event: PaymentEvent) -> bool:
    if event.type in ("subscription_updated", "subscription_deleted"):
        if not event.customer_id:
            return False
        subscription = Subscription.objects.filter(stripe_customer_id=event.customer_id).first()
        if subscription is None:
            return False

        if event.type == "subscription_deleted" or event.provider_status in ("canceled", "unpaid", "incomplete_expired"):
            subscription.cancel()
        else:
            plan = event.plan or subscription.plan or "monthly"
            subscription.activate(plan, event.period_end, stripe_subscription_id=event.subscription_id)
        return True

    if event.type == "payment_method_attached":
        if not event.customer_id or not event.payment_method_id:
            return False
        registry.by_name(event.processor).set_default_payment_method(event.customer_id, event.payment_method_id)
        return True

    if event.type == "payment_captured":
        if not event.customer_id or not event.payment_reference:
            return False
        subscription = Subscription.objects.filter(stripe_customer_id=event.customer_id).first()
        if subscription is None:
            return False
        subscription.record_last_payment_reference(event.payment_reference)
        return True

    if event.type == "payment_failed":
        if not event.customer_id:
            return False
        subscription = Subscription.objects.filter(stripe_customer_id=event.customer_id).first()
        if subscription is None:
            return False
        subscription.mark_past_due()
        return True

    return False


def reconcile(since):
    """Repairs a local Subscription row whose processor-id link never got saved — e.g. a crash
    between a processor call succeeding in start_checkout/start_payment_method_setup and the
    row being saved. Driven from each configured processor's own subscription list (keyed by
    the user_id metadata every checkout already attaches), not by scanning local rows for a
    missing link, since a null link is also just the normal state for a trialing user who
    hasn't subscribed yet. Returns {"checked", "repaired", "errors"}.

    Single-instance assumption, same as the Java/dotnet siblings: no claim/lock step, so a
    second replica would run this concurrently — lower-stakes here since relinking + resyncing
    status is idempotent either way.
    """
    checked = 0
    repaired = []
    errors = []

    for gateway in registry.configured():
        try:
            candidates = gateway.list_recent_subscriptions(since)
        except Exception as e:
            errors.append(f"{gateway.name}: failed to list subscriptions — {e}")
            continue

        for candidate in candidates:
            checked += 1
            if not candidate.user_id:
                errors.append(
                    f"{candidate.processor} subscription {candidate.subscription_id} "
                    "has no usable user_id metadata, skipped"
                )
                continue
            try:
                if _relink(candidate):
                    repaired.append(f"{candidate.processor}:{candidate.subscription_id} -> user {candidate.user_id}")
                _resync_status(candidate)
            except Exception as e:
                errors.append(f"{candidate.processor} subscription {candidate.subscription_id}: {e}")

    return {"checked": checked, "repaired": repaired, "errors": errors}


def _relink(candidate):
    """Returns True if the local row's link was actually missing/mismatched and got repaired."""
    subscription, _ = Subscription.objects.get_or_create(
        user_id=candidate.user_id, defaults={"trial_end": timezone.now()}
    )
    mismatched = (
        subscription.stripe_customer_id != candidate.customer_id
        or subscription.stripe_subscription_id != candidate.subscription_id
    )
    if mismatched:
        subscription.attach_processor(candidate.processor, candidate.customer_id, candidate.subscription_id)
    return mismatched


def _resync_status(candidate):
    """Re-syncs status/plan/period_end via the already-tested webhook-effect path, now that the
    link is guaranteed to resolve. event_id is left unset so apply_event's dedup check doesn't
    apply — safe, since _apply_event_effects's subscription_updated case just re-asserts
    current status.
    """
    apply_event(PaymentEvent(
        type="subscription_updated",
        customer_id=candidate.customer_id,
        subscription_id=candidate.subscription_id,
        plan=candidate.plan,
        provider_status=candidate.provider_status,
        period_end=candidate.period_end,
        processor=candidate.processor,
    ))


def _is_orphaned(record):
    return not record.completed and record.is_stale(STALE_RESERVATION_AGE)


def _require_owner(record, user):
    if record.user_id != user.id:
        raise ValueError("Idempotency key already used")
    return record


def _reserve(key, endpoint, user):
    try:
        with transaction.atomic():
            return IdempotencyRecord.objects.create(key=key, endpoint=endpoint, user=user)
    except IntegrityError:
        raise IdempotencyConflictError("A request with this idempotency key is already in progress") from None


def grant(user, plan="yearly", days=365):
    subscription = get_or_start_trial(user)
    subscription.activate(plan, timezone.now() + timezone.timedelta(days=days))
    return subscription


def revoke(user):
    subscription = Subscription.objects.get(user=user)
    subscription.cancel()
    return subscription


def extend_trial(user, days=7):
    subscription = get_or_start_trial(user)
    subscription.extend_trial(days)
    return subscription


def stats():
    subscriptions = list(Subscription.objects.all())

    def count(status):
        return sum(1 for s in subscriptions if s.effective_status == status)

    active_monthly = sum(
        1 for s in subscriptions if s.effective_status == Subscription.ACTIVE and s.plan == "monthly"
    )
    active_yearly = sum(
        1 for s in subscriptions if s.effective_status == Subscription.ACTIVE and s.plan == "yearly"
    )
    mrr = active_monthly * MONTHLY_CAD + active_yearly * YEARLY_CAD / 12

    return {
        "trialing": count(Subscription.TRIALING),
        "active": count(Subscription.ACTIVE),
        "canceled": count(Subscription.CANCELED),
        "expired": count(Subscription.EXPIRED),
        "activeMonthly": active_monthly,
        "activeYearly": active_yearly,
        "mrrCad": round(mrr, 2),
    }

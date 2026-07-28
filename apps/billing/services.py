from django.utils import timezone

from .models import Subscription

TRIAL_DAYS = 7
MONTHLY_CAD = 5
YEARLY_CAD = 29


def get_or_start_trial(user):
    subscription, _ = Subscription.objects.get_or_create(
        user=user,
        defaults={"trial_end": timezone.now() + timezone.timedelta(days=TRIAL_DAYS)},
    )
    return subscription


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

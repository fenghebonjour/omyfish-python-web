from rest_framework import serializers


def subscription_response(subscription):
    return {
        "status": subscription.effective_status,
        "plan": subscription.plan,
        "trialEnd": subscription.trial_end,
        "currentPeriodEnd": subscription.current_period_end,
    }


def subscription_row(subscription):
    return {
        "userId": str(subscription.user.id),
        "email": subscription.user.email,
        **subscription_response(subscription),
    }


class CheckoutSerializer(serializers.Serializer):
    plan = serializers.ChoiceField(choices=["monthly", "yearly"])


class GrantSerializer(serializers.Serializer):
    plan = serializers.ChoiceField(choices=["monthly", "yearly"], default="yearly")
    days = serializers.IntegerField(default=365)


class ExtendTrialSerializer(serializers.Serializer):
    days = serializers.IntegerField(default=7)

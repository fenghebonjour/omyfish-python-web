from rest_framework import serializers


def subscription_response(subscription):
    return {
        "status": subscription.effective_status,
        "plan": subscription.plan,
        "trialEnd": subscription.trial_end,
        "currentPeriodEnd": subscription.current_period_end,
        "paymentProcessor": subscription.payment_processor,
    }


def subscription_row(subscription):
    return {
        "userId": str(subscription.user.id),
        "email": subscription.user.email,
        **subscription_response(subscription),
    }


def checkout_response(intent):
    return {
        "processor": intent.processor,
        "clientSecret": intent.client_secret,
        "subscriptionId": intent.subscription_id,
        "status": intent.status,
    }


def setup_intent_response(intent):
    return {
        "processor": intent.processor,
        "customerId": intent.customer_id,
        "clientSecret": intent.client_secret,
    }


def refund_response(result):
    return {
        "refundId": result.refund_id,
        "status": result.status,
        "amountCents": result.amount_cents,
    }


class CheckoutSerializer(serializers.Serializer):
    plan = serializers.ChoiceField(choices=["monthly", "yearly"])


class RefundSerializer(serializers.Serializer):
    amountCents = serializers.IntegerField(required=False, allow_null=True, default=None)


class PortalSessionSerializer(serializers.Serializer):
    returnUrl = serializers.CharField()


class GrantSerializer(serializers.Serializer):
    plan = serializers.ChoiceField(choices=["monthly", "yearly"], default="yearly")
    days = serializers.IntegerField(default=365)


class ExtendTrialSerializer(serializers.Serializer):
    days = serializers.IntegerField(default=7)

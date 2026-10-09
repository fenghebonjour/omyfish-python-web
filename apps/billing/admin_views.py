from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User

from . import services
from .models import Subscription
from .permissions import IsAdmin
from .serializers import ExtendTrialSerializer, GrantSerializer, RefundSerializer, refund_response, subscription_row


class StatsView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        return Response(services.stats())


class SubscriptionListView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        subscriptions = Subscription.objects.select_related("user").all()
        return Response([subscription_row(s) for s in subscriptions])


class GrantView(APIView):
    permission_classes = [IsAdmin]

    def post(self, request, user_id):
        user = get_object_or_404(User, id=user_id)
        serializer = GrantSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        subscription = services.grant(user, **serializer.validated_data)
        return Response(subscription_row(subscription))


class RevokeView(APIView):
    permission_classes = [IsAdmin]

    def post(self, request, user_id):
        user = get_object_or_404(User, id=user_id)
        try:
            subscription = services.revoke(user)
        except Subscription.DoesNotExist:
            return Response(
                {"detail": "No subscription for that user"}, status=status.HTTP_404_NOT_FOUND
            )
        return Response(subscription_row(subscription))


class ExtendTrialView(APIView):
    permission_classes = [IsAdmin]

    def post(self, request, user_id):
        user = get_object_or_404(User, id=user_id)
        serializer = ExtendTrialSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        subscription = services.extend_trial(user, **serializer.validated_data)
        return Response(subscription_row(subscription))


class RefundView(APIView):
    permission_classes = [IsAdmin]

    def post(self, request, user_id):
        user = get_object_or_404(User, id=user_id)
        serializer = RefundSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)
        idempotency_key = request.headers.get("Idempotency-Key")
        if not idempotency_key:
            return Response(
                {"error": "Idempotency-Key header is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            result = services.refund(user, serializer.validated_data["amountCents"], idempotency_key)
        except (Subscription.DoesNotExist, services.NoProcessorCustomerError):
            return Response(status=status.HTTP_404_NOT_FOUND)
        except services.IdempotencyConflictError as e:
            return Response({"error": str(e)}, status=status.HTTP_409_CONFLICT)

        if result is None:
            return Response(
                {"detail": "No payment processor is configured, or nothing to refund"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response(refund_response(result))


class ReconcileView(APIView):
    permission_classes = [IsAdmin]

    def post(self, request):
        lookback_hours = int(request.query_params.get("lookbackHours", 24))
        result = services.reconcile(timezone.now() - timezone.timedelta(hours=lookback_hours))
        return Response(result)

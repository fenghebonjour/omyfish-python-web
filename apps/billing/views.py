from django.http import HttpResponse
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .gateways import registry
from .models import Subscription
from .serializers import (
    CheckoutSerializer,
    PortalSessionSerializer,
    checkout_response,
    setup_intent_response,
    subscription_response,
)


class MeView(APIView):
    def get(self, request):
        subscription = services.get_or_start_trial(request.user)
        return Response(subscription_response(subscription))


class CheckoutView(APIView):
    def post(self, request):
        serializer = CheckoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        idempotency_key = request.headers.get("Idempotency-Key")
        if not idempotency_key:
            return Response(
                {"error": "Idempotency-Key header is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            intent = services.start_checkout(request.user, serializer.validated_data["plan"], idempotency_key)
        except services.AlreadySubscribedError as e:
            return Response({"error": str(e)}, status=status.HTTP_409_CONFLICT)
        except services.IdempotencyConflictError as e:
            return Response({"error": str(e)}, status=status.HTTP_409_CONFLICT)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        if intent is None:
            return Response(
                {"detail": "No payment processor is configured"}, status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        return Response(checkout_response(intent))


class PaymentMethodSetupView(APIView):
    def post(self, request):
        intent = services.start_payment_method_setup(request.user)
        if intent is None:
            return Response(
                {"detail": "No payment processor is configured"}, status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        return Response(setup_intent_response(intent))


class PortalSessionView(APIView):
    def post(self, request):
        serializer = PortalSessionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            url = services.create_portal_session(request.user, serializer.validated_data["returnUrl"])
        except (Subscription.DoesNotExist, services.NoProcessorCustomerError):
            return Response(status=status.HTTP_404_NOT_FOUND)

        if url is None:
            return Response(
                {"detail": "No self-service portal is available for this payment processor"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response({"url": url})


class WebhookView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, processor):
        if not registry.exists(processor):
            return Response(
                {"error": f"Unknown payment processor: {processor}"}, status=status.HTTP_404_NOT_FOUND
            )
        gateway = registry.by_name(processor)
        if not gateway.is_configured():
            return Response(
                {"error": f"Payment processor is not configured: {processor}"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        headers = {k.lower(): v for k, v in request.headers.items()}
        event = gateway.verify_webhook(request.body, headers)
        if event is None:
            return Response({"error": "Invalid webhook signature"}, status=status.HTTP_400_BAD_REQUEST)

        handled = services.apply_event(event)

        # Adyen requires this exact literal body (not JSON) or it keeps retrying the webhook.
        if processor == "adyen":
            return HttpResponse("[accepted]", content_type="text/plain")
        return Response({"handled": handled})

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .serializers import CheckoutSerializer, subscription_response


class MeView(APIView):
    def get(self, request):
        subscription = services.get_or_start_trial(request.user)
        return Response(subscription_response(subscription))


class CheckoutView(APIView):
    def post(self, request):
        serializer = CheckoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # Stripe is not wired up in this scaffold — mirrors the siblings'
        # "empty when not configured" checkout behavior.
        return Response(
            {"detail": "Stripe is not configured"}, status=status.HTTP_503_SERVICE_UNAVAILABLE
        )

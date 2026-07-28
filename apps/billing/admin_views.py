from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User

from . import services
from .models import Subscription
from .permissions import IsAdmin
from .serializers import ExtendTrialSerializer, GrantSerializer, subscription_row


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

from django.shortcuts import get_object_or_404
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Notification
from .serializers import NotificationSerializer


class NotificationListView(ListAPIView):
    serializer_class = NotificationSerializer

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)


class NotificationMarkReadView(APIView):
    def put(self, request, notification_id):
        notification = get_object_or_404(
            Notification, id=notification_id, user=request.user
        )
        notification.read = True
        notification.save(update_fields=["read"])
        return Response(NotificationSerializer(notification).data)

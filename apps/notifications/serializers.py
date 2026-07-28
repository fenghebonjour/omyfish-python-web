from rest_framework import serializers

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(read_only=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model = Notification
        fields = ["id", "title", "message", "read", "createdAt"]

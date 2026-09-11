from rest_framework import serializers

from .models import User


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ["email", "password"]

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


def auth_response(user, token):
    # No refreshToken here — it travels only as an httpOnly cookie now
    # (BACKLOG.md item G, WEAKNESS_AUDIT.md §1.3).
    return {
        "token": str(token),
        "userId": str(user.id),
        "email": user.email,
        "role": user.role,
    }

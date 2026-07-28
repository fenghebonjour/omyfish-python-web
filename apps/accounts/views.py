from django.contrib.auth import authenticate
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User
from .serializers import LoginSerializer, RegisterSerializer, auth_response


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        return Response(
            auth_response(user, refresh.access_token, refresh),
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate(
            request,
            username=serializer.validated_data["email"],
            password=serializer.validated_data["password"],
        )
        if user is None:
            return Response(
                {"detail": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED
            )
        refresh = RefreshToken.for_user(user)
        return Response(auth_response(user, refresh.access_token, refresh))


class RefreshView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        raw_refresh = request.data.get("refreshToken")
        if not raw_refresh:
            return Response(
                {"detail": "refreshToken is required"}, status=status.HTTP_400_BAD_REQUEST
            )
        try:
            refresh = RefreshToken(raw_refresh)
            user = User.objects.get(id=refresh["user_id"])
        except (TokenError, User.DoesNotExist):
            return Response(
                {"detail": "Invalid refresh token"}, status=status.HTTP_401_UNAUTHORIZED
            )
        return Response(auth_response(user, refresh.access_token, refresh))

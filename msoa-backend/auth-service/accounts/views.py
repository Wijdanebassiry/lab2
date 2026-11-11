from django.shortcuts import render

# Create your views here.
from django.contrib.auth import authenticate
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import AccessToken

from .models import User


def error(message, code):
    return Response({"message": message, "error": message}, status=code)


def public_user(user):
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
    }


class LoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        email = str(request.data.get("email", "")).strip().lower()
        password = request.data.get("password", "")

        user = authenticate(request, email=email, password=password)
        if user is None:
            return error("Invalid email or password.", status.HTTP_401_UNAUTHORIZED)

        token = AccessToken.for_user(user)
        return Response({"user": public_user(user), "token": str(token)})


class RegisterView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        name = str(request.data.get("name", "")).strip()
        email = str(request.data.get("email", "")).strip().lower()
        password = request.data.get("password", "")

        if not name or not email or not password:
            return error("All fields are required.", status.HTTP_400_BAD_REQUEST)

        if User.objects.filter(email=email).exists():
            return error("Email already registered.", status.HTTP_409_CONFLICT)

        user = User.objects.create_user(email=email, password=password, name=name)
        return Response(public_user(user), status=status.HTTP_201_CREATED)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(public_user(request.user))
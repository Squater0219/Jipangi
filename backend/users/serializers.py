from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db import IntegrityError, transaction
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from config.exceptions import APIError


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = get_user_model()
        fields = ("id", "username", "email")


class AuthResponseSerializer(serializers.Serializer):
    access_token = serializers.CharField()
    refresh_token = serializers.CharField()
    user = UserSerializer()


class RefreshResponseSerializer(serializers.Serializer):
    access_token = serializers.CharField()
    refresh_token = serializers.CharField()


class MeResponseSerializer(UserSerializer):
    joined_at = serializers.DateTimeField()
    total_completed_analyses = serializers.IntegerField()

    class Meta(UserSerializer.Meta):
        fields = UserSerializer.Meta.fields + ("joined_at", "total_completed_analyses")


class SignupSerializer(serializers.Serializer):
    username = serializers.CharField(min_length=2, max_length=30)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)

    def validate_email(self, value):
        email = get_user_model().objects.normalize_email(value).lower()
        if get_user_model().objects.filter(email__iexact=email).exists():
            raise APIError(
                status_code=409,
                code="EMAIL_ALREADY_EXISTS",
                message="이미 가입된 이메일입니다.",
            )
        return email

    def validate_password(self, value):
        validate_password(value)
        return value

    def create(self, validated_data):
        try:
            with transaction.atomic():
                return get_user_model().objects.create_user(**validated_data)
        except IntegrityError as exc:
            raise APIError(
                status_code=409,
                code="EMAIL_ALREADY_EXISTS",
                message="이미 가입된 이메일입니다.",
            ) from exc


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = get_user_model().objects.normalize_email(attrs["email"]).lower()
        user = authenticate(
            request=self.context.get("request"),
            email=email,
            password=attrs["password"],
        )
        if user is None or not user.is_active:
            raise APIError(
                status_code=401,
                code="INVALID_CREDENTIALS",
                message="이메일 또는 비밀번호가 올바르지 않습니다.",
            )
        attrs["user"] = user
        return attrs


class RefreshSerializer(serializers.Serializer):
    refresh_token = serializers.CharField()

    def validate(self, attrs):
        serializer = TokenRefreshSerializer(data={"refresh": attrs["refresh_token"]})
        try:
            serializer.is_valid(raise_exception=True)
        except Exception as exc:
            raise APIError(
                status_code=401,
                code="INVALID_TOKEN",
                message="Refresh Token이 유효하지 않습니다.",
            ) from exc

        return {
            "access_token": serializer.validated_data["access"],
            "refresh_token": serializer.validated_data["refresh"],
        }


class LogoutSerializer(serializers.Serializer):
    refresh_token = serializers.CharField()

    def save(self, **kwargs):
        try:
            RefreshToken(self.validated_data["refresh_token"]).blacklist()
        except Exception as exc:
            raise APIError(
                status_code=401,
                code="INVALID_TOKEN",
                message="Refresh Token이 유효하지 않습니다.",
            ) from exc


def token_pair_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {
        "access_token": str(refresh.access_token),
        "refresh_token": str(refresh),
    }

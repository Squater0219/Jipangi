from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from pronunciation.models import PronunciationAnalysis

from .serializers import (
    AuthResponseSerializer,
    LoginSerializer,
    LogoutSerializer,
    MeResponseSerializer,
    RefreshResponseSerializer,
    RefreshSerializer,
    SignupSerializer,
    UserSerializer,
    token_pair_for_user,
)
from .throttles import LoginEmailRateThrottle, LoginIPRateThrottle, SignupRateThrottle


class SignupView(APIView):
    permission_classes = (AllowAny,)
    authentication_classes = ()
    throttle_classes = (SignupRateThrottle,)

    @extend_schema(request=SignupSerializer, responses={201: AuthResponseSerializer})
    def post(self, request):
        serializer = SignupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            {
                **token_pair_for_user(user),
                "user": UserSerializer(user).data,
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    permission_classes = (AllowAny,)
    authentication_classes = ()
    throttle_classes = (LoginIPRateThrottle, LoginEmailRateThrottle)

    @extend_schema(request=LoginSerializer, responses={200: AuthResponseSerializer})
    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        return Response(
            {
                **token_pair_for_user(user),
                "user": UserSerializer(user).data,
            }
        )


class RefreshView(APIView):
    permission_classes = (AllowAny,)
    authentication_classes = ()

    @extend_schema(request=RefreshSerializer, responses={200: RefreshResponseSerializer})
    def post(self, request):
        serializer = RefreshSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data)


class LogoutView(APIView):
    @extend_schema(request=LogoutSerializer, responses={204: None})
    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    @extend_schema(responses={200: MeResponseSerializer})
    def get(self, request):
        total_completed_analyses = PronunciationAnalysis.objects.filter(
            user=request.user,
            status=PronunciationAnalysis.Status.COMPLETED,
            consent_to_store=True,
        ).count()
        return Response(
            {
                "id": request.user.id,
                "username": request.user.username,
                "email": request.user.email,
                "joined_at": request.user.date_joined,
                "total_completed_analyses": total_completed_analyses,
            }
        )
    AuthResponseSerializer,

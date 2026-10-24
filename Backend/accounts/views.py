from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import generics, permissions, serializers, status
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .serializers import CurrentUserSerializer, RegisterSerializer


class LoginView(ObtainAuthToken):
    """Exchange a username and password for an API token."""

    # A stale token in the request must not block logging in again.
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'login'


class RegisterView(generics.CreateAPIView):
    """Create a student account and return an API token for it."""

    serializer_class = RegisterSerializer
    authentication_classes = []
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'register'

    @extend_schema(responses={201: inline_serializer('Registration', {
        'token': serializers.CharField(), 'user': CurrentUserSerializer(),
    })})
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        token = Token.objects.create(user=user)
        return Response(
            {'token': token.key, 'user': CurrentUserSerializer(user).data}, status=status.HTTP_201_CREATED
        )


class LogoutView(APIView):
    """Revoke the caller's API token."""

    @extend_schema(request=None, responses={204: None})
    def post(self, request):
        Token.objects.filter(user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CurrentUserView(generics.RetrieveUpdateAPIView):
    """The signed-in user's own profile."""

    serializer_class = CurrentUserSerializer
    http_method_names = ['get', 'patch', 'head', 'options']

    def get_object(self):
        return self.request.user

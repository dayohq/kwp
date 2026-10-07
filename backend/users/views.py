from django.contrib.auth import login, logout
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import LoginSerializer, ProfileSerializer, RegistrationSerializer


@method_decorator(never_cache, name='dispatch')
class CsrfView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({'csrfToken': get_token(request)})


# DRF only enforces session CSRF for authenticated callers. Explicitly protect
# dispatch so anonymous login and registration also require Django CSRF checks.
@method_decorator(csrf_protect, name='dispatch')
@method_decorator(never_cache, name='dispatch')
class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(ProfileSerializer(serializer.save()).data, status=201)


@method_decorator(csrf_protect, name='dispatch')
@method_decorator(never_cache, name='dispatch')
class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        login(request, user)
        return Response(ProfileSerializer(user).data)


@method_decorator(never_cache, name='dispatch')
class MeView(APIView):
    def get(self, request):
        return Response(ProfileSerializer(request.user).data)


@method_decorator(csrf_protect, name='dispatch')
@method_decorator(never_cache, name='dispatch')
class LogoutView(APIView):
    def post(self, request):
        logout(request)
        return Response({'detail': 'Logged out.'})

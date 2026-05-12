from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .throttles import LoginThrottle

# All auth endpoints below are POST'd cross-origin by the SPA (gridar.app
# -> api.gridar.app) BEFORE any session exists. Django's CsrfViewMiddleware
# rejects them with 'CSRF Failed: CSRF token missing' unless we exempt
# them. Safe because these endpoints don't rely on session-cookie auth.
# The login flow's security comes from the username+password check (or the
# OAuth code in the social variants), not from a CSRF token.

COOKIE_OPTS = {
    'httponly': True,
    'secure': not settings.DEBUG,
    'samesite': 'Lax',
    'path': '/',
}

ACCESS_MAX_AGE = int(settings.SIMPLE_JWT['ACCESS_TOKEN_LIFETIME'].total_seconds())
REFRESH_MAX_AGE = int(settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME'].total_seconds())


@method_decorator(csrf_exempt, name='dispatch')
class CookieTokenObtainPairView(TokenObtainPairView):
    """Login: returns tokens in httpOnly cookies + JSON body (for backwards compat)."""
    throttle_classes = [LoginThrottle]

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            data = response.data
            response.set_cookie(
                'access_token', data['access'],
                max_age=ACCESS_MAX_AGE, **COOKIE_OPTS,
            )
            response.set_cookie(
                'refresh_token', data['refresh'],
                max_age=REFRESH_MAX_AGE, **COOKIE_OPTS,
            )
        return response


@method_decorator(csrf_exempt, name='dispatch')
class CookieTokenRefreshView(TokenRefreshView):
    """Refresh: reads refresh token from cookie or body."""
    throttle_classes = [LoginThrottle]

    def post(self, request, *args, **kwargs):
        # If refresh token is in cookie but not in body, inject it
        if 'refresh' not in request.data:
            cookie_refresh = request.COOKIES.get('refresh_token')
            if cookie_refresh:
                request.data._mutable = True
                request.data['refresh'] = cookie_refresh
                request.data._mutable = False

        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            data = response.data
            response.set_cookie(
                'access_token', data['access'],
                max_age=ACCESS_MAX_AGE, **COOKIE_OPTS,
            )
        return response


@method_decorator(csrf_exempt, name='dispatch')
class CookieLogoutView(TokenObtainPairView):
    """Logout: clears auth cookies."""

    def post(self, request, *args, **kwargs):
        response = Response({'detail': 'Logged out'})
        response.delete_cookie('access_token', path='/')
        response.delete_cookie('refresh_token', path='/')
        return response


# ---------------------------------------------------------------------------
# Lazy / progressive registration
# ---------------------------------------------------------------------------
# UX flow on /login:
#   1. User types email only.
#   2. Frontend POSTs to /api/auth/check-email/ -> {exists: bool}.
#   3. If exists -> reveal password field, POST to /api/auth/token/.
#      If not   -> reveal password + confirm fields, POST to /api/auth/register/.
#
# Email enumeration is partially exposed by check-email (any throttled request
# can probe whether an email is on the platform), which is the trade-off for
# the better UX. We mitigate via LoginThrottle (30/minute per IP). Not a
# concern at our scale; revisit if abuse appears.

def _validate_email(value):
    EmailValidator()(value)


def _set_jwt_cookies(response, access, refresh):
    response.set_cookie(
        'access_token', access,
        max_age=ACCESS_MAX_AGE, **COOKIE_OPTS,
    )
    response.set_cookie(
        'refresh_token', refresh,
        max_age=REFRESH_MAX_AGE, **COOKIE_OPTS,
    )


@method_decorator(csrf_exempt, name='dispatch')
class EmailCheckView(APIView):
    """POST /api/auth/check-email/ {email} -> {exists: bool}."""
    permission_classes = [AllowAny]
    throttle_classes = [LoginThrottle]

    def post(self, request):
        email = (request.data.get('email') or '').strip().lower()
        if not email:
            return Response({'error': 'email requis'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            _validate_email(email)
        except ValidationError:
            return Response({'error': 'email invalide'}, status=status.HTTP_400_BAD_REQUEST)

        UserModel = get_user_model()
        exists = (
            UserModel.objects.filter(email__iexact=email).exists()
            or UserModel.objects.filter(username__iexact=email).exists()
        )
        return Response({'exists': exists})


@method_decorator(csrf_exempt, name='dispatch')
class RegisterView(APIView):
    """POST /api/auth/register/ {email, password} -> creates the user, sets
    the same JWT cookie pair as CookieTokenObtainPairView, returns the tokens
    in the body for sessionStorage parity with the login flow."""
    permission_classes = [AllowAny]
    throttle_classes = [LoginThrottle]

    def post(self, request):
        email = (request.data.get('email') or '').strip().lower()
        password = request.data.get('password') or ''
        if not email or not password:
            return Response(
                {'error': 'email et mot de passe requis'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            _validate_email(email)
        except ValidationError:
            return Response({'error': 'email invalide'}, status=status.HTTP_400_BAD_REQUEST)

        UserModel = get_user_model()
        if (
            UserModel.objects.filter(email__iexact=email).exists()
            or UserModel.objects.filter(username__iexact=email).exists()
        ):
            return Response(
                {'error': 'compte déjà existant', 'email_exists': True},
                status=status.HTTP_409_CONFLICT,
            )

        # Password rules per AUTH_PASSWORD_VALIDATORS in settings.
        try:
            validate_password(password)
        except ValidationError as e:
            return Response(
                {'error': ' '.join(e.messages)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Use email as username so the user only ever needs to remember one.
        user = UserModel.objects.create_user(
            username=email,
            email=email,
            password=password,
        )

        # Auto-create a free Subscription so /billing/me/ works on day 1.
        try:
            from sites_mgmt.models import Subscription
            Subscription.objects.get_or_create(user=user)
        except Exception:
            # Don't block signup if Subscription model fails to import for some reason.
            pass

        refresh = RefreshToken.for_user(user)
        access = refresh.access_token
        response = Response(
            {'access': str(access), 'refresh': str(refresh)},
            status=status.HTTP_201_CREATED,
        )
        _set_jwt_cookies(response, str(access), str(refresh))
        return response

import os

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
# When the marketing site (gridar.app) and the dashboard SPA (e.g. gridar.app
# proxied, app.gridar.app, or a preview URL) live on different hosts within
# the same registrable domain, we need the cookie scoped to the parent
# domain so both surfaces see the same session. Set
# AUTH_COOKIE_DOMAIN=.gridar.app on Railway in production. Left unset, the
# cookie stays host-only (correct for localhost during dev).
_AUTH_COOKIE_DOMAIN = os.getenv('AUTH_COOKIE_DOMAIN', '').strip()
if _AUTH_COOKIE_DOMAIN:
    COOKIE_OPTS['domain'] = _AUTH_COOKIE_DOMAIN

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
    """Refresh: reads refresh token from cookie or body, rotates BOTH cookies.

    BUG fixed: previous version only wrote the new access_token cookie and not
    the new refresh_token. Combined with SIMPLE_JWT.ROTATE_REFRESH_TOKENS=True
    + BLACKLIST_AFTER_ROTATION=True, this meant the browser kept the blacklisted
    refresh token cookie after the first refresh and the second refresh attempt
    would 401, brutally logging the user out every ~2 hours.

    Also drops the `request.data._mutable` hack which only works for form data,
    not JSON requests. We validate via the simplejwt serializer directly.
    """
    throttle_classes = [LoginThrottle]

    def post(self, request, *args, **kwargs):
        from rest_framework_simplejwt.exceptions import (
            InvalidToken, TokenError,
        )
        from rest_framework_simplejwt.serializers import TokenRefreshSerializer

        refresh = request.data.get('refresh') or request.COOKIES.get('refresh_token')
        if not refresh:
            return Response(
                {'detail': 'No refresh token provided.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = TokenRefreshSerializer(data={'refresh': refresh})
        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as e:
            raise InvalidToken(e.args[0])

        data = serializer.validated_data
        response = Response(data, status=status.HTTP_200_OK)
        response.set_cookie(
            'access_token', data['access'],
            max_age=ACCESS_MAX_AGE, **COOKIE_OPTS,
        )
        # CRITICAL: when ROTATE_REFRESH_TOKENS=True, simplejwt returns a new
        # refresh in `data['refresh']` and blacklists the previous one. Without
        # writing the new cookie here, the next refresh attempt would use the
        # blacklisted token and fail.
        new_refresh = data.get('refresh')
        if new_refresh:
            response.set_cookie(
                'refresh_token', new_refresh,
                max_age=REFRESH_MAX_AGE, **COOKIE_OPTS,
            )
        return response


@method_decorator(csrf_exempt, name='dispatch')
class CookieLogoutView(APIView):
    """Logout: clears auth cookies. AllowAny because the user may be hitting
    this with an already-expired access token; we still want the cookies wiped."""
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        response = Response({'detail': 'Logged out'})
        # delete_cookie must mirror the domain used when the cookie was set,
        # otherwise the browser leaves the original cookie in place and the
        # user appears logged in until the access_token TTL elapses.
        response.delete_cookie('access_token', path='/', domain=_AUTH_COOKIE_DOMAIN or None)
        response.delete_cookie('refresh_token', path='/', domain=_AUTH_COOKIE_DOMAIN or None)
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
    """POST /api/auth/check-email/ {email}
    Returns:
      {
        exists: bool,
        has_password: bool,        # False if account was created via OAuth only
        social_providers: [str],   # e.g. ["google"]
      }

    The frontend uses has_password to decide whether to show the password field
    or pivot to OAuth buttons. Without this, a user who signed up via Google
    would be asked for a password they never set and get rejected on login.
    """
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
        user = (
            UserModel.objects.filter(email__iexact=email).first()
            or UserModel.objects.filter(username__iexact=email).first()
        )
        if not user:
            return Response({
                'exists': False,
                'has_password': False,
                'social_providers': [],
            })

        # has_usable_password() returns False when password is '!...' (set by
        # set_unusable_password). allauth does this for OAuth-only accounts.
        has_password = user.has_usable_password()

        social_providers = []
        try:
            from allauth.socialaccount.models import SocialAccount
            social_providers = list(
                SocialAccount.objects.filter(user=user)
                .values_list('provider', flat=True)
            )
        except Exception:
            pass

        return Response({
            'exists': True,
            'has_password': has_password,
            'social_providers': social_providers,
        })


# ---------------------------------------------------------------------------
# Password reset flow
# ---------------------------------------------------------------------------
# Two endpoints:
#   POST /api/auth/password/reset/request/  {email}
#     -> If a user with that email exists AND has a usable password,
#        generate a signed token and email a link `${FRONTEND_URL}/reset-password?token=...&uid=...`
#        Always returns 200 (don't leak which emails exist - same response shape).
#   POST /api/auth/password/reset/confirm/  {uid, token, password}
#     -> Validate uid + token, set new password, return JWT cookies so the user
#        is logged in immediately.
#
# Email backend: when DEBUG=True, prints to console. In prod, Django needs
# EMAIL_BACKEND + provider creds configured (Resend / Mailgun / SES). Until
# then, we log the full URL at INFO so Darius can grab it from Railway logs
# and DM it to the user if they ping support.

@method_decorator(csrf_exempt, name='dispatch')
class PasswordResetRequestView(APIView):
    """POST /api/auth/password/reset/request/ {email} -> {detail}"""
    permission_classes = [AllowAny]
    throttle_classes = [LoginThrottle]

    def post(self, request):
        import logging
        logger = logging.getLogger(__name__)

        email = (request.data.get('email') or '').strip().lower()
        if not email:
            return Response({'error': 'email requis'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            _validate_email(email)
        except ValidationError:
            return Response({'error': 'email invalide'}, status=status.HTTP_400_BAD_REQUEST)

        # Generic response shape regardless of whether the email exists. This
        # mitigates email enumeration via this endpoint (the check-email
        # endpoint exposes existence for UX reasons, but this one shouldn't).
        generic_ok = Response({
            'detail': (
                "Si un compte avec mot de passe est associé à cet email, "
                "un lien de réinitialisation vient d'être envoyé."
            )
        })

        UserModel = get_user_model()
        user = (
            UserModel.objects.filter(email__iexact=email).first()
            or UserModel.objects.filter(username__iexact=email).first()
        )
        if not user or not user.has_usable_password():
            # No user OR OAuth-only account (no password to reset).
            return generic_ok

        from django.contrib.auth.tokens import default_token_generator
        from django.utils.encoding import force_bytes
        from django.utils.http import urlsafe_base64_encode

        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        frontend = getattr(settings, 'FRONTEND_URL', 'https://gridar.app').rstrip('/')
        reset_url = f"{frontend}/reset-password?uid={uid}&token={token}"

        subject = "Gridar - Réinitialisation de ton mot de passe"
        body = (
            f"Quelqu'un (probablement toi) a demandé une réinitialisation du mot de passe "
            f"pour ce compte Gridar.\n\n"
            f"Clique ici pour choisir un nouveau mot de passe :\n{reset_url}\n\n"
            f"Le lien expire dans 24 heures. Si tu n'as pas fait cette demande, ignore ce courriel."
        )

        try:
            from django.core.mail import send_mail
            send_mail(
                subject=subject,
                message=body,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@gridar.app'),
                recipient_list=[user.email],
                fail_silently=True,
            )
        except Exception:
            logger.exception("Failed to send reset email")

        # Always log the URL too so we can fish it out of Railway logs while
        # SMTP isn't configured. Remove this once email is wired up properly.
        logger.info("Password reset URL for %s: %s", user.email, reset_url)

        return generic_ok


@method_decorator(csrf_exempt, name='dispatch')
class PasswordResetConfirmView(APIView):
    """POST /api/auth/password/reset/confirm/ {uid, token, password}
    -> 200 + JWT cookies (user logged in)
    -> 400 if invalid token / weak password
    """
    permission_classes = [AllowAny]
    throttle_classes = [LoginThrottle]

    def post(self, request):
        uid = request.data.get('uid') or ''
        token = request.data.get('token') or ''
        password = request.data.get('password') or ''
        if not uid or not token or not password:
            return Response(
                {'error': 'uid, token et password requis'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from django.contrib.auth.tokens import default_token_generator
        from django.utils.encoding import force_str
        from django.utils.http import urlsafe_base64_decode

        UserModel = get_user_model()
        try:
            user_pk = force_str(urlsafe_base64_decode(uid))
            user = UserModel.objects.get(pk=user_pk)
        except (TypeError, ValueError, UserModel.DoesNotExist):
            return Response(
                {'error': 'lien invalide'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not default_token_generator.check_token(user, token):
            return Response(
                {'error': 'lien invalide ou expiré'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            validate_password(password, user=user)
        except ValidationError as e:
            return Response(
                {'error': ' '.join(e.messages)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(password)
        user.save(update_fields=['password'])

        # Log the user in immediately by issuing a fresh JWT pair.
        refresh = RefreshToken.for_user(user)
        access = refresh.access_token
        response = Response(
            {'access': str(access), 'refresh': str(refresh)},
            status=status.HTTP_200_OK,
        )
        _set_jwt_cookies(response, str(access), str(refresh))
        return response


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

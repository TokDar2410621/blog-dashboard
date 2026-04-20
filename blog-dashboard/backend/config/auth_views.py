from django.conf import settings
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .throttles import LoginThrottle

COOKIE_OPTS = {
    'httponly': True,
    'secure': not settings.DEBUG,
    'samesite': 'Lax',
    'path': '/',
}

ACCESS_MAX_AGE = int(settings.SIMPLE_JWT['ACCESS_TOKEN_LIFETIME'].total_seconds())
REFRESH_MAX_AGE = int(settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME'].total_seconds())


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


class CookieLogoutView(TokenObtainPairView):
    """Logout: clears auth cookies."""

    def post(self, request, *args, **kwargs):
        response = Response({'detail': 'Logged out'})
        response.delete_cookie('access_token', path='/')
        response.delete_cookie('refresh_token', path='/')
        return response

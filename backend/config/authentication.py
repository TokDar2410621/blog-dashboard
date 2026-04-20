from rest_framework_simplejwt.authentication import JWTAuthentication


class CookieJWTAuthentication(JWTAuthentication):
    """Read JWT from httpOnly cookie if Authorization header is absent."""

    def authenticate(self, request):
        # Try standard header first
        result = super().authenticate(request)
        if result is not None:
            return result

        # Fall back to cookie
        raw_token = request.COOKIES.get('access_token')
        if raw_token is None:
            return None

        validated_token = self.get_validated_token(raw_token)
        return self.get_user(validated_token), validated_token

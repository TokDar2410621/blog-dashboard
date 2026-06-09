from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken


# Gridar's developer-API tokens (issued via /api/auth/tokens/) carry a
# distinct "btb_" prefix so they can be distinguished from session JWTs
# at a glance. ApiTokenAuthentication owns those - CookieJWTAuthentication
# must NOT try to validate them as JWTs (it would raise InvalidToken and
# DRF would stop processing further auth classes, breaking the MCP / n8n /
# Zapier paths).
API_TOKEN_BEARER_PREFIX = 'btb_'


class CookieJWTAuthentication(JWTAuthentication):
    """Read JWT from httpOnly cookie if Authorization header is absent.

    Auth-class composition note: when this class is paired with
    ApiTokenAuthentication on a view (`authentication_classes = [
    CookieJWTAuthentication, ApiTokenAuthentication]`), it must
    *gracefully decline* any Bearer token that's clearly not a JWT, so
    DRF moves on to the next class instead of failing with 401. Two
    decline paths:
      1. Header missing entirely -> super().authenticate() returns None.
      2. Header present but holds an API token (`Bearer btb_...`) ->
         return None ourselves so ApiTokenAuthentication can pick it up.
    """

    def authenticate(self, request):
        # Short-circuit: if the Authorization header is a Gridar API
        # token, defer to ApiTokenAuthentication instead of letting
        # simplejwt try (and fail) to parse it as a JWT.
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if (
            auth_header.lower().startswith('bearer ')
            and auth_header[len('bearer '):].strip().startswith(
                API_TOKEN_BEARER_PREFIX
            )
        ):
            return None

        # Defensive: even for non-API-token headers, swallow InvalidToken
        # from the header path so a malformed or expired JWT in the
        # Authorization header doesn't block the cookie fallback.
        try:
            result = super().authenticate(request)
        except InvalidToken:
            result = None
        if result is not None:
            return result

        # Fall back to cookie
        raw_token = request.COOKIES.get('access_token')
        if raw_token is None:
            return None

        validated_token = self.get_validated_token(raw_token)
        return self.get_user(validated_token), validated_token

"""
Social authentication endpoints. Google + GitHub login over JWT cookies.

The SPA flow:
  1. User clicks "Continue with Google/GitHub" on /login.
  2. SPA redirects to the provider's OAuth screen.
  3. Provider redirects back to https://gridar.app/auth/<provider>/callback?code=...
  4. SPA POSTs {code, redirect_uri} to /api/auth/<provider>/.
  5. THIS module exchanges the code for the user profile, creates/links the
     Django user via django-allauth, and issues a JWT pair.
  6. dj-rest-auth's JWTSerializer sets the access_token + refresh_token
     httpOnly cookies (same names CookieTokenObtainPairView uses), so the
     frontend's existing CookieJWTAuthentication picks them up automatically.

CSRF: these endpoints are cross-origin POSTs from the SPA. They don't use
session cookies (the JWT pair only gets set in the RESPONSE). We mark them
csrf_exempt so Django's CsrfViewMiddleware doesn't reject the request with
'CSRF token missing'. Safe because the security guarantee comes from the
OAuth `code` itself (single-use, bound to redirect_uri, verified with the
provider), not from session-tied CSRF tokens.
"""
from urllib.parse import urlparse

from allauth.socialaccount.providers.github.views import GitHubOAuth2Adapter
from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from allauth.socialaccount.providers.oauth2.client import OAuth2Client
from dj_rest_auth.registration.views import SocialLoginView
from django.conf import settings
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

# Hosts allowed to host the OAuth callback page. The exchange redirect_uri
# must EXACTLY match the one the SPA used at the authorize step, and the SPA
# builds it from window.location.origin - which is www.gridar.app or
# gridar.app depending on which one Vercel currently has as the primary
# domain. A hardcoded settings value breaks every time the primary flips
# (Google answers "invalid_grant" -> the UI shows "Echec de l'echange de
# code"). So we accept the SPA's value, but only after strict validation.
_ALLOWED_CALLBACK_HOSTS = {'gridar.app', 'www.gridar.app'}
_LOCAL_CALLBACK_HOSTS = {'localhost:5173', 'localhost:3000', '127.0.0.1:3000'}


def _negotiated_callback_url(request, provider: str, fallback: str) -> str:
    """Return the redirect_uri the SPA actually used at the authorize step,
    if and only if it matches our exact callback shape on a whitelisted
    host. Anything else falls back to the static settings value."""
    sent = (request.data.get('redirect_uri') or '').strip()
    if not sent:
        return fallback
    u = urlparse(sent)
    host = u.netloc.lower()
    path_ok = u.path == f'/auth/{provider}/callback'
    clean = not u.query and not u.fragment and not u.params
    if path_ok and clean:
        if u.scheme == 'https' and host in _ALLOWED_CALLBACK_HOSTS:
            return sent
        if u.scheme == 'http' and host in _LOCAL_CALLBACK_HOSTS and settings.DEBUG:
            return sent
    return fallback


@method_decorator(csrf_exempt, name='dispatch')
class GoogleLoginView(SocialLoginView):
    adapter_class = GoogleOAuth2Adapter
    client_class = OAuth2Client
    # CRITICAL: DRF's SessionAuthentication enforces its OWN CSRF check
    # (independent of Django's CsrfViewMiddleware that csrf_exempt covers).
    # On a cross-origin SPA POST it raises 'CSRF Failed: CSRF token missing'.
    # The OAuth `code` itself is the authentication credential here, no
    # session-tied auth needed - so wipe authentication_classes entirely.
    authentication_classes = []

    @property
    def callback_url(self):
        return _negotiated_callback_url(
            self.request, 'google', settings.GOOGLE_OAUTH_CALLBACK_URL,
        )


@method_decorator(csrf_exempt, name='dispatch')
class GitHubLoginView(SocialLoginView):
    adapter_class = GitHubOAuth2Adapter
    client_class = OAuth2Client
    authentication_classes = []  # see GoogleLoginView for the reason

    @property
    def callback_url(self):
        return _negotiated_callback_url(
            self.request, 'github', settings.GITHUB_OAUTH_CALLBACK_URL,
        )

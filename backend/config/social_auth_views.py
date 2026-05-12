"""
Social authentication endpoints - Google + GitHub login over JWT cookies.

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
"""
from allauth.socialaccount.providers.github.views import GitHubOAuth2Adapter
from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from allauth.socialaccount.providers.oauth2.client import OAuth2Client
from dj_rest_auth.registration.views import SocialLoginView
from django.conf import settings


class GoogleLoginView(SocialLoginView):
    adapter_class = GoogleOAuth2Adapter
    client_class = OAuth2Client

    @property
    def callback_url(self):
        return settings.GOOGLE_OAUTH_CALLBACK_URL


class GitHubLoginView(SocialLoginView):
    adapter_class = GitHubOAuth2Adapter
    client_class = OAuth2Client

    @property
    def callback_url(self):
        return settings.GITHUB_OAUTH_CALLBACK_URL

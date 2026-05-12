from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from .auth_views import (
    CookieTokenObtainPairView,
    CookieTokenRefreshView,
    CookieLogoutView,
    EmailCheckView,
    RegisterView,
)
from .social_auth_views import GoogleLoginView, GitHubLoginView

urlpatterns = [
    path('admin/', admin.site.urls),
    # Username/password login (existing flow, unchanged)
    path('api/auth/token/', CookieTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/auth/token/refresh/', CookieTokenRefreshView.as_view(), name='token_refresh'),
    path('api/auth/logout/', CookieLogoutView.as_view(), name='token_logout'),
    # Lazy / progressive registration: email-first flow.
    path('api/auth/check-email/', EmailCheckView.as_view(), name='auth_check_email'),
    path('api/auth/register/', RegisterView.as_view(), name='auth_register'),
    # Social login (Google + GitHub) via dj-rest-auth + django-allauth
    path('api/auth/google/', GoogleLoginView.as_view(), name='google_login'),
    path('api/auth/github/', GitHubLoginView.as_view(), name='github_login'),
    # Allauth's own URLs (signup confirmation flows etc., not used by the SPA but
    # required by allauth internals - namespaced under /accounts/).
    path('accounts/', include('allauth.urls')),
    path('api/', include('sites_mgmt.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

"""Public developer API — `/api/v1/*` endpoints.

Authenticated via Bearer ApiToken (separate from the dashboard JWT). Designed
for clients to integrate with their own automation (n8n, Zapier, Make, custom
scripts). Curated subset of internal endpoints; nothing destructive exposed.

Plan-based rate limits enforced at request time:
  free   → blocked entirely (403)
  pro    → 60 requests / hour / user
  agency → 600 requests / hour / user
"""
from __future__ import annotations

import hashlib
import logging
import os
import secrets
from datetime import timedelta

from django.utils import timezone
from rest_framework import authentication, exceptions, status
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from blog.models import BlogPost
from .models import (
    ApiToken, HostedPost, Site, Subscription, TrackedKeyword,
    SerpRank,
)

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

TOKEN_PREFIX = 'btb_'


def generate_api_token() -> tuple[str, str, str]:
    """Generate a new plain token + its hash + a short prefix for UI display.
    Returns (plain, hash_hex, prefix). Plain is shown ONCE to the user.
    """
    plain = TOKEN_PREFIX + secrets.token_urlsafe(32)
    h = hashlib.sha256(plain.encode('utf-8')).hexdigest()
    prefix = plain[:12]
    return plain, h, prefix


def _hash_token(plain: str) -> str:
    return hashlib.sha256(plain.encode('utf-8')).hexdigest()


def _get_subscription(user):
    sub, _ = Subscription.objects.get_or_create(user=user)
    return sub


# --------------------------------------------------------------------------
# DRF Authentication: Bearer ApiToken
# --------------------------------------------------------------------------

class ApiTokenAuthentication(authentication.BaseAuthentication):
    """Authenticates `Authorization: Bearer <plain_token>` against ApiToken
    rows. Updates last_used_at on success. Returns (user, token_obj)."""

    keyword = 'Bearer'

    def authenticate(self, request):
        auth = request.META.get('HTTP_AUTHORIZATION', '')
        if not auth or not auth.startswith(self.keyword + ' '):
            return None  # no header → fall through to other auth classes

        plain = auth.split(' ', 1)[1].strip()
        if not plain.startswith(TOKEN_PREFIX):
            raise exceptions.AuthenticationFailed('Format de token invalide.')

        try:
            tok = ApiToken.objects.select_related('user').get(
                key_hash=_hash_token(plain), revoked_at__isnull=True
            )
        except ApiToken.DoesNotExist:
            raise exceptions.AuthenticationFailed('Token invalide ou révoqué.')

        # Soft last_used update — fire-and-forget, no transaction
        ApiToken.objects.filter(pk=tok.pk).update(last_used_at=timezone.now())
        return (tok.user, tok)

    def authenticate_header(self, request):
        return self.keyword


# --------------------------------------------------------------------------
# Plan-based throttling
# --------------------------------------------------------------------------

PLAN_API_LIMITS = {
    'free': {'rate': 0, 'per_hour': 0},     # blocked
    'pro': {'rate': 60, 'per_hour': 60},
    'agency': {'rate': 600, 'per_hour': 600},
}


class ApiPlanThrottle(UserRateThrottle):
    """Per-user hourly rate limit derived from the user's subscription plan."""
    scope = 'api_v1'
    cache_format = 'throttle_api_v1_user_{ident}'

    def get_rate(self):
        # We override allow_request, so this just returns a sensible default.
        return '600/hour'

    def allow_request(self, request, view):
        user = getattr(request, 'user', None)
        if not user or not user.is_authenticated:
            return False
        sub = _get_subscription(user)
        limit = PLAN_API_LIMITS.get(sub.plan, PLAN_API_LIMITS['free'])['per_hour']
        if limit == 0:
            # Free plan → reject with explicit message via PlanGate below.
            return True  # let the view decide (we'll gate on plan in BaseV1View)
        # Manual sliding window using DRF's cache helpers
        self.num_requests = limit
        self.duration = 3600  # 1h
        self.key = self.cache_format.format(ident=user.pk)
        self.history = self.cache.get(self.key, [])
        self.now = self.timer()
        while self.history and self.history[-1] <= self.now - self.duration:
            self.history.pop()
        if len(self.history) >= self.num_requests:
            return False
        self.history.insert(0, self.now)
        self.cache.set(self.key, self.history, self.duration)
        return True


# --------------------------------------------------------------------------
# Base view: enforces ApiToken auth + plan check
# --------------------------------------------------------------------------

class BaseV1View(APIView):
    authentication_classes = [ApiTokenAuthentication]
    throttle_classes = [ApiPlanThrottle]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if not request.user or not request.user.is_authenticated:
            raise exceptions.AuthenticationFailed('Bearer token requis.')
        sub = _get_subscription(request.user)
        if sub.plan == 'free':
            raise exceptions.PermissionDenied(
                'Accès API réservé aux plans Pro et Agence. Mets à niveau sur /billing.'
            )

    def get_user_site(self, request, site_id):
        """Look up a site that belongs to the authenticated user. 404 otherwise."""
        try:
            return Site.objects.get(id=int(site_id), owner=request.user, is_active=True)
        except (Site.DoesNotExist, ValueError, TypeError):
            from django.http import Http404
            raise Http404('Site introuvable.')


# --------------------------------------------------------------------------
# Endpoints
# --------------------------------------------------------------------------

class V1MeView(BaseV1View):
    """GET /api/v1/me/ — sanity check."""
    def get(self, request):
        sub = _get_subscription(request.user)
        return Response({
            'username': request.user.username,
            'email': request.user.email,
            'plan': sub.plan,
            'rate_limit_per_hour': PLAN_API_LIMITS.get(sub.plan, {}).get('per_hour', 0),
        })


class V1SitesView(BaseV1View):
    """GET /api/v1/sites/ — list sites the authenticated user owns."""
    def get(self, request):
        sites = Site.objects.filter(owner=request.user, is_active=True)
        return Response({
            'results': [
                {
                    'id': s.id,
                    'name': s.name,
                    'domain': s.domain,
                    'is_hosted': s.is_hosted,
                    'is_wordpress': s.is_wordpress,
                    'default_language': s.default_language,
                    'available_languages': s.effective_languages,
                }
                for s in sites
            ]
        })


class V1ArticlesView(BaseV1View):
    """GET /api/v1/sites/<id>/articles/?status=published&language=fr&limit=50"""
    def get(self, request, site_id):
        site = self.get_user_site(request, site_id)
        try:
            limit = max(1, min(int(request.query_params.get('limit', 50)), 200))
        except (TypeError, ValueError):
            limit = 50
        status_filter = request.query_params.get('status')
        language = request.query_params.get('language')

        if site.is_wordpress:
            from .wordpress_adapter import WordPressClient, WordPressError
            try:
                page = WordPressClient(site).list_posts(
                    status=status_filter, language=language, per_page=limit
                )
                return Response(page)
            except WordPressError as e:
                return Response({'error': str(e)}, status=status.HTTP_502_BAD_GATEWAY)

        if site.is_hosted:
            qs = HostedPost.objects.filter(site=site)
        else:
            from .db_utils import ensure_site_connection
            alias = ensure_site_connection(site)
            qs = BlogPost.objects.using(alias).all()
        if status_filter:
            qs = qs.filter(status=status_filter)
        if language:
            qs = qs.filter(language=language)
        qs = qs.order_by('-published_at')[:limit]

        return Response({
            'results': [
                {
                    'slug': p.slug,
                    'title': p.title,
                    'excerpt': getattr(p, 'excerpt', ''),
                    'status': p.status,
                    'language': getattr(p, 'language', 'fr'),
                    'published_at': p.published_at.isoformat() if p.published_at else None,
                    'view_count': getattr(p, 'view_count', 0),
                }
                for p in qs
            ]
        })


class V1GenerateView(BaseV1View):
    """POST /api/v1/sites/<id>/generate/ {topic, title?, type?, length?, language?, keywords?, brief?}"""
    def post(self, request, site_id):
        site = self.get_user_site(request, site_id)
        from .article_generator import ArticleGenerator
        from .db_utils import ensure_site_connection

        topic = request.data.get('topic') or None
        title = request.data.get('title') or None
        article_type = request.data.get('type', 'guide')
        length = request.data.get('length', 'medium')
        language = (request.data.get('language') or 'fr').lower()
        keywords = request.data.get('keywords') or None
        brief = request.data.get('brief')
        if not isinstance(brief, dict):
            brief = None

        if language not in ('fr', 'en', 'es'):
            return Response({'error': 'Langue invalide.'}, status=status.HTTP_400_BAD_REQUEST)
        if not site.supports_language(language):
            return Response(
                {'error': f'Langue non autorisée pour ce site (langues: {site.effective_languages}).'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        alias = None if site.is_wordpress else ensure_site_connection(site)
        try:
            generator = ArticleGenerator(
                alias,
                knowledge_base=site.knowledge_base or '',
                wp_site=site if site.is_wordpress else None,
            )
            result = generator.generate(
                search_method='serper',
                topic=topic, title=title,
                article_type=article_type, length=length,
                keywords=keywords, dry_run=False,
                language=language, brief=brief,
            )
            return Response({
                'output': result['output'],
                'post_count': result['post_count'],
            })
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception('V1 generate failed')
            return Response({'error': f'Erreur génération: {str(e)[:120]}'},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class V1AuditView(BaseV1View):
    """POST /api/v1/audit/ {title, excerpt, content, keyword?, language='fr'}"""
    def post(self, request):
        from .views import _run_seo_audit
        title = request.data.get('title', '')
        excerpt = request.data.get('excerpt', '')
        content = request.data.get('content', '')
        keyword = request.data.get('keyword', '')
        language = (request.data.get('language') or 'fr').lower()
        if not title or not content:
            return Response({'error': 'title et content requis.'},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            result, from_cache = _run_seo_audit(
                title, excerpt, content, keyword=keyword, language=language
            )
        except RuntimeError as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            return Response({'error': f'Erreur audit: {str(e)[:120]}'},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response({**result, 'cache_hit': from_cache})


class V1BriefView(BaseV1View):
    """POST /api/v1/brief/ {keyword, language='fr'}"""
    def post(self, request):
        # Reuse the existing ContentBriefView logic by delegating
        from .views import ContentBriefView
        view = ContentBriefView()
        view.request = request
        view.kwargs = {}
        # ContentBriefView.post just reads request.data — call it directly.
        return view.post(request)


class V1KeywordsView(BaseV1View):
    """GET /api/v1/sites/<id>/keywords/ — list tracked keywords + latest rank."""
    def get(self, request, site_id):
        site = self.get_user_site(request, site_id)
        items = list(TrackedKeyword.objects.filter(site=site, is_active=True))
        latest_map = {}
        if items:
            ids = [k.id for k in items]
            for snap in (
                SerpRank.objects.filter(tracked_id__in=ids)
                .order_by('tracked_id', '-recorded_at')
            ):
                if snap.tracked_id not in latest_map:
                    latest_map[snap.tracked_id] = snap
        return Response({
            'results': [
                {
                    'id': k.id,
                    'keyword': k.keyword,
                    'language': k.language,
                    'target_url': k.target_url,
                    'latest_position': (
                        latest_map[k.id].position if k.id in latest_map else None
                    ),
                    'latest_recorded_at': (
                        latest_map[k.id].recorded_at.isoformat()
                        if k.id in latest_map else None
                    ),
                }
                for k in items
            ]
        })


class V1RankSnapshotView(BaseV1View):
    """POST /api/v1/sites/<id>/keywords/snapshot/ — trigger rank crawl now."""
    def post(self, request, site_id):
        site = self.get_user_site(request, site_id)
        from .views import RankSnapshotView
        view = RankSnapshotView()
        view.request = request
        view.kwargs = {'site_id': site.id}
        return view.post(request, site.id)


class V1DigestView(BaseV1View):
    """GET /api/v1/sites/<id>/digest/weekly/ — weekly digest JSON."""
    def get(self, request, site_id):
        site = self.get_user_site(request, site_id)
        from .views import WeeklyDigestView
        view = WeeklyDigestView()
        view.request = request
        view.kwargs = {'site_id': site.id}
        return view.get(request, site.id)


# --------------------------------------------------------------------------
# Token management — uses the dashboard's JWT auth (not Bearer api_token)
# --------------------------------------------------------------------------

from rest_framework.permissions import IsAuthenticated  # noqa: E402


class TokenManagementView(APIView):
    """GET / POST /account/api-tokens/ — list user's tokens or create one."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        tokens = ApiToken.objects.filter(user=request.user).order_by('-created_at')
        return Response({
            'results': [
                {
                    'id': t.id,
                    'name': t.name,
                    'prefix': t.key_prefix,
                    'last_used_at': t.last_used_at.isoformat() if t.last_used_at else None,
                    'revoked_at': t.revoked_at.isoformat() if t.revoked_at else None,
                    'created_at': t.created_at.isoformat(),
                    'is_active': t.is_active,
                }
                for t in tokens
            ]
        })

    def post(self, request):
        name = (request.data.get('name') or '').strip()[:100]
        if not name:
            return Response({'error': 'name requis.'},
                            status=status.HTTP_400_BAD_REQUEST)
        plain, key_hash, prefix = generate_api_token()
        tok = ApiToken.objects.create(
            user=request.user,
            name=name,
            key_hash=key_hash,
            key_prefix=prefix,
        )
        return Response({
            'id': tok.id,
            'name': tok.name,
            'token': plain,  # shown ONCE
            'prefix': tok.key_prefix,
            'created_at': tok.created_at.isoformat(),
            'message': "Stocke ce token dans un endroit sûr — il ne sera plus jamais affiché.",
        }, status=status.HTTP_201_CREATED)


class TokenRevokeView(APIView):
    """DELETE /account/api-tokens/<id>/ — revoke (soft-delete) a token."""
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        try:
            tok = ApiToken.objects.get(id=pk, user=request.user)
        except ApiToken.DoesNotExist:
            return Response({'error': 'Token introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)
        if tok.revoked_at:
            return Response({'message': 'Déjà révoqué.'})
        tok.revoked_at = timezone.now()
        tok.save(update_fields=['revoked_at'])
        return Response(status=status.HTTP_204_NO_CONTENT)

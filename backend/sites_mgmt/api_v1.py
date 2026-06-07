"""Public developer API - `/api/v1/*` endpoints.

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

        # Soft last_used update - fire-and-forget, no transaction
        ApiToken.objects.filter(pk=tok.pk).update(last_used_at=timezone.now())
        return (tok.user, tok)

    def authenticate_header(self, request):
        return self.keyword


# --------------------------------------------------------------------------
# Plan-based throttling
# --------------------------------------------------------------------------

PLAN_API_LIMITS = {
    'free':   {'rate': 0,   'per_hour': 0},    # blocked
    'solo':   {'rate': 0,   'per_hour': 0},    # blocked - API is Pro+ only
    'pro':    {'rate': 30,  'per_hour': 30},
    'agency': {'rate': 200, 'per_hour': 200},
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
        if sub.plan in ('free', 'solo'):
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
    """GET /api/v1/me/ - sanity check."""
    def get(self, request):
        from .quota import get_articles_used, current_month_key
        sub = _get_subscription(request.user)
        limits = sub.get_limits()
        return Response({
            'username': request.user.username,
            'email': request.user.email,
            'plan': sub.plan,
            'rate_limit_per_hour': PLAN_API_LIMITS.get(sub.plan, {}).get('per_hour', 0),
            'usage': {
                'articles_this_month': get_articles_used(request.user),
                'articles_per_month_limit': limits.get('articles_per_month'),
                'month_key': current_month_key(),
            },
        })


class V1SitesView(BaseV1View):
    """GET /api/v1/sites/ - list sites the authenticated user owns."""
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

        if site.is_shopify:
            from .shopify_adapter import ShopifyClient, ShopifyError
            try:
                page = ShopifyClient(site).list_posts(
                    status=status_filter, language=language, per_page=limit
                )
                return Response(page)
            except ShopifyError as e:
                return Response({'error': str(e)}, status=status.HTTP_502_BAD_GATEWAY)

        if site.is_webflow:
            from .webflow_adapter import WebflowClient, WebflowError
            try:
                page = WebflowClient(site).list_posts(
                    status=status_filter, language=language, per_page=limit
                )
                return Response(page)
            except WebflowError as e:
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


class V1ArticleDetailView(BaseV1View):
    """GET /api/v1/sites/<id>/articles/<slug>/ - single article with full content."""
    def get(self, request, site_id, slug):
        site = self.get_user_site(request, site_id)

        if site.is_wordpress:
            from .wordpress_adapter import WordPressClient, WordPressError
            try:
                post = WordPressClient(site).get_post(slug)
            except WordPressError as e:
                return Response({'error': str(e)}, status=status.HTTP_502_BAD_GATEWAY)
            if not post:
                return Response({'error': 'Article introuvable.'}, status=status.HTTP_404_NOT_FOUND)
            return Response(post)

        if site.is_shopify:
            from .shopify_adapter import ShopifyClient, ShopifyError
            try:
                post = ShopifyClient(site).get_post(slug)
            except ShopifyError as e:
                return Response({'error': str(e)}, status=status.HTTP_502_BAD_GATEWAY)
            if not post:
                return Response({'error': 'Article introuvable.'}, status=status.HTTP_404_NOT_FOUND)
            return Response(post)

        if site.is_webflow:
            from .webflow_adapter import WebflowClient, WebflowError
            try:
                post = WebflowClient(site).get_post(slug)
            except WebflowError as e:
                return Response({'error': str(e)}, status=status.HTTP_502_BAD_GATEWAY)
            if not post:
                return Response({'error': 'Article introuvable.'}, status=status.HTTP_404_NOT_FOUND)
            return Response(post)

        # Hosted / external Postgres
        if site.is_hosted:
            from .models import HostedPost
            try:
                p = HostedPost.objects.get(site=site, slug=slug)
            except HostedPost.DoesNotExist:
                return Response({'error': 'Article introuvable.'}, status=status.HTTP_404_NOT_FOUND)
            return Response({
                'slug': p.slug, 'title': p.title, 'excerpt': p.excerpt,
                'content': p.content, 'cover_image': p.cover_image,
                'language': p.language, 'status': p.status,
                'published_at': p.published_at.isoformat() if p.published_at else None,
                'updated_at': p.updated_at.isoformat() if p.updated_at else None,
            })

        from .db_utils import ensure_site_connection
        alias = ensure_site_connection(site)
        try:
            p = BlogPost.objects.using(alias).get(slug=slug)
        except BlogPost.DoesNotExist:
            return Response({'error': 'Article introuvable.'}, status=status.HTTP_404_NOT_FOUND)
        return Response({
            'slug': p.slug, 'title': p.title,
            'excerpt': getattr(p, 'excerpt', ''),
            'content': getattr(p, 'content', ''),
            'cover_image': getattr(p, 'cover_image', ''),
            'language': getattr(p, 'language', 'fr'),
            'status': p.status,
            'published_at': p.published_at.isoformat() if p.published_at else None,
            'updated_at': p.updated_at.isoformat() if p.updated_at else None,
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

        alias = None if (site.is_wordpress or site.is_shopify or site.is_webflow) else ensure_site_connection(site)

        # Enforce article quota (monthly first, then top-up credits).
        from .quota import check_article_quota, consume_article
        try:
            check_article_quota(request.user)
        except exceptions.PermissionDenied as e:
            return Response(
                {'error': str(e), 'quota_exceeded': True},
                status=status.HTTP_402_PAYMENT_REQUIRED,
            )

        try:
            generator = ArticleGenerator(
                alias,
                knowledge_base=site.knowledge_base or '',
                wp_site=site if site.is_wordpress else None,
                shopify_site=site if site.is_shopify else None,
                webflow_site=site if site.is_webflow else None,
                site=site,
            )
            result = generator.generate(
                search_method='serper',
                topic=topic, title=title,
                article_type=article_type, length=length,
                keywords=keywords, dry_run=False,
                language=language, brief=brief,
            )
            consume_article(request.user)
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
        # ContentBriefView.post just reads request.data - call it directly.
        return view.post(request)


class V1KeywordsView(BaseV1View):
    """GET /api/v1/sites/<id>/keywords/ - list tracked keywords + latest rank."""
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
    """POST /api/v1/sites/<id>/keywords/snapshot/ - trigger rank crawl now."""
    def post(self, request, site_id):
        site = self.get_user_site(request, site_id)
        from .views import RankSnapshotView
        view = RankSnapshotView()
        view.request = request
        view.kwargs = {'site_id': site.id}
        return view.post(request, site.id)


class V1DigestView(BaseV1View):
    """GET /api/v1/sites/<id>/digest/weekly/ - weekly digest JSON."""
    def get(self, request, site_id):
        site = self.get_user_site(request, site_id)
        from .views import WeeklyDigestView
        view = WeeklyDigestView()
        view.request = request
        view.kwargs = {'site_id': site.id}
        return view.get(request, site.id)


# --------------------------------------------------------------------------
# Token management - uses the dashboard's JWT auth (not Bearer api_token)
# --------------------------------------------------------------------------

from rest_framework.permissions import IsAuthenticated  # noqa: E402


class TokenManagementView(APIView):
    """GET / POST /account/api-tokens/ - list user's tokens or create one."""
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
            'message': "Stocke ce token dans un endroit sûr - il ne sera plus jamais affiché.",
        }, status=status.HTTP_201_CREATED)


class TokenRevokeView(APIView):
    """DELETE /account/api-tokens/<id>/ - revoke (soft-delete) a token."""
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


# --------------------------------------------------------------------------
# Extended v1 endpoints (added 2026-06-02 for the @gridar/mcp-server 0.2)
# --------------------------------------------------------------------------

class V1SiteDetailView(BaseV1View):
    """GET /api/v1/sites/<id>/ - full site config + integration status."""

    def get(self, request, site_id):
        s = self.get_user_site(request, site_id)
        return Response({
            'id': s.id, 'name': s.name, 'domain': s.domain,
            'is_hosted': s.is_hosted, 'is_wordpress': s.is_wordpress,
            'is_shopify': s.is_shopify, 'is_webflow': s.is_webflow,
            'default_language': s.default_language,
            'available_languages': s.effective_languages,
            'public_blog_domain': s.public_blog_domain,
            'description': getattr(s, 'description', ''),
            'knowledge_base': s.knowledge_base or '',
            'competitors': getattr(s, 'competitors', '') or '',
            'gsc_connected': bool(s.gsc_property_url and s.gsc_refresh_token),
            'gsc_property_url': s.gsc_property_url or '',
            'autopilot_enabled': bool(getattr(s, 'autopilot_enabled', False)),
            'author_bio': getattr(s, 'author_bio', '') or '',
            'author_credentials': getattr(s, 'author_credentials', '') or '',
        })


class V1SiteUpdateView(BaseV1View):
    """PATCH /api/v1/sites/<id>/ - update editable site fields.

    Whitelisted fields only: name, description, knowledge_base, competitors,
    default_language, author_bio, author_credentials, public_blog_domain.
    """
    EDITABLE = {
        'name', 'description', 'knowledge_base', 'competitors',
        'default_language', 'author_bio', 'author_credentials',
        'public_blog_domain',
    }

    def patch(self, request, site_id):
        s = self.get_user_site(request, site_id)
        updated = []
        for field, value in (request.data or {}).items():
            if field not in self.EDITABLE:
                continue
            if hasattr(s, field):
                setattr(s, field, value)
                updated.append(field)
        if updated:
            s.save(update_fields=updated)
        return Response({'updated_fields': updated, 'site_id': s.id})


class V1ArticleCreateView(BaseV1View):
    """POST /api/v1/sites/<id>/articles/manual/ - create a manual (non-AI) article."""

    def post(self, request, site_id):
        s = self.get_user_site(request, site_id)
        if not s.is_hosted:
            return Response(
                {'error': 'Manual article creation is only available on hosted sites.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        from django.utils.text import slugify
        data = request.data or {}
        title = (data.get('title') or '').strip()
        content = data.get('content') or ''
        if not title or not content:
            return Response(
                {'error': 'title and content are required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        slug = (data.get('slug') or slugify(title))[:200]
        if HostedPost.objects.filter(site=s, slug=slug).exists():
            return Response(
                {'error': f'Slug "{slug}" already exists on this site.'},
                status=status.HTTP_409_CONFLICT,
            )
        from datetime import date as _date
        status_val = (data.get('status') or 'draft').lower()
        if status_val not in ('draft', 'published', 'scheduled'):
            status_val = 'draft'
        post = HostedPost.objects.create(
            site=s,
            title=title[:200],
            slug=slug,
            excerpt=(data.get('excerpt') or '')[:500],
            content=content,
            author=(data.get('author') or 'API')[:100],
            language=(data.get('language') or s.default_language or 'fr')[:2],
            status=status_val,
            cover_image=(data.get('cover_image') or '')[:500],
            published_at=_date.today() if status_val == 'published' else None,
        )
        return Response(
            {'slug': post.slug, 'id': post.id, 'status': post.status},
            status=status.HTTP_201_CREATED,
        )


class V1ArticleMutateView(BaseV1View):
    """PATCH/DELETE /api/v1/sites/<id>/articles/<slug>/manual/.

    PATCH: partial update (title, excerpt, content, status, cover_image, slug).
    DELETE: delete the article.

    Cross-mode: works on hosted (HostedPost), external (BlogPost via alias),
    WordPress, Shopify, and Webflow sites. The adapter is selected from
    the site's mode flag; if the underlying CMS rejects the change a 502
    Bad Gateway is returned with the upstream error message.
    """
    UPDATABLE = {'title', 'excerpt', 'content', 'status',
                 'cover_image', 'slug', 'author'}

    def _collect_fields(self, data):
        fields = {}
        for key, value in (data or {}).items():
            if key not in self.UPDATABLE:
                continue
            if key == 'status' and value not in ('draft', 'published', 'scheduled'):
                continue
            fields[key] = value
        return fields

    # ── Adapter dispatch (PATCH) ────────────────────────────────────────

    def patch(self, request, site_id, slug):
        site = self.get_user_site(request, site_id)
        fields = self._collect_fields(request.data)
        if not fields:
            return Response({'updated_fields': [], 'slug': slug})

        if site.is_wordpress:
            from .wordpress_adapter import WordPressClient, WordPressError
            return self._patch_via_adapter(
                WordPressClient(site), WordPressError, slug, fields,
            )
        if site.is_shopify:
            from .shopify_adapter import ShopifyClient, ShopifyError
            return self._patch_via_adapter(
                ShopifyClient(site), ShopifyError, slug, fields,
            )
        if site.is_webflow:
            from .webflow_adapter import WebflowClient, WebflowError
            return self._patch_via_adapter(
                WebflowClient(site), WebflowError, slug, fields,
            )
        if site.is_hosted:
            return self._patch_hosted(site, slug, fields)
        return self._patch_external(site, slug, fields)

    def _patch_hosted(self, site, slug, fields):
        try:
            post = HostedPost.objects.get(site=site, slug=slug)
        except HostedPost.DoesNotExist:
            return Response({'error': 'Article introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)
        updated = []
        for key, value in fields.items():
            setattr(post, key, value)
            updated.append(key)
        if 'status' in updated and post.status == 'published' and not post.published_at:
            from datetime import date as _date
            post.published_at = _date.today()
            updated.append('published_at')
        post.save(update_fields=updated)
        return Response({'updated_fields': updated, 'slug': post.slug})

    def _patch_external(self, site, slug, fields):
        from .db_utils import ensure_site_connection
        alias = ensure_site_connection(site)
        try:
            post = BlogPost.objects.using(alias).get(slug=slug)
        except BlogPost.DoesNotExist:
            return Response({'error': 'Article introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)
        updated = []
        for key, value in fields.items():
            if not hasattr(post, key):
                continue
            setattr(post, key, value)
            updated.append(key)
        if updated:
            post.save(using=alias, update_fields=updated)
        return Response({'updated_fields': updated, 'slug': post.slug})

    def _patch_via_adapter(self, client, error_cls, slug, fields):
        """Lookup the post by slug, then PATCH via the CMS adapter."""
        try:
            current = client.get_post(slug)
        except error_cls as e:
            return Response({'error': str(e)},
                            status=status.HTTP_502_BAD_GATEWAY)
        if not current:
            return Response({'error': 'Article introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)
        post_id = current.get('id') or current.get('post_id')
        if not post_id:
            return Response(
                {'error': 'Adapter did not return a post id.'},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        try:
            updated_post = client.update_post(post_id, **fields)
        except error_cls as e:
            return Response({'error': str(e)},
                            status=status.HTTP_502_BAD_GATEWAY)
        return Response({
            'updated_fields': list(fields.keys()),
            'slug': updated_post.get('slug', slug),
        })

    # ── Adapter dispatch (DELETE) ───────────────────────────────────────

    def delete(self, request, site_id, slug):
        site = self.get_user_site(request, site_id)

        if site.is_wordpress:
            from .wordpress_adapter import WordPressClient, WordPressError
            return self._delete_via_adapter(WordPressClient(site), WordPressError, slug)
        if site.is_shopify:
            from .shopify_adapter import ShopifyClient, ShopifyError
            return self._delete_via_adapter(ShopifyClient(site), ShopifyError, slug)
        if site.is_webflow:
            from .webflow_adapter import WebflowClient, WebflowError
            return self._delete_via_adapter(WebflowClient(site), WebflowError, slug)
        if site.is_hosted:
            try:
                post = HostedPost.objects.get(site=site, slug=slug)
            except HostedPost.DoesNotExist:
                return Response({'error': 'Article introuvable.'},
                                status=status.HTTP_404_NOT_FOUND)
            post.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        # External
        from .db_utils import ensure_site_connection
        alias = ensure_site_connection(site)
        try:
            post = BlogPost.objects.using(alias).get(slug=slug)
        except BlogPost.DoesNotExist:
            return Response({'error': 'Article introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)
        post.delete(using=alias)
        return Response(status=status.HTTP_204_NO_CONTENT)

    def _delete_via_adapter(self, client, error_cls, slug):
        try:
            current = client.get_post(slug)
        except error_cls as e:
            return Response({'error': str(e)},
                            status=status.HTTP_502_BAD_GATEWAY)
        if not current:
            return Response({'error': 'Article introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)
        post_id = current.get('id') or current.get('post_id')
        if not post_id:
            return Response(
                {'error': 'Adapter did not return a post id.'},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        try:
            client.delete_post(post_id, force=True)
        except error_cls as e:
            return Response({'error': str(e)},
                            status=status.HTTP_502_BAD_GATEWAY)
        return Response(status=status.HTTP_204_NO_CONTENT)


class V1KeywordTrackView(BaseV1View):
    """POST /api/v1/sites/<id>/keywords/ - track a new keyword.

    DELETE /api/v1/sites/<id>/keywords/<pk>/ - untrack (soft via is_active=False).
    """

    def post(self, request, site_id):
        s = self.get_user_site(request, site_id)
        data = request.data or {}
        keyword = (data.get('keyword') or '').strip()
        if not keyword:
            return Response({'error': 'keyword required.'},
                            status=status.HTTP_400_BAD_REQUEST)
        language = (data.get('language') or s.default_language or 'fr')[:2]
        target_url = (data.get('target_url') or '')[:500]
        from .quota import check_keyword_quota
        try:
            check_keyword_quota(request.user)
        except exceptions.PermissionDenied as e:
            return Response({'error': str(e), 'limit_exceeded': True},
                            status=status.HTTP_402_PAYMENT_REQUIRED)
        existing = TrackedKeyword.objects.filter(
            site=s, keyword=keyword, language=language
        ).first()
        if existing:
            if not existing.is_active:
                existing.is_active = True
                existing.save(update_fields=['is_active'])
            return Response(
                {'id': existing.id, 'keyword': existing.keyword,
                 'language': existing.language, 'reactivated': not existing.is_active},
            )
        tk = TrackedKeyword.objects.create(
            site=s, keyword=keyword, language=language,
            target_url=target_url, is_active=True,
        )
        return Response(
            {'id': tk.id, 'keyword': tk.keyword, 'language': tk.language},
            status=status.HTTP_201_CREATED,
        )


class V1KeywordUntrackView(BaseV1View):
    """DELETE /api/v1/sites/<id>/keywords/<pk>/"""

    def delete(self, request, site_id, pk):
        s = self.get_user_site(request, site_id)
        try:
            tk = TrackedKeyword.objects.get(site=s, id=pk)
        except TrackedKeyword.DoesNotExist:
            return Response({'error': 'Keyword introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)
        tk.is_active = False
        tk.save(update_fields=['is_active'])
        return Response(status=status.HTTP_204_NO_CONTENT)


def _delegate(dashboard_view_cls, request, **kwargs):
    """Instantiate a dashboard APIView and call its handler with the v1 request."""
    view = dashboard_view_cls()
    view.request = request
    view.kwargs = kwargs
    method = request.method.lower()
    handler = getattr(view, method, None)
    if not handler:
        return Response({'error': f'Method {request.method} not allowed.'},
                        status=status.HTTP_405_METHOD_NOT_ALLOWED)
    return handler(request, **kwargs)


class V1CompetitorsAnalyzeView(BaseV1View):
    """POST /api/v1/competitors/ {keyword, language} - analyze SERP top 10."""

    def post(self, request):
        from .views import CompetitorAnalysisView
        return _delegate(CompetitorAnalysisView, request)


class V1ContentDecayView(BaseV1View):
    """GET /api/v1/sites/<id>/content-decay/?days=30"""

    def get(self, request, site_id):
        s = self.get_user_site(request, site_id)
        from .views import ContentDecayView
        return _delegate(ContentDecayView, request, site_id=s.id)


class V1BrokenLinksView(BaseV1View):
    """GET /api/v1/sites/<id>/broken-links/"""

    def get(self, request, site_id):
        s = self.get_user_site(request, site_id)
        from .views import BrokenLinksView
        return _delegate(BrokenLinksView, request, site_id=s.id)


class V1HreflangCheckView(BaseV1View):
    """POST /api/v1/hreflang-check/"""

    def post(self, request):
        from .views import HreflangCheckView
        return _delegate(HreflangCheckView, request)


class V1CannibalizationView(BaseV1View):
    """GET /api/v1/sites/<id>/cannibalization/"""

    def get(self, request, site_id):
        s = self.get_user_site(request, site_id)
        from .views import SiteCannibalizationView
        return _delegate(SiteCannibalizationView, request, site_id=s.id)


class V1LinkSuggestionsView(BaseV1View):
    """POST /api/v1/sites/<id>/link-suggestions/"""

    def post(self, request, site_id):
        s = self.get_user_site(request, site_id)
        from .views import LinkSuggestionsView
        return _delegate(LinkSuggestionsView, request, site_id=s.id)


class V1BulkAuditView(BaseV1View):
    """GET /api/v1/sites/<id>/audit-all/"""

    def get(self, request, site_id):
        s = self.get_user_site(request, site_id)
        from .views import BulkSEOAuditView
        return _delegate(BulkSEOAuditView, request, site_id=s.id)


class V1ReadabilityView(BaseV1View):
    """POST /api/v1/readability/ {content, language}"""

    def post(self, request):
        from .views import ReadabilityView
        return _delegate(ReadabilityView, request)


class V1PlagiarismView(BaseV1View):
    """POST /api/v1/plagiarism/ {content}"""

    def post(self, request):
        from .views import PlagiarismCheckView
        return _delegate(PlagiarismCheckView, request)


class V1GSCQueriesView(BaseV1View):
    """GET /api/v1/sites/<id>/gsc/queries/?days=28&limit=50"""

    def get(self, request, site_id):
        s = self.get_user_site(request, site_id)
        from .views import GSCQueriesView
        return _delegate(GSCQueriesView, request, site_id=s.id)


class V1AutopilotConfigView(BaseV1View):
    """GET/POST /api/v1/sites/<id>/autopilot/"""

    def get(self, request, site_id):
        s = self.get_user_site(request, site_id)
        from .views import AutopilotConfigView
        return _delegate(AutopilotConfigView, request, site_id=s.id)

    def post(self, request, site_id):
        s = self.get_user_site(request, site_id)
        from .views import AutopilotConfigView
        return _delegate(AutopilotConfigView, request, site_id=s.id)


class V1AutopilotRunView(BaseV1View):
    """POST /api/v1/sites/<id>/autopilot/run/ - manual trigger."""

    def post(self, request, site_id):
        s = self.get_user_site(request, site_id)
        from .views import AutopilotRunView
        return _delegate(AutopilotRunView, request, site_id=s.id)


class V1MemoriesListView(BaseV1View):
    """GET/POST /api/v1/sites/<id>/memories/

    GET: list site memories.
    POST {content, title?, kind='manual'}: add a manual note.
    """

    def get(self, request, site_id):
        s = self.get_user_site(request, site_id)
        from .views import SiteMemoryView
        return _delegate(SiteMemoryView, request, site_id=s.id)

    def post(self, request, site_id):
        s = self.get_user_site(request, site_id)
        from .views import SiteMemoryView
        return _delegate(SiteMemoryView, request, site_id=s.id)


class V1MemoryDetailView(BaseV1View):
    """DELETE /api/v1/sites/<id>/memories/<pk>/"""

    def delete(self, request, site_id, pk):
        s = self.get_user_site(request, site_id)
        from .views import SiteMemoryDetailView
        return _delegate(SiteMemoryDetailView, request, site_id=s.id, pk=pk)


class V1MemoryRebuildView(BaseV1View):
    """POST /api/v1/sites/<id>/memories/rebuild/"""

    def post(self, request, site_id):
        s = self.get_user_site(request, site_id)
        from .views import SiteMemoryRebuildView
        return _delegate(SiteMemoryRebuildView, request, site_id=s.id)


class V1ProofSummaryView(BaseV1View):
    """GET /api/v1/sites/<id>/proof/summary/"""

    def get(self, request, site_id):
        s = self.get_user_site(request, site_id)
        from .views_proof import ProofSummaryView
        return _delegate(ProofSummaryView, request, site_id=s.id)


class V1ProofAttributionView(BaseV1View):
    """GET /api/v1/sites/<id>/proof/attribution/?post=<pk>"""

    def get(self, request, site_id):
        s = self.get_user_site(request, site_id)
        from .views_proof import ProofAttributionView
        return _delegate(ProofAttributionView, request, site_id=s.id)


class V1ProofShareView(BaseV1View):
    """GET/POST/DELETE /api/v1/sites/<id>/proof/share/"""

    def get(self, request, site_id):
        s = self.get_user_site(request, site_id)
        from .views_proof import ProofShareView
        return _delegate(ProofShareView, request, site_id=s.id)

    def post(self, request, site_id):
        s = self.get_user_site(request, site_id)
        from .views_proof import ProofShareView
        return _delegate(ProofShareView, request, site_id=s.id)

    def delete(self, request, site_id):
        s = self.get_user_site(request, site_id)
        from .views_proof import ProofShareView
        return _delegate(ProofShareView, request, site_id=s.id)


class V1SuggestKeywordsView(BaseV1View):
    """POST /api/v1/sites/<id>/suggest-keywords/"""

    def post(self, request, site_id):
        s = self.get_user_site(request, site_id)
        from .views import SuggestKeywordsView
        return _delegate(SuggestKeywordsView, request, site_id=s.id)


class V1SuggestCompetitorsView(BaseV1View):
    """POST /api/v1/sites/<id>/suggest-competitors/"""

    def post(self, request, site_id):
        s = self.get_user_site(request, site_id)
        from .views import SuggestCompetitorsView
        return _delegate(SuggestCompetitorsView, request, site_id=s.id)


class V1KeywordResearchView(BaseV1View):
    """POST /api/v1/keyword-research/"""

    def post(self, request):
        from .views import KeywordResearchView
        return _delegate(KeywordResearchView, request)


class V1PageSpeedView(BaseV1View):
    """POST /api/v1/page-speed/"""

    def post(self, request):
        from .views import PageSpeedView
        return _delegate(PageSpeedView, request)


class V1PAAView(BaseV1View):
    """POST /api/v1/paa/ - People Also Ask harvest."""

    def post(self, request):
        from .views import PAAView
        return _delegate(PAAView, request)

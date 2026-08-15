"""Public developer API - `/api/v1/*` endpoints.

Two callers share these endpoints:
  1. External integrations (n8n, Zapier, MCP, scripts) authenticate via
     Bearer ApiToken.
  2. The Gridar dashboard itself - logged-in users in the browser - calls
     /api/v1/sites/<id>/ai-visibility/* and friends with the same httpOnly
     JWT cookie that secures the rest of the dashboard. We accept both auth
     classes so the dashboard doesn't have to mint and manage an API token
     just to read its own data.

Plan-based gating: external Bearer-token requests on free/solo plans are
blocked (this is paid-API territory). Cookie-authenticated dashboard users
go through the same plan check; the frontend should render an upgrade
banner when it gets the resulting 403.

Plan-based rate limits enforced at request time:
  free   → blocked entirely (403)
  pro    → 60 requests / hour / user
  agency → 600 requests / hour / user
"""
from __future__ import annotations

import hashlib
import logging
import os
import re
import secrets
import unicodedata
from datetime import timedelta

import requests

from django.utils import timezone
from rest_framework import authentication, exceptions, status
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from config.authentication import CookieJWTAuthentication
from blog.models import BlogPost
from .models import (
    AiVisibilityPrompt, AiVisibilityResult,
    ApiToken, HostedPost, HostedLanding, KeywordStrategy,
    Site, Subscription, TrackedKeyword, SerpRank,
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
        # DRF calls wait() on us after a False to compute Retry-After. If we
        # short-circuit before setting num_requests / duration / history /
        # now (e.g. for an anonymous request), wait() crashes with
        # AttributeError, which is uncaught and surfaces as a 500 HTML to
        # the client. Seed safe defaults upfront so an early `return False`
        # still leaves wait() callable.
        self.num_requests = 1
        self.duration = 3600
        self.history = []
        self.now = self.timer()

        user = getattr(request, 'user', None)
        if not user or not user.is_authenticated:
            # Let DRF respond with the standard 401 from the view layer.
            # We don't throttle anonymous calls here.
            return True
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
    # CookieJWTAuthentication first so the dashboard's existing session
    # cookie authenticates without a Bearer token. ApiTokenAuthentication
    # stays as the fallback for external integrations (n8n, MCP, scripts)
    # that present `Authorization: Bearer btb_...`.
    authentication_classes = [CookieJWTAuthentication, ApiTokenAuthentication]
    throttle_classes = [ApiPlanThrottle]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if not request.user or not request.user.is_authenticated:
            raise exceptions.AuthenticationFailed(
                'Session ou Bearer token requis.'
            )
        # Plan-gate the *developer API* surface (Bearer ApiToken). When the
        # caller is the dashboard (cookie JWT), let them through - the
        # frontend is the gating layer there (hide Pro-only features for
        # free/solo users in the sidebar). Staff bypass everything.
        if request.user.is_staff:
            return
        authenticator = getattr(request, 'successful_authenticator', None)
        if isinstance(authenticator, ApiTokenAuthentication):
            sub = _get_subscription(request.user)
            if sub.plan in ('free', 'solo'):
                raise exceptions.PermissionDenied(
                    'Accès API réservé aux plans Pro et Agence. '
                    'Mets à niveau sur /billing.'
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
        from .delivery import block_reason
        _blk = block_reason(site)
        if _blk:
            return Response({'error': _blk, 'code': 'delivery_blocked'},
                            status=status.HTTP_409_CONFLICT)
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

        # Mandatory onboarding: refuse to generate if the site has no
        # business_model declared OR no author_bio (E-E-A-T signal). Both
        # drive prompt construction, so missing them produces generic slop.
        missing_fields = []
        if not (site.business_model or '').strip():
            missing_fields.append('business_model')
        if not (site.author_bio or '').strip():
            missing_fields.append('author_bio')
        if missing_fields:
            return Response(
                {
                    'error': (
                        "Onboarding incomplet : renseigne d'abord ces champs dans "
                        "les paramètres du site avant de générer un article."
                    ),
                    'missing_fields': missing_fields,
                },
                status=422,
            )

        alias = None if (site.is_hosted or site.is_wordpress or site.is_shopify or site.is_webflow) else ensure_site_connection(site)

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


class V1GenerateSisterArticleView(BaseV1View):
    """POST /api/v1/sites/<id>/articles/<slug>/generate-sister-article/

    Body: {"target_language": "fr" | "en" | "es"}

    Translate + adapt the source article into `target_language` and create a
    new HostedPost in the same translation_group, so the hreflang alternates
    wiring picks it up automatically. Consumes one article from the user's
    monthly quota (translations count as articles).

    Only available on hosted-mode sites (HostedPost). CMS-backed sites
    (WordPress / Shopify / Webflow) get a 400 - they'd need adapter-specific
    create paths we don't have yet.
    """
    def post(self, request, site_id, slug):
        site = self.get_user_site(request, site_id)
        from .delivery import block_reason
        _blk = block_reason(site)
        if _blk:
            return Response({'error': _blk, 'code': 'delivery_blocked'},
                            status=status.HTTP_409_CONFLICT)
        from .article_generator import ArticleGenerator

        if not site.is_hosted:
            return Response(
                {'error': 'Sister article generation is only available on hosted sites.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        target_language = (request.data.get('target_language') or '').lower().strip()
        if target_language not in ('fr', 'en', 'es'):
            return Response(
                {'error': "target_language must be one of: 'fr', 'en', 'es'."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not site.supports_language(target_language):
            return Response(
                {'error': f'Langue non autorisee pour ce site (langues: {site.effective_languages}).'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            source_post = HostedPost.objects.get(site=site, slug=slug)
        except HostedPost.DoesNotExist:
            return Response({'error': 'Article source introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)

        # Quota: a sister article is a generation event. Block if the user
        # would exceed their monthly plan + credit balance.
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
                alias=None,
                knowledge_base=site.knowledge_base or '',
                site=site,
            )
            new_post = generator.generate_sister_article(source_post, target_language)
            consume_article(request.user)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception('V1 generate-sister-article failed')
            return Response(
                {'error': f'Erreur generation traduction: {str(e)[:120]}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            {
                'slug': new_post.slug,
                'id': new_post.id,
                'language': new_post.language,
                'translation_group': str(new_post.translation_group),
                'status': new_post.status,
                'title': new_post.title,
            },
            status=status.HTTP_201_CREATED,
        )


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

        # Deterministic pass over the same text. The LLM audit reads a precise
        # figure as an E-E-A-T signal and scores it up, so an article full of
        # invented statistics comes back praised: measured on a real draft, it
        # returned 93/100 and quoted the fabricated numbers as proof of
        # first-hand experience. Regexes cannot know a figure is false either,
        # but they can say nobody cited a source for it, which is the part the
        # model gets backwards.
        sourcing = None
        try:
            from .content_verify import verify_text
            sourcing = verify_text(content, lang=language)
        except Exception:  # noqa: BLE001 - never let the check break the audit
            logger.exception('content_verify failed on audit')

        payload = {**result, 'cache_hit': from_cache}
        if sourcing is not None:
            payload['sourcing'] = sourcing
        return Response(payload)


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
        from .rank_display import keyword_display_rank, DEFAULT_WINDOW

        site = self.get_user_site(request, site_id)
        items = list(TrackedKeyword.objects.filter(site=site, is_active=True))
        # One bulk query for both the latest reading and the stability window.
        latest_map = {}
        snaps_map = {}
        if items:
            ids = [k.id for k in items]
            for snap in (
                SerpRank.objects.filter(tracked_id__in=ids)
                .order_by('tracked_id', '-recorded_at')
            ):
                if snap.tracked_id not in latest_map:
                    latest_map[snap.tracked_id] = snap
                bucket = snaps_map.setdefault(snap.tracked_id, [])
                if len(bucket) < DEFAULT_WINDOW:
                    bucket.append(snap)
        results = []
        for k in items:
            row = {
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
            # Stability-aware honest rank (same shape as the dashboard endpoints).
            row.update(keyword_display_rank(k, snapshots=snaps_map.get(k.id)))
            results.append(row)
        return Response({'results': results})


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
# OAuth-MCP token issuance (2026-06-07)
# --------------------------------------------------------------------------
# Used by the gridar.app /oauth/mcp-authorize bridge page:
# the user is logged in (JWT cookie), this endpoint mints an ApiToken on
# their behalf, named after the requesting client (Claude Desktop /
# Code / Cursor / ...). The plain token is then returned to the MCP
# Streamable HTTP server's callback so it can complete the OAuth flow
# with the MCP client.

class IssueMcpTokenView(APIView):
    """POST /api/auth/issue-mcp-token/

    Body: {"client_name": "Claude Desktop", "scope": "mcp:full"}
    Auth: JWT cookie (user logged in via the dashboard).
    Returns: {"access_token": "btb_xxx", "token_type": "Bearer", "name": "..."}
    """
    permission_classes = [IsAuthenticated]
    plan_gated = False  # explicit: do NOT enforce the v1 plan gate here

    def post(self, request):
        client_name = (request.data.get('client_name') or 'MCP client').strip()[:60]
        scope = (request.data.get('scope') or 'mcp:full').strip()[:40]
        token_name = f"MCP - {client_name}"

        plain, key_hash, prefix = generate_api_token()
        tok = ApiToken.objects.create(
            user=request.user,
            name=token_name[:100],
            key_hash=key_hash,
            key_prefix=prefix,
        )
        return Response({
            'access_token': plain,
            'token_type': 'Bearer',
            'name': tok.name,
            'prefix': tok.key_prefix,
            'scope': scope,
            'created_at': tok.created_at.isoformat(),
        }, status=status.HTTP_201_CREATED)


# --------------------------------------------------------------------------
# Extended v1 endpoints (added 2026-06-02 for the @gridar/mcp-server 0.2)
# --------------------------------------------------------------------------

class V1SiteDetailView(BaseV1View):
    """GET /api/v1/sites/<id>/ - full site config + integration status."""

    def get(self, request, site_id):
        from .delivery import delivery_status
        s = self.get_user_site(request, site_id)
        return Response({
            'id': s.id, 'name': s.name, 'domain': s.domain,
            'is_hosted': s.is_hosted, 'is_wordpress': s.is_wordpress,
            'is_shopify': s.is_shopify, 'is_webflow': s.is_webflow,
            'delivery_mode': getattr(s, 'delivery_mode', 'auto'),
            'delivery_status': delivery_status(s),
            'default_language': s.default_language,
            'available_languages': s.effective_languages,
            'public_blog_domain': s.public_blog_domain,
            'description': getattr(s, 'description', ''),
            'knowledge_base': s.knowledge_base or '',
            'competitors': getattr(s, 'competitors', '') or '',
            'gsc_connected': bool(s.gsc_property_url and s.gsc_refresh_token),
            'gsc_property_url': s.gsc_property_url or '',
            'autopilot_enabled': bool(getattr(s, 'autopilot_enabled', False)),
            'autopilot_mode': getattr(s, 'autopilot_mode', 'balanced') or 'balanced',
            'min_refresh_interval_days': getattr(s, 'min_refresh_interval_days', 30) or 30,
            'author_bio': getattr(s, 'author_bio', '') or '',
            'author_credentials': getattr(s, 'author_credentials', '') or '',
            'business_model': getattr(s, 'business_model', '') or '',
        })


class V1SiteUpdateView(BaseV1View):
    """PATCH /api/v1/sites/<id>/ - update editable site fields.

    Whitelisted fields only: name, description, knowledge_base, competitors,
    default_language, author_bio, author_credentials, public_blog_domain.
    """
    EDITABLE = {
        'name', 'description', 'knowledge_base', 'competitors',
        'default_language', 'author_bio', 'author_credentials',
        'public_blog_domain', 'business_model',
        'primary_cta_text', 'primary_cta_url',
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
        if post.status == 'published':
            from .index_now import submit_one_safe, hosted_public_url
            submit_one_safe(site, hosted_public_url(site, post.slug))  # auto-ping IndexNow
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


# --------------------------------------------------------------------------
# Topic Cluster Planner (2026-06-08)
# --------------------------------------------------------------------------

def _normalize_intent_kw(keyword: str) -> str:
    """Lowercase, strip accents, and flatten apostrophes to spaces so the
    lexical intent patterns (written in plain ASCII) match FR/EN/ES keywords
    regardless of accents or curly/straight apostrophes.

    "logiciel qui gère mon SEO au Québec" -> "logiciel qui gere mon seo au quebec"
    "qu'est-ce que le SEO"                 -> "qu est-ce que le seo"
    """
    k = (keyword or '').strip().lower()
    if not k:
        return ''
    k = ''.join(
        c for c in unicodedata.normalize('NFKD', k)
        if not unicodedata.combining(c)
    )
    # curly/straight apostrophes and backticks -> space (so "s'abonner"
    # normalizes to "s abonner", matching the phrase patterns below)
    k = re.sub(r"[‘’ʼ'`]", ' ', k)
    # collapse repeated whitespace
    k = re.sub(r'\s+', ' ', k).strip()
    return k


# navigational: brand / account / login destinations (FR + EN + ES)
_NAV_PATTERN = re.compile(
    r'\b(login|log in|sign in|signin|log on|logon|connexion|se connecter|'
    r'mon compte|mon espace|espace client|espace membre|dashboard|'
    r'tableau de bord|page d accueil|iniciar sesion|mi cuenta)\b',
    re.IGNORECASE,
)

# Intent classification regex (FR + EN + ES). Matched against the *normalized*
# keyword. First match wins, in precedence order:
#   transactional -> navigational -> commercial -> informational -> local.
# Informational also acts as the 0.5 fallback when nothing matches.
# These are simple lexical signals; LLM is used as backup in propose_strategy.
_INTENT_PATTERNS = [
    # transactional: imminent purchase / quote / hire / subscribe / download
    ('transactional', re.compile(
        r'\b(achat|acheter|prix|tarif|tarifs|cout|couts|coute|combien coute|'
        r'devis|commande|commander|reserver|reservation|service|services|'
        r'agence|agency|cabinet|consultant|consultation|engager|embaucher|'
        r'hire|buy|purchase|order|book|pricing|quote|'
        r's abonner|abonnement|souscrire|souscription|inscription|s inscrire|'
        r'inscrire|essai|essai gratuit|demo|telecharger|download|descargar|'
        r'creer un compte|comprar|precio|tarifa|reservar|suscribir|'
        r'suscribirse)\b',
        re.IGNORECASE,
    )),
    # navigational: someone looking for a specific login / account / brand page
    ('navigational', _NAV_PATTERN),
    # commercial: comparing / evaluating tools & software before buying
    ('commercial', re.compile(
        r'\b(logiciel|logiciels|outil|outils|application|applications|appli|'
        r'plateforme|plateformes|solution|solutions|saas|software|tool|tools|'
        r'platform|meilleur|meilleure|meilleurs|meilleures|best|top|'
        r'comparatif|comparatifs|comparaison|comparaisons|comparison|vs|'
        r'versus|alternative|alternatives|avis|review|reviews|test|note|'
        r'notation|classement|opinion|opiniones|mejor|mejores)\b'
        r'|quel(?:le|les|s)?\b.*\bchoisir\b',
        re.IGNORECASE,
    )),
    # informational: how / what / why / guide / definition
    ('informational', re.compile(
        r'\b(comment|pourquoi|quoi|quelle|quel|qu est-ce que|c est quoi|'
        r'guide|tutoriel|tutorial|exemple|exemples|liste de|conseils|astuces|'
        r'how|what|why|when|where|definition|signification|explained|que es|'
        r'como|por que)\b',
        re.IGNORECASE,
    )),
    # local: geo signal
    ('local', re.compile(
        r'\b(pres de moi|near me|cerca de mi|montreal|quebec|paris|lyon|'
        r'toronto|vancouver|local|locale|locaux)\b',
        re.IGNORECASE,
    )),
]


def _classify_intent_regex(keyword: str) -> tuple[str, float]:
    """Return (intent, confidence) from lexical regex match.

    Confidence is 0.85 for a strong regex match, 0.5 if nothing matches
    (default to 'informational'). Precedence: transactional > navigational >
    commercial > informational > local.
    """
    k = _normalize_intent_kw(keyword)
    if not k:
        return ('informational', 0.0)
    for intent, pattern in _INTENT_PATTERNS:
        if pattern.search(k):
            return (intent, 0.85)
    return ('informational', 0.5)


def _is_navigational(keyword: str, site_name: str | None = None) -> bool:
    """Crude brand/destination detection: True if the keyword matches a known
    brand (the user's own site name, a login/account destination, or a single
    brand-shaped token)."""
    k = (keyword or '').strip().lower()
    if not k:
        return False
    if site_name and site_name.lower() in k:
        return True
    # Explicit login / account / dashboard destinations
    if _NAV_PATTERN.search(_normalize_intent_kw(keyword)):
        return True
    # Single CamelCase / lowercase token = likely a brand name
    if ' ' not in k and len(k) <= 20 and not any(c.isdigit() for c in k):
        return True
    return False


class V1ClassifyIntentView(BaseV1View):
    """POST /api/v1/classify-intent/ {keyword, site_id?}

    Returns: {keyword, intent, confidence, navigational_match}

    Used standalone OR as the first step of /keyword-strategy/.
    """

    def post(self, request):
        keyword = (request.data.get('keyword') or '').strip()
        if not keyword:
            return Response({'error': 'keyword is required.'},
                            status=status.HTTP_400_BAD_REQUEST)
        site_id = request.data.get('site_id')
        site_name = None
        if site_id:
            try:
                site = self.get_user_site(request, site_id)
                site_name = site.name
            except Exception:
                site_name = None

        intent, confidence = _classify_intent_regex(keyword)
        nav = _is_navigational(keyword, site_name)
        # Navigational overrides everything else when the keyword IS the brand.
        if nav and site_name and site_name.lower() in keyword.lower():
            intent = 'navigational'
            confidence = 0.95

        return Response({
            'keyword': keyword,
            'intent': intent,
            'confidence': confidence,
            'navigational_match': nav,
        })


def _propose_structure_for_intent(intent: str, keyword: str) -> str:
    """Map (intent, keyword shape) to a proposed_structure enum."""
    k = _normalize_intent_kw(keyword)
    if intent == 'transactional':
        # imminent purchase -> service/product landing
        return 'single_landing'
    if intent == 'commercial':
        # comparing/evaluating tools -> a comparison/positioning LANDING,
        # never a blog article. "X vs Y" and "best X software" both map to a
        # landing page (page_subtype 'comparison'), not a pillar_cluster.
        return 'comparison_table'
    if intent == 'local':
        return 'local_landing'
    if intent == 'navigational':
        return 'single_landing'
    # informational default
    return 'pillar_cluster'


def _propose_pages(structure: str, keyword: str, language: str = 'fr') -> list:
    """Generate a default proposed_pages list given the structure + keyword."""
    from django.utils.text import slugify
    base_slug = slugify(keyword)[:80] or 'page'

    if structure == 'single_landing':
        return [{
            'type': 'landing',
            'title': keyword.title(),
            'slug': base_slug,
            'keyword': keyword,
            'role': 'pillar',
            'page_subtype': 'service',
        }]

    if structure == 'comparison_table':
        return [{
            'type': 'landing',
            'title': keyword.title(),
            'slug': base_slug,
            'keyword': keyword,
            'role': 'pillar',
            'page_subtype': 'comparison',
        }]

    if structure == 'local_landing':
        return [{
            'type': 'landing',
            'title': keyword.title(),
            'slug': base_slug,
            'keyword': keyword,
            'role': 'pillar',
            'page_subtype': 'local',
        }]

    if structure == 'pillar_cluster':
        # 1 pillar + 4 cluster articles
        return [
            {
                'type': 'landing',
                'title': f'{keyword.title()} - Guide complet',
                'slug': base_slug,
                'keyword': keyword,
                'role': 'pillar',
                'page_subtype': 'pillar',
            },
            {
                'type': 'article',
                'title': f'Comment choisir {keyword}',
                'slug': f'comment-choisir-{base_slug}'[:200],
                'keyword': f'comment choisir {keyword}',
                'role': 'cluster',
            },
            {
                'type': 'article',
                'title': f'{keyword.title()} - Erreurs frequentes',
                'slug': f'erreurs-{base_slug}'[:200],
                'keyword': f'erreurs {keyword}',
                'role': 'cluster',
            },
            {
                'type': 'article',
                'title': f'{keyword.title()} - Prix et tarifs',
                'slug': f'prix-{base_slug}'[:200],
                'keyword': f'prix {keyword}',
                'role': 'cluster',
            },
            {
                'type': 'article',
                'title': f'{keyword.title()} - Cas pratiques',
                'slug': f'cas-pratiques-{base_slug}'[:200],
                'keyword': f'cas pratiques {keyword}',
                'role': 'cluster',
            },
        ]

    return [{
        'type': 'article',
        'title': keyword.title(),
        'slug': base_slug,
        'keyword': keyword,
        'role': 'standalone',
    }]


def _call_claude_for_strategy(keyword: str, intent: str, site, serp_summary: str = '') -> dict:
    """Use Claude to enrich the proposed strategy with rationale + tuned
    proposed_pages. Falls back to defaults if Claude unavailable.
    """
    try:
        bm = site.business_model or 'agency'
        prompt = f"""Tu es expert SEO topic cluster.

KEYWORD: "{keyword}"
INTENT DETECTE: {intent}
BUSINESS MODEL DU SITE: {bm}
SITE: {site.name}
{serp_summary}

Propose une structure de pages optimale et explique ton choix en 1 phrase.
Reponds en JSON strict (pas de markdown):
{{
  "rationale": "<1 phrase qui explique le choix de structure>",
  "structure": "<single_landing|pillar_cluster|comparison_table|local_landing|blog_post>",
  "pages": [
    {{"type":"landing"|"article", "title":str, "slug":str, "keyword":str,
      "role":"pillar"|"cluster"|"alternative", "page_subtype":str}},
    ...
  ]
}}
Pour un intent transactional, propose UNE landing.
Pour informational, propose 1 pillar landing + 3-5 articles cluster.
Pour commercial avec "vs", propose une comparison_table.
"""
        from .llm import call_llm
        text = call_llm(prompt, max_tokens=1500, timeout=60)  # Anthropic -> DeepSeek
        if not text:
            return {}
        import re as _re
        match = _re.search(r'\{[\s\S]*\}', text)
        if not match:
            return {}
        import json as _json
        return _json.loads(match.group())
    except Exception as exc:
        logger.warning('Strategy LLM enrichment failed: %s', exc)
        return {}


def _fetch_serp_summary(keyword: str, language: str = 'fr') -> str:
    """Optional helper: fetch a brief SERP snapshot via Serper for the prompt.

    Returns a plain-text summary or '' if the API key is missing / call fails.
    """
    api_key = os.environ.get('SERPER_API_KEY')
    if not api_key:
        return ''
    try:
        resp = requests.post(
            'https://google.serper.dev/search',
            headers={'X-API-KEY': api_key, 'Content-Type': 'application/json'},
            json={'q': keyword, 'gl': 'ca', 'hl': language, 'num': 5},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        organic = data.get('organic', [])[:5]
        lines = ['SERP top 5:']
        for i, item in enumerate(organic, 1):
            lines.append(f"{i}. {item.get('title','')} - {item.get('link','')}")
        return '\n'.join(lines)
    except Exception:
        return ''


class V1ProposeKeywordStrategyView(BaseV1View):
    """POST /api/v1/sites/<id>/keyword-strategy/ {keyword, language?}

    Classifies intent, analyzes SERP, proposes structure + pages.
    Idempotent on (site, keyword): re-running returns the existing draft.
    """

    def post(self, request, site_id):
        site = self.get_user_site(request, site_id)
        keyword = (request.data.get('keyword') or '').strip()
        if not keyword:
            return Response({'error': 'keyword is required.'},
                            status=status.HTTP_400_BAD_REQUEST)
        language = (request.data.get('language') or site.default_language or 'fr')[:2]

        # Classify intent (regex + brand check)
        intent, confidence = _classify_intent_regex(keyword)
        if _is_navigational(keyword, site.name) and site.name.lower() in keyword.lower():
            intent = 'navigational'
            confidence = 0.95

        # SERP summary (best-effort)
        serp_summary = _fetch_serp_summary(keyword, language)

        # Claude enrichment (best-effort)
        llm_data = _call_claude_for_strategy(keyword, intent, site, serp_summary)

        if llm_data and llm_data.get('structure'):
            structure = llm_data['structure']
            pages = llm_data.get('pages') or _propose_pages(structure, keyword, language)
            rationale = llm_data.get('rationale') or ''
        else:
            structure = _propose_structure_for_intent(intent, keyword)
            pages = _propose_pages(structure, keyword, language)
            rationale = (
                f"Intent '{intent}' detecte (confiance {confidence:.0%}). "
                f"Structure proposee: {structure}."
            )

        # Preserve status if the strategy already exists and was approved /
        # done - only re-running on a draft should overwrite content blocks.
        existing = KeywordStrategy.objects.filter(site=site, keyword=keyword).first()
        preserved_status = 'draft'
        if existing and existing.status in ('approved', 'generating', 'done'):
            preserved_status = existing.status

        strategy, created = KeywordStrategy.objects.update_or_create(
            site=site, keyword=keyword,
            defaults={
                'language': language,
                'intent': intent,
                'intent_confidence': confidence,
                'business_model_detected': site.business_model or '',
                'serp_analysis': {'summary': serp_summary} if serp_summary else {},
                'proposed_structure': structure,
                'proposed_pages': pages,
                'rationale': rationale,
                'status': preserved_status,
            },
        )

        return Response({
            'id': strategy.id,
            'site_id': site.id,
            'keyword': strategy.keyword,
            'intent': strategy.intent,
            'intent_confidence': strategy.intent_confidence,
            'proposed_structure': strategy.proposed_structure,
            'proposed_pages': strategy.proposed_pages,
            'rationale': strategy.rationale,
            'status': strategy.status,
            'created': created,
        }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class V1ApproveStrategyView(BaseV1View):
    """POST /api/v1/sites/<id>/keyword-strategy/<strategy_id>/approve/

    Body: {customizations?: {pages: [...]}}

    Marks the strategy approved and generates each proposed_page using
    LandingGenerator (for type='landing') or queues an article generation
    (for type='article'). For articles we currently just register the
    intent - the user runs gridar_generate_article on each title manually
    to keep quota usage explicit.
    """

    def post(self, request, site_id, strategy_id):
        site = self.get_user_site(request, site_id)
        from .delivery import block_reason
        _blk = block_reason(site)
        if _blk:
            return Response({'error': _blk, 'code': 'delivery_blocked'},
                            status=status.HTTP_409_CONFLICT)
        try:
            strategy = KeywordStrategy.objects.get(site=site, id=int(strategy_id))
        except (KeywordStrategy.DoesNotExist, ValueError, TypeError):
            return Response({'error': 'Strategy introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)

        if strategy.status not in ('draft', 'approved'):
            return Response(
                {'error': f"Strategy deja en etat '{strategy.status}'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Optional customizations override the proposed_pages list
        customizations = request.data.get('customizations') or {}
        if isinstance(customizations.get('pages'), list):
            pages = customizations['pages']
            strategy.proposed_pages = pages
        else:
            pages = list(strategy.proposed_pages or [])

        strategy.status = 'generating'
        strategy.approved_at = timezone.now()
        strategy.approved_by = request.user
        strategy.save(update_fields=[
            'proposed_pages', 'status', 'approved_at', 'approved_by', 'updated_at',
        ])

        generated_landings = []
        generated_articles = []
        errors = []

        from .landing_generator import LandingGenerator, LandingGeneratorError

        gen = LandingGenerator(site=site, language=strategy.language)

        for page in pages:
            try:
                if page.get('type') == 'landing':
                    payload = gen.generate(
                        keyword=page.get('keyword') or strategy.keyword,
                        page_subtype=page.get('page_subtype') or 'service',
                    )
                    # Override the slug if proposed_pages had a custom one
                    if page.get('slug'):
                        payload['slug'] = page['slug'][:200]
                    # Dedup slug
                    base_slug = payload['slug']
                    n = 1
                    while HostedLanding.objects.filter(
                        site=site, slug=payload['slug']
                    ).exists():
                        n += 1
                        payload['slug'] = f'{base_slug}-{n}'[:200]
                    landing = HostedLanding.objects.create(site=site, **payload)
                    generated_landings.append(landing.id)
                else:
                    # type='article' - we just register the intent in
                    # generated_pages_fks so the UI can show it as "to do".
                    # Actual article generation is left to gridar_generate_article
                    # so quota usage stays explicit.
                    generated_articles.append({
                        'planned': True,
                        'title': page.get('title'),
                        'keyword': page.get('keyword'),
                        'slug': page.get('slug'),
                    })
            except LandingGeneratorError as e:
                errors.append({'page': page, 'error': str(e)})
            except Exception as e:  # noqa: BLE001
                logger.exception('Strategy approve - page failed')
                errors.append({'page': page, 'error': str(e)[:120]})

        strategy.generated_pages_fks = {
            'landings': generated_landings,
            'articles': generated_articles,
        }
        strategy.status = 'done' if not errors else 'approved'
        strategy.save(update_fields=[
            'generated_pages_fks', 'status', 'updated_at',
        ])

        return Response({
            'id': strategy.id,
            'status': strategy.status,
            'generated_landings': generated_landings,
            'planned_articles': generated_articles,
            'errors': errors,
        })


class V1CreateLandingView(BaseV1View):
    """POST /api/v1/sites/<id>/landings/manual/

    Body: {title, h1, slug?, hero_subtitle?, value_props?, faq?, ...}

    Manual (non-AI) landing creation. Mirrors V1ArticleCreateView for landings.
    """

    def post(self, request, site_id):
        site = self.get_user_site(request, site_id)
        if not site.is_hosted:
            return Response(
                {'error': 'Landings are only available on hosted sites.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        data = request.data or {}
        title = (data.get('title') or '').strip()
        h1 = (data.get('h1') or title).strip()
        if not title:
            return Response({'error': 'title is required.'},
                            status=status.HTTP_400_BAD_REQUEST)
        from django.utils.text import slugify
        slug = (data.get('slug') or slugify(title))[:200]
        if HostedLanding.objects.filter(site=site, slug=slug).exists():
            return Response(
                {'error': f'Slug "{slug}" already exists on this site.'},
                status=status.HTTP_409_CONFLICT,
            )
        language = (data.get('language') or site.default_language or 'fr')[:2]
        status_val = (data.get('status') or 'draft').lower()
        if status_val not in ('draft', 'published'):
            status_val = 'draft'

        from datetime import date as _date
        landing = HostedLanding.objects.create(
            site=site,
            title=title[:200],
            slug=slug,
            h1=h1[:200],
            hero_subtitle=(data.get('hero_subtitle') or '')[:500],
            hero_cta_text=(data.get('hero_cta_text') or '')[:80],
            hero_cta_url=(data.get('hero_cta_url') or '')[:500],
            value_props=data.get('value_props') or [],
            social_proof=data.get('social_proof') or [],
            faq=data.get('faq') or [],
            cta_bottom_text=(data.get('cta_bottom_text') or '')[:80],
            cta_bottom_url=(data.get('cta_bottom_url') or '')[:500],
            body_markdown=data.get('body_markdown') or '',
            target_keyword=(data.get('target_keyword') or '')[:200],
            schema_type=(data.get('schema_type') or 'WebPage')[:20],
            page_subtype=(data.get('page_subtype') or 'generic')[:20],
            language=language,
            status=status_val,
            cover_image=(data.get('cover_image') or '')[:500],
            meta_description=(data.get('meta_description') or '')[:300],
            published_at=_date.today() if status_val == 'published' else None,
        )
        return Response({
            'id': landing.id,
            'slug': landing.slug,
            'status': landing.status,
        }, status=status.HTTP_201_CREATED)


class V1GenerateLandingView(BaseV1View):
    """POST /api/v1/sites/<id>/landings/generate/

    Body: {keyword, primary_cta_text?, primary_cta_url?, value_props?, page_subtype?}

    AI-generates a landing payload via LandingGenerator and saves it as a draft.
    Consumes one article from the user's monthly quota (landing == article unit).
    """

    def post(self, request, site_id):
        site = self.get_user_site(request, site_id)
        from .delivery import block_reason
        _blk = block_reason(site)
        if _blk:
            return Response({'error': _blk, 'code': 'delivery_blocked'},
                            status=status.HTTP_409_CONFLICT)
        if not site.is_hosted:
            return Response(
                {'error': 'AI landing generation is only available on hosted sites.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        data = request.data or {}
        keyword = (data.get('keyword') or '').strip()
        if not keyword:
            return Response({'error': 'keyword is required.'},
                            status=status.HTTP_400_BAD_REQUEST)

        # Onboarding gate (same as V1GenerateView)
        missing = []
        if not (site.business_model or '').strip():
            missing.append('business_model')
        if missing:
            return Response(
                {'error': "Renseigne d'abord business_model dans les params du site.",
                 'missing_fields': missing},
                status=422,
            )

        # Quota
        from .quota import check_article_quota, consume_article
        try:
            check_article_quota(request.user)
        except exceptions.PermissionDenied as e:
            return Response({'error': str(e), 'quota_exceeded': True},
                            status=status.HTTP_402_PAYMENT_REQUIRED)

        from .landing_generator import LandingGenerator, LandingGeneratorError
        try:
            gen = LandingGenerator(site=site, language=data.get('language'))
            payload = gen.generate(
                keyword=keyword,
                primary_cta_text=data.get('primary_cta_text'),
                primary_cta_url=data.get('primary_cta_url'),
                value_props_seed=data.get('value_props'),
                page_subtype=(data.get('page_subtype') or 'service'),
            )
        except LandingGeneratorError as e:
            return Response({'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:  # noqa: BLE001
            logger.exception('V1GenerateLanding failed')
            return Response({'error': f'Generation error: {str(e)[:120]}'},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Dedup slug
        base = payload['slug']
        n = 1
        while HostedLanding.objects.filter(site=site, slug=payload['slug']).exists():
            n += 1
            payload['slug'] = f'{base}-{n}'[:200]

        landing = HostedLanding.objects.create(site=site, **payload)
        consume_article(request.user)
        return Response({
            'id': landing.id,
            'slug': landing.slug,
            'title': landing.title,
            'h1': landing.h1,
            'status': landing.status,
            'page_subtype': landing.page_subtype,
        }, status=status.HTTP_201_CREATED)


class V1LinkPagesView(BaseV1View):
    """POST /api/v1/sites/<id>/link-pages/

    Body: {source_slug, target_slug, anchor_text, source_type?, target_type?}

    Inserts an inline markdown link from source page to target page. Both
    pages can be landings OR articles. The source's body is patched in-place;
    if the anchor is already present we no-op.

    source_type / target_type default to 'auto' which checks landing first then article.
    """

    def post(self, request, site_id):
        site = self.get_user_site(request, site_id)
        if not site.is_hosted:
            return Response(
                {'error': 'link-pages is only available on hosted sites.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        data = request.data or {}
        src = (data.get('source_slug') or '').strip()
        tgt = (data.get('target_slug') or '').strip()
        anchor = (data.get('anchor_text') or '').strip()
        if not src or not tgt or not anchor:
            return Response(
                {'error': 'source_slug, target_slug, anchor_text required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if src == tgt:
            return Response({'error': 'source and target must differ.'},
                            status=status.HTTP_400_BAD_REQUEST)

        def _find_page(slug):
            landing = HostedLanding.objects.filter(site=site, slug=slug).first()
            if landing:
                return ('landing', landing)
            post = HostedPost.objects.filter(site=site, slug=slug).first()
            if post:
                return ('article', post)
            return (None, None)

        src_kind, src_obj = _find_page(src)
        tgt_kind, tgt_obj = _find_page(tgt)
        if not src_obj:
            return Response({'error': f'Source slug "{src}" not found.'},
                            status=status.HTTP_404_NOT_FOUND)
        if not tgt_obj:
            return Response({'error': f'Target slug "{tgt}" not found.'},
                            status=status.HTTP_404_NOT_FOUND)

        # Build the link
        if tgt_kind == 'landing':
            target_url = f'/landings/{tgt_obj.slug}'
        else:
            target_url = f'/blog/{tgt_obj.slug}'
        md_link = f'[{anchor}]({target_url})'

        # Get source body field
        if src_kind == 'landing':
            body_field = 'body_markdown'
        else:
            body_field = 'content'
        body = getattr(src_obj, body_field) or ''

        if md_link in body or target_url in body:
            return Response({
                'status': 'already_linked',
                'source_slug': src,
                'target_slug': tgt,
            })

        # Replace first occurrence of `anchor` (case-insensitive, word-bounded)
        pattern = re.compile(rf'\b({re.escape(anchor)})\b', re.IGNORECASE)
        new_body, count = pattern.subn(md_link, body, count=1)
        if count == 0:
            # Anchor text not in body - append a "Voir aussi" line at the end
            sep = '\n\n' if body else ''
            new_body = body + f'{sep}Voir aussi: {md_link}'

        setattr(src_obj, body_field, new_body)
        src_obj.save(update_fields=[body_field, 'updated_at'])

        return Response({
            'status': 'linked',
            'source_slug': src,
            'source_type': src_kind,
            'target_slug': tgt,
            'target_type': tgt_kind,
            'anchor_text': anchor,
            'inserted_inline': count > 0,
        })


# --------------------------------------------------------------------------
# Site SEO Score (composite) - P1 #7 (2026-06-08)
# --------------------------------------------------------------------------

# Weighted checks for the composite score. Weights sum to 100 so the score is
# already in [0, 100] without extra normalization.
_SEO_SCORE_WEIGHTS = {
    'indexability':              15,
    'author_bio_filled':         10,
    'business_model_declared':   10,
    'gsc_connected':             15,
    'has_cluster':               10,
    'hreflang_valid':            10,
    'cwv_ok':                    10,
    'faq_coverage':              10,
    'no_transactional_blog':     10,
}

# What each check actually reads. 'config' checks read Gridar's own database
# (is the field filled, is GSC linked); 'measured' checks look at the site
# itself. The split matters because a site can be perfectly configured here
# and never have been crawled, and the two must not be reported as one number.
_SEO_SCORE_KIND = {
    'indexability':              'measured',
    'author_bio_filled':         'config',
    'business_model_declared':   'config',
    'gsc_connected':             'config',
    'has_cluster':               'config',
    'hreflang_valid':            'measured',
    'cwv_ok':                    'measured',
    'faq_coverage':              'measured',
    'no_transactional_blog':     'config',
}

# Data sufficiency gate, ported from claude-seo v2.2.4 skills/seo-backlinks
# (MIT, Daniel Agrici). Its rule: below a floor of factors carrying real data,
# emit no number at all, because a low score computed on absent data reads as
# "your SEO is bad" when the truth is "we did not measure it". Here the floor
# applies to the measured subset: with fewer than 2 of the 4 measured checks
# carrying data, `seo_score` comes back None instead of a misleading integer.
_MEASURED_FLOOR = 2


def _compute_site_seo_score(site) -> dict:
    """Return {score, breakdown, action_items} for the given site.

    Each check returns True/False (or a float in [0,1] for partial credit).
    Weighted by `_SEO_SCORE_WEIGHTS`; final score in [0, 100].
    """
    from django.db.models import Count

    breakdown: dict[str, float] = {}
    action_items: list[dict] = []

    # 1) Indexability: a site is "indexable" if it has at least one published
    # post (else Google has nothing to crawl). We don't fetch robots.txt here -
    # that's the job of the bulk audit. This is a content-presence proxy.
    if site.is_hosted:
        published_count = HostedPost.objects.filter(site=site, status='published').count()
        total_count = HostedPost.objects.filter(site=site).count()
    else:
        # External site: we cannot count its published pages from here without
        # setting up its DB connection. Report no data rather than inferring
        # indexability from "a domain is filled in", which measured Gridar's
        # own config and passed for a crawl result.
        published_count = None
        total_count = 0

    indexable = None if published_count is None else published_count > 0
    breakdown['indexability'] = None if indexable is None else bool(indexable)
    if indexable is False:
        action_items.append({
            'issue': 'Aucun article publie - Google n a rien a indexer.',
            'fix_url': f'/sites/{site.id}/posts/new/',
        })

    # 2) Author bio filled (E-E-A-T signal)
    author_ok = bool((site.author_bio or '').strip())
    breakdown['author_bio_filled'] = author_ok
    if not author_ok:
        action_items.append({
            'issue': 'Bio de l auteur vide - signal E-E-A-T manquant.',
            'fix_url': f'/sites/{site.id}/settings/',
        })

    # 3) Business model declared (drives prompts). 'personal_blog' is the DB
    # default but the other business_model gates in this API accept it as a
    # declared value; this check must agree with them.
    bm = (site.business_model or '').strip()
    bm_ok = bool(bm)
    breakdown['business_model_declared'] = bm_ok
    if not bm_ok:
        action_items.append({
            'issue': 'Modele d affaires non declare - generations IA seront generiques.',
            'fix_url': f'/sites/{site.id}/settings/',
        })

    # 4) GSC connected
    gsc_ok = bool(site.gsc_property_url and site.gsc_refresh_token)
    breakdown['gsc_connected'] = gsc_ok
    if not gsc_ok:
        action_items.append({
            'issue': 'Google Search Console non connecte - pas de mesure d impressions / clics.',
            'fix_url': f'/sites/{site.id}/integrations/',
        })

    # 5) Has at least one approved/generated pillar+spokes cluster strategy.
    has_cluster = KeywordStrategy.objects.filter(
        site=site,
        status__in=['approved', 'generating', 'done'],
        proposed_structure__in=['pillar_cluster', 'pillar_spokes'],
    ).exists()
    breakdown['has_cluster'] = has_cluster
    if not has_cluster:
        action_items.append({
            'issue': 'Aucun cluster pillar + spokes approuve - autorite topique faible.',
            'fix_url': f'/sites/{site.id}/keyword-strategy/',
        })

    # 6) Hreflang valid if multilingual. Pass if site is monolingual (nothing
    # to wire) OR if at least one translation_group has posts in >=2 languages.
    languages = site.effective_languages or [site.default_language or 'fr']
    is_multilingual = len(set(languages)) > 1
    if not is_multilingual:
        hreflang_ok = True
    elif site.is_hosted:
        groups = (
            HostedPost.objects.filter(site=site, status='published')
            .values('translation_group')
            .annotate(lang_count=Count('language', distinct=True))
            .filter(lang_count__gte=2)
        )
        hreflang_ok = groups.exists()
    else:
        # Multilingual external site: no data from here. V1HreflangCheckView
        # can answer it properly; defaulting to True credited sites that had
        # never been checked.
        hreflang_ok = None
    breakdown['hreflang_valid'] = hreflang_ok
    if hreflang_ok is False:
        action_items.append({
            'issue': 'Site multilingue sans hreflang - cannibalisation cross-langue probable.',
            'fix_url': f'/sites/{site.id}/site-audit/',
        })

    # 7) Core Web Vitals OK. We don't run PageSpeed here (too slow / quota);
    # instead we check whether the latest cached bulk audit recorded a CWV
    # pass. Best-effort: if no audit data exists yet, mark as 'unknown' and
    # neither pass nor fail (0.5 partial credit).
    from django.core.cache import cache as _cache
    audit_cached = _cache.get(f'site-audit:{site.id}')
    if audit_cached and isinstance(audit_cached, dict):
        ps = audit_cached.get('pagespeed') or {}
        perf = ps.get('performance')
        if perf is None:
            cwv_value = None
        else:
            cwv_value = 1.0 if perf >= 70 else 0.0
    else:
        # No audit run yet. None, not 0.5: half credit was a guess dressed up
        # as a measurement, and it moved the score either way for no reason.
        cwv_value = None
    breakdown['cwv_ok'] = cwv_value
    if cwv_value is not None and cwv_value < 1.0:
        action_items.append({
            'issue': 'Core Web Vitals non valides ou non mesures - lancer un audit PageSpeed.',
            'fix_url': f'/sites/{site.id}/site-audit/',
        })

    # 8) FAQ coverage: share of published posts carrying FAQPage JSON-LD.
    if site.is_hosted and total_count > 0:
        # Counted in Python on purpose: `@type` is sometimes a list
        # (['BlogPosting', 'FAQPage']) and sometimes a string, and the
        # JSONField `contains` lookup matches neither shape reliably across
        # Postgres and SQLite. The previous query asked only "has an @type
        # key", so every article with any schema at all counted as an FAQ.
        def _has_faq(blob) -> bool:
            if not isinstance(blob, dict):
                return False
            t = blob.get('@type')
            return t == 'FAQPage' or (isinstance(t, list) and 'FAQPage' in t)

        blobs = HostedPost.objects.filter(site=site).values_list(
            'schema_jsonld', flat=True,
        )
        with_faq = sum(1 for b in blobs if _has_faq(b))
        faq_ratio = with_faq / max(1, total_count)
    else:
        # Nothing to read: an external site's posts are not in this database.
        # Zero would have been reported as "no FAQ anywhere", which is a claim
        # about the site we never checked.
        faq_ratio = None
    breakdown['faq_coverage'] = None if faq_ratio is None else round(faq_ratio, 3)
    if faq_ratio is not None and faq_ratio < 0.5:
        action_items.append({
            'issue': (
                f'Couverture FAQ schema faible ({int(faq_ratio * 100)}%). '
                'Une section FAQ rend les reponses extractibles par les moteurs '
                'IA (Google a retire les rich results FAQ en mai 2026).'
            ),
            'fix_url': f'/sites/{site.id}/posts/',
        })

    # 9) No transactional intent on blog posts. If the user tracks keywords
    # whose intent is "transactional" but no landing exists (only blog posts),
    # they're competing with their own commercial pages.
    transactional_strategies = KeywordStrategy.objects.filter(
        site=site, intent='transactional', status__in=['draft', 'approved', 'generating', 'done'],
    )
    bad_transactional = transactional_strategies.filter(
        proposed_structure='blog_post',
    ).count()
    no_trans_blog_ok = bad_transactional == 0
    breakdown['no_transactional_blog'] = no_trans_blog_ok
    if not no_trans_blog_ok:
        action_items.append({
            'issue': (
                f'{bad_transactional} mot-cle(s) transactionnel(s) classe(s) comme '
                'blog post - devraient etre des landings.'
            ),
            'fix_url': f'/sites/{site.id}/keyword-strategy/',
        })

    # Weighted score. A check that came back None carries no data: its weight
    # is redistributed over the checks that do, rather than counting as a zero
    # and inventing a failure the site never had.
    def _weighted(names):
        acc = 0.0
        total = 0
        for check in names:
            val = breakdown.get(check)
            if val is None:
                continue
            if isinstance(val, bool):
                val = 1.0 if val else 0.0
            else:
                try:
                    val = max(0.0, min(1.0, float(val)))
                except (TypeError, ValueError):
                    continue
            acc += val * _SEO_SCORE_WEIGHTS[check]
            total += _SEO_SCORE_WEIGHTS[check]
        return (acc / total * 100) if total else None

    measured = [k for k, kind in _SEO_SCORE_KIND.items() if kind == 'measured']
    config = [k for k, kind in _SEO_SCORE_KIND.items() if kind == 'config']
    with_data = [k for k in measured if breakdown.get(k) is not None]
    unknown = [k for k in _SEO_SCORE_WEIGHTS if breakdown.get(k) is None]

    overall = _weighted(list(_SEO_SCORE_WEIGHTS.keys()))
    seo_only = _weighted(measured)
    onboarding = _weighted(config)
    sufficient = len(with_data) >= _MEASURED_FLOOR

    if not sufficient:
        action_items.insert(0, {
            'issue': (
                f'Score SEO indisponible : seulement {len(with_data)} des '
                f'{len(measured)} verifications portant sur le site ont des '
                'donnees. Lance un audit du site pour en obtenir un.'
            ),
            'fix_url': f'/sites/{site.id}/site-audit/',
        })

    return {
        # Kept for existing callers: all nine checks, weights redistributed.
        'score': None if overall is None else int(round(overall)),
        # The site itself, config checks excluded. None when the gate trips.
        'seo_score': int(round(seo_only)) if (sufficient and seo_only is not None) else None,
        # What Gridar knows about the site, which is a different question.
        'onboarding_completeness': None if onboarding is None else int(round(onboarding)),
        'data_sufficiency': {
            'measured_with_data': len(with_data),
            'measured_total': len(measured),
            'floor': _MEASURED_FLOOR,
            'sufficient': sufficient,
            'unknown_checks': unknown,
        },
        'breakdown': breakdown,
        'kinds': _SEO_SCORE_KIND,
        'action_items': action_items,
    }


class V1SiteSeoScoreView(BaseV1View):
    """GET /api/v1/sites/<id>/seo-score/

    Nine weighted checks: indexability, author bio, business model, GSC
    connection, pillar+spokes cluster, hreflang validity (if multilingual),
    Core Web Vitals, FAQ schema coverage, no transactional intent stuck on
    blog posts.

    Four of them measure the site, five read Gridar's own configuration, and
    `kinds` says which is which. A check with no data available returns null
    and its weight is redistributed rather than counted as a failure. Below
    the data sufficiency floor, `seo_score` is null on purpose: a number
    computed on absent data reads as bad SEO when nothing was measured.

    Response: {score, seo_score, onboarding_completeness, data_sufficiency,
    breakdown, kinds, action_items: [{issue, fix_url}]}
    """

    def get(self, request, site_id):
        site = self.get_user_site(request, site_id)
        return Response(_compute_site_seo_score(site))


# --------------------------------------------------------------------------
# AI Overview Readiness - P1 #6 (2026-06-08)
# --------------------------------------------------------------------------
#
# Scores how well-suited a single article is for being picked as the source
# block of Google's AI Overview (SGE), Bing Copilot answers, Perplexity
# citations and ChatGPT browse answers. The five sub-checks lean on
# established AI-Overview research signals:
#   - faq_density: explicit Q&A blocks (LLMs love direct questions)
#   - h2_h3_structure: extractible sectioning
#   - eeat_signals: author bio + sources/dates in the body
#   - concrete_data: numbers, dates, percentages, units
#   - extractible_quotes: short paragraphs right after a heading (snippet
#     candidates - the kind of block LLMs love to lift verbatim)

_AIO_QUESTION_RE = re.compile(r'[^.?!\n]*\?\s', re.UNICODE)
_AIO_H2_RE = re.compile(r'^##\s+\S', re.MULTILINE)
_AIO_H3_RE = re.compile(r'^###\s+\S', re.MULTILINE)
_AIO_NUMBER_RE = re.compile(
    r'\b\d{1,4}([.,]\d+)?\s*(%|\$|EUR|USD|CAD|kg|km|m|cm|mm|g|ml|l|'
    r'h|hr|min|sec|annee|annees|ans|jours|mois|semaines)?\b',
    re.IGNORECASE,
)
_AIO_DATE_RE = re.compile(
    r'\b(20\d{2}|19\d{2}|janvier|fevrier|mars|avril|mai|juin|juillet|'
    r'aout|septembre|octobre|novembre|decembre|january|february|march|'
    r'april|may|june|july|august|september|october|november|december|'
    r'\d{1,2}/\d{1,2}/\d{2,4})\b',
    re.IGNORECASE,
)
_AIO_SOURCE_RE = re.compile(
    r'\b(source|sources|reference|references|selon|according to|cite|'
    r'cited|etude|study|recherche|research|rapport|report|d apres|'
    r'd\'apres)\b',
    re.IGNORECASE,
)


def _compute_ai_overview_readiness(site, article: dict) -> dict:
    """Score how AI-Overview-ready an article is.

    Args:
        site: Site object (for E-E-A-T author_bio signal).
        article: dict with at least {title, content} keys. Optional: excerpt.

    Returns: {score: 0-100, breakdown: {...}, suggestions: [str, ...]}
    """
    title = (article.get('title') or '').strip()
    content = (article.get('content') or '').strip()
    words = re.findall(r"\b\w+\b", content)
    word_count = len(words)

    # --- 1) FAQ density ----------------------------------------------------
    # nb_questions / max(1, word_count // 200). >=1.0 = ~1 question per 200
    # words which is solid for FAQ-rich Q&A pages. Cap at 1.0 for scoring.
    questions = _AIO_QUESTION_RE.findall(content)
    nb_questions = len(questions)
    denom = max(1, word_count // 200)
    faq_density_raw = nb_questions / denom
    faq_density_score = min(1.0, faq_density_raw)

    # --- 2) H2/H3 structure -----------------------------------------------
    nb_h2 = len(_AIO_H2_RE.findall(content))
    nb_h3 = len(_AIO_H3_RE.findall(content))
    nb_headings = nb_h2 + nb_h3
    has_good_structure = nb_headings > 5
    # Partial credit: 0.5 for 3-5 headings, 1.0 for >5, 0.0 for <3
    if nb_headings > 5:
        structure_score = 1.0
    elif nb_headings >= 3:
        structure_score = 0.5
    else:
        structure_score = 0.0

    # --- 3) E-E-A-T signals -----------------------------------------------
    has_author_bio = bool((getattr(site, 'author_bio', '') or '').strip())
    has_sources_or_dates = bool(
        _AIO_SOURCE_RE.search(content) or _AIO_DATE_RE.search(content)
    )
    eeat_count = int(has_author_bio) + int(has_sources_or_dates)
    eeat_score = eeat_count / 2.0  # 0, 0.5 or 1.0

    # --- 4) Concrete data --------------------------------------------------
    # Density of numeric / date tokens. We expect at least 1 every 250 words
    # for a data-rich article. Cap at 1.0.
    numbers = _AIO_NUMBER_RE.findall(content)
    dates = _AIO_DATE_RE.findall(content)
    nb_data_tokens = len(numbers) + len(dates)
    data_denom = max(1, word_count // 250)
    data_density_raw = nb_data_tokens / data_denom
    data_score = min(1.0, data_density_raw)

    # --- 5) Extractible quotes ---------------------------------------------
    # Short paragraphs (< 250 chars) directly after a "## " heading - prime
    # snippet material for AI-Overview lifts.
    lines = content.split('\n')
    extractible_count = 0
    nb_h2_seen = 0
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith('## ') and not line.startswith('### '):
            nb_h2_seen += 1
            # Look at the next non-empty paragraph
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines):
                # Collect the next paragraph (until blank line)
                para_lines = []
                while j < len(lines) and lines[j].strip():
                    para_lines.append(lines[j])
                    j += 1
                para = ' '.join(para_lines).strip()
                # Skip headings as "paragraphs"
                if para and not para.startswith('#') and len(para) < 250:
                    extractible_count += 1
            i = j
        else:
            i += 1
    # Score: ratio of H2 sections that have an extractible lead paragraph.
    if nb_h2_seen > 0:
        quotes_score = min(1.0, extractible_count / nb_h2_seen)
    else:
        quotes_score = 0.0

    # --- Weighted score ---------------------------------------------------
    score_float = (
        faq_density_score * 0.25
        + structure_score * 0.20
        + eeat_score * 0.20
        + data_score * 0.20
        + quotes_score * 0.15
    ) * 100
    score = int(round(score_float))

    breakdown = {
        'faq_density': round(faq_density_score, 3),
        'h2_h3_structure': bool(has_good_structure),
        'eeat_signals': eeat_count,
        'concrete_data': round(data_score, 3),
        'extractible_quotes': extractible_count,
    }

    # --- Suggestions -------------------------------------------------------
    suggestions: list[str] = []
    if faq_density_score < 0.5:
        suggestions.append(
            f"Ajouter une section FAQ : actuellement {nb_questions} question(s) "
            f"pour {word_count} mots. Vise 1 question tous les 200 mots."
        )
    if not has_good_structure:
        suggestions.append(
            f"Renforcer la structure : seulement {nb_headings} en-tetes "
            "H2/H3 detectes. Cible >5 pour faciliter l extraction AI Overview."
        )
    if not has_author_bio:
        suggestions.append(
            "Remplir la bio de l auteur dans les parametres du site (signal "
            "E-E-A-T attendu par Google SGE)."
        )
    if not has_sources_or_dates:
        suggestions.append(
            "Ajouter des sources, dates ou references dans le contenu "
            "(mots-cles : 'selon', 'source', 'etude', annees 20xx)."
        )
    if data_score < 0.5:
        suggestions.append(
            f"Inclure plus de donnees chiffrees : seulement {nb_data_tokens} "
            "nombres/dates detectes. Les LLM citent les chiffres concrets."
        )
    if quotes_score < 0.5 and nb_h2_seen > 0:
        suggestions.append(
            f"Ajouter une phrase de resume (<250 chars) directement sous chaque "
            f"## : {extractible_count}/{nb_h2_seen} sections en ont une. "
            "C est le format prefere des AI Overviews."
        )
    if not suggestions:
        suggestions.append(
            "Tres bonne base AI Overview-ready. Continue a monitorer "
            "la qualite des sources et la fraicheur des donnees."
        )

    return {
        'score': score,
        'breakdown': breakdown,
        'suggestions': suggestions,
    }


def _fetch_article_for_readiness(site, slug: str) -> dict | None:
    """Look up an article in any storage mode (hosted, external, CMS) and
    return a {title, content, excerpt} dict, or None if not found.

    Mirrors the dispatch logic in V1ArticleDetailView - we keep it local
    so the JWT view can reuse it without going through the v1 endpoint.
    """
    if site.is_wordpress:
        from .wordpress_adapter import WordPressClient, WordPressError
        try:
            post = WordPressClient(site).get_post(slug)
        except WordPressError:
            return None
        if not post:
            return None
        return {
            'title': post.get('title', ''),
            'content': post.get('content', ''),
            'excerpt': post.get('excerpt', ''),
        }
    if site.is_shopify:
        from .shopify_adapter import ShopifyClient, ShopifyError
        try:
            post = ShopifyClient(site).get_post(slug)
        except ShopifyError:
            return None
        if not post:
            return None
        return {
            'title': post.get('title', ''),
            'content': post.get('content', ''),
            'excerpt': post.get('excerpt', ''),
        }
    if site.is_webflow:
        from .webflow_adapter import WebflowClient, WebflowError
        try:
            post = WebflowClient(site).get_post(slug)
        except WebflowError:
            return None
        if not post:
            return None
        return {
            'title': post.get('title', ''),
            'content': post.get('content', ''),
            'excerpt': post.get('excerpt', ''),
        }
    if site.is_hosted:
        try:
            p = HostedPost.objects.get(site=site, slug=slug)
        except HostedPost.DoesNotExist:
            return None
        return {'title': p.title, 'content': p.content, 'excerpt': p.excerpt}
    from .db_utils import ensure_site_connection
    alias = ensure_site_connection(site)
    try:
        p = BlogPost.objects.using(alias).get(slug=slug)
    except BlogPost.DoesNotExist:
        return None
    return {
        'title': p.title,
        'content': getattr(p, 'content', ''),
        'excerpt': getattr(p, 'excerpt', ''),
    }


class V1AIOverviewReadinessView(BaseV1View):
    """GET /api/v1/sites/<id>/articles/<slug>/ai-overview-readiness/

    Score how AI-Overview-ready an article is. 0-100 composite from 5
    weighted checks: FAQ density (25%), H2/H3 structure (20%), E-E-A-T
    signals (20%), concrete data (20%), extractible quotes (15%).

    Response: {score: int, breakdown: {...}, suggestions: [str]}
    """

    def get(self, request, site_id, slug):
        site = self.get_user_site(request, site_id)
        article = _fetch_article_for_readiness(site, slug)
        if not article:
            return Response({'error': 'Article introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)
        return Response(_compute_ai_overview_readiness(site, article))


# --------------------------------------------------------------------------
# Renderability check - P1 #9 (2026-06-08)
# --------------------------------------------------------------------------
#
# Quick "is this page server-rendered or client-rendered (SPA)?" probe.
# Googlebot can render JS but it's slow + flaky; SSR / prerender is still
# the gold standard for SEO. We fetch the raw HTML once and check whether
# the <body> contains a meaningful chunk of text (>100 words). If not,
# the page is most likely a JS-heavy SPA shell that needs prerendering
# (Next.js SSG/SSR, Nuxt, Astro, prerender.io, etc.).
#
# We deliberately avoid Playwright/headless Chromium here - that would
# require shipping a 300MB browser in the Railway container. Static HTML
# fetch is enough to catch the worst offenders (Vite/CRA/Vue SPAs that
# return `<div id="root"></div>` and nothing else).

_HTML_TAG_RE = re.compile(r'<[^>]+>')
_SCRIPT_STYLE_RE = re.compile(
    r'<(script|style|noscript)[^>]*>.*?</\1>',
    re.IGNORECASE | re.DOTALL,
)
_BODY_RE = re.compile(r'<body[^>]*>(.*?)</body>', re.IGNORECASE | re.DOTALL)
_WHITESPACE_RE = re.compile(r'\s+')


def _extract_body_text(html: str) -> str:
    """Strip <script>/<style>/<noscript>, then HTML tags, from inside <body>.

    Falls back to the whole document if no <body> tag is found (some
    minified pages drop the explicit tag). Returns plain text whitespace-
    normalized.
    """
    if not html:
        return ''
    match = _BODY_RE.search(html)
    body = match.group(1) if match else html
    # Remove script/style/noscript blocks first - their text doesn't count.
    cleaned = _SCRIPT_STYLE_RE.sub(' ', body)
    # Then strip every remaining HTML tag.
    text = _HTML_TAG_RE.sub(' ', cleaned)
    # Normalize whitespace.
    return _WHITESPACE_RE.sub(' ', text).strip()


def _check_renderability(url: str) -> dict:
    """Fetch `url` and decide whether the static HTML already contains
    meaningful body text (>100 words) or whether the page looks like an
    unprerendered SPA shell.

    Returns the response dict directly (no Django Response wrapper) so
    both the v1 endpoint and the JWT view can reuse it.
    """
    out = {
        'url': url,
        'is_prerendered': False,
        'html_contains_main_text': False,
        'word_count': 0,
        'warning': '',
        'suggestion': '',
    }

    try:
        resp = requests.get(
            url,
            timeout=10,
            headers={
                # Pretend to be Googlebot-ish so servers that gate prerender
                # on UA still serve us the SEO version.
                'User-Agent': (
                    'Mozilla/5.0 (compatible; Googlebot/2.1; '
                    '+http://www.google.com/bot.html)'
                ),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            },
            allow_redirects=True,
        )
    except requests.exceptions.Timeout:
        out['warning'] = 'Timeout > 10s en recuperant la page.'
        out['suggestion'] = (
            'Le serveur ne repond pas assez vite. Verifier la performance '
            'du backend ou tester avec une URL plus rapide.'
        )
        return out
    except requests.exceptions.RequestException as exc:
        out['warning'] = f'Erreur reseau: {str(exc)[:120]}'
        out['suggestion'] = (
            'Verifier que l URL est accessible publiquement et qu il n y a '
            'pas de redirection cassee, de SSL invalide ou de pare-feu.'
        )
        return out

    if resp.status_code >= 400:
        out['warning'] = f'HTTP {resp.status_code} renvoye par la page.'
        out['suggestion'] = (
            'La page retourne une erreur HTTP. Googlebot ne pourra pas '
            'l indexer tant que ce code ne sera pas 200.'
        )
        return out

    html = resp.text or ''
    body_text = _extract_body_text(html)
    words = body_text.split()
    word_count = len(words)
    out['word_count'] = word_count

    if word_count > 100:
        out['is_prerendered'] = True
        out['html_contains_main_text'] = True
        out['warning'] = ''
        out['suggestion'] = (
            f'OK: la page contient {word_count} mots de texte visible des le '
            'premier HTML. Googlebot peut l indexer sans dependre du JS.'
        )
        return out

    # Suspect: SPA shell or content gated behind JS.
    out['is_prerendered'] = False
    out['html_contains_main_text'] = False
    out['warning'] = (
        f'Seulement {word_count} mots de texte detectes dans le HTML brut. '
        'La page semble etre une SPA non-prerenderisee - Google doit '
        'executer le JS pour voir le contenu, ce qui ralentit l indexation '
        'et peut faire perdre du ranking.'
    )
    out['suggestion'] = (
        'Activer le prerendering ou le SSR: Next.js (getStaticProps / '
        'getServerSideProps), Nuxt, Astro, Vite SSG, ou un service externe '
        'comme prerender.io / Rendertron. Verifier ensuite que le HTML '
        'retourne sans JS contient bien les titres et le contenu principal.'
    )
    return out


class V1CheckRenderabilityView(BaseV1View):
    """POST /api/v1/check-renderability/ {url}

    Fetches the URL and inspects whether the raw HTML response contains
    enough body text (>100 words) to be considered server-rendered. Used
    to warn users whose sites ship as JS-heavy SPAs (which Googlebot can
    render but indexes more slowly and less reliably).

    Response:
        {
            url: str,
            is_prerendered: bool,
            html_contains_main_text: bool,
            word_count: int,
            warning: str,
            suggestion: str,
        }
    """

    def post(self, request):
        url = (request.data.get('url') or '').strip()
        if not url:
            return Response({'error': 'url is required.'},
                            status=status.HTTP_400_BAD_REQUEST)
        if not (url.startswith('http://') or url.startswith('https://')):
            return Response(
                {'error': 'url must start with http:// or https://.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(_check_renderability(url))


# ---------------------------------------------------------------------------
# Link Opportunities (P2 #11, 2026-06-08)
# ---------------------------------------------------------------------------


# Domains we never want to surface as link targets (social, marketplaces,
# generic giants - cold outreach there is hopeless).
_LINK_OPPORTUNITY_BLOCKLIST = {
    'youtube.com', 'youtu.be', 'facebook.com', 'instagram.com', 'twitter.com',
    'x.com', 'linkedin.com', 'pinterest.com', 'tiktok.com', 'reddit.com',
    'quora.com', 'wikipedia.org', 'amazon.com', 'amazon.ca', 'amazon.fr',
    'ebay.com', 'aliexpress.com', 'shopify.com', 'medium.com', 'github.com',
    'stackoverflow.com', 'apple.com', 'google.com', 'microsoft.com',
}

# Country/language top-level domains used to bias filtering.
_LANG_TLDS = {
    'fr': {'.fr', '.ca', '.be', '.ch', '.lu', '.qc.ca'},
    'en': {'.com', '.co.uk', '.uk', '.us', '.ca', '.au', '.nz', '.ie'},
    'es': {'.es', '.mx', '.ar', '.co', '.cl', '.pe'},
}


def _extract_root_domain(url: str) -> str:
    """Pull the registrable domain from a URL. Best-effort, no PSL."""
    if not url:
        return ''
    try:
        from urllib.parse import urlparse
        host = urlparse(url).netloc.lower()
        if host.startswith('www.'):
            host = host[4:]
        return host
    except Exception:
        return ''


def _is_blocklisted(domain: str) -> bool:
    if not domain:
        return True
    for blocked in _LINK_OPPORTUNITY_BLOCKLIST:
        if domain == blocked or domain.endswith('.' + blocked):
            return True
    return False


def _matches_language(url: str, language: str) -> bool:
    """Loose language filter: TLD match OR no obvious cross-language signal.

    We accept by default rather than reject - Serper's hl/gl already biases
    the results to the right locale, so we only need to drop obvious misses.
    """
    if language not in _LANG_TLDS:
        return True
    domain = _extract_root_domain(url)
    if not domain:
        return False
    # If it ends with one of the language's TLDs, accept.
    for tld in _LANG_TLDS[language]:
        if domain.endswith(tld):
            return True
    # Accept .org/.net/.io regardless - they're language-neutral and Serper
    # already filtered by hl/gl.
    for neutral in ('.org', '.net', '.io', '.info', '.app', '.blog'):
        if domain.endswith(neutral):
            return True
    return False


def _serper_organic(query: str, hl: str, gl: str, num: int = 10) -> list:
    """Run one Serper organic search. Returns [] on any failure."""
    api_key = os.environ.get('SERPER_API_KEY')
    if not api_key:
        return []
    try:
        resp = requests.post(
            'https://google.serper.dev/search',
            headers={'X-API-KEY': api_key, 'Content-Type': 'application/json'},
            json={'q': query, 'num': num, 'hl': hl, 'gl': gl},
            timeout=10,
        )
        if resp.status_code != 200:
            return []
        return (resp.json() or {}).get('organic', []) or []
    except Exception as exc:
        logger.warning('Serper link-opportunity query failed: %s', exc)
        return []


class V1LinkOpportunitiesView(BaseV1View):
    """POST /api/v1/link-opportunities/ {keyword, language?}

    Surface candidate sites for backlink outreach by querying Serper for
    "best <keyword> sites" + "ressources <keyword>" (FR) or "resources
    <keyword>" (EN/ES) and de-duplicating the SERP results by domain.

    Returns {targets: [{domain, url, title, snippet, source_query}], count}.
    """

    def post(self, request):
        keyword = (request.data.get('keyword') or '').strip()
        if not keyword:
            return Response({'error': 'keyword is required.'},
                            status=status.HTTP_400_BAD_REQUEST)
        language = (request.data.get('language') or 'fr').strip().lower()[:2]

        if not os.environ.get('SERPER_API_KEY'):
            return Response(
                {'error': 'SERPER_API_KEY non configuree.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        if language == 'en':
            hl, gl = 'en', 'us'
            queries = [
                f'best {keyword} sites',
                f'top {keyword} blogs',
                f'{keyword} resources',
            ]
        elif language == 'es':
            hl, gl = 'es', 'es'
            queries = [
                f'mejores sitios de {keyword}',
                f'recursos {keyword}',
                f'blogs sobre {keyword}',
            ]
        else:
            hl, gl = 'fr', 'ca'
            queries = [
                f'meilleurs sites {keyword}',
                f'ressources {keyword}',
                f'blogs sur {keyword}',
            ]

        seen_domains: set[str] = set()
        targets: list[dict] = []

        for q in queries:
            organic = _serper_organic(q, hl=hl, gl=gl, num=10)
            for item in organic:
                url = (item.get('link') or '').strip()
                if not url:
                    continue
                domain = _extract_root_domain(url)
                if not domain or domain in seen_domains:
                    continue
                if _is_blocklisted(domain):
                    continue
                if not _matches_language(url, language):
                    continue
                seen_domains.add(domain)
                targets.append({
                    'domain': domain,
                    'url': url,
                    'title': item.get('title') or '',
                    'snippet': item.get('snippet') or '',
                    'source_query': q,
                })
                if len(targets) >= 20:
                    break
            if len(targets) >= 20:
                break

        return Response({
            'keyword': keyword,
            'language': language,
            'targets': targets,
            'count': len(targets),
        })


# --------------------------------------------------------------------------
# SERP Analyzer (2026-06-08) - lightweight Surfer-like view of the top 10
# --------------------------------------------------------------------------


class V1SerpAnalyzeView(BaseV1View):
    """POST /api/v1/sites/<id>/serp-analyze/

    Body: {"keyword": str, "language": "fr"|"en"|"es"}

    Fetches the top 10 organic results for `keyword` via Serper.dev, then for
    each URL fetches the HTML and computes:
      - word_count    (visible text)
      - headings_count (h1+h2+h3 tags)
      - has_faq        (heuristic: "FAQ" or schema.org FAQPage)
      - has_video      (presence of <video> or youtube embed)
      - domain         (root domain, sans scheme/www)

    Returns:
      {
        keyword, language,
        top_10: [{position, url, domain, title, snippet,
                  word_count, headings_count, has_faq, has_video}],
        averages: {word_count_avg, headings_avg, faq_pct, video_pct}
      }

    Fetch failures degrade gracefully: the row still appears with null metrics
    and a `fetch_error: true` flag - the averages skip null values.
    """

    def post(self, request, site_id):
        # Authenticate the site even though we don't use any site-scoped data;
        # this keeps the endpoint behind the same plan/quota as other v1 calls
        # and lets us report per-site usage later.
        self.get_user_site(request, site_id)

        keyword = (request.data.get('keyword') or '').strip()
        if not keyword:
            return Response({'error': 'keyword est requis.'},
                            status=status.HTTP_400_BAD_REQUEST)
        language = (request.data.get('language') or 'fr').strip().lower()[:2]
        if language not in ('fr', 'en', 'es'):
            language = 'fr'

        api_key = os.environ.get('SERPER_API_KEY')
        if not api_key:
            return Response({'error': 'SERPER_API_KEY non configuree.'},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        if language == 'en':
            hl, gl = 'en', 'us'
        elif language == 'es':
            hl, gl = 'es', 'es'
        else:
            hl, gl = 'fr', 'ca'

        try:
            resp = requests.post(
                'https://google.serper.dev/search',
                headers={
                    'X-API-KEY': api_key,
                    'Content-Type': 'application/json',
                },
                json={'q': keyword, 'num': 10, 'hl': hl, 'gl': gl},
                timeout=10,
            )
        except requests.Timeout:
            return Response({'error': 'Serper timeout.'},
                            status=status.HTTP_504_GATEWAY_TIMEOUT)
        except Exception as e:
            return Response({'error': f'Serper erreur: {str(e)[:120]}'},
                            status=status.HTTP_502_BAD_GATEWAY)

        if resp.status_code != 200:
            return Response({'error': f'Serper HTTP {resp.status_code}'},
                            status=status.HTTP_502_BAD_GATEWAY)

        organic = (resp.json() or {}).get('organic', []) or []
        organic = organic[:10]

        tag_re = re.compile(r'<[^>]+>')
        head_re = re.compile(r'<h[1-3][\s>]', re.IGNORECASE)
        script_re = re.compile(r'<(script|style)[^>]*>.*?</\1>',
                               re.IGNORECASE | re.DOTALL)
        ws_re = re.compile(r'\s+')
        faq_re = re.compile(
            r'(FAQPage|"@type"\s*:\s*"FAQPage"|\bFAQ\b|'
            r'questions? frequentes?|foire aux questions)',
            re.IGNORECASE,
        )
        video_re = re.compile(
            r'(<video[\s>]|youtube\.com/embed|youtu\.be/|vimeo\.com/video)',
            re.IGNORECASE,
        )

        def _root_domain(u: str) -> str:
            try:
                from urllib.parse import urlparse
                netloc = urlparse(u).netloc.lower()
                if netloc.startswith('www.'):
                    netloc = netloc[4:]
                return netloc
            except Exception:
                return ''

        top_10 = []
        for idx, item in enumerate(organic, start=1):
            url = (item.get('link') or '').strip()
            entry = {
                'position': idx,
                'url': url,
                'domain': _root_domain(url),
                'title': item.get('title') or '',
                'snippet': item.get('snippet') or '',
                'word_count': None,
                'headings_count': None,
                'has_faq': False,
                'has_video': False,
                'fetch_error': False,
            }

            if not url:
                entry['fetch_error'] = True
                top_10.append(entry)
                continue

            try:
                page = requests.get(
                    url,
                    timeout=6,
                    headers={'User-Agent': 'Mozilla/5.0 GridarSerpBot/1.0'},
                )
                if not page.ok:
                    entry['fetch_error'] = True
                    top_10.append(entry)
                    continue
                html = page.text or ''
                entry['headings_count'] = len(head_re.findall(html))
                entry['has_faq'] = bool(faq_re.search(html))
                entry['has_video'] = bool(video_re.search(html))
                cleaned = script_re.sub(' ', html)
                text = tag_re.sub(' ', cleaned)
                text = ws_re.sub(' ', text).strip()
                entry['word_count'] = (
                    len([w for w in text.split(' ') if w]) if text else 0
                )
            except Exception:
                entry['fetch_error'] = True

            top_10.append(entry)

        words = [r['word_count'] for r in top_10 if r['word_count'] is not None]
        heads = [r['headings_count'] for r in top_10
                 if r['headings_count'] is not None]
        total = len(top_10) or 1
        faq_count = sum(1 for r in top_10 if r['has_faq'])
        video_count = sum(1 for r in top_10 if r['has_video'])

        averages = {
            'word_count_avg': int(sum(words) / len(words)) if words else 0,
            'headings_avg': round(sum(heads) / len(heads), 1) if heads else 0,
            'faq_pct': round(100.0 * faq_count / total, 1),
            'video_pct': round(100.0 * video_count / total, 1),
        }

        return Response({
            'keyword': keyword,
            'language': language,
            'top_10': top_10,
            'averages': averages,
        })


# --------------------------------------------------------------------------
# AI Visibility tracking (2026-06-08)
# Track how a site is mentioned in LLM responses (ChatGPT / Perplexity /
# Gemini / SearchGPT / Claude). V1: mocked results to validate the UX.
# --------------------------------------------------------------------------

AI_ENGINE_WEIGHTS = {
    'chatgpt': 0.30,
    'perplexity': 0.25,
    'gemini': 0.20,
    'searchgpt': 0.15,
    'claude': 0.10,
}

AI_ENGINES = list(AI_ENGINE_WEIGHTS.keys())


def _ai_visibility_compute_score(qs) -> float:
    """Weighted score = sum(weight_engine * cite_rate_engine) * 100.

    qs is a queryset of AiVisibilityResult. Engines with zero checks are
    skipped (their weight is ignored, not penalised) so a site that hasn't
    been tested on Gemini doesn't lose 20 points.
    """
    from collections import defaultdict
    totals: dict[str, int] = defaultdict(int)
    cited: dict[str, int] = defaultdict(int)
    for engine, is_cited in qs.values_list('engine', 'is_cited'):
        totals[engine] += 1
        if is_cited:
            cited[engine] += 1
    if not totals:
        return 0.0
    used_weight = sum(AI_ENGINE_WEIGHTS.get(e, 0.0) for e in totals.keys())
    if used_weight == 0:
        return 0.0
    weighted = 0.0
    for engine, total in totals.items():
        w = AI_ENGINE_WEIGHTS.get(engine, 0.0)
        rate = cited[engine] / total if total else 0.0
        weighted += (w / used_weight) * rate
    return round(weighted * 100.0, 1)


def _mock_engine_response(engine: str, prompt_text: str, site) -> dict:
    """Generate a plausible mocked LLM response for V1 testing.

    Returns dict with is_cited, response_excerpt, citation_url, citation_rank.
    Cite probability is engine-biased so the breakdown looks realistic.
    """
    import random
    # Engine bias: Perplexity cites sources most often; Claude rarely cites.
    cite_probability = {
        'chatgpt': 0.45,
        'perplexity': 0.65,
        'gemini': 0.40,
        'searchgpt': 0.55,
        'claude': 0.25,
    }.get(engine, 0.40)

    is_cited = random.random() < cite_probability
    citation_url = None
    citation_rank = None
    domain = (site.domain or '').strip() or 'example.com'

    if is_cited:
        citation_rank = random.randint(1, 5)
        path_options = ['', '/blog', '/articles', '/guide', '/about']
        citation_url = f"https://{domain}{random.choice(path_options)}"

    engine_label = {
        'chatgpt': 'ChatGPT',
        'perplexity': 'Perplexity',
        'gemini': 'Gemini',
        'searchgpt': 'SearchGPT',
        'claude': 'Claude',
    }.get(engine, engine.title())

    if is_cited:
        excerpt = (
            f"[{engine_label} mock] Pour repondre a \"{prompt_text[:80]}\", "
            f"plusieurs ressources peuvent t'aider, notamment {domain} qui "
            f"propose une approche detaillee du sujet. Voir aussi d'autres "
            f"references citees en position {citation_rank}."
        )
    else:
        excerpt = (
            f"[{engine_label} mock] Pour repondre a \"{prompt_text[:80]}\", "
            f"voici une synthese generale sans citer {domain}. Plusieurs "
            f"approches existent selon ton contexte."
        )

    return {
        'is_cited': is_cited,
        'response_excerpt': excerpt[:500],
        'citation_url': citation_url,
        'citation_rank': citation_rank,
    }


class V1AiVisibilitySummaryView(BaseV1View):
    """GET /api/v1/sites/<id>/ai-visibility/summary/

    Returns aggregated visibility metrics for the site:
      - score (weighted 0-100)
      - total_mentions
      - cited_pages_count
      - breakdown_by_engine
      - delta_7d (vs the previous 7-day window)
    """
    def get(self, request, site_id):
        site = self.get_user_site(request, site_id)
        prompts_qs = AiVisibilityPrompt.objects.filter(site=site)
        all_results = AiVisibilityResult.objects.filter(prompt__site=site)

        score = _ai_visibility_compute_score(all_results)

        now = timezone.now()
        last_7d_qs = all_results.filter(checked_at__gte=now - timedelta(days=7))
        prev_7d_qs = all_results.filter(
            checked_at__gte=now - timedelta(days=14),
            checked_at__lt=now - timedelta(days=7),
        )
        score_last = _ai_visibility_compute_score(last_7d_qs)
        score_prev = _ai_visibility_compute_score(prev_7d_qs)
        delta_7d = round(score_last - score_prev, 1)

        total_mentions = all_results.filter(is_cited=True).count()
        cited_pages_count = (
            all_results.filter(is_cited=True)
            .exclude(citation_url__isnull=True)
            .exclude(citation_url='')
            .values('citation_url').distinct().count()
        )

        breakdown: dict[str, dict] = {}
        for engine in AI_ENGINES:
            engine_qs = all_results.filter(engine=engine)
            total = engine_qs.count()
            cited = engine_qs.filter(is_cited=True).count()
            breakdown[engine] = {
                'total_checks': total,
                'cited_count': cited,
                'cite_rate': round((cited / total) * 100.0, 1) if total else 0.0,
            }

        return Response({
            'score': score,
            'total_mentions': total_mentions,
            'cited_pages_count': cited_pages_count,
            'total_checks': all_results.count(),
            'total_prompts': prompts_qs.count(),
            'breakdown_by_engine': breakdown,
            'delta_7d': delta_7d,
        })


class V1AiVisibilityPromptsView(BaseV1View):
    """GET/POST /api/v1/sites/<id>/ai-visibility/prompts/

    GET: list every tracked prompt with citation aggregates.
    POST: create a new prompt to track.
    """
    def get(self, request, site_id):
        site = self.get_user_site(request, site_id)
        prompts = AiVisibilityPrompt.objects.filter(site=site).order_by('-created_at')

        results = []
        for p in prompts:
            qs = p.results.all()
            total_checks = qs.count()
            citation_count = qs.filter(is_cited=True).count()
            engines_mentioning = sorted(
                set(qs.filter(is_cited=True).values_list('engine', flat=True))
            )
            last = qs.order_by('-checked_at').first()
            results.append({
                'id': p.id,
                'prompt': p.prompt,
                'target_intent': p.target_intent,
                'language': p.language,
                'created_at': p.created_at.isoformat(),
                'total_checks': total_checks,
                'citation_count': citation_count,
                'engines_mentioning': engines_mentioning,
                'last_checked_at': last.checked_at.isoformat() if last else None,
            })

        return Response({'results': results, 'count': len(results)})

    def post(self, request, site_id):
        site = self.get_user_site(request, site_id)
        prompt_text = (request.data.get('prompt') or '').strip()
        if not prompt_text:
            return Response(
                {'error': 'Le champ prompt est obligatoire.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        target_intent = (request.data.get('target_intent') or '').strip() or None
        valid_intents = dict(AiVisibilityPrompt.TARGET_INTENT_CHOICES)
        if target_intent and target_intent not in valid_intents:
            return Response(
                {'error': f'target_intent doit etre dans {list(valid_intents)}.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        language = (request.data.get('language') or site.default_language or 'fr').lower()[:2]
        if language not in ('fr', 'en', 'es'):
            language = 'fr'

        prompt = AiVisibilityPrompt.objects.create(
            site=site,
            prompt=prompt_text,
            target_intent=target_intent,
            language=language,
        )
        return Response({
            'id': prompt.id,
            'prompt': prompt.prompt,
            'target_intent': prompt.target_intent,
            'language': prompt.language,
            'created_at': prompt.created_at.isoformat(),
        }, status=status.HTTP_201_CREATED)


class V1AiVisibilityRunView(BaseV1View):
    """POST /api/v1/sites/<id>/ai-visibility/run/

    Trigger a check series for the site's tracked prompts.

    V1 (NO external LLM API calls): create mocked AiVisibilityResult rows
    for every (prompt, engine) pair so the UI can be validated.

    Body: {prompt_id?: int}
      - if prompt_id provided, only run checks for that single prompt
      - else run checks for every tracked prompt on the site
    """
    def post(self, request, site_id):
        site = self.get_user_site(request, site_id)
        prompt_id = request.data.get('prompt_id')

        if prompt_id is not None:
            try:
                prompts = [AiVisibilityPrompt.objects.get(
                    id=int(prompt_id), site=site
                )]
            except (AiVisibilityPrompt.DoesNotExist, ValueError, TypeError):
                return Response(
                    {'error': 'Prompt introuvable.'},
                    status=status.HTTP_404_NOT_FOUND,
                )
        else:
            prompts = list(AiVisibilityPrompt.objects.filter(site=site))

        if not prompts:
            return Response(
                {'error': 'Aucun prompt tracke. Ajoute un prompt avant de lancer un check.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        created_results = []
        for p in prompts:
            for engine in AI_ENGINES:
                mock = _mock_engine_response(engine, p.prompt, site)
                r = AiVisibilityResult.objects.create(
                    prompt=p,
                    engine=engine,
                    response_excerpt=mock['response_excerpt'],
                    is_cited=mock['is_cited'],
                    citation_url=mock['citation_url'],
                    citation_rank=mock['citation_rank'],
                )
                created_results.append({
                    'id': r.id,
                    'prompt_id': p.id,
                    'engine': engine,
                    'is_cited': r.is_cited,
                    'citation_url': r.citation_url,
                    'citation_rank': r.citation_rank,
                    'checked_at': r.checked_at.isoformat(),
                })

        return Response({
            'checks_run': len(created_results),
            'prompts_checked': len(prompts),
            'engines_per_prompt': len(AI_ENGINES),
            'results': created_results,
            'mocked': True,
            'note': 'V1 mock - external LLM APIs not called yet.',
        }, status=status.HTTP_201_CREATED)


class V1AiVisibilitySuggestView(BaseV1View):
    """POST /api/v1/sites/<id>/ai-visibility/suggest/

    Ask Claude for prompts a real prospect would type into an LLM (ChatGPT,
    Perplexity, Gemini...) and for which THIS site would deserve to be cited,
    so the user can track their AI visibility on them. Returns candidates for
    review; never auto-creates. Body: {count?: int} (default 6, max 12).
    Response: {prompts: [{prompt, target_intent, language}, ...]}.
    """
    def post(self, request, site_id):
        import json as _json
        import re
        site = self.get_user_site(request, site_id)

        try:
            count = int(request.data.get('count') or 6)
        except (TypeError, ValueError):
            count = 6
        count = max(3, min(12, count))

        language = (site.default_language or 'fr').lower()[:2]
        if language not in ('fr', 'en', 'es'):
            language = 'fr'

        from .models import TrackedKeyword
        kws = list(
            TrackedKeyword.objects.filter(site=site, is_active=True)
            .order_by('-updated_at').values_list('keyword', flat=True)[:12]
        )
        kw_block = '\n'.join(f'- {k}' for k in kws) or '(aucun mot-cle tracke)'
        valid_intents = [c[0] for c in AiVisibilityPrompt.TARGET_INTENT_CHOICES]

        prompt = f"""Tu es strategiste en visibilite sur les moteurs IA (ChatGPT, Perplexity, Gemini, SearchGPT, Claude). Genere {count} questions qu'un PROSPECT reel taperait a un LLM et pour lesquelles CE site meriterait d'etre cite dans la reponse.

SITE
- Nom: {site.name or '(sans nom)'}
- Domaine: {site.domain or '(non renseigne)'}
- Modele d'affaires: {site.business_model or 'inconnu'}
- Description: {(site.description or '').strip() or '(non renseignee)'}

MOTS-CLES TRACKES (contexte du marche vise):
{kw_block}

REGLES
- Ecris comme un vrai humain PARLE a une IA, pas un mot-cle SEO. Ex: "quel est le meilleur couvreur a Saint-Hyacinthe pour une toiture plate?" plutot que "couvreur toiture plate".
- Varie les intentions: informationnel, commercial/comparatif, transactionnel, local.
- Redige dans la variante de francais du MARCHE vise (deduis-la du domaine et des mots-cles: Quebec, France, Afrique francophone...), pas une variante par defaut.
- Chaque question doit pouvoir mener a une reponse ou ce site serait une bonne source.

REPONDS EN JSON STRICT (pas de markdown):
{{"prompts": [{{"prompt": "...", "target_intent": "informational|commercial|transactional|navigational|local"}}, ...]}}
"""

        from .llm import call_llm
        text = call_llm(prompt, max_tokens=1200, timeout=45)  # Anthropic -> DeepSeek
        if not text:
            return Response({'error': 'Aucune reponse LLM (Anthropic + fallback DeepSeek indisponibles).'},
                            status=status.HTTP_502_BAD_GATEWAY)

        match = re.search(r'\{[\s\S]*\}', text)
        if not match:
            return Response({'error': 'Reponse Claude non parsable', 'raw': text[:500]},
                            status=status.HTTP_502_BAD_GATEWAY)
        try:
            parsed = _json.loads(match.group())
        except _json.JSONDecodeError:
            return Response({'error': 'JSON Claude invalide', 'raw': text[:500]},
                            status=status.HTTP_502_BAD_GATEWAY)

        seen = set()
        out = []
        for item in (parsed.get('prompts') or []):
            if not isinstance(item, dict):
                continue
            p = (item.get('prompt') or '').strip()
            key = p.lower()
            if not p or key in seen:
                continue
            intent = (item.get('target_intent') or '').strip().lower()
            if intent not in valid_intents:
                intent = 'informational'
            seen.add(key)
            out.append({'prompt': p[:500], 'target_intent': intent, 'language': language})
            if len(out) >= count:
                break

        return Response({'prompts': out})


# ===========================================================================
# Strategic Opportunities (2026-06-09)
# ===========================================================================
# Cross-section of tracked keywords + site context + Claude. For each
# transactional / commercial / local keyword without a matching landing, the
# engine produces a structured page concept (hook, capture mechanism,
# conversion path) + traffic estimate. The user reviews them on
# /dashboard/X/opportunites and approves the ones to ship - approving
# spawns a HostedLanding via the existing LandingGenerator path.

class V1StrategicOpportunitiesView(BaseV1View):
    """GET /api/v1/sites/<id>/strategic-opportunities/

    Returns the current list ordered by priority then created_at desc. Does
    NOT trigger Claude - call /refresh/ for that. Archived rows (status 'done',
    i.e. a page was already created, and 'dismissed') are hidden by default so
    the list stays focused on what is left to action; pass ?include_archived=1
    to bring both back. ?include_dismissed=1 is kept for backward compat.
    """

    def get(self, request, site_id):
        from .models import StrategicOpportunity
        site = self.get_user_site(request, site_id)
        include_archived = request.query_params.get('include_archived') == '1'
        include_dismissed = (
            include_archived
            or request.query_params.get('include_dismissed') == '1'
        )
        qs = StrategicOpportunity.objects.filter(site=site)
        if not include_archived:
            qs = qs.exclude(status='done')
        if not include_dismissed:
            qs = qs.exclude(status='dismissed')
        results = []
        for op in qs.select_related('tracked_keyword', 'generated_landing'):
            results.append({
                'id': op.id,
                'keyword': op.keyword,
                'intent': op.intent,
                'language': op.language,
                'current_position': op.current_position,
                'priority': op.priority,
                'status': op.status,
                'concept': op.concept,
                'estimate': op.estimate,
                'tracked_keyword_id': op.tracked_keyword_id,
                'generated_landing_id': op.generated_landing_id,
                'generated_landing_slug': (
                    op.generated_landing.slug if op.generated_landing else None
                ),
                'created_at': op.created_at.isoformat(),
                'refreshed_at': (
                    op.refreshed_at.isoformat() if op.refreshed_at else None
                ),
            })
        return Response({'results': results, 'count': len(results)})


class V1StrategicOpportunitiesRefreshView(BaseV1View):
    """POST /api/v1/sites/<id>/strategic-opportunities/refresh/

    Loops over the eligible tracked keywords (non-info intent, no matching
    landing) and re-runs the Claude strategic prompt for each. Upserts a
    StrategicOpportunity row per (site, keyword). Bounded to max_keywords
    (default 8, capped at 20) to keep Claude cost predictable.
    """

    def post(self, request, site_id):
        from django.utils import timezone
        from .models import StrategicOpportunity
        from .strategic_opportunities import (
            candidate_keywords, propose_opportunity,
        )

        site = self.get_user_site(request, site_id)
        try:
            max_kw = max(1, min(int(request.data.get('max_keywords') or 8), 20))
        except (TypeError, ValueError):
            max_kw = 8

        candidates = list(candidate_keywords(site)[:max_kw])
        refreshed = []
        skipped = []

        for tk in candidates:
            result = propose_opportunity(site, tk)
            if not result:
                skipped.append({
                    'keyword': tk.keyword, 'reason': 'llm_unavailable',
                })
                continue

            concept = result['concept']
            estimate = result['estimate']
            priority = (concept.get('priority') or 'medium').lower()
            if priority not in ('high', 'medium', 'low'):
                priority = 'medium'

            op, _ = StrategicOpportunity.objects.update_or_create(
                site=site,
                keyword=tk.keyword,
                language=result['language'],
                defaults={
                    'tracked_keyword': tk,
                    'intent': tk.intent or 'commercial',
                    'concept': concept,
                    'estimate': estimate,
                    'current_position': result['current_position'],
                    'priority': priority,
                    # Preserve dismissed / done status if user already acted.
                    'status': 'proposed',
                    'refreshed_at': timezone.now(),
                },
            )
            refreshed.append({
                'id': op.id, 'keyword': op.keyword, 'priority': op.priority,
            })

        return Response({
            'refreshed': refreshed,
            'skipped': skipped,
            'count_refreshed': len(refreshed),
            'count_skipped': len(skipped),
            'count_candidates': len(candidates),
        })


class V1StrategicOpportunityActionView(BaseV1View):
    """POST /api/v1/sites/<id>/strategic-opportunities/<op_id>/<action>/

    action = `dismiss` | `restore` | `approve`.

    - dismiss : marks the opportunity as Ecartee. Won't reappear on refresh
      unless the user restores it.
    - restore : flips a dismissed row back to proposed.
    - approve : generates a HostedLanding from the concept via
      LandingGenerator (same engine as V1ApproveStrategyView). Marks the
      opportunity `done` and links the new landing.
    """

    def post(self, request, site_id, op_id, action):
        from django.utils import timezone
        from .models import StrategicOpportunity, HostedLanding

        site = self.get_user_site(request, site_id)
        try:
            op = StrategicOpportunity.objects.get(site=site, id=int(op_id))
        except (StrategicOpportunity.DoesNotExist, ValueError, TypeError):
            return Response({'error': 'Opportunite introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)

        if action == 'dismiss':
            op.status = 'dismissed'
            op.dismissed_at = timezone.now()
            op.save(update_fields=['status', 'dismissed_at', 'updated_at'])
            return Response({'id': op.id, 'status': op.status})

        if action == 'restore':
            op.status = 'proposed'
            op.dismissed_at = None
            op.save(update_fields=['status', 'dismissed_at', 'updated_at'])
            return Response({'id': op.id, 'status': op.status})

        if action == 'approve':
            if op.status == 'done' and op.generated_landing_id:
                return Response({
                    'id': op.id, 'status': op.status,
                    'landing_id': op.generated_landing_id,
                    'note': 'Page deja creee.',
                })

            # Landings are only hosted-servable. On a non-hosted site (external
            # Postgres or a connected CMS) a generated HostedLanding would be
            # stranded in Gridar's DB and never reach the client's real site -
            # the "black hole". Instead of faking success, tell the user why and
            # point them to the build prompt, which the UI exposes as the
            # primary action for external sites.
            from .delivery import block_reason
            _blk = block_reason(site)
            if _blk:
                return Response({'error': _blk, 'code': 'delivery_blocked'},
                                status=status.HTTP_409_CONFLICT)
            if not site.is_hosted:
                return Response({
                    'error': (
                        "Ce site n'est pas heberge chez Gridar : il utilise un "
                        "stockage externe. Gridar ne peut pas publier une landing "
                        "directement dessus. Utilise \"Obtenir le prompt de "
                        "creation\" pour batir cette page sur ton propre site."
                    ),
                    'delivery': 'external',
                    'reason': 'not_hosted',
                }, status=status.HTTP_400_BAD_REQUEST)

            # Map page_type -> LandingGenerator page_subtype.
            page_type = (op.concept or {}).get('page_type') or 'service_page'
            subtype_map = {
                'tool_landing': 'service',
                'service_page': 'service',
                'comparison': 'comparison',
                'guide_pillar': 'pillar',
                'quiz_landing': 'service',
                'calculator': 'service',
                'local_landing': 'local',
                'lead_magnet': 'service',
            }
            page_subtype = subtype_map.get(page_type, 'service')

            # Doorway-page gate. A pile of location pages that differ only by
            # city name is the pattern Google penalizes, and the cost lands on
            # the whole domain, not just those pages. Refuse past the hard
            # stop unless the caller states a justification.
            if page_subtype == 'local':
                from .quality_gates import check_location_volume
                existing_local = HostedLanding.objects.filter(
                    site=site, page_subtype='local',
                ).count()
                gate = check_location_volume(existing_local, adding=1)
                forced = str(
                    request.data.get('force') or request.query_params.get('force') or ''
                ).lower() in ('1', 'true', 'yes')
                if gate['level'] == 'hard_stop' and not forced:
                    return Response(
                        {
                            'error': gate['message'],
                            'code': 'doorway_hard_stop',
                            'requirements': gate['requirements'],
                            'existing_local_pages': existing_local,
                            'hint': "Renvoie force=true pour passer outre en connaissance de cause.",
                        },
                        status=status.HTTP_409_CONFLICT,
                    )
            else:
                gate = None

            from .landing_generator import LandingGenerator, LandingGeneratorError
            try:
                gen = LandingGenerator(site=site, language=op.language)
                payload = gen.generate(
                    keyword=op.keyword,
                    page_subtype=page_subtype,
                )
                # Honour the LLM-suggested slug if Claude gave one.
                suggested_slug = (op.concept or {}).get('suggested_url_path') or ''
                suggested_slug = suggested_slug.lstrip('/').strip()[:200]
                if suggested_slug:
                    payload['slug'] = suggested_slug
                base_slug = payload['slug']
                n = 1
                while HostedLanding.objects.filter(
                    site=site, slug=payload['slug']
                ).exists():
                    n += 1
                    payload['slug'] = f'{base_slug}-{n}'[:200]
                landing = HostedLanding.objects.create(site=site, **payload)
            except LandingGeneratorError as e:
                return Response({'error': str(e)},
                                status=status.HTTP_502_BAD_GATEWAY)
            except Exception as e:  # noqa: BLE001
                logger.exception('Strategic opportunity approve failed')
                return Response({'error': str(e)[:200]},
                                status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            op.status = 'done'
            op.generated_landing = landing
            op.save(update_fields=[
                'status', 'generated_landing', 'updated_at',
            ])
            payload_out = {
                'id': op.id, 'status': op.status,
                'landing_id': landing.id, 'landing_slug': landing.slug,
            }
            if gate and gate['level'] != 'ok':
                payload_out['quality_warning'] = {
                    'message': gate['message'],
                    'requirements': gate['requirements'],
                    'level': gate['level'],
                }
            return Response(payload_out)

        return Response({'error': f"Action inconnue: {action}"},
                        status=status.HTTP_400_BAD_REQUEST)


# ===========================================================================
# Prompt export (2026-06-10)
# ===========================================================================
# For users who build their site with an AI assistant (ChatGPT, Lovable, v0,
# Bolt...) and have no CMS Gridar can push into. We hand them a ready-to-
# paste prompt; THEIR AI does the integration in THEIR codebase. Pure
# templating server-side - no LLM call, no quota.

class V1LandingPromptView(BaseV1View):
    """GET /api/v1/sites/<id>/landings/<landing_id>/prompt/?stack=nextjs

    INTEGRATE mode: the landing copy already exists, the prompt instructs
    the user's AI to integrate it verbatim (meta, structure, JSON-LD,
    exact slug). `stack` adapts the final instructions - one of nextjs,
    react, html, astro, wordpress, webflow, generic (default).
    """

    def get(self, request, site_id, landing_id):
        from .models import HostedLanding
        from .prompt_export import build_landing_prompt, normalize_stack

        site = self.get_user_site(request, site_id)
        landing = HostedLanding.objects.filter(
            site=site, id=landing_id,
        ).first()
        if landing is None:
            return Response({'error': 'Landing introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)

        stack = normalize_stack(request.query_params.get('stack'))
        prompt = build_landing_prompt(landing, site, stack=stack)
        return Response({
            'prompt': prompt,
            'source': 'landing',
            'landing_id': landing.id,
            'slug': landing.slug,
            'stack': stack,
            'char_count': len(prompt),
        })


class V1OpportunityPromptView(BaseV1View):
    """GET /api/v1/sites/<id>/strategic-opportunities/<op_id>/prompt/?stack=...

    CREATE mode: only the strategic concept exists, the prompt instructs
    the user's AI to write the page following the brief (hook, capture
    mechanism, conversion path, angle, FR-CA lexicon when language=fr).
    """

    def get(self, request, site_id, op_id):
        from .models import StrategicOpportunity
        from .prompt_export import build_opportunity_prompt, normalize_stack

        site = self.get_user_site(request, site_id)
        try:
            op = StrategicOpportunity.objects.get(site=site, id=int(op_id))
        except (StrategicOpportunity.DoesNotExist, ValueError, TypeError):
            return Response({'error': 'Opportunite introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)

        stack = normalize_stack(request.query_params.get('stack'))
        prompt = build_opportunity_prompt(op, site, stack=stack)
        return Response({
            'prompt': prompt,
            'source': 'opportunity',
            'opportunity_id': op.id,
            'keyword': op.keyword,
            'stack': stack,
            'char_count': len(prompt),
        })


class V1BuildQueueView(BaseV1View):
    """GET /api/v1/sites/<id>/build-queue/?stack=nextjs|react|html|astro|generic

    The queue of pages a coding agent (Claude Code, Cursor...) should create in
    the client's OWN repo, for a dev-built / external site that Gridar can't
    publish to directly. Two kinds, by design:

      - landings: BRIEFS from strategic opportunities still to action. The agent
        writes the copy itself from the concept + build prompt (C1). Pure
        templating, no LLM call here.
      - articles: GENERATED COPY from draft HostedPosts (C2). The agent
        integrates the finished, keyword-calibrated article verbatim.

    Report each built URL back via /build-queue/mark-built/ so the delivery and
    proof loop can close.
    """

    def get(self, request, site_id):
        from .models import StrategicOpportunity, HostedPost, TrackedKeyword
        from .prompt_export import (
            build_opportunity_prompt, build_article_brief_prompt, normalize_stack,
        )

        site = self.get_user_site(request, site_id)
        stack = normalize_stack(request.query_params.get('stack'))

        # Landings = every actionable strategic opportunity (commercial /
        # transactional / local intent). Each entry's (kind, id) is exactly what
        # to echo back to mark-built.
        landings = []
        opp = (StrategicOpportunity.objects
               .filter(site=site)
               .exclude(status__in=('done', 'dismissed'))
               .order_by('-priority', '-created_at'))
        for op in opp:
            concept = op.concept or {}
            landings.append({
                'kind': 'landing',
                'id': op.id,
                'opportunity_id': op.id,
                'keyword': op.keyword,
                'intent': op.intent,
                'priority': op.priority,
                'page_type': concept.get('page_type'),
                'suggested_title': concept.get('suggested_title'),
                'suggested_slug': (concept.get('suggested_url_path') or '').lstrip('/'),
                'concept': concept,
                'build_prompt': build_opportunity_prompt(op, site, stack=stack),
            })

        articles = []
        # C2: ready-to-integrate copy generated by Gridar. Undelivered drafts
        # only (external_url stamped => already live on the client's site).
        drafts = (HostedPost.objects
                  .filter(site=site, status='draft', external_url='')
                  .order_by('-created_at')[:50])
        for p in drafts:
            articles.append({
                'kind': 'article',
                'id': p.id,
                'post_id': p.id,
                'title': p.title,
                'slug': p.slug,
                'language': p.language,
                'excerpt': p.excerpt,
                'content': p.content,
            })
        # Briefs: info-intent tracked keywords not yet covered by an article.
        # target_url is Gridar's "URL we expect to rank" field; empty => no
        # article yet, so the agent writes one from the brief. mark-built stamps
        # target_url, which drops it here and feeds rank tracking.
        n_ready = len(articles)
        briefs = (TrackedKeyword.objects
                  .filter(site=site, intent='info', is_active=True, target_url='')
                  .order_by('-created_at')[:50])
        for kw in briefs:
            articles.append({
                'kind': 'article_brief',
                'id': kw.id,
                'tracked_keyword_id': kw.id,
                'keyword': kw.keyword,
                'intent': kw.intent,
                'language': kw.language,
                'build_prompt': build_article_brief_prompt(
                    kw.keyword, site, stack=stack,
                    language=kw.language, intent=kw.intent,
                ),
            })

        return Response({
            'site_id': site.id,
            'stack': stack,
            'delivery_mode': site.delivery_mode,
            'landings': landings,
            'articles': articles,
            'counts': {
                'landings': len(landings),
                'articles': len(articles),
                'articles_ready': n_ready,
                'articles_brief': len(articles) - n_ready,
            },
            'note': (
                "Pour chaque entree, reporte via mark-built avec SON 'kind' et son 'id'. "
                "landings = briefs de page, ecris la copy depuis build_prompt. "
                "articles kind=article = copy generee (champ content), integre verbatim. "
                "articles kind=article_brief = ecris l'article depuis build_prompt."
            ),
        })


class V1BuildQueueMarkBuiltView(BaseV1View):
    """POST /api/v1/sites/<id>/build-queue/mark-built/

    An agent reports that a queued page is now live in the client's repo. Echo
    back the queue entry's own 'kind' and 'id'. Body: {kind, id, url}.
      - 'landing' (id = opportunity_id): marks the opportunity 'done' so it
        archives out of the active list.
      - 'article' (id = post_id, a ready article): stamps the draft's delivered
        URL so the proof loop can attribute positions.
      - 'article_brief' (id = tracked_keyword_id, an article written from a
        brief): stamps the keyword's target_url, which drops the brief out of
        the queue and feeds SERP-rank tracking for that keyword.
    """

    def post(self, request, site_id):
        from .models import StrategicOpportunity, HostedPost, TrackedKeyword
        from .index_now import submit_one_safe
        site = self.get_user_site(request, site_id)
        kind = (request.data.get('kind') or '').strip().lower()
        url = (request.data.get('url') or '').strip()
        try:
            obj_id = int(request.data.get('id'))
        except (TypeError, ValueError):
            return Response({'error': 'id invalide.'}, status=status.HTTP_400_BAD_REQUEST)

        if kind == 'landing':
            try:
                op = StrategicOpportunity.objects.get(site=site, id=obj_id)
            except StrategicOpportunity.DoesNotExist:
                return Response({'error': 'Opportunite introuvable.'},
                                status=status.HTTP_404_NOT_FOUND)
            op.status = 'done'
            op.save(update_fields=['status', 'updated_at'])
            submit_one_safe(site, url)  # auto-ping IndexNow (Bing/AI search)
            return Response({'ok': True, 'kind': kind, 'id': op.id, 'status': 'done', 'url': url})

        if kind == 'article':
            if not url:
                return Response(
                    {'error': "url requise pour un article (l'URL live sur le site du client)."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            try:
                post = HostedPost.objects.get(site=site, id=obj_id)
            except HostedPost.DoesNotExist:
                return Response({'error': 'Article introuvable.'},
                                status=status.HTTP_404_NOT_FOUND)
            # Stamp the delivered URL: the article is now live on the client's
            # OWN site. This drops it out of the build queue and lets the proof
            # loop attribute positions to the real external URL.
            post.external_url = url
            post.delivered_at = timezone.now()
            post.save(update_fields=['external_url', 'delivered_at', 'updated_at'])
            submit_one_safe(site, url)  # auto-ping IndexNow (Bing/AI search)
            return Response({'ok': True, 'kind': 'article', 'id': post.id,
                             'url': url, 'delivered': True})

        if kind == 'article_brief':
            if not url:
                return Response(
                    {'error': "url requise pour un article (l'URL live sur le site du client)."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            try:
                kw = TrackedKeyword.objects.get(site=site, id=obj_id)
            except TrackedKeyword.DoesNotExist:
                return Response({'error': 'Mot-cle introuvable.'},
                                status=status.HTTP_404_NOT_FOUND)
            # target_url = "the URL we expect to rank" for this keyword. Setting
            # it records the brief as delivered (drops it out of the queue) and
            # points SERP-rank tracking at the real live article.
            kw.target_url = url
            kw.save(update_fields=['target_url', 'updated_at'])
            submit_one_safe(site, url)  # auto-ping IndexNow (Bing/AI search)
            return Response({'ok': True, 'kind': 'article_brief', 'id': kw.id,
                             'url': url, 'delivered': True})

        return Response({'error': "kind doit etre 'landing', 'article' ou 'article_brief'."},
                        status=status.HTTP_400_BAD_REQUEST)


class V1ClusterMapView(BaseV1View):
    """GET /api/v1/sites/<id>/clusters/

    Site-wide topic cluster map: groups the site's known keywords (tracked +
    strategic opportunities) into topic clusters (one pillar + N spokes) and
    flags which keywords already have a page. Deterministic, no LLM call, no
    quota. Feed a cluster to the build endpoint to generate the whole thing.
    """

    def get(self, request, site_id):
        from .topic_clusters import build_cluster_map
        site = self.get_user_site(request, site_id)
        result = build_cluster_map(site)
        result['site_id'] = site.id
        return Response(result)


class V1ClusterBuildView(BaseV1View):
    """POST /api/v1/sites/<id>/clusters/build/

    Body: {pillar_keyword: str, spokes: [str], stack?: str, language?: str}

    Builds the coordinated prompt bundle for a whole topic cluster: the pillar
    page + each spoke article, with the internal mesh baked into every prompt
    (pillar -> spokes, each spoke -> pillar). Each page is tied to a tracked
    keyword so the agent closes the loop via mark-built (kind='article_brief').
    No LLM call, so it works even while generation is capped. Returns
    {pillar, spokes, counts, note}.
    """

    def post(self, request, site_id):
        from .topic_clusters import build_cluster
        site = self.get_user_site(request, site_id)
        pillar_keyword = (request.data.get('pillar_keyword') or '').strip()
        if not pillar_keyword:
            return Response({'error': 'pillar_keyword est requis.'},
                            status=status.HTTP_400_BAD_REQUEST)
        spokes = request.data.get('spokes') or []
        if not isinstance(spokes, list) or not all(isinstance(x, str) for x in spokes):
            return Response({'error': 'spokes doit etre une liste de chaines (mots-cles).'},
                            status=status.HTTP_400_BAD_REQUEST)
        stack = request.data.get('stack') or 'generic'
        language = request.data.get('language')
        pillar_slug = request.data.get('pillar_slug')
        try:
            bundle = build_cluster(
                site, pillar_keyword, spokes, stack=stack, language=language,
                pillar_slug=pillar_slug,
            )
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        bundle['site_id'] = site.id
        return Response(bundle)


class V1IndexCoverageView(BaseV1View):
    """GET /api/v1/sites/<id>/index-coverage/?max_inspect=25

    Which of the site's expected pages Google has actually indexed. Cross-refs
    the sitemap (or Gridar-known pages) against `site:<domain>` (works on any
    site) and, when GSC is connected, the authoritative GSC URL Inspection
    status + the reason a page is not indexed. No LLM, no quota.
    """

    def get(self, request, site_id):
        from .index_coverage import index_coverage
        site = self.get_user_site(request, site_id)
        try:
            max_inspect = max(0, min(int(request.query_params.get('max_inspect') or 25), 100))
        except (TypeError, ValueError):
            max_inspect = 25
        try:
            result = index_coverage(site, max_inspect=max_inspect)
        except Exception as e:
            logger.warning('index_coverage failed for site %s: %s', site.id, e)
            return Response(
                {'error': "L'audit d'indexation a echoue (service externe ou delai). Reessaie."},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        result['site_id'] = site.id
        return Response(result)


class V1IndexNowView(BaseV1View):
    """GET /api/v1/sites/<id>/indexnow/

    The site's IndexNow key + the ownership file to host at the domain root, so
    the site can submit URLs to Bing / Yandex / Seznam / Naver (not Google).
    Generates + persists the key on first call. No LLM, no quota.
    """

    def get(self, request, site_id):
        from .index_now import key_file_info
        site = self.get_user_site(request, site_id)
        info = key_file_info(site)
        info['site_id'] = site.id
        return Response(info)


class V1IndexNowSubmitView(BaseV1View):
    """POST /api/v1/sites/<id>/indexnow/submit/  {urls?: [str]}

    Submit URLs to IndexNow. If `urls` is omitted, defaults to the site's
    sitemap URLs. All URLs must be on the site's own host.
    """

    def post(self, request, site_id):
        from .index_now import submit_urls
        from .index_coverage import _fetch_sitemap_urls, _public_base
        site = self.get_user_site(request, site_id)
        urls = request.data.get('urls')
        if not isinstance(urls, list) or not urls:
            base, _ = _public_base(site)
            urls = _fetch_sitemap_urls(base) if base else []
            if not urls:
                return Response(
                    {'error': "Aucune URL a soumettre : fournis 'urls' ou "
                              "configure un sitemap.xml pour ce site."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        result = submit_urls(site, [str(u) for u in urls])
        result['site_id'] = site.id
        return Response(result)


class V1SitemapSubmitView(BaseV1View):
    """POST /api/v1/sites/<id>/sitemap/submit/  {sitemap_url?: str}

    Re-soumet le sitemap du site a Google Search Console, ce qui force Google a
    le RELIRE au lieu d'attendre son prochain passage. Sans `sitemap_url`, prend
    `<host public>/sitemap.xml`. Exige que GSC soit connectee avec le scope
    d'ecriture. Codes : 401 `gsc_reauth_required` (jeton mort), 409
    `gsc_scope_readonly` (site connecte avant l'elargissement du scope), 400
    sinon. Pas de LLM ; consomme le quota Search Console.
    """

    def post(self, request, site_id):
        from .proof_loop import submit_sitemap
        site = self.get_user_site(request, site_id)
        demande = request.data.get('sitemap_url')
        if demande is not None and not isinstance(demande, str):
            return Response({'error': "sitemap_url doit etre une chaine."},
                            status=status.HTTP_400_BAD_REQUEST)
        result = submit_sitemap(site, demande or '')
        result['site_id'] = site.id
        if result.get('ok'):
            return Response(result)
        if result.get('code') == 'gsc_reauth_required':
            # Meme contrat que les autres vues GSC du projet, que le frontend
            # sait deja afficher (ContentDecayPage, MultiSiteHealthTable).
            return Response(result, status=status.HTTP_401_UNAUTHORIZED)
        # 409 quand c'est le jeton qui bloque : l'appelant a un geste a faire
        # (reconnecter GSC), ce n'est ni sa requete ni une panne serveur.
        code = (status.HTTP_409_CONFLICT if result.get('needs_reconnect')
                else status.HTTP_400_BAD_REQUEST)
        return Response(result, status=code)

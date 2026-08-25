import os
import re
import uuid
import base64
import hashlib
import logging
from urllib.parse import quote, urlparse

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied as DRFPermissionDenied
from rest_framework.throttling import UserRateThrottle
from django.shortcuts import get_object_or_404
from django.conf import settings
from django.core.cache import cache
from django.db import ProgrammingError
from django.db.models import Sum
from django.utils.text import slugify
from django.core.management import call_command
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from datetime import date, datetime
from io import StringIO
import requests as http_requests

from .url_safety import safe_get

from django.http import HttpResponse

import markdown as md_lib

from .models import (
    Site, UploadedImage, HostedPost, HostedCategory, HostedTag, HostedLanding,
    TrackedKeyword, SerpRank, Redirect, Subscription,
)
from .db_utils import ensure_site_connection, test_site_connection
from .blog_adapter import detect_blog_tables, setup_blog_views
from .rank_display import keyword_display_rank, DEFAULT_WINDOW

logger = logging.getLogger(__name__)


def _markdown_to_html(text):
    """Convert Markdown to HTML for sites that store content as HTML."""
    return md_lib.markdown(
        text,
        extensions=['tables', 'fenced_code', 'nl2br', 'sane_lists'],
    )
from .serializers import (
    SiteSerializer, SiteListSerializer,
    BlogPostListSerializer, BlogPostDetailSerializer, BlogPostWriteSerializer,
    CategorySerializer, TagSerializer,
)
from blog.models import BlogPost, Category, Tag


def get_site_for_user(request, site_id):
    return get_object_or_404(Site, id=site_id, owner=request.user)


def trigger_vercel_deploy(site):
    """Trigger a Vercel redeployment if a deploy hook is configured."""
    if not site.vercel_deploy_hook:
        return
    try:
        http_requests.post(site.vercel_deploy_hook, timeout=5)
    except Exception:
        pass  # Non-blocking - don't fail the request if deploy hook fails


class SiteViewSet(viewsets.ModelViewSet):
    """CRUD pour les sites."""
    permission_classes = [IsAuthenticated]
    serializer_class = SiteSerializer

    def get_queryset(self):
        return Site.objects.filter(owner=self.request.user)

    def get_serializer_class(self):
        if self.action == 'list':
            return SiteListSerializer
        return SiteSerializer

    def create(self, request, *args, **kwargs):
        # Enforce sites_max from the user's plan before creating a new site.
        from .quota import check_site_quota
        try:
            check_site_quota(request.user)
        except DRFPermissionDenied as e:
            return Response(
                {'error': str(e), 'quota_exceeded': True, 'limit_type': 'sites'},
                status=status.HTTP_402_PAYMENT_REQUIRED,
            )
        return super().create(request, *args, **kwargs)

    @action(detail=True, methods=['post'])
    def test(self, request, pk=None):
        site = self.get_object()
        success, message = test_site_connection(site)
        return Response({'success': success, 'message': message})

    @action(detail=True, methods=['post'])
    def init_db(self, request, pk=None):
        """Create blog tables in the site's database."""
        site = self.get_object()
        try:
            alias = ensure_site_connection(site)
        except ValueError:
            return Response(
                {'error': "Cette action nécessite une base de données externe configurée pour ce site."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            out = StringIO()
            call_command('migrate', 'blog', database=alias, stdout=out, stderr=out)
            return Response({'success': True, 'output': out.getvalue()})
        except Exception as e:
            return Response(
                {'success': False, 'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'])
    def detect_blog(self, request, pk=None):
        """Auto-detect blog tables in the site's database."""
        site = self.get_object()
        try:
            alias = ensure_site_connection(site)
        except ValueError:
            return Response(
                {'error': "Cette action nécessite une base de données externe configurée pour ce site."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            result = detect_blog_tables(alias)
            return Response(result)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'])
    def setup_blog(self, request, pk=None):
        """Create SQL views mapping custom blog tables to standard blog_* names."""
        site = self.get_object()
        try:
            alias = ensure_site_connection(site)
        except ValueError:
            return Response(
                {'error': "Cette action nécessite une base de données externe configurée pour ce site."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        config = request.data.get('config') or site.blog_config
        if not config:
            return Response(
                {'error': 'Aucune config fournie. Utilisez detect_blog d\'abord.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            setup_blog_views(alias, config)
            site.blog_config = config
            site.save(update_fields=['blog_config'])
            return Response({
                'success': True,
                'message': 'Vues SQL creees avec succes.',
            })
        except Exception as e:
            return Response(
                {'success': False, 'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class UserProfileView(APIView):
    """GET /api/auth/me/

    Returns a denormalized snapshot of the current user so the SPA doesn't
    need to fan out to /billing/me/ + /sites/ + /credit-balance/ on every
    page load. The frontend AuthContext caches this and re-fetches on
    explicit checkAuth() calls (after login, register, social-login, password
    reset, plan change, etc.).
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from .models import CreditBalance, Subscription

        u = request.user
        sub = Subscription.objects.filter(user=u).only(
            'plan', 'status', 'current_period_end', 'cancel_at_period_end',
        ).first()
        bal = CreditBalance.objects.filter(user=u).only('balance').first()

        # Social providers linked to this account (for the UI to show "Linked
        # accounts" + the OAuth-only login pivot if has_password is False).
        social_providers = []
        try:
            from allauth.socialaccount.models import SocialAccount
            social_providers = list(
                SocialAccount.objects.filter(user=u).values_list('provider', flat=True)
            )
        except Exception:
            pass

        return Response({
            'id': u.id,
            'username': u.username,
            'email': u.email,
            'is_staff': u.is_staff,
            'is_superuser': u.is_superuser,
            'has_password': u.has_usable_password(),
            'social_providers': social_providers,
            'sites_count': u.sites.count(),
            'plan': sub.plan if sub else 'free',
            'subscription_status': sub.status if sub else 'active',
            'cancel_at_period_end': bool(sub.cancel_at_period_end) if sub else False,
            'current_period_end': sub.current_period_end.isoformat() if sub and sub.current_period_end else None,
            'credit_balance': bal.balance if bal else 0,
            'date_joined': u.date_joined.isoformat(),
            'last_login': u.last_login.isoformat() if u.last_login else None,
        })


def _serialize_hosted_post(post, detail=True):
    """Serialize a HostedPost to match the BlogPost API shape."""
    base = {
        'id': post.id,
        'title': post.title,
        'slug': post.slug,
        'excerpt': post.excerpt,
        'author': post.author,
        'category': post.category.name if post.category else None,
        'category_slug': post.category.slug if post.category else None,
        'tags': list(post.tags.values_list('name', flat=True)),
        'cover_image': post.cover_image,
        'reading_time': post.reading_time,
        'featured': post.featured,
        'status': post.status,
        'view_count': post.view_count,
        'language': post.language,
        'translation_group': str(post.translation_group),
        'scheduled_at': post.scheduled_at.isoformat() if post.scheduled_at else None,
        'published_at': post.published_at.isoformat() if post.published_at else None,
        'created_at': post.created_at.isoformat(),
        'updated_at': post.updated_at.isoformat(),
    }
    if detail:
        base['content'] = post.content
        base['memory_chunks_used'] = post.memory_chunks_used or []
        base['feedback_rating'] = post.feedback_rating
        # FAQPage JSON-LD computed on save() from the markdown "## FAQ" block.
        # The frontend (BlogPost.tsx) injects it in <head> when non-empty.
        base['schema_jsonld'] = post.schema_jsonld or {}
        # Hreflang alternates: any sibling HostedPost sharing the same
        # translation_group (other languages), including the current one. The
        # frontend injects `<link rel="alternate" hreflang="X" href="Y">` in
        # <head> so Google can cluster the multi-lingual versions. We return
        # only `lang` + `url` here because the frontend reuses the same
        # `/blog/<slug>` route prefix; full origins are resolved client-side
        # via window.location.origin.
        siblings = HostedPost.objects.filter(
            site_id=post.site_id,
            translation_group=post.translation_group,
            status='published',
        ).values('language', 'slug')
        base['hreflang_alternates'] = [
            {'lang': s['language'], 'url': f"/blog/{s['slug']}"}
            for s in siblings
        ]
    return base


class SitePostsView(APIView):
    """List/Create posts for a specific site."""
    permission_classes = [IsAuthenticated]

    def get(self, request, site_id):
        site = get_site_for_user(request, site_id)

        search = request.query_params.get('search', '')
        status_filter = request.query_params.get('status', '')
        page = int(request.query_params.get('page', 1))
        page_size = 20

        # WordPress mode: delegate to the REST adapter.
        if site.is_wordpress:
            from .wordpress_adapter import WordPressClient, WordPressError
            try:
                client = WordPressClient(site)
                return Response(client.list_posts(
                    status=status_filter or None, search=search,
                    page=page, per_page=page_size,
                ))
            except WordPressError as e:
                return Response({'error': str(e)}, status=status.HTTP_502_BAD_GATEWAY)

        # Shopify mode: delegate to the Admin API adapter.
        if site.is_shopify:
            from .shopify_adapter import ShopifyClient, ShopifyError
            try:
                client = ShopifyClient(site)
                return Response(client.list_posts(
                    status=status_filter or None, search=search,
                    page=page, per_page=page_size,
                ))
            except ShopifyError as e:
                return Response({'error': str(e)}, status=status.HTTP_502_BAD_GATEWAY)

        # Webflow mode: delegate to the CMS API adapter.
        if site.is_webflow:
            from .webflow_adapter import WebflowClient, WebflowError
            try:
                client = WebflowClient(site)
                return Response(client.list_posts(
                    status=status_filter or None, search=search,
                    page=page, per_page=page_size,
                ))
            except WebflowError as e:
                return Response({'error': str(e)}, status=status.HTTP_502_BAD_GATEWAY)

        if site.is_hosted:
            posts = HostedPost.objects.filter(site=site).select_related('category').prefetch_related('tags').order_by('-created_at')
            if search:
                posts = posts.filter(title__icontains=search)
            if status_filter:
                posts = posts.filter(status=status_filter)
            total = posts.count()
            start = (page - 1) * page_size
            end = start + page_size
            results = [_serialize_hosted_post(p, detail=False) for p in posts[start:end]]
            return Response({
                'count': total,
                'results': results,
                'next': page + 1 if end < total else None,
                'previous': page - 1 if page > 1 else None,
            })

        alias = ensure_site_connection(site)
        posts = (
            BlogPost.objects.using(alias)
            .select_related('category')
            .prefetch_related('tags')
            .all()
            .order_by('-created_at')
        )
        if search:
            posts = posts.filter(title__icontains=search)
        if status_filter:
            posts = posts.filter(status=status_filter)
        total = posts.count()
        start = (page - 1) * page_size
        end = start + page_size

        serializer = BlogPostListSerializer(posts[start:end], many=True)
        return Response({
            'count': total,
            'results': serializer.data,
            'next': page + 1 if end < total else None,
            'previous': page - 1 if page > 1 else None,
        })

    def post(self, request, site_id):
        site = get_site_for_user(request, site_id)

        # WordPress mode: bypass the BlogPost serializer (which validates
        # against the canonical schema) and forward to the REST adapter.
        if site.is_wordpress:
            from .wordpress_adapter import WordPressClient, WordPressError
            data_in = request.data
            try:
                client = WordPressClient(site)
                created = client.create_post(
                    title=data_in.get('title', ''),
                    content=data_in.get('content', ''),
                    excerpt=data_in.get('excerpt', '') or '',
                    slug=data_in.get('slug', '') or slugify(data_in.get('title', '') or 'article'),
                    status=data_in.get('status', 'draft'),
                )
                return Response(created, status=status.HTTP_201_CREATED)
            except WordPressError as e:
                return Response({'error': str(e)}, status=status.HTTP_502_BAD_GATEWAY)

        # Shopify mode: forward to the Admin API adapter.
        if site.is_shopify:
            from .shopify_adapter import ShopifyClient, ShopifyError
            data_in = request.data
            try:
                client = ShopifyClient(site)
                created = client.create_post(
                    title=data_in.get('title', ''),
                    content=data_in.get('content', ''),
                    excerpt=data_in.get('excerpt', '') or '',
                    slug=data_in.get('slug', '') or slugify(data_in.get('title', '') or 'article'),
                    status=data_in.get('status', 'draft'),
                    author=site.author_for_articles,
                    tags=data_in.get('tags_input') or data_in.get('tags') or [],
                    featured_image_url=data_in.get('cover_image', '') or '',
                )
                return Response(created, status=status.HTTP_201_CREATED)
            except ShopifyError as e:
                return Response({'error': str(e)}, status=status.HTTP_502_BAD_GATEWAY)

        # Webflow mode: forward to the CMS API adapter.
        if site.is_webflow:
            from .webflow_adapter import WebflowClient, WebflowError
            data_in = request.data
            try:
                client = WebflowClient(site)
                created = client.create_post(
                    title=data_in.get('title', ''),
                    content=data_in.get('content', ''),
                    excerpt=data_in.get('excerpt', '') or '',
                    slug=data_in.get('slug', '') or slugify(data_in.get('title', '') or 'article'),
                    status=data_in.get('status', 'draft'),
                    featured_image_url=data_in.get('cover_image', '') or '',
                )
                return Response(created, status=status.HTTP_201_CREATED)
            except WebflowError as e:
                return Response({'error': str(e)}, status=status.HTTP_502_BAD_GATEWAY)

        serializer = BlogPostWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        cat_name = data.pop('category', '')
        tags_input = data.pop('tags_input', [])

        if not data.get('slug'):
            data['slug'] = slugify(data['title'])
        if not data.get('published_at'):
            data['published_at'] = date.today()

        if site.is_hosted:
            category = None
            if cat_name:
                category, _ = HostedCategory.objects.get_or_create(
                    site=site, name=cat_name,
                    defaults={'slug': slugify(cat_name)}
                )
            post = HostedPost.objects.create(site=site, category=category, **data)
            for tag_name in tags_input:
                tag, _ = HostedTag.objects.get_or_create(site=site, name=tag_name.strip())
                post.tags.add(tag)
            trigger_vercel_deploy(site)
            return Response(_serialize_hosted_post(post), status=status.HTTP_201_CREATED)

        alias = ensure_site_connection(site)
        category = None
        if cat_name:
            category, _ = Category.objects.using(alias).get_or_create(
                name=cat_name,
                defaults={'slug': slugify(cat_name)}
            )

        content_format = (site.blog_config or {}).get('content_format', 'markdown')
        if content_format == 'html' and data.get('content'):
            data['content'] = _markdown_to_html(data['content'])

        post = BlogPost(category=category, **data)
        post.save(using=alias)

        for tag_name in tags_input:
            tag, _ = Tag.objects.using(alias).get_or_create(name=tag_name.strip())
            post.tags.add(tag)

        result = BlogPostDetailSerializer(
            BlogPost.objects.using(alias).prefetch_related('tags').get(pk=post.pk)
        ).data
        trigger_vercel_deploy(site)
        return Response(result, status=status.HTTP_201_CREATED)


class SitePostDetailView(APIView):
    """Get/Update/Delete a single post for a site."""
    permission_classes = [IsAuthenticated]

    def get(self, request, site_id, slug):
        site = get_site_for_user(request, site_id)
        language = request.query_params.get('language')

        if site.is_wordpress:
            from .wordpress_adapter import WordPressClient, WordPressError
            try:
                client = WordPressClient(site)
                post = client.get_post(slug)
            except WordPressError as e:
                return Response({'error': str(e)}, status=status.HTTP_502_BAD_GATEWAY)
            if not post:
                from django.http import Http404
                raise Http404
            return Response(post)

        if site.is_shopify:
            from .shopify_adapter import ShopifyClient, ShopifyError
            try:
                client = ShopifyClient(site)
                post = client.get_post(slug)
            except ShopifyError as e:
                return Response({'error': str(e)}, status=status.HTTP_502_BAD_GATEWAY)
            if not post:
                from django.http import Http404
                raise Http404
            return Response(post)

        if site.is_webflow:
            from .webflow_adapter import WebflowClient, WebflowError
            try:
                client = WebflowClient(site)
                post = client.get_post(slug)
            except WebflowError as e:
                return Response({'error': str(e)}, status=status.HTTP_502_BAD_GATEWAY)
            if not post:
                from django.http import Http404
                raise Http404
            return Response(post)

        if site.is_hosted:
            qs = HostedPost.objects.filter(site=site, slug=slug) \
                .select_related('category').prefetch_related('tags')
            if language:
                qs = qs.filter(language=language)
            post = qs.first()
            if not post:
                from django.http import Http404
                raise Http404
            return Response(_serialize_hosted_post(post))

        alias = ensure_site_connection(site)
        qs = BlogPost.objects.using(alias).filter(slug=slug) \
            .select_related('category').prefetch_related('tags')
        if language:
            qs = qs.filter(language=language)
        post = qs.first()
        if not post:
            from django.http import Http404
            raise Http404
        serializer = BlogPostDetailSerializer(post)
        return Response(serializer.data)

    def patch(self, request, site_id, slug):
        site = get_site_for_user(request, site_id)
        data = request.data
        language = request.query_params.get('language')

        if site.is_wordpress:
            from .wordpress_adapter import WordPressClient, WordPressError
            try:
                client = WordPressClient(site)
                # Look up the post first (we need its WP id to PATCH).
                existing = client.get_post(slug)
                if not existing:
                    from django.http import Http404
                    raise Http404
                updated = client.update_post(
                    existing['wp_id'],
                    title=data.get('title', existing['title']),
                    content=data.get('content', existing['content']),
                    excerpt=data.get('excerpt', existing['excerpt']),
                    slug=data.get('slug', existing['slug']) or existing['slug'],
                    status=data.get('status', existing['status']),
                )
                # Track redirect if slug changed
                old_slug = existing['slug']
                new_slug = updated['slug']
                if new_slug and old_slug != new_slug:
                    Redirect.objects.update_or_create(
                        site=site, from_slug=old_slug, language=existing.get('language', 'fr'),
                        defaults={'to_slug': new_slug, 'is_active': True},
                    )
                return Response(updated)
            except WordPressError as e:
                return Response({'error': str(e)}, status=status.HTTP_502_BAD_GATEWAY)

        if site.is_shopify:
            from .shopify_adapter import ShopifyClient, ShopifyError
            try:
                client = ShopifyClient(site)
                existing = client.get_post(slug)
                if not existing:
                    from django.http import Http404
                    raise Http404
                updated = client.update_post(
                    existing['shopify_id'],
                    title=data.get('title', existing['title']),
                    content=data.get('content', existing['content']),
                    excerpt=data.get('excerpt', existing['excerpt']),
                    slug=data.get('slug', existing['slug']) or existing['slug'],
                    status=data.get('status', existing['status']),
                    tags=data.get('tags_input') or data.get('tags') or existing.get('tags', []),
                    featured_image_url=data.get('cover_image', '') or existing.get('cover_image', '') or '',
                )
                old_slug = existing['slug']
                new_slug = updated['slug']
                if new_slug and old_slug != new_slug:
                    Redirect.objects.update_or_create(
                        site=site, from_slug=old_slug, language=existing.get('language', 'fr'),
                        defaults={'to_slug': new_slug, 'is_active': True},
                    )
                return Response(updated)
            except ShopifyError as e:
                return Response({'error': str(e)}, status=status.HTTP_502_BAD_GATEWAY)

        if site.is_webflow:
            from .webflow_adapter import WebflowClient, WebflowError
            try:
                client = WebflowClient(site)
                existing = client.get_post(slug)
                if not existing:
                    from django.http import Http404
                    raise Http404
                updated = client.update_post(
                    existing['webflow_id'],
                    title=data.get('title', existing['title']),
                    content=data.get('content', existing['content']),
                    excerpt=data.get('excerpt', existing['excerpt']),
                    slug=data.get('slug', existing['slug']) or existing['slug'],
                    status=data.get('status', existing['status']),
                    featured_image_url=data.get('cover_image', '') or existing.get('cover_image', '') or '',
                )
                old_slug = existing['slug']
                new_slug = updated['slug']
                if new_slug and old_slug != new_slug:
                    Redirect.objects.update_or_create(
                        site=site, from_slug=old_slug, language=existing.get('language', 'fr'),
                        defaults={'to_slug': new_slug, 'is_active': True},
                    )
                return Response(updated)
            except WebflowError as e:
                return Response({'error': str(e)}, status=status.HTTP_502_BAD_GATEWAY)

        if site.is_hosted:
            hosted_qs = HostedPost.objects.filter(site=site, slug=slug)
            if language:
                hosted_qs = hosted_qs.filter(language=language)
            post = hosted_qs.first()
            if not post:
                from django.http import Http404
                raise Http404
            old_slug = post.slug
            old_lang = post.language
            for field in ['title', 'slug', 'excerpt', 'content', 'author',
                          'cover_image', 'reading_time', 'featured', 'status',
                          'scheduled_at', 'published_at', 'language', 'translation_group']:
                if field in data:
                    setattr(post, field, data[field])
            # Auto-create a 301 Redirect when the slug changes (hosted)
            if 'slug' in data and data['slug'] and data['slug'] != old_slug:
                Redirect.objects.update_or_create(
                    site=site, from_slug=old_slug, language=old_lang,
                    defaults={'to_slug': data['slug'], 'is_active': True},
                )
            if 'category' in data:
                cat_name = data['category']
                if cat_name:
                    category, _ = HostedCategory.objects.get_or_create(
                        site=site, name=cat_name,
                        defaults={'slug': slugify(cat_name)}
                    )
                    post.category = category
                else:
                    post.category = None
            post.save()
            if 'tags_input' in data:
                post.tags.clear()
                for tag_name in data['tags_input']:
                    tag, _ = HostedTag.objects.get_or_create(site=site, name=tag_name.strip())
                    post.tags.add(tag)
            trigger_vercel_deploy(site)
            return Response(_serialize_hosted_post(post))

        alias = ensure_site_connection(site)
        ext_qs = BlogPost.objects.using(alias).filter(slug=slug)
        if language:
            ext_qs = ext_qs.filter(language=language)
        post = ext_qs.first()
        if not post:
            from django.http import Http404
            raise Http404

        content_format = (site.blog_config or {}).get('content_format', 'markdown')
        if content_format == 'html' and 'content' in data:
            data = dict(data)
            data['content'] = _markdown_to_html(data['content'])

        old_slug_ext = post.slug
        old_lang_ext = getattr(post, 'language', 'fr') or 'fr'
        for field in ['title', 'slug', 'excerpt', 'content', 'author',
                      'cover_image', 'reading_time', 'featured', 'status',
                      'scheduled_at', 'published_at', 'language', 'translation_group']:
            if field in data:
                setattr(post, field, data[field])
        # Auto-create a 301 Redirect when the slug changes (external mode)
        # The Redirect itself lives in the dashboard DB, indexed by site.
        if 'slug' in data and data['slug'] and data['slug'] != old_slug_ext:
            Redirect.objects.update_or_create(
                site=site, from_slug=old_slug_ext, language=old_lang_ext,
                defaults={'to_slug': data['slug'], 'is_active': True},
            )

        if 'category' in data:
            cat_name = data['category']
            if cat_name:
                category, _ = Category.objects.using(alias).get_or_create(
                    name=cat_name,
                    defaults={'slug': slugify(cat_name)}
                )
                post.category = category
            else:
                post.category = None

        post.save(using=alias)

        if 'tags_input' in data:
            post.tags.clear()
            for tag_name in data['tags_input']:
                tag, _ = Tag.objects.using(alias).get_or_create(name=tag_name.strip())
                post.tags.add(tag)

        result = BlogPostDetailSerializer(
            BlogPost.objects.using(alias).prefetch_related('tags').get(pk=post.pk)
        ).data
        trigger_vercel_deploy(site)
        return Response(result)

    def delete(self, request, site_id, slug):
        site = get_site_for_user(request, site_id)
        language = request.query_params.get('language')
        from django.http import Http404

        if site.is_wordpress:
            from .wordpress_adapter import WordPressClient, WordPressError
            try:
                client = WordPressClient(site)
                existing = client.get_post(slug)
                if not existing:
                    raise Http404
                ok = client.delete_post(existing['wp_id'], force=False)
                if not ok:
                    return Response({'error': 'WP delete failed'}, status=status.HTTP_502_BAD_GATEWAY)
                return Response(status=status.HTTP_204_NO_CONTENT)
            except WordPressError as e:
                return Response({'error': str(e)}, status=status.HTTP_502_BAD_GATEWAY)

        if site.is_shopify:
            from .shopify_adapter import ShopifyClient, ShopifyError
            try:
                client = ShopifyClient(site)
                existing = client.get_post(slug)
                if not existing:
                    raise Http404
                ok = client.delete_post(existing['shopify_id'])
                if not ok:
                    return Response({'error': 'Shopify delete failed'}, status=status.HTTP_502_BAD_GATEWAY)
                return Response(status=status.HTTP_204_NO_CONTENT)
            except ShopifyError as e:
                return Response({'error': str(e)}, status=status.HTTP_502_BAD_GATEWAY)

        if site.is_webflow:
            from .webflow_adapter import WebflowClient, WebflowError
            try:
                client = WebflowClient(site)
                existing = client.get_post(slug)
                if not existing:
                    raise Http404
                ok = client.delete_post(existing['webflow_id'])
                if not ok:
                    return Response({'error': 'Webflow delete failed'}, status=status.HTTP_502_BAD_GATEWAY)
                return Response(status=status.HTTP_204_NO_CONTENT)
            except WebflowError as e:
                return Response({'error': str(e)}, status=status.HTTP_502_BAD_GATEWAY)

        if site.is_hosted:
            qs = HostedPost.objects.filter(site=site, slug=slug)
            if language:
                qs = qs.filter(language=language)
            post = qs.first()
            if not post:
                raise Http404
            post.delete()
            trigger_vercel_deploy(site)
            return Response(status=status.HTTP_204_NO_CONTENT)

        alias = ensure_site_connection(site)
        qs = BlogPost.objects.using(alias).filter(slug=slug)
        if language:
            qs = qs.filter(language=language)
        post = qs.first()
        if not post:
            raise Http404
        post.delete(using=alias)
        trigger_vercel_deploy(site)
        return Response(status=status.HTTP_204_NO_CONTENT)


class SiteCannibalizationView(APIView):
    """Detect cannibalization risks between published articles of a site.

    Two articles compete for the same ranking when their titles or slugs are
    highly similar AND they share the same language. We compute a similarity
    based on title-token Jaccard + slug SequenceMatcher ratio.
    """
    permission_classes = [IsAuthenticated]

    # Minimal FR+EN stopword list (kept inline to avoid external deps)
    _STOPWORDS = {
        # French
        'les', 'des', 'une', 'aux', 'dans', 'pour', 'par', 'sur', 'avec', 'sans',
        'est', 'sont', 'son', 'ses', 'leur', 'leurs', 'que', 'qui', 'quoi', 'dont',
        'mais', 'donc', 'car', 'ainsi', 'aussi', 'plus', 'moins', 'tres', 'etre',
        'avoir', 'faire', 'cela', 'cette', 'cet', 'ces', 'votre', 'notre', 'comme',
        'tout', 'tous', 'toute', 'toutes', 'entre', 'chez', 'vers', 'depuis',
        # English
        'the', 'and', 'for', 'that', 'this', 'with', 'from', 'your', 'our', 'you',
        'are', 'was', 'were', 'has', 'have', 'had', 'but', 'not', 'they', 'their',
        'them', 'what', 'which', 'when', 'where', 'why', 'how', 'who', 'into',
        'about', 'over', 'under', 'than', 'then', 'there', 'here', 'some', 'any',
        'all', 'will', 'would', 'should', 'could', 'been', 'being',
    }

    def _title_tokens(self, title):
        import re
        words = re.findall(r"[\w]+", (title or '').lower(), flags=re.UNICODE)
        return {w for w in words if len(w) >= 3 and w not in self._STOPWORDS}

    def _jaccard(self, a, b):
        if not a or not b:
            return 0.0
        inter = len(a & b)
        union = len(a | b)
        return inter / union if union else 0.0

    def _compute_pairs(self, posts):
        import difflib
        # posts: list of dicts with title, slug, excerpt, language
        enriched = []
        for p in posts:
            enriched.append({
                **p,
                '_tokens': self._title_tokens(p.get('title') or ''),
            })

        pairs = []
        n = len(enriched)
        for i in range(n):
            a = enriched[i]
            for j in range(i + 1, n):
                b = enriched[j]
                if (a.get('language') or '') != (b.get('language') or ''):
                    continue
                if a['slug'] == b['slug']:
                    continue
                tok_sim = self._jaccard(a['_tokens'], b['_tokens'])
                slug_sim = difflib.SequenceMatcher(
                    None, a['slug'] or '', b['slug'] or ''
                ).ratio()
                sim = max(tok_sim, slug_sim)
                if sim < 0.55:
                    continue
                if tok_sim >= slug_sim:
                    reason = f"Titres similaires ({int(tok_sim * 100)}% de mots communs)"
                else:
                    reason = f"Slugs similaires ({int(slug_sim * 100)}%)"
                pairs.append({
                    'slug_a': a['slug'],
                    'slug_b': b['slug'],
                    'title_a': a.get('title') or '',
                    'title_b': b.get('title') or '',
                    'language': a.get('language') or '',
                    'similarity': round(sim, 3),
                    'reason': reason,
                })

        pairs.sort(key=lambda p: p['similarity'], reverse=True)
        return pairs[:30]

    def get(self, request, site_id):
        site = get_site_for_user(request, site_id)

        if site.is_hosted:
            qs = HostedPost.objects.filter(site=site, status='published') \
                .values('title', 'slug', 'excerpt', 'language')
            posts = list(qs)
        else:
            try:
                alias = ensure_site_connection(site)
            except ValueError:
                return Response(
                    {'error': "Cette action nécessite une base de données externe configurée pour ce site."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            qs = BlogPost.objects.using(alias).filter(status='published') \
                .values('title', 'slug', 'excerpt', 'language')
            posts = list(qs)

        pairs = self._compute_pairs(posts)
        return Response({'pairs': pairs})


class SiteStatsView(APIView):
    """Dashboard stats for a site."""
    permission_classes = [IsAuthenticated]

    def get(self, request, site_id):
        site = get_site_for_user(request, site_id)

        # CMS-mode sites (WordPress, Shopify, Webflow) store posts in the
        # external CMS, not in our DB. Hitting BlogPost.objects.using(...)
        # would crash with 'relation blog_blogpost does not exist' on
        # Railway's primary DB. We fetch live counts from the CMS adapter
        # instead. Counts only - fetching all post titles for 'recent_posts'
        # would be too slow on every dashboard load.
        if site.is_wordpress or site.is_shopify or site.is_webflow:
            return Response(self._cms_stats(site))

        if site.is_hosted:
            posts = HostedPost.objects.filter(site=site)
            total_posts = posts.count()
            total_views = posts.aggregate(total=Sum('view_count'))['total'] or 0
            drafts = posts.filter(status='draft').count()
            scheduled = posts.filter(status='scheduled').count()
            published = posts.filter(status='published').count()
            categories_data = [
                {'name': cat.name, 'count': cat.posts.count()}
                for cat in HostedCategory.objects.filter(site=site)
            ]
            recent_posts = list(
                posts.values('slug', 'title', 'status', 'view_count', 'created_at')
                .order_by('-created_at')[:5]
            )
            return Response({
                'total_posts': total_posts,
                'total_views': total_views,
                'drafts': drafts,
                'scheduled': scheduled,
                'published': published,
                'categories': categories_data,
                'recent_posts': recent_posts,
            })

        # External-mode site (site.database_url set, blog_* tables in their
        # own Postgres). If database_url is empty (no mode set at all), bail
        # with zero stats so the dashboard renders instead of crashing.
        if not site.database_url:
            return Response({
                'total_posts': 0,
                'total_views': 0,
                'drafts': 0,
                'scheduled': 0,
                'published': 0,
                'categories': [],
                'recent_posts': [],
                'storage': 'unconfigured',
            })

        alias = ensure_site_connection(site)
        # If the external DB has database_url set but the blog_* tables were
        # never created (user forgot to run init_db), the count() raises
        # ProgrammingError 'relation does not exist'. Catch it and degrade
        # to zero stats with a flag so the frontend can prompt 'Init tables'.
        try:
            posts = BlogPost.objects.using(alias)
            total_posts = posts.count()
            total_views = posts.aggregate(total=Sum('view_count'))['total'] or 0
            drafts = posts.filter(status='draft').count()
            scheduled = posts.filter(status='scheduled').count()
            published = posts.filter(status='published').count()

            categories_data = []
            for cat in Category.objects.using(alias).all():
                categories_data.append({
                    'name': cat.name,
                    'count': cat.posts.using(alias).count(),
                })

            recent_posts = list(
                posts.values('slug', 'title', 'status', 'view_count', 'created_at')
                .order_by('-created_at')[:5]
            )

            return Response({
                'total_posts': total_posts,
                'total_views': total_views,
                'drafts': drafts,
                'scheduled': scheduled,
                'published': published,
                'categories': categories_data,
                'recent_posts': recent_posts,
            })
        except ProgrammingError:
            logger.warning(
                "Site %s: external DB connected but blog_* tables missing. "
                "User needs to POST /api/sites/%s/init_db/ to migrate.",
                site.id, site.id,
            )
            return Response({
                'total_posts': 0,
                'total_views': 0,
                'drafts': 0,
                'scheduled': 0,
                'published': 0,
                'categories': [],
                'recent_posts': [],
                'storage': 'external_uninitialized',
            })

    def _cms_stats(self, site):
        """Fetch counts from the live CMS adapter. Wrapped in try/except so a
        CMS API outage degrades to empty stats rather than 500 on the dashboard."""
        empty = {
            'total_posts': 0,
            'total_views': 0,
            'drafts': 0,
            'scheduled': 0,
            'published': 0,
            'categories': [],
            'recent_posts': [],
        }
        try:
            if site.is_wordpress:
                from .wordpress_adapter import WordPressClient
                client = WordPressClient(site)
                storage = 'wordpress'
            elif site.is_shopify:
                from .shopify_adapter import ShopifyClient
                client = ShopifyClient(site)
                storage = 'shopify'
            elif site.is_webflow:
                from .webflow_adapter import WebflowClient
                client = WebflowClient(site)
                storage = 'webflow'
            else:
                return {**empty, 'storage': 'unknown'}

            published_page = client.list_posts(status='published', per_page=5)
            draft_page = client.list_posts(status='draft', per_page=1)
            published_total = published_page.get('total', len(published_page.get('items', [])))
            drafts_total = draft_page.get('total', len(draft_page.get('items', [])))
            recent = [
                {
                    'slug': item.get('slug', ''),
                    'title': item.get('title', ''),
                    'status': 'published',
                    'view_count': 0,
                    'created_at': item.get('created_at') or item.get('published_at'),
                }
                for item in published_page.get('items', [])[:5]
            ]
            return {
                **empty,
                'total_posts': published_total + drafts_total,
                'published': published_total,
                'drafts': drafts_total,
                'recent_posts': recent,
                'storage': storage,
            }
        except Exception:
            logger.exception("Failed to fetch CMS stats for site %s", site.id)
            return {**empty, 'storage': 'cms_error'}


class SiteCategoriesView(APIView):
    """List categories for a site."""
    permission_classes = [IsAuthenticated]

    def get(self, request, site_id):
        site = get_site_for_user(request, site_id)
        if site.is_wordpress:
            from .wordpress_adapter import WordPressClient, WordPressError
            try:
                return Response(WordPressClient(site).list_categories())
            except WordPressError as e:
                return Response({'error': str(e)}, status=status.HTTP_502_BAD_GATEWAY)
        if site.is_shopify:
            # Shopify articles don't have categories.
            return Response([])
        if site.is_webflow:
            # Webflow collections vary; we don't expose categories.
            return Response([])
        if site.is_hosted:
            categories = HostedCategory.objects.filter(site=site)
            return Response([
                {'id': c.id, 'name': c.name, 'slug': c.slug, 'description': c.description, 'posts_count': c.posts.count()}
                for c in categories
            ])
        alias = ensure_site_connection(site)
        categories = Category.objects.using(alias).all()
        serializer = CategorySerializer(categories, many=True)
        return Response(serializer.data)


class SiteTagsView(APIView):
    """List tags for a site."""
    permission_classes = [IsAuthenticated]

    def get(self, request, site_id):
        site = get_site_for_user(request, site_id)
        if site.is_wordpress:
            from .wordpress_adapter import WordPressClient, WordPressError
            try:
                return Response(WordPressClient(site).list_tags())
            except WordPressError as e:
                return Response({'error': str(e)}, status=status.HTTP_502_BAD_GATEWAY)
        if site.is_shopify:
            from .shopify_adapter import ShopifyClient, ShopifyError
            try:
                return Response(ShopifyClient(site).list_tags())
            except ShopifyError as e:
                return Response({'error': str(e)}, status=status.HTTP_502_BAD_GATEWAY)
        if site.is_webflow:
            return Response([])
        if site.is_hosted:
            tags = HostedTag.objects.filter(site=site)
            return Response([{'id': t.id, 'name': t.name} for t in tags])
        alias = ensure_site_connection(site)
        tags = Tag.objects.using(alias).all()
        serializer = TagSerializer(tags, many=True)
        return Response(serializer.data)


class PexelsSearchView(APIView):
    """Proxy search on Pexels for cover images."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        query = request.query_params.get('query', '')
        page = int(request.query_params.get('page', 1))
        per_page = min(int(request.query_params.get('per_page', 15)), 30)

        if not query:
            return Response(
                {'error': 'Le parametre "query" est requis'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        api_key = os.environ.get('PEXELS_API_KEY')
        if not api_key:
            return Response(
                {'error': 'PEXELS_API_KEY non configuree'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        try:
            resp = http_requests.get(
                'https://api.pexels.com/v1/search',
                headers={'Authorization': api_key},
                params={
                    'query': query,
                    'page': page,
                    'per_page': per_page,
                    'locale': 'fr-FR',
                },
                timeout=10,
            )

            if resp.status_code == 429:
                return Response(
                    {'error': 'Limite de requetes Pexels atteinte, reessayez plus tard'},
                    status=status.HTTP_429_TOO_MANY_REQUESTS,
                )

            if resp.status_code != 200:
                return Response(
                    {'error': f'Erreur Pexels: {resp.status_code}'},
                    status=status.HTTP_502_BAD_GATEWAY,
                )

            data = resp.json()
            photos = [
                {
                    'id': p['id'],
                    'url': p['src']['large2x'],
                    'thumb': p['src']['medium'],
                    'alt': p.get('alt', ''),
                    'photographer': p['photographer'],
                }
                for p in data.get('photos', [])
            ]
            return Response({
                'photos': photos,
                'total_results': data.get('total_results', 0),
                'page': page,
                'per_page': per_page,
            })

        except http_requests.Timeout:
            return Response(
                {'error': 'Delai de requete Pexels depasse'},
                status=status.HTTP_504_GATEWAY_TIMEOUT,
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class GenerateArticleView(APIView):
    """Generate a blog article using AI for a specific site."""
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    throttle_scope = 'ai_generate'

    def post(self, request, site_id):
        site = get_site_for_user(request, site_id)
        from .delivery import block_reason
        _blk = block_reason(site)
        if _blk:
            return Response({'error': _blk, 'code': 'delivery_blocked'},
                            status=status.HTTP_409_CONFLICT)
        # Hosted mode + CMS modes (WordPress, Shopify, Webflow) don't open an
        # external Postgres connection - their content lives in our DB (hosted)
        # or in the remote CMS API.
        if site.is_hosted or site.is_wordpress or site.is_shopify or site.is_webflow:
            alias = None
        else:
            alias = ensure_site_connection(site)

        # Extract parameters from request
        search_method = request.data.get('search', 'serper')
        topic = request.data.get('topic', None) or None
        title = request.data.get('title', None) or None
        article_type = request.data.get('type', 'news')
        length = request.data.get('length', 'medium')
        keywords = request.data.get('keywords', None) or None
        dry_run = request.data.get('dry_run', False)
        language = request.data.get('language', 'fr')
        # Optional Content Brief from /content-brief/ - passed through to the
        # generator which injects it into the Claude prompt.
        brief = request.data.get('brief')
        if not isinstance(brief, dict):
            brief = None
        if language not in ('fr', 'en', 'es'):
            language = 'fr'
        # Enforce per-site allowed languages
        if not site.supports_language(language):
            return Response(
                {'error': f'La langue "{language}" n\'est pas autorisee pour ce site. Langues disponibles: {", ".join(site.effective_languages)}'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate inputs
        if search_method not in ('serper', 'gemini'):
            return Response(
                {'error': 'Methode de recherche invalide (serper ou gemini)'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if article_type not in ('news', 'tutorial', 'comparison', 'guide', 'review', 'story', 'local'):
            return Response(
                {'error': 'Type d\'article invalide'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if length not in ('short', 'medium', 'long'):
            return Response(
                {'error': 'Longueur invalide (short, medium, long)'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Enforce article quota (monthly first, then top-up credits).
        # Skip on dry_run since nothing is saved.
        from .quota import check_article_quota, consume_article
        if not dry_run:
            try:
                check_article_quota(request.user)
            except DRFPermissionDenied as e:
                return Response(
                    {'error': str(e), 'quota_exceeded': True},
                    status=status.HTTP_402_PAYMENT_REQUIRED,
                )

        try:
            from .article_generator import ArticleGenerator

            generator = ArticleGenerator(
                alias,
                knowledge_base=site.knowledge_base or '',
                wp_site=site if site.is_wordpress else None,
                shopify_site=site if site.is_shopify else None,
                webflow_site=site if site.is_webflow else None,
                site=site,
            )
            result = generator.generate(
                search_method=search_method,
                topic=topic,
                title=title,
                article_type=article_type,
                length=length,
                keywords=keywords,
                dry_run=dry_run,
                language=language,
                brief=brief,
            )

            # Count this generation: consumes monthly quota first, then a credit.
            if not dry_run:
                consume_article(request.user)

            trigger_vercel_deploy(site)
            return Response({
                'output': result['output'],
                'post_count': result['post_count'],
            })

        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.exception("Article generation failed for site %s", site_id)
            return Response(
                {'error': f'Erreur generation: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class GenerateInlineView(APIView):
    """Generate article content and return it without saving - fills the editor."""
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    throttle_scope = 'ai_generate'

    def post(self, request, site_id):
        site = get_site_for_user(request, site_id)
        from .delivery import block_reason
        _blk = block_reason(site)
        if _blk:
            return Response({'error': _blk, 'code': 'delivery_blocked'},
                            status=status.HTTP_409_CONFLICT)
        # Hosted mode + CMS modes don't open an external Postgres connection.
        if site.is_hosted or site.is_wordpress or site.is_shopify or site.is_webflow:
            alias = None
        else:
            alias = ensure_site_connection(site)

        topic = request.data.get('topic') or None
        title = request.data.get('title') or None
        article_type = request.data.get('type', 'news')
        length = request.data.get('length', 'medium')
        keywords = request.data.get('keywords') or None
        context_urls = request.data.get('context_urls') or []
        brief = request.data.get('brief')
        if not isinstance(brief, dict):
            brief = None
        language = request.data.get('language', 'fr')
        if language not in ('fr', 'en', 'es'):
            language = 'fr'
        # Enforce per-site allowed languages
        if not site.supports_language(language):
            return Response(
                {'error': f'La langue "{language}" n\'est pas autorisee pour ce site. Langues disponibles: {", ".join(site.effective_languages)}'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Fetch context from URLs
        url_context = ''
        for url in context_urls[:5]:
            try:
                resp = http_requests.get(url, timeout=10, headers={
                    'User-Agent': 'Mozilla/5.0 BlogDashboard/1.0'
                })
                if resp.ok:
                    # Extract text content (strip HTML tags)
                    import re
                    text = re.sub(r'<[^>]+>', ' ', resp.text)
                    text = re.sub(r'\s+', ' ', text).strip()
                    url_context += f'\n\n--- Source: {url} ---\n{text[:3000]}'
            except Exception:
                pass

        try:
            from .article_generator import ArticleGenerator

            generator = ArticleGenerator(
                alias,
                knowledge_base=(site.knowledge_base or '') + url_context,
                wp_site=site if site.is_wordpress else None,
                shopify_site=site if site.is_shopify else None,
                webflow_site=site if site.is_webflow else None,
                site=site,
            )
            # Use dry_run to prevent saving
            result = generator.generate(
                search_method='serper',
                topic=topic,
                title=title,
                article_type=article_type,
                length=length,
                keywords=keywords,
                dry_run=True,
                language=language,
                brief=brief,
            )

            # Extract the generated data from the generator's internal state
            topic_analysis = getattr(generator, '_last_topic_analysis', {})

            # Re-generate to get the full content
            # The generator in dry_run mode still processes everything
            # We need to extract the article fields from the logs
            logs = result['output']

            # Parse from generator attributes
            gen_title = getattr(generator, '_gen_title', title or topic or '')
            gen_slug = slugify(gen_title)
            gen_content = getattr(generator, '_gen_content', '')
            gen_excerpt = getattr(generator, '_gen_excerpt', '')
            gen_tags = getattr(generator, '_gen_tags', [])
            gen_cover = getattr(generator, '_gen_cover', '')
            gen_memory_chunks = getattr(generator, '_gen_memory_chunks', [])

            return Response({
                'title': gen_title,
                'slug': gen_slug,
                'content': gen_content,
                'excerpt': gen_excerpt,
                'tags': gen_tags,
                'cover_image': gen_cover,
                'memory_chunks_used': gen_memory_chunks,
            })

        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.exception("Inline generation failed for site %s", site_id)
            return Response(
                {'error': f'Erreur generation: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class UploadImageView(APIView):
    """Upload an image file, store in DB, return a permanent URL."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        file = request.FILES.get('image')
        if not file:
            return Response(
                {'error': 'Aucun fichier envoye'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        allowed_types = ('image/jpeg', 'image/png', 'image/gif', 'image/webp')
        if file.content_type not in allowed_types:
            return Response(
                {'error': 'Type de fichier non supporte (JPEG, PNG, GIF, WebP uniquement)'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Limit size to 5MB
        if file.size > 5 * 1024 * 1024:
            return Response(
                {'error': 'Fichier trop volumineux (max 5 Mo)'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        img = UploadedImage.objects.create(
            data=file.read(),
            mime_type=file.content_type,
            filename=file.name,
            owner=request.user,
        )

        image_url = request.build_absolute_uri(f'/api/images/{img.uid}/')
        return Response({'url': image_url})


class ServeImageView(APIView):
    """Serve an uploaded image from DB. Public (no auth) for blog display."""
    permission_classes = []  # Public - images are referenced in articles

    def get(self, request, uid):
        img = get_object_or_404(UploadedImage, uid=uid)
        response = HttpResponse(bytes(img.data), content_type=img.mime_type)
        response['Cache-Control'] = 'public, max-age=31536000, immutable'
        return response


def _serialize_uploaded_image(img, request):
    """Shape an UploadedImage for the media gallery (matches the frontend which
    reads secure_url/url/public_id/format)."""
    url = request.build_absolute_uri(f'/api/images/{img.uid}/')
    return {
        'public_id': img.filename or str(img.uid),
        'url': url,
        'secure_url': url,
        'format': (img.mime_type or '').split('/')[-1],
        'created_at': img.created_at.isoformat(),
    }


class SiteImagesView(APIView):
    """List the owner's uploaded images (media library) + upload a new one.

    Images belong to the USER, not a site (UploadedImage has no site FK), so the
    same library shows across the owner's sites; the site_id in the path only
    namespaces the route the dashboard already calls (/sites/<id>/images/).
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, site_id):
        get_site_for_user(request, site_id)  # 404 si le site n'appartient pas au user
        images = UploadedImage.objects.filter(owner=request.user).order_by('-created_at')[:500]
        return Response([_serialize_uploaded_image(img, request) for img in images])


class SiteImageUploadView(APIView):
    """Upload an image to the owner's media library via the site-scoped route
    the dashboard uses (/sites/<id>/images/upload/)."""
    permission_classes = [IsAuthenticated]

    def post(self, request, site_id):
        get_site_for_user(request, site_id)  # 404 si le site n'appartient pas au user
        file = request.FILES.get('image')
        if not file:
            return Response(
                {'error': 'Aucun fichier envoye'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        allowed_types = ('image/jpeg', 'image/png', 'image/gif', 'image/webp')
        if file.content_type not in allowed_types:
            return Response(
                {'error': 'Type de fichier non supporte (JPEG, PNG, GIF, WebP uniquement)'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if file.size > 5 * 1024 * 1024:
            return Response(
                {'error': 'Fichier trop volumineux (max 5 Mo)'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        img = UploadedImage.objects.create(
            data=file.read(),
            mime_type=file.content_type,
            filename=file.name,
            owner=request.user,
        )
        return Response(
            _serialize_uploaded_image(img, request),
            status=status.HTTP_201_CREATED,
        )


class GenerateImageView(APIView):
    """Generate a blog cover image using Imagen 3."""
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    throttle_scope = 'ai_generate'

    def post(self, request):
        prompt = request.data.get('prompt', '')
        if not prompt:
            return Response(
                {'error': 'Le prompt est requis'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        api_key = os.environ.get('GEMINI_API_KEY')
        if not api_key:
            return Response(
                {'error': 'GEMINI_API_KEY non configuree'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        try:
            from google import genai

            client = genai.Client(api_key=api_key)
            full_prompt = (
                f"{prompt}. "
                "High quality blog cover image, professional, modern. "
                "Do not include any text, letters, words, watermarks "
                "or typography on the image."
            )

            # imagen-3.0-generate-002 was deprecated and removed from v1beta in
            # 2026. Imagen 4 family is the current line. imagen-4.0-fast is the
            # cheapest tier ($0.02/img) and quality is fine for blog covers.
            # TODO before 2026-06-24: migrate to Gemini "Nano Banana" image
            # models (gemini-2.5-flash-image via generate_content) - all Imagen
            # models will be shut down on that date.
            response = client.models.generate_images(
                model="imagen-4.0-fast-generate-001",
                prompt=full_prompt,
                config=genai.types.GenerateImagesConfig(
                    number_of_images=1,
                    aspect_ratio="16:9",
                ),
            )

            if response.generated_images:
                image_data = response.generated_images[0].image.image_bytes
                mime = 'image/png'

                # Save to DB for persistent URL
                img = UploadedImage.objects.create(
                    data=image_data,
                    mime_type=mime,
                    filename=f"gen_{uuid.uuid4().hex[:12]}.png",
                    owner=request.user,
                )
                image_url = request.build_absolute_uri(f'/api/images/{img.uid}/')
                image_base64 = base64.b64encode(image_data).decode('utf-8')

                return Response({
                    'image': image_base64,
                    'mime_type': mime,
                    'image_url': image_url,
                })

            return Response(
                {'error': 'Aucune image generee par le modele'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        except Exception as e:
            error_msg = str(e)
            # Log full traceback so Railway logs show what actually broke.
            # Without this, Django's request logger only emits "Internal Server
            # Error: <path>" without context, masking Imagen API errors.
            logger.exception('Imagen generate_images failed: %s', error_msg)
            if 'RESOURCE_EXHAUSTED' in error_msg or 'quota' in error_msg.lower():
                return Response(
                    {'error': 'Quota Gemini epuise. Reessayez plus tard.'},
                    status=status.HTTP_429_TOO_MANY_REQUESTS,
                )
            return Response(
                {'error': f'Erreur generation image: {error_msg}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class SerperImageSearchView(APIView):
    """Search images using Serper (Google Images)."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        query = request.query_params.get('query', '')
        if not query:
            return Response(
                {'error': 'Le parametre "query" est requis'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        api_key = os.environ.get('SERPER_API_KEY')
        if not api_key:
            return Response(
                {'error': 'SERPER_API_KEY non configuree'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        try:
            resp = http_requests.post(
                'https://google.serper.dev/images',
                headers={
                    'X-API-KEY': api_key,
                    'Content-Type': 'application/json',
                },
                json={'q': query, 'num': 20},
                timeout=10,
            )

            if resp.status_code != 200:
                return Response(
                    {'error': f'Erreur Serper: {resp.status_code}'},
                    status=status.HTTP_502_BAD_GATEWAY,
                )

            data = resp.json()
            photos = [
                {
                    'id': i,
                    'url': img['imageUrl'],
                    'thumb': img.get('thumbnailUrl', img['imageUrl']),
                    'alt': img.get('title', ''),
                    'photographer': img.get('source', ''),
                }
                for i, img in enumerate(data.get('images', []))
                if img.get('imageUrl')
            ]
            return Response({
                'photos': photos,
                'total_results': len(photos),
            })

        except http_requests.Timeout:
            return Response(
                {'error': 'Delai de requete Serper depasse'},
                status=status.HTTP_504_GATEWAY_TIMEOUT,
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


SEO_CACHE_TTL = 3600  # 1 hour


def _seo_cache_key(prefix, *parts):
    """Build a deterministic cache key from hashed input parts."""
    raw = ''.join(parts)
    digest = hashlib.sha256(raw.encode('utf-8')).hexdigest()
    return f"{prefix}{digest}"


class GenerateTagsView(APIView):
    """Generate relevant tags for a blog post using Gemini."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        title = request.data.get('title', '')
        content = request.data.get('content', '')
        excerpt = request.data.get('excerpt', '')

        if not title and not content:
            return Response(
                {'error': 'Titre ou contenu requis'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        api_key = os.environ.get('GEMINI_API_KEY')
        if not api_key:
            return Response(
                {'error': 'GEMINI_API_KEY non configuree'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        cache_key = _seo_cache_key('gen-tags:', title, excerpt, content[:5000])
        cached = cache.get(cache_key)
        if cached is not None:
            resp = Response(cached)
            resp['X-Cache'] = 'HIT'
            return resp

        try:
            from google import genai
            import json

            client = genai.Client(api_key=api_key)
            prompt = f"""Analyse cet article de blog et genere 5 a 8 tags pertinents pour le SEO.
Les tags doivent etre courts (1-3 mots), en francais, pertinents pour le sujet.

Titre: {title}
Extrait: {excerpt}
Contenu (debut): {content[:1500]}

Reponds UNIQUEMENT avec un JSON: {{"tags": ["tag1", "tag2", ...]}}"""

            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[prompt],
            )

            text = response.text.strip()
            if text.startswith('```'):
                text = text.split('\n', 1)[1]
                if text.endswith('```'):
                    text = text[:-3]
                text = text.strip()

            data = json.loads(text)
            result = {'tags': data.get('tags', [])}
            cache.set(cache_key, result, timeout=SEO_CACHE_TTL)
            resp = Response(result)
            resp['X-Cache'] = 'MISS'
            return resp

        except Exception as e:
            return Response(
                {'error': f'Erreur generation tags: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


def _sourcing_report(content, language='fr'):
    """Passe deterministe sur le texte : quels chiffres n'ont aucune source.

    Rend None si le module echoue. Cette verification ne doit jamais faire
    tomber l'audit, mais son absence doit se voir plutot que se deviner : un
    None dans la charge utile dit "pas verifie", pas "rien a signaler".
    """
    try:
        from .content_verify import sourcing_gate, verify_text
        rapport = verify_text(content or '', lang=language)
        rapport['gate'] = sourcing_gate(rapport)
        return rapport
    except Exception:  # noqa: BLE001 - jamais casser l'audit sur ce controle
        logger.exception('content_verify a echoue pendant l audit')
        return None


def _sourcing_prompt_section(sourcing, limit):
    """Constats de sourcage a injecter dans le prompt de l'auditeur.

    Le modele lit un chiffre precis comme un signal E-E-A-T et monte la note :
    mesure sur un vrai brouillon, il rendait 93/100 et citait les chiffres
    fabriques comme preuve d'experience vecue. Une regex ne sait pas non plus
    si un chiffre est faux, mais elle sait que personne n'a cite de source, et
    c'est exactement la partie que le modele prend a l'envers. Lui donner ces
    constats vaut mieux que les produire a cote de lui.

    Seules les affirmations situees dans les `limit` premiers caracteres sont
    listees : c'est tout ce que le modele recoit, et lui parler d'un passage
    qu'il ne voit pas l'inviterait a inventer.
    """
    if not sourcing:
        return ''
    visibles = [
        claim for claim in sourcing.get('claims') or []
        if not claim.get('has_citation') and (claim.get('position') or 0) < limit
    ]
    if not visibles:
        return ''

    lignes = '\n'.join(f'- "{claim["claim"]}"' for claim in visibles[:12])
    reste = len(visibles) - 12
    if reste > 0:
        lignes += f'\n- ... and {reste} more'
    return f"""
A deterministic pass over this text found {len(visibles)} factual claim(s) with
no source marker anywhere near them:
{lignes}

Treat that as established fact, not opinion. An unsourced figure is not an
E-E-A-T signal, it is a liability: never list one among the strengths, and say
so in the verdict when the article leans on several of them. You cannot tell
whether a figure is false, and neither can this check - what is established is
that nobody cited a source for it.
"""


def _run_seo_audit(title, excerpt, content, keyword='', language='fr', api_key=None):
    """Run the SEO audit prompt against Gemini and return the parsed result.

    Shared between SEOAuditView (single-article) and BulkSEOAuditView. Caches
    by content hash for 1h. Raises on hard failures (API key missing, JSON
    parse error, network error).
    """
    import json
    from google import genai

    if not api_key:
        api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        raise RuntimeError('GEMINI_API_KEY non configuree')

    # v2 : le prompt a change (constats de sourcage injectes), donc les entrees
    # ecrites par l'ancienne version ne doivent plus repondre.
    cache_key = _seo_cache_key(
        'seo-audit-v2:', title, excerpt, content[:5000], keyword, language
    )

    # Hors du cache : c'est une passe de regex sur le texte complet, elle ne
    # coute rien et le cache est indexe sur les 5000 premiers caracteres. Deux
    # articles partageant ce debut rendraient sinon le rapport de l'autre.
    sourcing = _sourcing_report(content, language)

    cached = cache.get(cache_key)
    if cached is not None:
        return {**cached, 'sourcing': sourcing}, True  # (result, from_cache)

    lang = 'French' if language == 'fr' else 'English'
    kw_section = f'Primary keyword: {keyword}\n' if keyword else ''
    sourcing_section = _sourcing_prompt_section(sourcing, limit=5000)

    prompt = f"""You are a senior SEO expert. Audit this blog article holistically.
Focus on REAL SEO signals, not checklists. Write feedback in {lang}.

{kw_section}Title: {title}
Meta description: {excerpt}
Content (first 5000 chars):
{content[:5000]}

Evaluate:
- Search intent alignment (does the article answer what someone would Google?)
- Keyword placement (title, intro, H2s, natural density - NOT stuffing)
- Content depth & originality (is this the same as 100 other articles?)
- E-E-A-T signals (experience, expertise, authority, trust cues)
- Readability (sentence length, active voice, scannability)
- Engagement hooks (intro, CTA, internal links)
- Technical basics (meta description quality, H2 hierarchy, image alt if mentioned)
{sourcing_section}
Be honest and specific. Your OWN feedback should cite numbers and examples
rather than platitudes. That is not the same as rewarding the article for
containing numbers.

Respond in JSON only (no markdown):
{{
  "score": <integer 0-100>,
  "verdict": "<1 sentence overall assessment>",
  "strengths": ["<strength 1>", "<strength 2>", ...],
  "weaknesses": ["<weakness 1>", "<weakness 2>", ...],
  "actions": ["<concrete action 1>", "<concrete action 2>", ...]
}}"""

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[prompt],
    )
    text = (response.text or '').strip()
    if text.startswith('```'):
        text = text.split('\n', 1)[1]
        if text.endswith('```'):
            text = text[:-3]
        text = text.strip()
    data = json.loads(text)
    result = {
        'score': int(data.get('score', 0)),
        'verdict': data.get('verdict', ''),
        'strengths': data.get('strengths', []),
        'weaknesses': data.get('weaknesses', []),
        'actions': data.get('actions', []),
    }
    cache.set(cache_key, result, timeout=SEO_CACHE_TTL)
    return {**result, 'sourcing': sourcing}, False


class SEOAuditView(APIView):
    """Full SEO audit via Gemini - returns score + strengths + weaknesses + actions."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        title = request.data.get('title', '')
        excerpt = request.data.get('excerpt', '')
        content = request.data.get('content', '')
        keyword = request.data.get('keyword', '')
        language = request.data.get('language', 'fr')

        if not title or not content:
            return Response(
                {'error': 'Titre et contenu requis'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            result, from_cache = _run_seo_audit(
                title, excerpt, content, keyword, language
            )
        except RuntimeError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except Exception as e:
            return Response(
                {'error': f'Erreur audit SEO: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        resp = Response(result)
        resp['X-Cache'] = 'HIT' if from_cache else 'MISS'
        return resp


class SEOFixView(APIView):
    """Fix SEO issues in an article using Gemini."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        title = request.data.get('title', '')
        excerpt = request.data.get('excerpt', '')
        content = request.data.get('content', '')
        issues = request.data.get('issues', '')
        language = request.data.get('language', 'fr')
        keyword = (request.data.get('keyword') or '').strip()
        competitor_summary = (request.data.get('competitor_summary') or '').strip()
        audit_context = (request.data.get('audit_context') or '').strip()

        if not title:
            return Response(
                {'error': 'Titre requis'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        api_key = os.environ.get('GEMINI_API_KEY')
        if not api_key:
            return Response(
                {'error': 'GEMINI_API_KEY non configuree'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        cache_key = _seo_cache_key(
            'seo-fix:', title, excerpt, content[:5000], issues, language,
            keyword, competitor_summary, audit_context,
        )
        cached = cache.get(cache_key)
        if cached is not None:
            resp = Response(cached)
            resp['X-Cache'] = 'HIT'
            return resp

        try:
            from google import genai
            import json

            client = genai.Client(api_key=api_key)

            lang_names = {
                'fr': ('French', 'français'),
                'en': ('English', 'English'),
                'es': ('Spanish', 'español'),
            }
            lang_en, lang_native = lang_names.get(language, ('French', 'français'))

            keyword_block = ''
            if keyword:
                keyword_block = f"""
PRIMARY KEYWORD: {keyword}
- The keyword (or a close variant) MUST appear naturally in the title, the first paragraph, and at least one H2.
- Do NOT stuff it - one occurrence per zone is enough.
"""

            competitor_block = f"\nCOMPETITOR CONTEXT:\n{competitor_summary}\n" if competitor_summary else ''
            audit_block = f"\nFULL AI AUDIT:\n{audit_context}\n" if audit_context else ''

            prompt = f"""You are an SEO expert. Fix the following issues in this blog article.

CRITICAL LANGUAGE RULE:
The article is written in {lang_en} ({lang_native}).
You MUST respond in {lang_en} ({lang_native}) ONLY.
Do NOT translate to English if the article is in French. Do NOT mix languages.
Every field you return (title, excerpt, content) must be in {lang_en} ({lang_native}).

Current title: {title}
Current excerpt (meta description): {excerpt}
Current content (first 3000 chars): {content[:3000]}
{keyword_block}{competitor_block}{audit_block}
SEO ISSUES TO FIX:
{issues}

RULES:
- Title: 50-60 characters, compelling, contains the primary keyword if provided
- Excerpt/meta description: 120-160 characters, contains the primary keyword if provided
- If content is too short or weaker than competitors, expand with relevant paragraphs (keep markdown format, same tone)
- Respect and reinforce the author's existing voice and style
- Only return fields that actually need changes - null for fields already good
- Use the competitor and audit context above to inform depth, structure, and angle

Respond in JSON only (no markdown blocks):
{{
  "title": "optimized title in {lang_native} or null",
  "excerpt": "optimized excerpt in {lang_native} or null",
  "content": "full improved content in markdown, in {lang_native}, or null"
}}"""

            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[prompt],
            )

            text = response.text.strip()
            if text.startswith('```'):
                text = text.split('\n', 1)[1]
                if text.endswith('```'):
                    text = text[:-3]
                text = text.strip()

            data = json.loads(text)
            # Only return non-null fields
            result = {}
            if data.get('title'):
                result['title'] = data['title']
            if data.get('excerpt'):
                result['excerpt'] = data['excerpt']
            if data.get('content'):
                result['content'] = data['content']

            cache.set(cache_key, result, timeout=SEO_CACHE_TTL)
            resp = Response(result)
            resp['X-Cache'] = 'MISS'
            return resp

        except Exception as e:
            return Response(
                {'error': f'Erreur correction SEO: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class SEOSuggestView(APIView):
    """Generate SEO suggestions using Gemini."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        title = request.data.get('title', '')
        content = request.data.get('content', '')
        excerpt = request.data.get('excerpt', '')
        language = request.data.get('language', 'fr')

        if not title:
            return Response(
                {'error': 'Le titre est requis'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        api_key = os.environ.get('GEMINI_API_KEY')
        if not api_key:
            return Response(
                {'error': 'GEMINI_API_KEY non configuree'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        cache_key = _seo_cache_key('seo-suggest:', title, excerpt, content[:5000], language)
        cached = cache.get(cache_key)
        if cached is not None:
            resp = Response(cached)
            resp['X-Cache'] = 'HIT'
            return resp

        try:
            from google import genai

            client = genai.Client(api_key=api_key)

            lang_label = 'French' if language == 'fr' else 'English'
            prompt = f"""You are an SEO expert. Analyze this blog article and provide suggestions in {lang_label}.

Title: {title}
Excerpt: {excerpt}
Content (first 2000 chars): {content[:2000]}

Respond in JSON format only (no markdown, no code blocks):
{{
  "meta_descriptions": ["3 optimized meta descriptions (150-160 chars each)"],
  "title_suggestions": ["3 alternative SEO-optimized titles (50-60 chars each)"],
  "keywords": ["8-12 relevant SEO keywords/phrases"]
}}"""

            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[prompt],
            )

            import json
            text = response.text.strip()
            # Remove potential markdown code block wrapping
            if text.startswith('```'):
                text = text.split('\n', 1)[1]
                if text.endswith('```'):
                    text = text[:-3]
                text = text.strip()

            data = json.loads(text)
            cache.set(cache_key, data, timeout=SEO_CACHE_TTL)
            resp = Response(data)
            resp['X-Cache'] = 'MISS'
            return resp

        except json.JSONDecodeError:
            return Response(
                {'error': 'Erreur parsing reponse IA'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except Exception as e:
            error_msg = str(e)
            if 'RESOURCE_EXHAUSTED' in error_msg or 'quota' in error_msg.lower():
                return Response(
                    {'error': 'Quota Gemini epuise'},
                    status=status.HTTP_429_TOO_MANY_REQUESTS,
                )
            return Response(
                {'error': f'Erreur suggestions SEO: {error_msg}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class SEOSynonymsView(APIView):
    """Generate synonyms, variants and translations for a keyword using Gemini.

    Used by the frontend SEO analyzer to perform semantic keyword matching
    (e.g. 'SEO' should match 'rÃ©fÃ©rencement' in French content).
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        keyword = (request.data.get('keyword') or '').strip()
        language = request.data.get('language', 'fr')

        if not keyword:
            return Response(
                {'error': 'Le mot-cle est requis'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if language not in ('fr', 'en'):
            language = 'fr'

        api_key = os.environ.get('GEMINI_API_KEY')
        if not api_key:
            return Response(
                {'error': 'GEMINI_API_KEY non configuree'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        try:
            from google import genai

            client = genai.Client(api_key=api_key)

            lang_label = 'French' if language == 'fr' else 'English'
            other_lang = 'English' if language == 'fr' else 'French'
            prompt = f"""You are an SEO and linguistics expert. Given a keyword, return 5 to 8 semantically equivalent terms: synonyms, spelling variants, singular/plural forms, acronyms, and translations from {other_lang} to {lang_label} (and vice-versa) that would be relevant for SEO matching in {lang_label} content.

Keyword: {keyword}
Target language: {lang_label}

Rules:
- Return short terms (1-3 words each).
- Include the keyword itself if it's the most natural form.
- Include common translations between French and English so a French article using "rÃ©fÃ©rencement" matches the keyword "SEO".
- Do NOT include generic unrelated words.

Respond in JSON format only (no markdown, no code blocks):
{{
  "synonyms": ["term1", "term2", "term3", "term4", "term5"]
}}"""

            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[prompt],
            )

            import json
            text = response.text.strip()
            if text.startswith('```'):
                text = text.split('\n', 1)[1]
                if text.endswith('```'):
                    text = text[:-3]
                text = text.strip()

            data = json.loads(text)
            synonyms = data.get('synonyms', [])
            if not isinstance(synonyms, list):
                synonyms = []
            # Normalize: keep only non-empty strings, dedupe preserving order.
            seen = set()
            clean = []
            for s in synonyms:
                if not isinstance(s, str):
                    continue
                s = s.strip()
                if not s:
                    continue
                key = s.lower()
                if key in seen:
                    continue
                seen.add(key)
                clean.append(s)

            return Response({'synonyms': clean[:8]})

        except json.JSONDecodeError:
            return Response(
                {'error': 'Erreur parsing reponse IA'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except Exception as e:
            error_msg = str(e)
            if 'RESOURCE_EXHAUSTED' in error_msg or 'quota' in error_msg.lower():
                return Response(
                    {'error': 'Quota Gemini epuise'},
                    status=status.HTTP_429_TOO_MANY_REQUESTS,
                )
            return Response(
                {'error': f'Erreur synonymes SEO: {error_msg}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class SEOCacheClearView(APIView):
    """Admin-only endpoint to flush the SEO AI cache."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not request.user.is_staff:
            return Response(
                {'error': 'Admin requis'},
                status=status.HTTP_403_FORBIDDEN,
            )
        cache.clear()
        return Response({'cleared': True})


class KeywordResearchView(APIView):
    """Keyword research combining Serper (related + PAA) and Gemini long-tail generation.

    Input: {seed_keyword, language}
    Returns a merged, deduplicated list of keywords with source and estimated intent.
    """
    permission_classes = [IsAuthenticated]

    COMMERCIAL_TOKENS = (
        'prix', 'price', 'acheter', 'buy', 'cost', 'cout', 'coÃ»t', 'pas cher',
        'cheap', 'deal', 'promo', 'discount', 'tarif', 'abonnement', 'subscription',
    )
    TRANSACTIONAL_TOKENS = (
        'commander', 'order', 'telecharger', 'tÃ©lÃ©charger', 'download',
        'inscription', 'signup', 'sign up', 'reserver', 'rÃ©server', 'book',
        'login', 'se connecter',
    )
    NAVIGATIONAL_TOKENS = (
        'login', 'connexion', 'site officiel', 'official site', 'website',
        'facebook', 'youtube', 'twitter', 'instagram', 'linkedin',
    )
    INFORMATIONAL_TOKENS = (
        'comment', 'how', 'pourquoi', 'why', 'qu\'est-ce', 'what is', 'what',
        'guide', 'tutoriel', 'tutorial', 'exemple', 'example', 'definition',
        'dÃ©finition', 'qui', 'who', 'quand', 'when',
    )

    def _estimate_intent(self, keyword):
        """Infer intent from keyword tokens â€” lightweight heuristic."""
        kw = keyword.lower()
        for token in self.TRANSACTIONAL_TOKENS:
            if token in kw:
                return 'transactional'
        for token in self.COMMERCIAL_TOKENS:
            if token in kw:
                return 'commercial'
        for token in self.NAVIGATIONAL_TOKENS:
            if token in kw:
                return 'navigational'
        for token in self.INFORMATIONAL_TOKENS:
            if token in kw:
                return 'informational'
        return 'informational'

    def post(self, request):
        import time
        import json

        seed_keyword = (request.data.get('seed_keyword') or '').strip()
        language = request.data.get('language', 'fr')

        if not seed_keyword:
            return Response(
                {'error': 'Le mot-cle de depart est requis'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serper_key = os.environ.get('SERPER_API_KEY')
        gemini_key = os.environ.get('GEMINI_API_KEY')

        if not serper_key and not gemini_key:
            return Response(
                {'error': 'SERPER_API_KEY ou GEMINI_API_KEY requise'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        deadline = time.monotonic() + 60.0
        collected = []  # list of (keyword, source)

        # 1) Serper â€” relatedSearches + peopleAlsoAsk
        if serper_key:
            try:
                remaining = max(1.0, deadline - time.monotonic())
                resp = http_requests.post(
                    'https://google.serper.dev/search',
                    headers={
                        'X-API-KEY': serper_key,
                        'Content-Type': 'application/json',
                    },
                    json={'q': seed_keyword, 'num': 10},
                    timeout=min(30.0, remaining),
                )
                if resp.status_code == 200:
                    data = resp.json() or {}
                    for item in data.get('relatedSearches') or []:
                        q = (item or {}).get('query')
                        if q:
                            collected.append((q, 'serper_related'))
                    for item in data.get('peopleAlsoAsk') or []:
                        q = (item or {}).get('question')
                        if q:
                            collected.append((q, 'serper_paa'))
            except http_requests.Timeout:
                logger.warning('Serper keyword research timeout')
            except Exception as e:
                logger.warning('Serper keyword research failed: %s', e)

        # 2) Gemini â€” generate 10 long-tail variants
        if gemini_key and (deadline - time.monotonic()) > 2.0:
            try:
                from google import genai

                lang_label = 'French' if language == 'fr' else (
                    'Spanish' if language == 'es' else 'English'
                )
                prompt = f"""You are an SEO keyword research expert. For the seed keyword below,
generate exactly 10 long-tail keyword variants (3-6 words each) that real users
would search. Mix question-based and descriptive variants. Write them in {lang_label}.

Seed keyword: {seed_keyword}

Respond in JSON only (no markdown, no code blocks):
{{"keywords": ["keyword 1", "keyword 2", ...]}}"""

                client = genai.Client(api_key=gemini_key)
                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=[prompt],
                )

                text = (response.text or '').strip()
                if text.startswith('```'):
                    text = text.split('\n', 1)[1]
                    if text.endswith('```'):
                        text = text[:-3]
                    text = text.strip()

                parsed = json.loads(text)
                for kw in parsed.get('keywords') or []:
                    if isinstance(kw, str) and kw.strip():
                        collected.append((kw.strip(), 'gemini_longtail'))
            except Exception as e:
                logger.warning('Gemini long-tail generation failed: %s', e)

        # 3) Dedupe case-insensitively, preserving the first occurrence's source
        seen = set()
        keywords = []
        seed_norm = seed_keyword.lower().strip()
        for kw, source in collected:
            norm = kw.lower().strip()
            if not norm or norm == seed_norm or norm in seen:
                continue
            seen.add(norm)
            keywords.append({
                'keyword': kw,
                'source': source,
                'estimated_intent': self._estimate_intent(kw),
            })

        return Response({'keywords': keywords})
class PageSpeedView(APIView):
    """Fetch Core Web Vitals + category scores from Google PageSpeed Insights."""
    permission_classes = [IsAuthenticated]

    PSI_ENDPOINT = 'https://www.googleapis.com/pagespeedonline/v5/runPagespeed'

    def post(self, request):
        url = (request.data.get('url') or '').strip()
        strategy = request.data.get('strategy') or 'mobile'

        if not url:
            return Response(
                {'error': 'Le parametre "url" est requis'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if strategy not in ('mobile', 'desktop'):
            return Response(
                {'error': 'Strategy invalide (mobile ou desktop)'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not (url.startswith('http://') or url.startswith('https://')):
            return Response(
                {'error': 'URL invalide (http:// ou https:// requis)'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Cache results for 30 min - PSI is slow and quota-limited
        cache_key = _seo_cache_key('page-speed:', url, strategy)
        cached = cache.get(cache_key)
        if cached is not None:
            resp_obj = Response(cached)
            resp_obj['X-Cache'] = 'HIT'
            return resp_obj

        # Optional API key removes rate limits (free at console.cloud.google.com)
        api_key = os.environ.get('PAGESPEED_API_KEY', '').strip()
        psi_url = (
            f'{self.PSI_ENDPOINT}'
            f'?url={quote(url, safe="")}'
            f'&strategy={strategy}'
            f'&category=PERFORMANCE&category=SEO&category=ACCESSIBILITY'
        )
        if api_key:
            psi_url += f'&key={api_key}'

        try:
            resp = http_requests.get(psi_url, timeout=120)
        except http_requests.Timeout:
            return Response(
                {'error': 'Delai PageSpeed Insights depasse (>120s). Reessayez dans quelques secondes.'},
                status=status.HTTP_504_GATEWAY_TIMEOUT,
            )
        except Exception as e:
            return Response(
                {'error': f'Erreur reseau PageSpeed: {str(e)}'},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        if resp.status_code != 200:
            try:
                err_body = resp.json()
                err_msg = err_body.get('error', {}).get('message', f'HTTP {resp.status_code}')
            except Exception:
                err_msg = f'HTTP {resp.status_code}'
            # Common: 429 quota exceeded - guide the user
            hint = ''
            if resp.status_code == 429:
                hint = ' Configure PAGESPEED_API_KEY (gratuit chez Google Cloud) pour eviter les limites.'
            elif resp.status_code in (400, 404):
                hint = ' Verifie que l\'URL est publique et accessible.'
            return Response(
                {'error': f'PageSpeed Insights: {err_msg}.{hint}'},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        try:
            data = resp.json()
            lh = data.get('lighthouseResult', {}) or {}
            categories = lh.get('categories', {}) or {}
            audits = lh.get('audits', {}) or {}

            def cat_score(key):
                cat = categories.get(key) or {}
                score = cat.get('score')
                if score is None:
                    return None
                return round(float(score) * 100)

            def audit_numeric(key):
                audit = audits.get(key) or {}
                val = audit.get('numericValue')
                if val is None:
                    return None
                return float(val)

            lcp_ms = audit_numeric('largest-contentful-paint')
            fcp_ms = audit_numeric('first-contentful-paint')
            cls_val = audit_numeric('cumulative-layout-shift')

            result = {
                'performance_score': cat_score('performance'),
                'seo_score': cat_score('seo'),
                'a11y_score': cat_score('accessibility'),
                'lcp_s': round(lcp_ms / 1000, 2) if lcp_ms is not None else None,
                'cls': round(cls_val, 3) if cls_val is not None else None,
                'fcp_s': round(fcp_ms / 1000, 2) if fcp_ms is not None else None,
                'strategy': strategy,
                'tested_url': url,
            }
            cache.set(cache_key, result, timeout=1800)  # 30 min
            resp_obj = Response(result)
            resp_obj['X-Cache'] = 'MISS'
            return resp_obj
        except Exception as e:
            logger.exception('PageSpeed parsing failed')
            return Response(
                {'error': f'Erreur parsing PageSpeed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class LinkSuggestionsView(APIView):
    """Suggest internal links (existing site articles) for the current draft using Gemini."""
    permission_classes = [IsAuthenticated]

    def post(self, request, site_id):
        site = get_site_for_user(request, site_id)

        title = request.data.get('title', '')
        content = request.data.get('content', '')
        current_slug = request.data.get('current_slug', '')
        language = request.data.get('language', 'fr')

        if not title and not content:
            return Response(
                {'error': 'Titre ou contenu requis'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        api_key = os.environ.get('GEMINI_API_KEY')
        if not api_key:
            return Response(
                {'error': 'GEMINI_API_KEY non configuree'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # Fetch candidate articles (published, same language, excluding current slug)
        lang = language if language in ('fr', 'en', 'es') else 'fr'
        candidates = []

        if site.is_hosted:
            qs = (
                HostedPost.objects
                .filter(site=site, language=lang, status='published')
                .order_by('-published_at', '-created_at')
            )
            if current_slug:
                qs = qs.exclude(slug=current_slug)
            for p in qs[:50]:
                candidates.append({
                    'slug': p.slug,
                    'title': p.title,
                    'excerpt': (p.excerpt or '')[:300],
                })
        else:
            try:
                alias = ensure_site_connection(site)
                qs = (
                    BlogPost.objects.using(alias)
                    .filter(language=lang, status='published')
                    .order_by('-published_at', '-created_at')
                )
                if current_slug:
                    qs = qs.exclude(slug=current_slug)
                for p in qs[:50]:
                    candidates.append({
                        'slug': p.slug,
                        'title': p.title,
                        'excerpt': (getattr(p, 'excerpt', '') or '')[:300],
                    })
            except Exception as e:
                return Response(
                    {'error': f'Erreur connexion site: {str(e)}'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        if not candidates:
            return Response({'suggestions': []})

        try:
            from google import genai
            import json

            client = genai.Client(api_key=api_key)
            prompt = (
                "You are an SEO internal linking assistant. Given a draft article and a list "
                "of existing articles on the same site, identify up to 5 highly relevant articles "
                "to link to from the draft, and propose a natural anchor text + a short sentence "
                "or phrase from the draft content where the link should be inserted.\n\n"
                f"Draft title: {title}\n"
                f"Draft content (first 3000 chars): {content[:3000]}\n\n"
                "Existing articles (JSON):\n"
                f"{json.dumps(candidates, ensure_ascii=False)}\n\n"
                "Respond in JSON only:\n"
                "{\n"
                '  "suggestions": [\n'
                '    {"slug": "...", "title": "...", "anchor_text": "...", '
                '"insert_hint": "quote a sentence or phrase from the draft where this link fits naturally", '
                '"reason": "why this link adds value"}\n'
                "  ]\n"
                "}"
            )

            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[prompt],
            )

            text = response.text.strip()
            if text.startswith('```'):
                text = text.split('\n', 1)[1]
                if text.endswith('```'):
                    text = text[:-3]
                text = text.strip()

            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                return Response(
                    {'error': 'Erreur parsing reponse IA'},
                    status=status.HTTP_502_BAD_GATEWAY,
                )

            # Only return suggestions whose slug is in our candidate list
            valid_slugs = {c['slug']: c['title'] for c in candidates}
            raw_suggestions = data.get('suggestions', []) or []
            suggestions = []
            for s in raw_suggestions[:5]:
                slug = s.get('slug', '')
                if slug in valid_slugs:
                    suggestions.append({
                        'slug': slug,
                        'title': s.get('title') or valid_slugs[slug],
                        'anchor_text': s.get('anchor_text', ''),
                        'insert_hint': s.get('insert_hint', ''),
                        'reason': s.get('reason', ''),
                    })

            return Response({'suggestions': suggestions})

        except Exception as e:
            error_msg = str(e)
            if 'RESOURCE_EXHAUSTED' in error_msg or 'quota' in error_msg.lower():
                return Response(
                    {'error': 'Quota Gemini epuise'},
                    status=status.HTTP_429_TOO_MANY_REQUESTS,
                )
            return Response(
                {'error': f'Erreur suggestions de liens: {error_msg}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class BacklinksView(APIView):
    """Lightweight backlink discovery via Serper (Google `link:` operator).

    This is an approximation: Google heavily deprecates the `link:` operator and
    real backlink data requires paid tools (Ahrefs/SEMrush/Moz). The response
    surfaces results grouped by referring hostname as a best-effort signal.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from urllib.parse import urlparse

        url = (request.data.get('url') or '').strip()
        warning = (
            'Serper results are approximations - for real data use Ahrefs/SEMrush'
        )

        if not url:
            return Response(
                {'error': 'Le parametre "url" est requis', 'warning': warning},
                status=status.HTTP_400_BAD_REQUEST,
            )

        api_key = os.environ.get('SERPER_API_KEY')
        if not api_key:
            return Response(
                {'error': 'SERPER_API_KEY non configuree', 'warning': warning},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        # Normalize the source URL so we can skip self-references
        try:
            source_host = urlparse(url).hostname or ''
        except Exception:
            source_host = ''
        source_host = source_host.lower().lstrip('www.')

        try:
            resp = http_requests.post(
                'https://google.serper.dev/search',
                headers={
                    'X-API-KEY': api_key,
                    'Content-Type': 'application/json',
                },
                json={'q': f'link:{url}', 'num': 20},
                timeout=10,
            )

            if resp.status_code != 200:
                return Response(
                    {
                        'error': f'Erreur Serper: {resp.status_code}',
                        'warning': warning,
                    },
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )

            data = resp.json()
            organic = data.get('organic', []) or []

            domain_map = {}
            raw_count = 0
            for item in organic:
                link = item.get('link') or ''
                if not link:
                    continue
                raw_count += 1
                try:
                    host = (urlparse(link).hostname or '').lower()
                except Exception:
                    continue
                if not host:
                    continue
                if host.startswith('www.'):
                    host = host[4:]
                # Skip self-references (same host as the source URL)
                if source_host and host == source_host:
                    continue
                bucket = domain_map.setdefault(
                    host, {'mentions': 0, 'sample_url': link}
                )
                bucket['mentions'] += 1

            top_domains = sorted(
                (
                    {
                        'domain': d,
                        'mentions': info['mentions'],
                        'sample_url': info['sample_url'],
                    }
                    for d, info in domain_map.items()
                ),
                key=lambda x: x['mentions'],
                reverse=True,
            )

            return Response({
                'total_referring_domains': len(domain_map),
                'top_domains': top_domains,
                'raw_count': raw_count,
                'warning': warning,
            })

        except http_requests.Timeout:
            return Response(
                {
                    'error': 'Delai de requete Serper depasse',
                    'warning': warning,
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception("Backlinks lookup failed for %s", url)
            return Response(
                {'error': str(e), 'warning': warning},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )


class SEOSchemaView(APIView):
    """Generate Schema.org JSON-LD for a blog article via Gemini.

    Detects whether the article is structured as an FAQPage or HowTo and
    enriches the JSON-LD accordingly. Falls back to a plain BlogPosting.
    """
    permission_classes = [IsAuthenticated]

    def _strip_code_fence(self, text):
        text = text.strip()
        if text.startswith('```'):
            text = text.split('\n', 1)[1] if '\n' in text else text[3:]
            if text.endswith('```'):
                text = text[:-3]
        return text.strip()

    def _build_page_url(self, site_domain, slug):
        if not site_domain:
            return slug or ''
        domain = site_domain.strip()
        if not domain.startswith(('http://', 'https://')):
            domain = 'https://' + domain
        domain = domain.rstrip('/')
        if slug:
            return f"{domain}/{slug.lstrip('/')}"
        return domain

    def post(self, request):
        title = request.data.get('title', '') or ''
        excerpt = request.data.get('excerpt', '') or ''
        content = request.data.get('content', '') or ''
        author = request.data.get('author', '') or ''
        cover_image = request.data.get('cover_image', '') or ''
        published_at = request.data.get('published_at', '') or ''
        site_domain = request.data.get('site_domain', '') or ''
        slug = request.data.get('slug', '') or ''
        language = request.data.get('language', 'fr') or 'fr'

        if not title or not content:
            return Response(
                {'error': 'Titre et contenu requis'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        page_url = self._build_page_url(site_domain, slug)

        # Base BlogPosting JSON-LD.
        jsonld = {
            '@context': 'https://schema.org',
            '@type': 'BlogPosting',
            'headline': title,
            'description': excerpt,
            'inLanguage': language,
            'mainEntityOfPage': {
                '@type': 'WebPage',
                '@id': page_url,
            },
        }
        if cover_image:
            jsonld['image'] = cover_image
        if published_at:
            jsonld['datePublished'] = published_at
            jsonld['dateModified'] = published_at
        if author:
            jsonld['author'] = {
                '@type': 'Person',
                'name': author,
            }

        schema_type = 'BlogPosting'
        usage_hint = (
            "Collez ce <script> dans le <head> de la page de l'article "
            "pour enrichir le SEO (Google Rich Results)."
            if language == 'fr'
            else
            "Paste this <script> into the page <head> to enrich SEO (Google Rich Results)."
        )

        api_key = os.environ.get('GEMINI_API_KEY')
        if not api_key:
            # Still return the base BlogPosting even if Gemini unavailable.
            import json as _json
            script_tag = (
                '<script type="application/ld+json">'
                + _json.dumps(jsonld, ensure_ascii=False, indent=2)
                + '</script>'
            )
            return Response({
                'schema_type': schema_type,
                'jsonld': jsonld,
                'script_tag': script_tag,
                'usage_hint': usage_hint,
            })

        try:
            from google import genai
            import json as _json

            client = genai.Client(api_key=api_key)

            # Step 1: detect schema type + extract structured data.
            detect_prompt = f"""You are a Schema.org expert. Analyze this blog article and decide which structured-data type fits best.

Rules:
- "FAQPage" if the article is mostly a list of questions & answers (markdown headings like "## Questions", "## FAQ", or repeated "Q:" / "A:" patterns, or interrogative H2/H3 followed by an answer paragraph).
- "HowTo" if the article is a step-by-step guide (headings like "## Étapes", "## Steps", or numbered steps "1.", "2.", "Étape 1", "Step 1").
- Otherwise "BlogPosting".

Title: {title}
Excerpt: {excerpt}
Content (first 4000 chars):
{content[:4000]}

Respond in strict JSON (no markdown, no code fences) with this exact shape:
{{
  "schema_type": "FAQPage" | "HowTo" | "BlogPosting",
  "faq": [{{"question": "...", "answer": "..."}}],
  "steps": [{{"name": "...", "text": "..."}}]
}}
- Fill "faq" only when schema_type is "FAQPage" (else []).
- Fill "steps" only when schema_type is "HowTo" (else []).
- Extract up to 10 FAQ pairs or steps, using the article's original language ({language}).
- Keep answers / step texts concise (<= 400 chars, plain text, no markdown)."""

            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[detect_prompt],
            )
            raw = self._strip_code_fence(response.text or '')
            try:
                data = _json.loads(raw)
            except Exception:
                data = {'schema_type': 'BlogPosting', 'faq': [], 'steps': []}

            detected = data.get('schema_type', 'BlogPosting')
            if detected == 'FAQPage':
                faq = data.get('faq') or []
                if faq:
                    schema_type = 'FAQPage'
                    jsonld['@type'] = ['BlogPosting', 'FAQPage']
                    jsonld['mainEntity'] = [
                        {
                            '@type': 'Question',
                            'name': (item.get('question') or '').strip(),
                            'acceptedAnswer': {
                                '@type': 'Answer',
                                'text': (item.get('answer') or '').strip(),
                            },
                        }
                        for item in faq
                        if item.get('question') and item.get('answer')
                    ]
            elif detected == 'HowTo':
                steps = data.get('steps') or []
                if steps:
                    schema_type = 'HowTo'
                    jsonld['@type'] = ['BlogPosting', 'HowTo']
                    jsonld['name'] = title
                    jsonld['step'] = [
                        {
                            '@type': 'HowToStep',
                            'position': idx + 1,
                            'name': (step.get('name') or f'Step {idx + 1}').strip(),
                            'text': (step.get('text') or '').strip(),
                        }
                        for idx, step in enumerate(steps)
                        if step.get('text')
                    ]

            script_tag = (
                '<script type="application/ld+json">'
                + _json.dumps(jsonld, ensure_ascii=False, indent=2)
                + '</script>'
            )

            return Response({
                'schema_type': schema_type,
                'jsonld': jsonld,
                'script_tag': script_tag,
                'usage_hint': usage_hint,
                # An LLM writes this JSON-LD, so it can invent a property or
                # leave a placeholder in it. Handing the user a script tag to
                # paste without checking it first is how broken markup ships.
                'validation': _validate_generated_schema(jsonld),
            })

        except Exception as e:
            error_msg = str(e)
            if 'RESOURCE_EXHAUSTED' in error_msg or 'quota' in error_msg.lower():
                return Response(
                    {'error': 'Quota Gemini epuise'},
                    status=status.HTTP_429_TOO_MANY_REQUESTS,
                )
            # Graceful fallback: return base BlogPosting on AI error.
            import json as _json
            script_tag = (
                '<script type="application/ld+json">'
                + _json.dumps(jsonld, ensure_ascii=False, indent=2)
                + '</script>'
            )
            return Response({
                'schema_type': schema_type,
                'jsonld': jsonld,
                'script_tag': script_tag,
                'usage_hint': usage_hint,
                'warning': f'AI detection failed: {error_msg}',
                'validation': _validate_generated_schema(jsonld),
            })


class TranslatePostView(APIView):
    """Translate a post to another language using Gemini. Does NOT save."""
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    throttle_scope = 'ai_generate'

    def post(self, request):
        title = request.data.get('title', '')
        excerpt = request.data.get('excerpt', '')
        content = request.data.get('content', '')
        source_lang = request.data.get('source_language', 'fr')
        target_lang = request.data.get('target_language', 'en')

        if not title or not content:
            return Response(
                {'error': 'Titre et contenu requis'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if source_lang == target_lang:
            return Response(
                {'error': 'Langue source et cible identiques'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        api_key = os.environ.get('GEMINI_API_KEY')
        if not api_key:
            return Response(
                {'error': 'GEMINI_API_KEY non configuree'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        try:
            from google import genai
            import json

            lang_names = {'fr': 'French', 'en': 'English', 'es': 'Spanish'}
            src_name = lang_names.get(source_lang, source_lang)
            tgt_name = lang_names.get(target_lang, target_lang)

            client = genai.Client(api_key=api_key)
            prompt = f"""Translate this blog article from {src_name} to {tgt_name}.
Preserve the markdown formatting (headings, lists, links, images).
Keep technical terms and code blocks unchanged.
Translate the slug to a URL-friendly version in {tgt_name}.

Title: {title}
Excerpt: {excerpt}
Content:
{content}

Respond in JSON only (no markdown blocks):
{{
  "title": "translated title",
  "slug": "translated-url-slug",
  "excerpt": "translated excerpt",
  "content": "full translated content with markdown preserved"
}}"""

            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[prompt],
            )

            text = response.text.strip()
            if text.startswith('```'):
                text = text.split('\n', 1)[1]
                if text.endswith('```'):
                    text = text[:-3]
                text = text.strip()

            data = json.loads(text)
            return Response({
                'title': data.get('title', ''),
                'slug': data.get('slug', ''),
                'excerpt': data.get('excerpt', ''),
                'content': data.get('content', ''),
                'language': target_lang,
            })

        except Exception as e:
            return Response(
                {'error': f'Erreur traduction: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class CompetitorAnalysisView(APIView):
    """Analyze top 10 Google SERP competitors for a keyword via Serper."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        import re
        from statistics import median

        keyword = (request.data.get('keyword') or '').strip()
        language = (request.data.get('language') or 'fr').strip().lower()

        if not keyword:
            return Response(
                {'error': 'Le mot-cle est requis'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        api_key = os.environ.get('SERPER_API_KEY')
        if not api_key:
            return Response(
                {'error': 'SERPER_API_KEY non configuree'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        if language == 'en':
            hl, gl = 'en', 'us'
        else:
            hl, gl = 'fr', 'ca'

        try:
            serper_resp = http_requests.post(
                'https://google.serper.dev/search',
                headers={
                    'X-API-KEY': api_key,
                    'Content-Type': 'application/json',
                },
                json={'q': keyword, 'num': 10, 'hl': hl, 'gl': gl},
                timeout=10,
            )
        except http_requests.Timeout:
            return Response(
                {'error': 'Delai de requete Serper depasse'},
                status=status.HTTP_504_GATEWAY_TIMEOUT,
            )
        except Exception as e:
            return Response(
                {'error': f'Erreur Serper: {str(e)}'},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        if serper_resp.status_code != 200:
            return Response(
                {'error': f'Erreur Serper: {serper_resp.status_code}'},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        organic = (serper_resp.json() or {}).get('organic', []) or []
        organic = organic[:10]

        tag_re = re.compile(r'<[^>]+>')
        h2_re = re.compile(r'<h2[\s>]', re.IGNORECASE)
        meta_re = re.compile(
            r'<meta\s+[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']',
            re.IGNORECASE,
        )
        meta_re_alt = re.compile(
            r'<meta\s+[^>]*content=["\']([^"\']*)["\'][^>]*name=["\']description["\']',
            re.IGNORECASE,
        )
        script_re = re.compile(r'<(script|style)[^>]*>.*?</\1>', re.IGNORECASE | re.DOTALL)
        ws_re = re.compile(r'\s+')

        results = []
        for idx, item in enumerate(organic, start=1):
            url = item.get('link') or ''
            entry = {
                'rank': idx,
                'url': url,
                'title': item.get('title') or '',
                'snippet': item.get('snippet') or '',
                'word_count': None,
                'h2_count': None,
                'meta_description': None,
                'fetch_error': False,
            }

            if not url:
                entry['fetch_error'] = True
                results.append(entry)
                continue

            try:
                resp = http_requests.get(
                    url,
                    timeout=6,
                    headers={'User-Agent': 'Mozilla/5.0 BlogDashboard/1.0'},
                )
                if not resp.ok:
                    entry['fetch_error'] = True
                    results.append(entry)
                    continue
                html = resp.text or ''

                # H2 count on raw HTML
                entry['h2_count'] = len(h2_re.findall(html))

                # Meta description
                m = meta_re.search(html) or meta_re_alt.search(html)
                entry['meta_description'] = m.group(1).strip() if m else None

                # Word count of visible text
                cleaned = script_re.sub(' ', html)
                text = tag_re.sub(' ', cleaned)
                text = ws_re.sub(' ', text).strip()
                entry['word_count'] = len([w for w in text.split(' ') if w]) if text else 0

            except Exception:
                entry['fetch_error'] = True

            results.append(entry)

        word_counts = [r['word_count'] for r in results if r['word_count'] is not None]
        h2_counts = [r['h2_count'] for r in results if r['h2_count'] is not None]
        median_words = int(median(word_counts)) if word_counts else None
        median_h2 = int(median(h2_counts)) if h2_counts else None

        return Response({
            'results': results,
            'keyword': keyword,
            'median_words': median_words,
            'median_h2': median_h2,
        })


class ContentBriefView(APIView):
    """Generate a pre-writing content brief for a target keyword.

    Combines Serper (SERP top 10 + People Also Ask) with Gemini synthesis to
    return a structured JSON brief: search intent, recommended titles, outline,
    word-count target, FAQ, entities, schemas, EEAT signals. Cached 1h.

    Input: {keyword: str, language: 'fr'|'en'|'es', site_id?: int}
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    throttle_scope = 'ai_generate'

    def post(self, request):
        import json
        import time

        keyword = (request.data.get('keyword') or '').strip()
        language = (request.data.get('language') or 'fr').strip().lower()

        if not keyword:
            return Response(
                {'error': 'Le mot-cle cible est requis'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if language not in ('fr', 'en', 'es'):
            return Response(
                {'error': "Langue invalide (fr, en, es)"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        gemini_key = os.environ.get('GEMINI_API_KEY')
        if not gemini_key:
            return Response(
                {'error': 'GEMINI_API_KEY non configuree'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        cache_key = _seo_cache_key('content-brief:', keyword, language)
        cached = cache.get(cache_key)
        if cached:
            return Response(cached)

        # 1) Serper - SERP top 10 + People Also Ask (best-effort)
        serper_key = os.environ.get('SERPER_API_KEY')
        organic = []
        paa = []
        related = []
        if serper_key:
            hl, gl = ('en', 'us') if language == 'en' else (
                ('es', 'es') if language == 'es' else ('fr', 'ca')
            )
            try:
                resp = http_requests.post(
                    'https://google.serper.dev/search',
                    headers={
                        'X-API-KEY': serper_key,
                        'Content-Type': 'application/json',
                    },
                    json={'q': keyword, 'num': 10, 'hl': hl, 'gl': gl},
                    timeout=10,
                )
                if resp.status_code == 200:
                    data = resp.json() or {}
                    organic = (data.get('organic') or [])[:10]
                    paa = [
                        (item or {}).get('question')
                        for item in (data.get('peopleAlsoAsk') or [])
                        if (item or {}).get('question')
                    ]
                    related = [
                        (item or {}).get('query')
                        for item in (data.get('relatedSearches') or [])
                        if (item or {}).get('query')
                    ]
            except http_requests.Timeout:
                logger.warning('Serper SERP timeout for content brief')
            except Exception as e:
                logger.warning('Serper SERP failed for content brief: %s', e)

        # 2) Build SERP context block for Gemini
        serp_lines = []
        for idx, item in enumerate(organic, start=1):
            title = (item.get('title') or '').strip()
            snippet = (item.get('snippet') or '').strip()
            if title:
                serp_lines.append(f"{idx}. {title} - {snippet}")
        serp_block = '\n'.join(serp_lines) if serp_lines else '(no SERP data available)'
        paa_block = '\n'.join(f"- {q}" for q in paa[:10]) if paa else '(no PAA available)'
        related_block = ', '.join(related[:10]) if related else '(none)'

        lang_label = {'fr': 'French (Quebec)', 'en': 'English', 'es': 'Spanish'}[language]

        prompt = f"""You are an SEO strategist producing a content brief for a blog article.

TARGET KEYWORD: {keyword}
TARGET LANGUAGE: {lang_label}

SERP TOP 10 (titles + snippets):
{serp_block}

PEOPLE ALSO ASK:
{paa_block}

RELATED SEARCHES: {related_block}

Produce a content brief as JSON. The brief MUST be in {lang_label}. Be specific and
actionable - a writer should be able to start writing from it without further research.

For "search_intent" choose ONE of: informational, commercial, transactional, navigational.

For "recommended_titles" produce 3 click-worthy variants under 60 chars.

For "outline" propose 6-12 H2 sections (level 2) with a few H3 sub-sections (level 3) where
useful. Prefer answering search intent and PAA questions. Order matters (top to bottom of article).

For "word_count_target" pick a number that matches the depth of top-ranking results
(typical 1200-2500 for informational FR-CA content).

For "faq" extract or generate 4-8 FAQ pairs ready to be turned into FAQPage schema. Each
"question" should be exactly the user's natural phrasing; "answer_hint" should be a 1-2
sentence summary the writer will expand.

For "entities" list 8-15 named entities, concepts, or LSI keywords the article should
mention to demonstrate topical breadth.

For "schemas_suggested" list which schema.org types fit (Article, BlogPosting, HowTo,
FAQPage, Question, LocalBusiness, etc.).

For "eeat_signals" list 3-6 concrete things to add to the article to satisfy E-E-A-T
(author bio with credentials, citation of regulators or studies, recent dates, etc.).

Respond with JSON only (no markdown code fences):
{{
  "search_intent": "...",
  "intent_explanation": "...",
  "recommended_titles": ["...", "...", "..."],
  "outline": [
    {{"level": 2, "text": "..."}},
    {{"level": 3, "text": "..."}}
  ],
  "word_count_target": 1500,
  "faq": [{{"question": "...", "answer_hint": "..."}}],
  "entities": ["...", "..."],
  "schemas_suggested": ["...", "..."],
  "eeat_signals": ["...", "..."]
}}"""

        try:
            from google import genai

            client = genai.Client(api_key=gemini_key)
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[prompt],
            )
            text = (response.text or '').strip()
            if text.startswith('```'):
                text = text.split('\n', 1)[1]
                if text.endswith('```'):
                    text = text[:-3]
                text = text.strip()
            brief = json.loads(text)
            if not isinstance(brief, dict):
                brief = {}
            # Le frontend accede a ces champs sans garde; garantir leur presence.
            for _list_key in ('recommended_titles', 'outline', 'faq', 'entities',
                              'schemas_suggested', 'eeat_signals'):
                if not isinstance(brief.get(_list_key), list):
                    brief[_list_key] = []
            brief.setdefault('search_intent', '')
            brief.setdefault('intent_explanation', '')
            brief.setdefault('word_count_target', 0)
        except Exception as e:
            logger.warning('Gemini content brief failed: %s', e)
            return Response(
                {'error': f'Erreur generation brief: {str(e)}'},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        result = {
            'keyword': keyword,
            'language': language,
            'serp_competitors': [
                {
                    'rank': idx,
                    'title': (item.get('title') or '').strip(),
                    'url': item.get('link') or '',
                    'snippet': (item.get('snippet') or '').strip(),
                }
                for idx, item in enumerate(organic, start=1)
            ],
            'people_also_ask': paa[:10],
            'related_searches': related[:10],
            'brief': brief,
        }
        cache.set(cache_key, result, SEO_CACHE_TTL)
        return Response(result)


class HreflangCheckView(APIView):
    """Validate translation_group consistency across published articles of a site.

    Two modes:
    - Per-group: pass {site_id, translation_group} → returns the siblings + which
      languages are missing from the site's `available_languages`.
    - Site-wide: pass {site_id} only → returns aggregate stats: groups with
      missing translations, articles without a group that look orphaned.

    No external API calls; pure DB introspection. Cache 5 min.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        site_id = request.data.get('site_id')
        translation_group = (request.data.get('translation_group') or '').strip()

        if not site_id:
            return Response(
                {'error': 'site_id requis'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            site = get_site_for_user(request, int(site_id))
        except (ValueError, TypeError):
            return Response(
                {'error': 'site_id invalide'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        cache_key = _seo_cache_key(
            'hreflang:', str(site.id), translation_group or '_all'
        )
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)

        expected_langs = list(site.effective_languages)

        # Helper to extract published rows in (translation_group, slug, lang, title) tuples
        def _all_published():
            if site.is_hosted:
                qs = HostedPost.objects.filter(site=site, status='published').values(
                    'translation_group', 'slug', 'language', 'title'
                )
            else:
                alias = ensure_site_connection(site)
                qs = BlogPost.objects.using(alias).filter(status='published').values(
                    'translation_group', 'slug', 'language', 'title'
                )
            return list(qs)

        try:
            rows = _all_published()
        except ValueError:
            return Response(
                {'error': "Cette action nécessite une base de données externe configurée pour ce site."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Per-group mode
        if translation_group:
            siblings = [
                r for r in rows if str(r.get('translation_group')) == translation_group
            ]
            languages_present = sorted({r['language'] for r in siblings if r.get('language')})
            missing = [lang for lang in expected_langs if lang not in languages_present]
            result = {
                'mode': 'group',
                'translation_group': translation_group,
                'expected_languages': expected_langs,
                'languages_present': languages_present,
                'missing_languages': missing,
                'is_complete': len(missing) == 0 and len(siblings) > 0,
                'siblings': [
                    {
                        'slug': r['slug'],
                        'language': r['language'],
                        'title': r.get('title') or '',
                    }
                    for r in siblings
                ],
            }
            cache.set(cache_key, result, timeout=300)
            return Response(result)

        # Site-wide mode: aggregate
        groups = {}  # tg -> [rows]
        for r in rows:
            tg = str(r.get('translation_group') or '')
            if tg:
                groups.setdefault(tg, []).append(r)

        groups_incomplete = []
        groups_complete = 0
        for tg, members in groups.items():
            langs = sorted({m['language'] for m in members if m.get('language')})
            missing = [lang for lang in expected_langs if lang not in langs]
            if missing:
                groups_incomplete.append({
                    'translation_group': tg,
                    'languages_present': langs,
                    'missing_languages': missing,
                    'sample_title': members[0].get('title') or '',
                    'sample_slug': members[0]['slug'],
                })
            else:
                groups_complete += 1

        # Articles published in only ONE language across the whole site,
        # whose group has no siblings - candidates for translation.
        single_lang_orphans = [
            {
                'slug': members[0]['slug'],
                'language': members[0]['language'],
                'title': members[0].get('title') or '',
                'translation_group': tg,
            }
            for tg, members in groups.items()
            if len(members) == 1
        ]

        result = {
            'mode': 'site',
            'site_id': site.id,
            'expected_languages': expected_langs,
            'total_groups': len(groups),
            'groups_complete': groups_complete,
            'groups_incomplete': groups_incomplete,
            'single_lang_orphans': single_lang_orphans[:50],
            'orphan_count': len(single_lang_orphans),
        }
        cache.set(cache_key, result, timeout=300)
        return Response(result)


class BulkSEOAuditView(APIView):
    """Run SEO audit on all published articles of a site, return aggregate stats.

    Synchronous for MVP (capped at limit articles). Each per-article audit uses
    the same cache as SEOAuditView, so re-runs are cheap once warm.

    GET /sites/<site_id>/audit-all/?limit=50&language=fr
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, site_id):
        from collections import Counter

        site = get_site_for_user(request, site_id)
        try:
            limit = max(1, min(int(request.query_params.get('limit', 50)), 100))
        except (TypeError, ValueError):
            limit = 50
        language_filter = request.query_params.get('language')

        api_key = os.environ.get('GEMINI_API_KEY')
        if not api_key:
            return Response(
                {'error': 'GEMINI_API_KEY non configuree'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # Fetch published articles
        if site.is_hosted:
            qs = HostedPost.objects.filter(site=site, status='published')
            if language_filter:
                qs = qs.filter(language=language_filter)
            qs = qs.order_by('-published_at')[:limit]
            articles = [
                {
                    'slug': p.slug,
                    'title': p.title,
                    'excerpt': p.excerpt or '',
                    'content': p.content or '',
                    'language': p.language or 'fr',
                }
                for p in qs
            ]
        else:
            try:
                alias = ensure_site_connection(site)
            except ValueError:
                return Response(
                    {'error': "Cette action nécessite une base de données externe configurée pour ce site."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            qs = BlogPost.objects.using(alias).filter(status='published')
            if language_filter:
                qs = qs.filter(language=language_filter)
            qs = qs.order_by('-published_at')[:limit]
            articles = [
                {
                    'slug': p.slug,
                    'title': p.title,
                    'excerpt': getattr(p, 'excerpt', '') or '',
                    'content': getattr(p, 'content', '') or '',
                    'language': getattr(p, 'language', 'fr') or 'fr',
                }
                for p in qs
            ]

        if not articles:
            return Response({
                'site_id': site.id,
                'audited_count': 0,
                'failed_count': 0,
                'mean_score': None,
                'distribution': {'excellent': 0, 'good': 0, 'average': 0, 'poor': 0},
                'top_weaknesses': [],
                'top_actions': [],
                'weakest_articles': [],
                'audited_articles': [],
            })

        # Audit each article in parallel - serial Gemini calls would blow
        # gunicorn's 30s timeout at ~5-8s per article (so anything past 4-5
        # articles hangs the worker). With max_workers=5 a batch of 10 takes
        # ~max(latency) instead of sum(latency). Cached articles (same content
        # hash) skip the API call entirely so re-runs are essentially free.
        from concurrent.futures import ThreadPoolExecutor

        def _audit_one(art):
            if not art['title'] or not art['content']:
                return None
            try:
                result, from_cache = _run_seo_audit(
                    art['title'], art['excerpt'], art['content'],
                    keyword='', language=art['language'], api_key=api_key,
                )
                return {
                    'slug': art['slug'],
                    'title': art['title'],
                    'language': art['language'],
                    'score': result['score'],
                    'verdict': result['verdict'],
                    'weaknesses': result['weaknesses'],
                    'actions': result['actions'],
                    '_from_cache': from_cache,
                }
            except Exception as e:
                logger.warning('Bulk audit failed for %s: %s', art['slug'], e)
                return {
                    'slug': art['slug'],
                    'title': art['title'],
                    'language': art['language'],
                    'score': None,
                    'error': str(e),
                }

        per_article = []
        cache_hits = 0
        with ThreadPoolExecutor(max_workers=5) as pool:
            for entry in pool.map(_audit_one, articles):
                if entry is None:
                    continue
                if entry.pop('_from_cache', False):
                    cache_hits += 1
                per_article.append(entry)

        scored = [a for a in per_article if a.get('score') is not None]
        failed = len(per_article) - len(scored)
        scores = [a['score'] for a in scored]

        if scores:
            mean_score = round(sum(scores) / len(scores), 1)
        else:
            mean_score = None

        distribution = {
            'excellent': sum(1 for s in scores if s >= 85),
            'good': sum(1 for s in scores if 70 <= s < 85),
            'average': sum(1 for s in scores if 50 <= s < 70),
            'poor': sum(1 for s in scores if s < 50),
        }

        weakness_counter = Counter()
        action_counter = Counter()
        for a in scored:
            for w in a.get('weaknesses', []):
                if isinstance(w, str) and w.strip():
                    # Normalize keep-first-words for grouping similar items
                    weakness_counter[w.strip()[:80]] += 1
            for ac in a.get('actions', []):
                if isinstance(ac, str) and ac.strip():
                    action_counter[ac.strip()[:80]] += 1

        weakest = sorted(scored, key=lambda x: x['score'])[:10]

        return Response({
            'site_id': site.id,
            'audited_count': len(scored),
            'failed_count': failed,
            'cache_hits': cache_hits,
            'mean_score': mean_score,
            'distribution': distribution,
            'top_weaknesses': [
                {'text': text, 'count': count}
                for text, count in weakness_counter.most_common(10)
            ],
            'top_actions': [
                {'text': text, 'count': count}
                for text, count in action_counter.most_common(10)
            ],
            'weakest_articles': [
                {
                    'slug': a['slug'],
                    'title': a['title'],
                    'language': a.get('language'),
                    'score': a['score'],
                    'verdict': a.get('verdict', ''),
                }
                for a in weakest
            ],
        })


class PAAView(APIView):
    """Harvest People Also Ask questions from Google SERP, optionally generate
    short answers via Gemini, and return both the raw list and a ready-to-paste
    FAQPage JSON-LD schema.

    Input: {keyword, language: 'fr'|'en'|'es', generate_answers?: bool}
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    throttle_scope = 'ai_generate'

    def post(self, request):
        import json

        keyword = (request.data.get('keyword') or '').strip()
        language = (request.data.get('language') or 'fr').strip().lower()
        generate_answers = bool(request.data.get('generate_answers', True))

        if not keyword:
            return Response(
                {'error': 'Le mot-cle cible est requis'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if language not in ('fr', 'en', 'es'):
            return Response(
                {'error': "Langue invalide (fr, en, es)"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serper_key = os.environ.get('SERPER_API_KEY')
        if not serper_key:
            return Response(
                {'error': 'SERPER_API_KEY non configuree'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        cache_key = _seo_cache_key(
            'paa:', keyword, language, '1' if generate_answers else '0'
        )
        cached = cache.get(cache_key)
        if cached:
            return Response(cached)

        hl, gl = ('en', 'us') if language == 'en' else (
            ('es', 'es') if language == 'es' else ('fr', 'ca')
        )

        # 1) Serper - peopleAlsoAsk
        try:
            resp = http_requests.post(
                'https://google.serper.dev/search',
                headers={
                    'X-API-KEY': serper_key,
                    'Content-Type': 'application/json',
                },
                json={'q': keyword, 'num': 10, 'hl': hl, 'gl': gl},
                timeout=10,
            )
        except http_requests.Timeout:
            return Response(
                {'error': 'Delai de requete Serper depasse'},
                status=status.HTTP_504_GATEWAY_TIMEOUT,
            )
        except Exception as e:
            return Response(
                {'error': f'Erreur Serper: {str(e)}'},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        if resp.status_code != 200:
            return Response(
                {'error': f'Erreur Serper: {resp.status_code}'},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        data = resp.json() or {}
        raw_paa = data.get('peopleAlsoAsk') or []
        questions = []
        for item in raw_paa[:10]:
            q = (item or {}).get('question')
            snippet = (item or {}).get('snippet') or ''
            if q:
                questions.append({
                    'question': q.strip(),
                    'snippet': snippet.strip(),
                    'answer': '',
                })

        if not questions:
            result = {
                'keyword': keyword,
                'language': language,
                'questions': [],
                'faq_schema': None,
            }
            cache.set(cache_key, result, SEO_CACHE_TTL)
            return Response(result)

        # 2) Gemini - short answers (best-effort; if it fails, fall back to snippet)
        if generate_answers:
            gemini_key = os.environ.get('GEMINI_API_KEY')
            if gemini_key:
                try:
                    from google import genai

                    lang_label = {
                        'fr': 'French (Quebec)',
                        'en': 'English',
                        'es': 'Spanish',
                    }[language]
                    qlist = '\n'.join(
                        f"{i+1}. {q['question']}" for i, q in enumerate(questions)
                    )
                    prompt = f"""You are a helpful expert. Below are {len(questions)} questions
that people search on Google around the keyword "{keyword}". Answer each in 1-2
factual, concise sentences in {lang_label}. Stay on-topic. No preamble, no marketing.

Questions:
{qlist}

Respond with JSON only:
{{"answers": ["answer 1", "answer 2", ...]}}
The answers array MUST have exactly {len(questions)} entries, in the same order."""

                    client = genai.Client(api_key=gemini_key)
                    g_resp = client.models.generate_content(
                        model="gemini-2.5-flash",
                        contents=[prompt],
                    )
                    text = (g_resp.text or '').strip()
                    if text.startswith('```'):
                        text = text.split('\n', 1)[1]
                        if text.endswith('```'):
                            text = text[:-3]
                        text = text.strip()
                    parsed = json.loads(text)
                    answers = parsed.get('answers') or []
                    for i, ans in enumerate(answers[:len(questions)]):
                        if isinstance(ans, str) and ans.strip():
                            questions[i]['answer'] = ans.strip()
                except Exception as e:
                    logger.warning('Gemini PAA answers failed: %s', e)

            # Fallback: use Serper snippet when no Gemini answer
            for q in questions:
                if not q['answer'] and q['snippet']:
                    q['answer'] = q['snippet']

        # 3) Build FAQPage JSON-LD schema (only includes questions with answers)
        answered = [q for q in questions if q['answer']]
        if answered:
            faq_schema = {
                '@context': 'https://schema.org',
                '@type': 'FAQPage',
                'mainEntity': [
                    {
                        '@type': 'Question',
                        'name': q['question'],
                        'acceptedAnswer': {
                            '@type': 'Answer',
                            'text': q['answer'],
                        },
                    }
                    for q in answered
                ],
            }
        else:
            faq_schema = None

        result = {
            'keyword': keyword,
            'language': language,
            'questions': questions,
            'faq_schema': faq_schema,
        }
        cache.set(cache_key, result, SEO_CACHE_TTL)
        return Response(result)


class ImageSEOSuggestView(APIView):
    """Use Gemini Vision to inspect an image and suggest SEO-friendly alt
    text + descriptive filename slug. Article context (title, keyword,
    language) is used to tailor the suggestion to the surrounding content.

    POST /image-suggest/ {image_url, article_title?, keyword?, language='fr'}
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    throttle_scope = 'ai_generate'

    def post(self, request):
        import json

        image_url = (request.data.get('image_url') or '').strip()
        article_title = (request.data.get('article_title') or '').strip()
        keyword = (request.data.get('keyword') or '').strip()
        language = (request.data.get('language') or 'fr').strip().lower()

        if not image_url:
            return Response(
                {'error': 'image_url requis'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not image_url.startswith(('http://', 'https://')):
            return Response(
                {'error': 'image_url doit etre une URL HTTP(S)'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        gemini_key = os.environ.get('GEMINI_API_KEY')
        if not gemini_key:
            return Response(
                {'error': 'GEMINI_API_KEY non configuree'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        cache_key = _seo_cache_key(
            'image-suggest:', image_url, article_title, keyword, language
        )
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)

        # Fetch the image bytes
        try:
            resp = http_requests.get(
                image_url,
                timeout=10,
                headers={'User-Agent': 'Mozilla/5.0 BlogDashboard/1.0'},
            )
            if not resp.ok or not resp.content:
                return Response(
                    {'error': 'Impossible de telecharger l\'image'},
                    status=status.HTTP_502_BAD_GATEWAY,
                )
            image_bytes = resp.content
            mime_type = resp.headers.get('Content-Type', 'image/jpeg').split(';')[0].strip()
            if not mime_type.startswith('image/'):
                mime_type = 'image/jpeg'
        except Exception as e:
            return Response(
                {'error': f'Erreur telechargement image: {str(e)[:100]}'},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        lang_label = {
            'fr': 'French (Quebec)',
            'en': 'English',
            'es': 'Spanish',
        }.get(language, 'French')

        context_block = ''
        if article_title:
            context_block += f"Article title: {article_title}\n"
        if keyword:
            context_block += f"Target keyword: {keyword}\n"

        prompt = f"""You are an SEO expert. Look at this image and suggest:
1. A descriptive alt text (under 125 chars) in {lang_label}, accurate to the
   image, and naturally including the target keyword if it fits without forcing.
2. A short URL-friendly filename slug (3-6 words, lowercase, hyphens, in
   {lang_label} stripped of accents) that describes the image content.
3. A 1-sentence description of what's in the image.

{context_block}
Respond with JSON only (no markdown):
{{
  "alt_text": "...",
  "filename_slug": "...",
  "description": "..."
}}"""

        try:
            from google import genai
            from google.genai import types as genai_types

            client = genai.Client(api_key=gemini_key)
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[
                    genai_types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                    prompt,
                ],
            )
            text = (response.text or '').strip()
            if text.startswith('```'):
                text = text.split('\n', 1)[1]
                if text.endswith('```'):
                    text = text[:-3]
                text = text.strip()
            data = json.loads(text)
        except Exception as e:
            logger.warning('Gemini image suggest failed: %s', e)
            return Response(
                {'error': f'Erreur Gemini: {str(e)[:120]}'},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        result = {
            'alt_text': (data.get('alt_text') or '').strip()[:200],
            'filename_slug': slugify((data.get('filename_slug') or '').strip())[:80],
            'description': (data.get('description') or '').strip(),
        }
        cache.set(cache_key, result, timeout=86400)  # 24h
        return Response(result)


class SearchTrendsView(APIView):
    """Google Trends data via pytrends - interest over time + related/rising
    queries for a keyword. Geo-scoped to Quebec / Canada / France / US per
    language. Cached 24h (trends move slowly).

    POST /trends/ {keyword, language='fr', timeframe='today 12-m'}
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        keyword = (request.data.get('keyword') or '').strip()
        language = (request.data.get('language') or 'fr').strip().lower()
        timeframe = (request.data.get('timeframe') or 'today 12-m').strip()

        if not keyword:
            return Response(
                {'error': 'Le mot-cle est requis'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if language not in ('fr', 'en', 'es'):
            return Response(
                {'error': "Langue invalide (fr, en, es)"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        cache_key = _seo_cache_key('trends:', keyword, language, timeframe)
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)

        # Geo + hl mapping. For FR sites, prefer Quebec (CA) but fall back to FR.
        if language == 'en':
            geo = 'US'
            hl = 'en-US'
        elif language == 'es':
            geo = 'ES'
            hl = 'es-ES'
        else:
            geo = 'CA'  # Canada - pytrends doesn't support sub-region directly for this query
            hl = 'fr-CA'

        try:
            from pytrends.request import TrendReq
        except ImportError:
            return Response(
                {'error': 'pytrends non installe sur le serveur'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        # pytrends 4.9 hasn't been updated since 2022 and internally constructs
        # urllib3.Retry(method_whitelist=...), a kwarg that was removed in
        # urllib3 2.0 (renamed to allowed_methods). Monkey-patch once at the
        # call site so we don't have to pin urllib3<2 globally (which would
        # break other libs). Idempotent via a sentinel attribute.
        from urllib3.util.retry import Retry
        if not getattr(Retry, '_patched_method_whitelist', False):
            _orig_init = Retry.__init__

            def _patched_init(self, *args, **kwargs):
                if 'method_whitelist' in kwargs:
                    kwargs['allowed_methods'] = kwargs.pop('method_whitelist')
                return _orig_init(self, *args, **kwargs)

            Retry.__init__ = _patched_init
            Retry._patched_method_whitelist = True

        try:
            pytrends = TrendReq(hl=hl, tz=300, retries=2, backoff_factor=0.5)
            pytrends.build_payload(
                kw_list=[keyword], cat=0, timeframe=timeframe, geo=geo, gprop=''
            )

            # Interest over time (DataFrame)
            iot = pytrends.interest_over_time()
            interest_over_time = []
            if not iot.empty and keyword in iot.columns:
                for ts, value in iot[keyword].items():
                    try:
                        interest_over_time.append({
                            'date': ts.strftime('%Y-%m-%d'),
                            'value': int(value),
                        })
                    except Exception:
                        continue

            # Related queries: dict {keyword: {'top': df, 'rising': df}}
            related = pytrends.related_queries() or {}
            related_for_kw = related.get(keyword) or {}
            top_df = related_for_kw.get('top')
            rising_df = related_for_kw.get('rising')

            top_queries = []
            if top_df is not None and not top_df.empty:
                for _, row in top_df.head(10).iterrows():
                    top_queries.append({
                        'query': str(row.get('query', '')),
                        'value': int(row.get('value', 0)),
                    })

            rising_queries = []
            if rising_df is not None and not rising_df.empty:
                for _, row in rising_df.head(10).iterrows():
                    rising_queries.append({
                        'query': str(row.get('query', '')),
                        'value': int(row.get('value', 0)),
                    })
        except Exception as e:
            logger.warning('pytrends failed for %s: %s', keyword, e)
            return Response(
                {'error': f'Erreur Trends (probable rate-limit Google): {str(e)[:120]}'},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        result = {
            'keyword': keyword,
            'language': language,
            'geo': geo,
            'timeframe': timeframe,
            'interest_over_time': interest_over_time,
            'top_queries': top_queries,
            'rising_queries': rising_queries,
        }
        cache.set(cache_key, result, timeout=86400)  # 24h
        return Response(result)


class PlagiarismCheckView(APIView):
    """Check an article for AI-generated content + plagiarism via Originality.ai.

    POST /plagiarism-check/ {title, content, language='fr'}

    Reads ORIGINALITY_API_KEY from env. Returns {ai_score, plagiarism_score,
    sources_matched, full_response}. ai_score is the % of content detected as
    AI-generated (0-100). plagiarism_score is the % matched to existing web
    content. Scores ≥50 are flagged.

    Cached 1h per content hash.
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    throttle_scope = 'ai_generate'

    def post(self, request):
        title = (request.data.get('title') or '').strip()
        content = (request.data.get('content') or '').strip()
        language = (request.data.get('language') or 'fr').strip().lower()

        if not content or len(content) < 50:
            return Response(
                {'error': 'Contenu trop court pour analyse (50 caractères minimum).'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        api_key = os.environ.get('ORIGINALITY_API_KEY')
        if not api_key:
            return Response(
                {'error': 'ORIGINALITY_API_KEY non configurée. Configure-la sur Railway pour activer ce module.',
                 'code': 'plagiarism_not_configured'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        cache_key = _seo_cache_key('plagiarism:', title, content[:5000])
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)

        try:
            resp = http_requests.post(
                'https://api.originality.ai/api/v1/scan/ai-and-plagiarism',
                headers={
                    'X-OAI-API-KEY': api_key,
                    'Accept': 'application/json',
                    'Content-Type': 'application/json',
                },
                json={
                    'title': title or 'Untitled',
                    'content': content[:50000],
                    'aiModelVersion': '3.0',
                    'storeScan': 'false',
                },
                timeout=60,
            )
        except http_requests.Timeout:
            return Response(
                {'error': 'Timeout Originality.ai (60s).'},
                status=status.HTTP_504_GATEWAY_TIMEOUT,
            )
        except Exception as e:
            return Response(
                {'error': f'Erreur Originality.ai: {str(e)[:120]}'},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        if resp.status_code != 200:
            return Response(
                {'error': f'Originality.ai {resp.status_code}: {resp.text[:200]}'},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        data = resp.json() or {}

        # Extract scores - defensive parsing since the API shape can vary
        ai_score_raw = (
            data.get('aiScore')
            or data.get('ai', {}).get('score')
            or 0
        )
        plagiarism_raw = (
            data.get('plagiarismScore')
            or data.get('plagiarism', {}).get('score')
            or 0
        )
        try:
            ai_score = round(float(ai_score_raw) * (100 if ai_score_raw <= 1 else 1), 1)
        except (TypeError, ValueError):
            ai_score = 0.0
        try:
            plagiarism_score = round(
                float(plagiarism_raw) * (100 if plagiarism_raw <= 1 else 1), 1
            )
        except (TypeError, ValueError):
            plagiarism_score = 0.0

        sources = data.get('plagiarism', {}).get('matches') or data.get('matches') or []
        sources_matched = [
            {
                'url': s.get('url', ''),
                'percent': s.get('percent') or s.get('score') or 0,
                'snippet': (s.get('snippet') or s.get('text') or '')[:200],
            }
            for s in sources[:5]
            if isinstance(s, dict)
        ]

        result = {
            'ai_score': ai_score,
            'plagiarism_score': plagiarism_score,
            'sources_matched': sources_matched,
            'verdict': self._verdict(ai_score, plagiarism_score, language),
            'credits_used': data.get('credits_used'),
        }
        cache.set(cache_key, result, timeout=SEO_CACHE_TTL)
        return Response(result)

    def _verdict(self, ai_score, plagiarism, lang):
        if ai_score >= 80 and plagiarism < 20:
            return ("Contenu très probablement IA (sans plagiat). "
                    "Ajoute des anecdotes, des données spécifiques, des citations "
                    "pour humaniser.")
        if plagiarism >= 30:
            return (f"Plagiat détecté ({plagiarism:.1f}%). "
                    "Réécris les passages signalés ou cite explicitement les sources.")
        if ai_score >= 50:
            return ("Contenu mixte IA/humain. Acceptable, mais ajoute des "
                    "éléments personnels (photos, expérience, opinion).")
        if ai_score < 30 and plagiarism < 10:
            return "Contenu humain et original. Excellent pour Google."
        return "Score acceptable, pas d'action urgente."


class CommunityQuestionsView(APIView):
    """Harvest questions and discussions about a keyword from Reddit and Quora
    via Serper. Useful to find the real-world phrasing people use when they
    have a problem in your topic area - strong source of long-tail headings
    and FAQ content.

    POST /community-questions/ {keyword, language: 'fr'|'en'|'es'}
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    throttle_scope = 'ai_generate'

    def post(self, request):
        keyword = (request.data.get('keyword') or '').strip()
        language = (request.data.get('language') or 'fr').strip().lower()

        if not keyword:
            return Response(
                {'error': 'Le mot-cle est requis'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if language not in ('fr', 'en', 'es'):
            return Response(
                {'error': "Langue invalide (fr, en, es)"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        api_key = os.environ.get('SERPER_API_KEY')
        if not api_key:
            return Response(
                {'error': 'SERPER_API_KEY non configuree'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        cache_key = _seo_cache_key('community-questions:', keyword, language)
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)

        hl, gl = ('en', 'us') if language == 'en' else (
            ('es', 'es') if language == 'es' else ('fr', 'ca')
        )

        def _query(domain):
            try:
                resp = http_requests.post(
                    'https://google.serper.dev/search',
                    headers={
                        'X-API-KEY': api_key,
                        'Content-Type': 'application/json',
                    },
                    json={
                        'q': f'site:{domain} {keyword}',
                        'num': 10,
                        'hl': hl,
                        'gl': gl,
                    },
                    timeout=10,
                )
                if resp.status_code != 200:
                    return []
                return (resp.json() or {}).get('organic') or []
            except Exception as e:
                logger.warning('Serper community query failed (%s): %s', domain, e)
                return []

        reddit = _query('reddit.com')
        quora = _query('quora.com')

        def _format(items, source):
            out = []
            for item in items[:10]:
                title = (item.get('title') or '').strip()
                snippet = (item.get('snippet') or '').strip()
                url = item.get('link') or ''
                # Strip site name suffix from titles like "X : a question - r/foo - Reddit"
                cleaned_title = title.rsplit(' - ', 1)[0] if ' - ' in title else title
                if title:
                    out.append({
                        'title': cleaned_title,
                        'snippet': snippet,
                        'url': url,
                        'source': source,
                    })
            return out

        results = _format(reddit, 'reddit') + _format(quora, 'quora')

        result = {
            'keyword': keyword,
            'language': language,
            'reddit_count': len(reddit),
            'quora_count': len(quora),
            'questions': results,
        }
        cache.set(cache_key, result, timeout=SEO_CACHE_TTL)
        return Response(result)


class BrokenLinksView(APIView):
    """Scan a site's published articles for outbound HTTP(S) links and report
    those that are dead (4xx/5xx, timeout, connection error).

    GET/POST /sites/<site_id>/broken-links/?limit=100&language=fr

    Each unique URL is checked once via HEAD (with GET fallback for servers
    that reject HEAD), cached 24h. Returns the broken URLs grouped by URL,
    each pointing back to the articles where it appears.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, site_id):
        # The v1 API exposes this as GET; post() already reads its params
        # from the query string too.
        return self.post(request, site_id)

    def post(self, request, site_id):
        import re as _re

        site = get_site_for_user(request, site_id)
        try:
            limit = max(5, min(int(
                request.data.get('limit') or request.query_params.get('limit') or 100
            ), 200))
        except (TypeError, ValueError):
            limit = 100
        language_filter = (
            request.data.get('language') or request.query_params.get('language') or ''
        ).strip().lower() or None

        # Domain to know what's "internal" - we skip internal links here.
        site_domain = (site.domain or '').lower().replace('https://', '').replace('http://', '').rstrip('/')

        # Fetch published articles
        if site.is_hosted:
            qs = HostedPost.objects.filter(site=site, status='published')
            if language_filter:
                qs = qs.filter(language=language_filter)
            qs = qs.order_by('-published_at')[:limit]
            articles = [
                {'slug': p.slug, 'title': p.title, 'content': p.content or ''}
                for p in qs
            ]
        else:
            try:
                alias = ensure_site_connection(site)
            except ValueError:
                return Response(
                    {'error': "Cette action nécessite une base de données externe configurée pour ce site."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            qs = BlogPost.objects.using(alias).filter(status='published')
            if language_filter:
                qs = qs.filter(language=language_filter)
            qs = qs.order_by('-published_at')[:limit]
            articles = [
                {'slug': p.slug, 'title': p.title,
                 'content': getattr(p, 'content', '') or ''}
                for p in qs
            ]

        url_re = _re.compile(r'https?://[^\s\)<>"\']+', _re.IGNORECASE)
        markdown_link_re = _re.compile(r'\[[^\]]*\]\((https?://[^)]+)\)')
        html_href_re = _re.compile(
            r'<a\b[^>]*\bhref=["\'](https?://[^"\']+)["\']', _re.IGNORECASE
        )

        # Map url -> list of (slug, title)
        url_to_articles = {}
        for art in articles:
            content = art['content']
            urls = set()
            for m in markdown_link_re.finditer(content):
                urls.add(m.group(1).rstrip('.,;:'))
            for m in html_href_re.finditer(content):
                urls.add(m.group(1).rstrip('.,;:'))
            # Plain URLs in text (rare in markdown but covered)
            for m in url_re.finditer(content):
                urls.add(m.group(0).rstrip('.,;:'))

            for url in urls:
                # Skip internal links
                if site_domain and site_domain in url.lower():
                    continue
                # Skip non-content links (mailto, tel, etc. - already filtered by regex but defense)
                if not url.startswith(('http://', 'https://')):
                    continue
                url_to_articles.setdefault(url, []).append(
                    {'slug': art['slug'], 'title': art['title']}
                )

        if not url_to_articles:
            return Response({
                'site_id': site.id,
                'checked_count': 0,
                'broken_count': 0,
                'broken_links': [],
                'note': 'Aucun lien externe HTTP(S) trouve dans les articles.',
            })

        # Check each unique URL (cached 24h)
        broken = []
        checked = 0
        for url in list(url_to_articles.keys()):
            cache_key = _seo_cache_key('broken-link:', url)
            cached = cache.get(cache_key)
            if cached is not None:
                status_code, error = cached
            else:
                status_code, error = self._check_url(url)
                cache.set(cache_key, (status_code, error), timeout=86400)  # 24h
            checked += 1
            is_broken = (
                error is not None
                or (status_code is not None and status_code >= 400)
            )
            if is_broken:
                broken.append({
                    'url': url,
                    'status_code': status_code,
                    'error': error or '',
                    'articles': url_to_articles[url][:20],  # cap at 20 articles
                    'article_count': len(url_to_articles[url]),
                })

        # Sort: errors first, then by status code descending (5xx before 4xx)
        broken.sort(key=lambda b: (
            -1 if b['error'] else -(b['status_code'] or 0),
            -b['article_count'],
        ))

        return Response({
            'site_id': site.id,
            'checked_count': checked,
            'broken_count': len(broken),
            'broken_links': broken,
        })

    def _check_url(self, url):
        """Probe a URL. Returns (status_code, error). status_code may be None
        if the request failed before getting a response."""
        try:
            resp = http_requests.head(
                url,
                timeout=5,
                allow_redirects=True,
                headers={'User-Agent': 'Mozilla/5.0 BlogDashboard/1.0'},
            )
            # Some servers return 405/403 on HEAD but work on GET - try GET.
            if resp.status_code in (403, 405, 501):
                try:
                    resp = http_requests.get(
                        url,
                        timeout=6,
                        allow_redirects=True,
                        stream=True,
                        headers={'User-Agent': 'Mozilla/5.0 BlogDashboard/1.0'},
                    )
                    resp.close()
                except Exception:
                    pass  # fall through, keep HEAD result
            return resp.status_code, None
        except http_requests.Timeout:
            return None, 'timeout'
        except http_requests.ConnectionError:
            return None, 'connection_error'
        except Exception as e:
            return None, str(e)[:100]


# Common French France → French Quebec lexicon. Each entry is
# (word_or_phrase_to_flag, suggested_quebecois, optional_explanation).
# Lowercased; matched as whole words (word-boundary regex).
QUEBECOIS_LEXICON = [
    # Lifestyle / commerce
    ('shopping', 'magasinage', "Au Québec on dit magasiner."),
    ('faire les magasins', 'magasiner', None),
    ('week-end', 'fin de semaine', None),
    ('weekend', 'fin de semaine', None),
    ('parking', 'stationnement', None),
    ('park-vehicule', 'stationnement', None),
    ('email', 'courriel', None),
    ('e-mail', 'courriel', None),
    ('mail', 'courriel', "Au Québec mail = courrier postal, pas électronique."),
    ('newsletter', 'infolettre', None),
    ('spam', 'pourriel', None),
    ('chat', 'clavardage', "Pour la conversation en ligne. Pour l'animal, chat est correct."),
    ('podcast', 'baladodiffusion', None),
    ('podcasts', 'baladodiffusions', None),
    ('smartphone', 'téléphone intelligent', None),
    ('smartphones', 'téléphones intelligents', None),
    ('streaming', 'diffusion en continu', None),

    # Education / work
    ('lycée', 'cégep ou école secondaire', "Le système québécois utilise cégep + secondaire."),
    ('lycéen', 'cégépien ou élève du secondaire', None),
    ('lycéenne', 'cégépienne ou élève du secondaire', None),
    ('bac', 'baccalauréat', "Le bac québécois = diplôme universitaire, pas le bac de France."),
    ('CAP', 'DEP', "DEP = Diplôme d'études professionnelles."),
    ('intérimaire', 'temporaire', None),
    ('intérim', 'travail temporaire', None),
    ('stagiaire', 'stagiaire', None),  # acceptable
    ('emploi à plein temps', 'emploi à temps plein', None),
    ('plein temps', 'temps plein', None),

    # Money / numbers
    ('TVA', 'TPS et TVQ', "Au Québec: TPS (5% fédéral) + TVQ (9.975% provincial)."),
    ('SARL', 'inc. ou SENC', "Société québécoise: Inc. (équivalent SARL)."),
    ('PME', 'PME', None),  # acceptable
    ('CDI', 'emploi permanent', None),
    ('CDD', 'contrat à durée déterminée', None),
    ('SMIC', 'salaire minimum', None),
    ('cagnotte', 'collecte de fonds', None),

    # Food / hospitality
    ('petit déjeuner', 'déjeuner', "Au Québec, déjeuner = matin, dîner = midi, souper = soir."),
    ('petit-déjeuner', 'déjeuner', None),
    ('déjeuner', 'dîner', None),  # When meaning the noon meal, in Quebec dîner = noon
    ('dîner', 'souper', None),    # When meaning evening meal
    ('boulot', 'travail', "Boulot = très familier France."),
    ('chéri', 'mon chum / ma blonde', None),

    # Cars / transport
    ('voiture', 'auto / char', None),  # both used in QC
    ('moto', 'moto', None),
    ('tramway', 'tramway', None),
    ('métro', 'métro', None),

    # Tech / IT
    ('mot de passe oublié', 'mot de passe oublié', None),
    ('login', 'identifiant', None),
    ('blogger', 'blogueur', None),
    ('bloguer', 'bloguer', None),
    ('e-commerce', 'commerce en ligne', None),
    ('startup', 'jeune pousse', "Anglicisme accepté, mais 'jeune pousse' est l'équivalent OQLF."),

    # Daily life
    ('soldes', 'rabais', None),
    ('soirée', 'veillée', None),
    ('embouteillage', 'bouchon de circulation', None),
    ('ticket', 'billet', None),
    ('tickets', 'billets', None),
]


def _quebecois_check(text):
    """Scan text for non-Quebecois terms and return matches with positions
    (line/column) so the frontend can highlight inline if it wants."""
    import re as _re

    if not text:
        return []

    # Sort longer phrases first so multi-word matches win over single-word
    sorted_lex = sorted(QUEBECOIS_LEXICON, key=lambda x: -len(x[0]))

    matches = []
    seen_terms = {}

    for term, suggestion, explanation in sorted_lex:
        # word-boundary regex, case-insensitive, hyphens treated as separators
        pattern = _re.compile(r'\b' + _re.escape(term) + r'\b', _re.IGNORECASE)
        positions = []
        for m in pattern.finditer(text):
            # Compute line + column
            prefix = text[: m.start()]
            line = prefix.count('\n') + 1
            col = m.start() - (prefix.rfind('\n') + 1) if '\n' in prefix else m.start() + 1
            positions.append({'line': line, 'col': col, 'matched_text': m.group(0)})
        if positions:
            key = term.lower()
            if key in seen_terms:
                continue
            seen_terms[key] = True
            matches.append({
                'term': term,
                'suggestion': suggestion,
                'explanation': explanation or '',
                'count': len(positions),
                'positions': positions[:20],
            })

    return matches


def _generate_person_schema(site):
    """Generate a Schema.org Person JSON-LD for the site's default author,
    using the EEAT fields configured on the Site. Returns None if there's no
    meaningful data (no name + no bio).
    """
    name = site.default_author or 'Admin'
    if not site.author_bio and not site.author_role and name == 'Admin':
        return None

    schema = {
        '@context': 'https://schema.org',
        '@type': 'Person',
        'name': name,
    }
    if site.author_role:
        schema['jobTitle'] = site.author_role
    if site.author_bio:
        schema['description'] = site.author_bio
    if site.author_image_url:
        schema['image'] = site.author_image_url
    if site.author_credentials:
        schema['hasCredential'] = site.author_credentials
    same_as = [
        u for u in (
            site.author_linkedin,
            site.author_twitter,
            site.author_website,
        ) if u
    ]
    if same_as:
        schema['sameAs'] = same_as
    if site.domain:
        url = site.domain
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        schema['worksFor'] = {
            '@type': 'Organization',
            'name': site.name,
            'url': url,
        }
    return schema


def _generate_local_business_schema(site, address=None, hours=None, phone=None,
                                    price_range=None, area_served=None):
    """Generate a Schema.org LocalBusiness JSON-LD adapted for Quebec.

    Defaults: addressCountry=CA, addressRegion=QC. Pass address dict with
    streetAddress/addressLocality/postalCode keys. hours is optional list of
    OpeningHoursSpecification dicts.
    """
    schema = {
        '@context': 'https://schema.org',
        '@type': 'LocalBusiness',
        'name': site.name,
    }
    if site.description:
        schema['description'] = site.description
    if site.domain:
        url = site.domain
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        schema['url'] = url
    if site.og_image_url:
        schema['image'] = site.og_image_url
    if phone:
        schema['telephone'] = phone
    if price_range:
        schema['priceRange'] = price_range
    if address:
        schema['address'] = {
            '@type': 'PostalAddress',
            'addressCountry': 'CA',
            'addressRegion': 'QC',
            **{k: v for k, v in address.items() if v},
        }
    if hours:
        schema['openingHoursSpecification'] = hours
    schema['areaServed'] = area_served or {
        '@type': 'AdministrativeArea',
        'name': 'Québec',
    }
    return schema


class LexiconCheckView(APIView):
    """Detect non-Quebecois (FR-FR) terms in content and suggest Quebec
    equivalents. Useful for sites targeting a Quebec audience.

    POST /lexicon-check/ {content: str}
    Returns: {matches: [{term, suggestion, explanation, count, positions}], total_matches}
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        content = request.data.get('content', '') or ''
        if not content.strip():
            return Response({'matches': [], 'total_matches': 0})

        matches = _quebecois_check(content)
        total = sum(m['count'] for m in matches)
        return Response({
            'matches': matches,
            'total_matches': total,
            'unique_terms': len(matches),
        })


class LocalBusinessSchemaView(APIView):
    """Generate a Schema.org LocalBusiness JSON-LD adapted for Quebec.

    POST /sites/<id>/local-business-schema/ {address?, hours?, phone?, price_range?, area_served?}
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, site_id):
        site = get_site_for_user(request, site_id)
        schema = _generate_local_business_schema(
            site,
            address=request.data.get('address'),
            hours=request.data.get('hours'),
            phone=request.data.get('phone'),
            price_range=request.data.get('price_range'),
            area_served=request.data.get('area_served'),
        )
        return Response({'schema': schema})


# ==========================================================================
# BILLING - Stripe subscriptions
# ==========================================================================

# Plan slug → env var of the Stripe Price ID. Configured by the operator.
PLAN_PRICE_ENV = {
    'solo': 'STRIPE_PRICE_SOLO',
    'pro': 'STRIPE_PRICE_PRO',
    'agency': 'STRIPE_PRICE_AGENCY',
}

# Legacy price-id env vars for plans with grandfathered subscribers.
# When the webhook receives a subscription event referencing one of these
# legacy prices, it still maps the user to the right plan tier (so old Pro
# subscribers at $79 stay 'pro' instead of being downgraded to 'free').
PLAN_PRICE_ENV_LEGACY = {
    'pro':    ['STRIPE_PRICE_PRO_LEGACY'],
    'agency': ['STRIPE_PRICE_AGENCY_LEGACY'],
}


def _get_or_create_subscription(user):
    sub, _ = Subscription.objects.get_or_create(user=user)
    return sub


def _serialize_subscription(sub):
    from .quota import get_articles_used, current_month_key, get_credit_balance
    used = get_articles_used(sub.user)
    return {
        'plan': sub.plan,
        'status': sub.status,
        'is_paid': sub.is_paid,
        'current_period_end': sub.current_period_end.isoformat() if sub.current_period_end else None,
        'cancel_at_period_end': sub.cancel_at_period_end,
        'limits': sub.get_limits(),
        'usage': {
            'articles_this_month': used,
            'month_key': current_month_key(),
        },
        'credits': {
            'balance': get_credit_balance(sub.user),
        },
    }


class BillingMeView(APIView):
    """GET /billing/me/ - current user's subscription state."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        sub = _get_or_create_subscription(request.user)
        return Response(_serialize_subscription(sub))


class BillingCreditsView(APIView):
    """GET /billing/credits/ - balance + recent transactions.
    POST /billing/credits/buy/ is on `BillingCreditsCheckoutView` below.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from .quota import get_credit_balance, CREDIT_PACKS
        from .models import CreditTransaction
        recent = CreditTransaction.objects.filter(
            user=request.user
        ).order_by('-created_at')[:30]
        return Response({
            'balance': get_credit_balance(request.user),
            'transactions': [
                {
                    'amount': t.amount,
                    'kind': t.kind,
                    'description': t.description,
                    'created_at': t.created_at.isoformat(),
                }
                for t in recent
            ],
            'packs': [
                {
                    'key': k,
                    'credits': v['credits'],
                    'price_cad': v['price_cents'] / 100,
                    'label': v['label'],
                }
                for k, v in CREDIT_PACKS.items()
            ],
        })


class BillingCreditsCheckoutView(APIView):
    """POST /billing/credits/buy/ {pack: 'small'|'medium'|'large'}
    Creates a Stripe Checkout session in mode='payment' (one-time charge).
    On success, the webhook handler `checkout.session.completed` adds credits
    to the user's balance.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from .quota import CREDIT_PACKS
        pack = (request.data.get('pack') or '').strip()
        if pack not in CREDIT_PACKS:
            return Response(
                {'error': "Pack invalide. Valides: 'small', 'medium', 'large'."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        secret = os.environ.get('STRIPE_SECRET_KEY')
        if not secret:
            return Response(
                {'error': 'STRIPE_SECRET_KEY non configurée'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        env_key = CREDIT_PACKS[pack]['env']
        price_id = os.environ.get(env_key)
        if not price_id:
            return Response(
                {'error': f"{env_key} non configuré"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        sub = _get_or_create_subscription(request.user)
        import stripe
        stripe.api_key = secret
        frontend_base = os.environ.get(
            'FRONTEND_BASE_URL', 'https://blog-dashboard-ebon.vercel.app'
        )
        try:
            kwargs = dict(
                mode='payment',
                line_items=[{'price': price_id, 'quantity': 1}],
                success_url=f'{frontend_base}/billing?credits=success',
                cancel_url=f'{frontend_base}/billing?credits=cancel',
                metadata={
                    'user_id': str(request.user.id),
                    'pack': pack,
                    'credits': str(CREDIT_PACKS[pack]['credits']),
                },
                # Important: pre-fill so Stripe attaches the new payment to the
                # same customer record as their subscription, if any.
            )
            if sub.stripe_customer_id:
                kwargs['customer'] = sub.stripe_customer_id
            elif request.user.email:
                kwargs['customer_email'] = request.user.email
            session = stripe.checkout.Session.create(**kwargs)
        except Exception as e:
            logger.exception('Credits checkout failed')
            return Response(
                {'error': f'Erreur Stripe: {str(e)[:120]}'},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response({'url': session.url})


class BillingCheckoutView(APIView):
    """POST /billing/checkout/ {plan: 'pro'|'agency'} → returns Stripe Checkout URL.

    Frontend redirects the user to that URL. After payment, Stripe redirects
    back to /billing/success and /billing/cancel based on the URLs we pass.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        plan = (request.data.get('plan') or '').strip().lower()
        if plan not in PLAN_PRICE_ENV:
            return Response(
                {'error': "Plan invalide (pro, agency)"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        secret = os.environ.get('STRIPE_SECRET_KEY')
        if not secret:
            return Response(
                {'error': 'STRIPE_SECRET_KEY non configurée'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        price_id = os.environ.get(PLAN_PRICE_ENV[plan])
        if not price_id:
            return Response(
                {'error': f"{PLAN_PRICE_ENV[plan]} non configuré"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        import stripe
        stripe.api_key = secret

        sub = _get_or_create_subscription(request.user)
        # Create a Stripe Customer if we don't have one yet
        if not sub.stripe_customer_id:
            try:
                customer = stripe.Customer.create(
                    email=request.user.email or None,
                    name=request.user.username,
                    metadata={'user_id': str(request.user.id)},
                )
                sub.stripe_customer_id = customer.id
                sub.save(update_fields=['stripe_customer_id'])
            except Exception as e:
                return Response(
                    {'error': f'Erreur Stripe: {str(e)[:120]}'},
                    status=status.HTTP_502_BAD_GATEWAY,
                )

        # Build success/cancel URLs
        frontend_base = os.environ.get('FRONTEND_BASE_URL', 'https://blog-dashboard-ebon.vercel.app')

        try:
            session = stripe.checkout.Session.create(
                customer=sub.stripe_customer_id,
                mode='subscription',
                line_items=[{'price': price_id, 'quantity': 1}],
                success_url=f'{frontend_base}/billing?status=success',
                cancel_url=f'{frontend_base}/billing?status=cancel',
                allow_promotion_codes=True,
                metadata={'user_id': str(request.user.id), 'plan': plan},
                subscription_data={
                    'metadata': {'user_id': str(request.user.id), 'plan': plan},
                },
            )
        except Exception as e:
            return Response(
                {'error': f'Erreur Stripe: {str(e)[:120]}'},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response({'url': session.url})


class BillingPortalView(APIView):
    """POST /billing/portal/ → returns Stripe Customer Portal URL.
    User can update card, cancel subscription, view invoices.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        secret = os.environ.get('STRIPE_SECRET_KEY')
        if not secret:
            return Response(
                {'error': 'STRIPE_SECRET_KEY non configurée'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        sub = _get_or_create_subscription(request.user)
        if not sub.stripe_customer_id:
            return Response(
                {'error': "Aucun compte Stripe associé. Souscris d'abord à un plan."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        import stripe
        stripe.api_key = secret

        frontend_base = os.environ.get('FRONTEND_BASE_URL', 'https://blog-dashboard-ebon.vercel.app')
        try:
            session = stripe.billing_portal.Session.create(
                customer=sub.stripe_customer_id,
                return_url=f'{frontend_base}/billing',
            )
        except Exception as e:
            return Response(
                {'error': f'Erreur Stripe: {str(e)[:120]}'},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        return Response({'url': session.url})


class BillingWebhookView(APIView):
    """POST /billing/webhook/ - Stripe webhook endpoint.

    Handles:
      - customer.subscription.{created,updated,deleted}  → mirror state into Subscription
      - invoice.payment_failed                           → mark Subscription past_due
      - invoice.payment_succeeded                        → ensure Subscription active
      - checkout.session.completed (mode=payment)        → apply purchased credits

    Security: no auth class - request is verified via Stripe's HMAC signature
    in the Stripe-Signature header. A missing or invalid signature returns 400.

    Reliability: any handler exception is caught + logged but the endpoint
    still returns 200 to Stripe, so Stripe doesn't retry indefinitely (3-day
    storm) when the bug is in OUR code. Stripe retries are only useful for
    transient infra failures, not handler bugs.
    """
    permission_classes = []

    def post(self, request):
        import stripe
        secret = os.environ.get('STRIPE_SECRET_KEY')
        webhook_secret = os.environ.get('STRIPE_WEBHOOK_SECRET')

        if not secret or not webhook_secret:
            return Response({'error': 'Stripe non configurée'}, status=503)

        stripe.api_key = secret

        sig_header = request.META.get('HTTP_STRIPE_SIGNATURE', '')
        payload = request.body

        try:
            event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
        except Exception as e:
            logger.warning('Stripe webhook signature failed: %s', e)
            return Response({'error': 'invalid signature'}, status=400)

        # Stripe SDK 12+ removed dict.get() from StripeObject - bracket access
        # is the supported pattern (raises KeyError if missing, but Stripe
        # guarantees these fields on every event so we don't guard them).
        event_id = event['id']
        event_type = event['type']
        logger.info('Stripe webhook received: id=%s type=%s', event_id, event_type)

        try:
            self._dispatch(event)
        except Exception as e:
            # Never propagate handler bugs to Stripe - log and ack 200.
            logger.exception(
                'Stripe webhook handler crashed (event=%s type=%s): %s',
                event_id, event_type, e,
            )

        return Response({'received': True})

    def _dispatch(self, event):
        event_type = event['type']
        data = event['data']['object']

        if event_type in (
            'customer.subscription.created',
            'customer.subscription.updated',
            'customer.subscription.deleted',
        ):
            self._handle_subscription_event(event_type, data)
        elif event_type == 'invoice.payment_failed':
            self._handle_invoice_payment_failed(data)
        elif event_type == 'invoice.payment_succeeded':
            self._handle_invoice_payment_succeeded(data)
        elif event_type == 'checkout.session.completed':
            self._handle_checkout_completed(data)

    def _handle_subscription_event(self, event_type, data):
        customer_id = data.get('customer')
        sub_obj = Subscription.objects.filter(stripe_customer_id=customer_id).first()
        if not sub_obj:
            logger.warning(
                'Stripe sub event for unknown customer_id=%s (event=%s)',
                customer_id, event_type,
            )
            return

        sub_obj.stripe_subscription_id = data.get('id', '')
        sub_obj.status = data.get('status', 'active')
        sub_obj.cancel_at_period_end = bool(data.get('cancel_at_period_end'))

        # Determine plan from price id - check current then legacy envs.
        items = data.get('items', {}).get('data', [])
        if items:
            price_id = items[0].get('price', {}).get('id', '')
            matched = False
            for plan_key, env_key in PLAN_PRICE_ENV.items():
                if os.environ.get(env_key) == price_id:
                    sub_obj.plan = plan_key
                    matched = True
                    break
            if not matched:
                for plan_key, env_keys in PLAN_PRICE_ENV_LEGACY.items():
                    if any(os.environ.get(k) == price_id for k in env_keys):
                        sub_obj.plan = plan_key
                        break

        period_end = data.get('current_period_end')
        if period_end:
            from datetime import datetime, timezone as tz
            sub_obj.current_period_end = datetime.fromtimestamp(period_end, tz=tz.utc)

        if event_type == 'customer.subscription.deleted':
            sub_obj.plan = 'free'
            sub_obj.status = 'canceled'

        sub_obj.save()
        logger.info(
            'Stripe webhook subscription updated: user=%s plan=%s status=%s',
            sub_obj.user_id, sub_obj.plan, sub_obj.status,
        )

    def _handle_invoice_payment_failed(self, invoice):
        """Renewal payment failed (declined card, expired card, etc.).

        Stripe retries for ~3 weeks. We mark the sub past_due immediately so
        the dashboard can surface a "Update payment method" CTA. The plan
        tier stays unchanged until the subscription is officially canceled.
        """
        customer_id = invoice.get('customer')
        sub_obj = Subscription.objects.filter(stripe_customer_id=customer_id).first()
        if not sub_obj:
            return
        sub_obj.status = 'past_due'
        sub_obj.save(update_fields=['status'])
        logger.warning(
            'Stripe invoice.payment_failed: user=%s amount=%s attempt=%s',
            sub_obj.user_id,
            invoice.get('amount_due'),
            invoice.get('attempt_count'),
        )
        # TODO(notif): trigger email "ton paiement a échoué, mets à jour ta carte".

    def _handle_invoice_payment_succeeded(self, invoice):
        """Successful renewal. Ensure status is 'active' (it should be already
        via customer.subscription.updated, but this is a belt-and-suspenders).
        """
        # Skip the very first invoice that Stripe creates with $0 (subscription_create)
        # - the subscription event fires at the same time and is the source of truth.
        if invoice.get('billing_reason') == 'subscription_create':
            return
        customer_id = invoice.get('customer')
        sub_obj = Subscription.objects.filter(stripe_customer_id=customer_id).first()
        if not sub_obj:
            return
        if sub_obj.status != 'active':
            sub_obj.status = 'active'
            sub_obj.save(update_fields=['status'])
        logger.info(
            'Stripe invoice.payment_succeeded: user=%s amount=%s',
            sub_obj.user_id, invoice.get('amount_paid'),
        )

    def _handle_checkout_completed(self, session):
        """One-time payment (credits pack) - apply credits.

        Subscription checkouts (mode='subscription') skip this branch and are
        instead handled via customer.subscription.created.
        """
        if session.get('mode') != 'payment':
            return
        metadata = session.get('metadata') or {}
        pack = metadata.get('pack')
        user_id = metadata.get('user_id')
        credits_str = metadata.get('credits')
        session_id = session.get('id') or ''
        if not pack or not user_id or not credits_str:
            logger.warning(
                'Credits checkout webhook missing metadata: %s', metadata
            )
            return

        from django.contrib.auth import get_user_model
        UserModel = get_user_model()
        try:
            user = UserModel.objects.get(id=int(user_id))
        except UserModel.DoesNotExist:
            logger.warning('Credits checkout: user_id=%s not found', user_id)
            return

        from .quota import add_credits
        n = int(credits_str)
        # add_credits is idempotent on stripe_session_id (see quota.py) so a
        # re-delivered webhook will NOT double-credit the user.
        new_balance = add_credits(
            user, n, kind='purchase',
            stripe_session_id=session_id,
            description=f'Pack {pack}: +{n} crédits',
        )
        logger.info(
            'Credits added: user=%s pack=%s +%d → balance=%d session=%s',
            user.id, pack, n, new_balance, session_id,
        )


# ==========================================================================
# WORDPRESS - discover & connect
# ==========================================================================


class WordPressDiscoverView(APIView):
    """Probe a URL to confirm it's a WordPress site with REST API enabled.

    POST /wp/discover/ {url}
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        url = (request.data.get('url') or '').strip()
        if not url:
            return Response(
                {'error': 'url requise'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        from .wordpress_adapter import WordPressClient
        result = WordPressClient.discover(url)
        if not result.get('valid_wp'):
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
        return Response(result)


class WordPressConnectView(APIView):
    """Authenticate with a WordPress site using Application Password and
    create / update a Site row for it.

    POST /wp/connect/ {url, username, app_password, name?}
    On success returns the Site dict - frontend can then redirect to the
    dashboard for that site.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        url = (request.data.get('url') or '').strip()
        username = (request.data.get('username') or '').strip()
        app_password = (request.data.get('app_password') or '').strip()
        explicit_name = (request.data.get('name') or '').strip()
        theme_config = request.data.get('theme_config')
        if not isinstance(theme_config, dict):
            theme_config = None

        if not url or not username or not app_password:
            return Response(
                {'error': 'url, username et app_password requis'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Normalize URL
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        url = url.rstrip('/')

        from .wordpress_adapter import WordPressClient, WordPressError

        # First, discovery to confirm it's WP and grab the name
        discovery = WordPressClient.discover(url)
        if not discovery.get('valid_wp'):
            return Response(
                {'error': discovery.get('error') or 'Site WordPress non détecté.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        url = discovery.get('normalized_url') or url
        wp_name = explicit_name or discovery.get('name') or 'Site WordPress'

        # Test auth before saving
        try:
            site = Site.objects.filter(owner=request.user, wp_url=url).first()
            if not site:
                # New connection - enforce sites_max
                from .quota import check_site_quota
                try:
                    check_site_quota(request.user)
                except DRFPermissionDenied as e:
                    return Response(
                        {'error': str(e), 'quota_exceeded': True, 'limit_type': 'sites'},
                        status=status.HTTP_402_PAYMENT_REQUIRED,
                    )
                site = Site(
                    owner=request.user,
                    name=wp_name,
                    domain=url.replace('https://', '').replace('http://', '').rstrip('/'),
                    wp_url=url,
                    description=discovery.get('description', '') or '',
                )
            # Always (re)set credentials and save before testing - WPClient reads them from the model.
            site.wp_url = url
            site.wp_username = username
            site.wp_app_password = app_password
            if theme_config:
                site.theme_config = theme_config
            site.save()

            client = WordPressClient(site)
            user_info = client.test_auth()
        except WordPressError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.exception('WP connect failed')
            return Response(
                {'error': f'Erreur inattendue : {str(e)[:120]}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response({
            'site': {
                'id': site.id,
                'name': site.name,
                'domain': site.domain,
                'wp_url': site.wp_url,
                'is_wordpress': True,
            },
            'wp_user': {
                'username': user_info.get('slug') or user_info.get('name') or username,
                'name': user_info.get('name') or username,
                'roles': user_info.get('roles') or [],
            },
            'discovery': {
                'site_name': discovery.get('name'),
                'post_count': discovery.get('post_count'),
            },
        }, status=status.HTTP_201_CREATED)


class WeeklyDigestView(APIView):
    """Generate a weekly digest for a site: articles published this week,
    top performing posts, tracked-keyword movements, and broken-link/decay
    counters cached from previous scans.

    GET /sites/<site_id>/weekly-digest/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, site_id):
        from datetime import timedelta
        from django.utils import timezone

        site = get_site_for_user(request, site_id)
        now = timezone.now()
        week_ago = now - timedelta(days=7)
        two_weeks_ago = now - timedelta(days=14)

        # Articles published this week
        if site.is_hosted:
            week_qs = HostedPost.objects.filter(
                site=site, status='published', published_at__gte=week_ago.date()
            )
            published_this_week = list(
                week_qs.order_by('-published_at')[:20].values(
                    'slug', 'title', 'language', 'view_count', 'published_at'
                )
            )
            top_views_qs = (
                HostedPost.objects.filter(site=site, status='published')
                .order_by('-view_count')[:5]
                .values('slug', 'title', 'view_count')
            )
            top_views = list(top_views_qs)
            total_articles = HostedPost.objects.filter(
                site=site, status='published'
            ).count()
        else:
            try:
                alias = ensure_site_connection(site)
            except ValueError:
                return Response(
                    {'error': "Cette action nécessite une base de données externe configurée pour ce site."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            week_qs = BlogPost.objects.using(alias).filter(
                status='published', published_at__gte=week_ago.date()
            )
            published_this_week = list(
                week_qs.order_by('-published_at')[:20].values(
                    'slug', 'title', 'language', 'view_count', 'published_at'
                )
            )
            top_views = list(
                BlogPost.objects.using(alias).filter(status='published')
                .order_by('-view_count')[:5]
                .values('slug', 'title', 'view_count')
            )
            total_articles = (
                BlogPost.objects.using(alias).filter(status='published').count()
            )

        # Format dates
        for p in published_this_week:
            if p.get('published_at'):
                p['published_at'] = p['published_at'].isoformat()

        # Tracked keyword movements: compare latest snapshot to one ~7 days old
        keyword_movements = []
        for tk in TrackedKeyword.objects.filter(site=site, is_active=True):
            snapshots = list(
                SerpRank.objects.filter(tracked=tk).order_by('-recorded_at')[:30]
            )
            if not snapshots:
                continue
            latest = snapshots[0]
            # Find snapshot closest to 7 days ago
            week_ago_snap = None
            for s in snapshots[1:]:
                if s.recorded_at <= week_ago:
                    week_ago_snap = s
                    break
            if week_ago_snap is None and len(snapshots) >= 2:
                week_ago_snap = snapshots[-1]
            if week_ago_snap is None:
                continue
            # Compute delta (lower position = better)
            old_pos = week_ago_snap.position
            new_pos = latest.position
            if old_pos is None and new_pos is None:
                continue
            if old_pos is None:
                delta = -100  # entered top 100
            elif new_pos is None:
                delta = 100  # fell out of top 100
            else:
                delta = new_pos - old_pos
            keyword_movements.append({
                'keyword': tk.keyword,
                'language': tk.language,
                'old_position': old_pos,
                'new_position': new_pos,
                'delta': delta,
            })

        # Sort: best improvers first (most negative delta), worst at the bottom
        keyword_movements.sort(key=lambda k: k['delta'])
        top_movers = keyword_movements[:5]
        worst_movers = sorted(
            keyword_movements, key=lambda k: -k['delta']
        )[:5]

        # Broken-link count (only if a recent scan was cached)
        # We don't trigger a scan; just sample the cache for a known key.
        # MVP: skip - leave 0 unless integrated later.
        broken_link_cache_count = 0

        # Active redirects + recent redirects (created or updated this week)
        recent_redirects_count = Redirect.objects.filter(
            site=site, updated_at__gte=week_ago
        ).count()
        total_redirects = Redirect.objects.filter(
            site=site, is_active=True
        ).count()

        return Response({
            'site': {
                'id': site.id,
                'name': site.name,
                'domain': site.domain,
            },
            'period': {
                'start': week_ago.isoformat(),
                'end': now.isoformat(),
                'previous_start': two_weeks_ago.isoformat(),
                'previous_end': week_ago.isoformat(),
            },
            'totals': {
                'total_published': total_articles,
                'published_this_week': len(published_this_week),
                'recent_redirects': recent_redirects_count,
                'active_redirects': total_redirects,
                'tracked_keywords': len(keyword_movements),
            },
            'published_this_week': published_this_week,
            'top_views': list(top_views),
            'top_movers': top_movers,
            'worst_movers': worst_movers,
            'generated_at': now.isoformat(),
        })


class MultiDomainStatsView(APIView):
    """Aggregate stats for ALL sites of the authenticated user - useful for
    agencies / multi-site owners who want a single view across their portfolio.

    GET /multi-domain-stats/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from collections import Counter

        sites = list(Site.objects.filter(owner=request.user).order_by('name'))
        results = []

        for site in sites:
            try:
                if site.is_hosted:
                    qs = HostedPost.objects.filter(site=site)
                    total = qs.count()
                    published_qs = qs.filter(status='published')
                    published = published_qs.count()
                    drafts = qs.filter(status='draft').count()
                    total_views = sum(
                        published_qs.values_list('view_count', flat=True)
                    ) or 0
                    last_pub = (
                        published_qs.order_by('-published_at')
                        .values_list('published_at', flat=True)
                        .first()
                    )
                    lang_counter = Counter(
                        published_qs.values_list('language', flat=True)
                    )
                else:
                    alias = ensure_site_connection(site)
                    qs = BlogPost.objects.using(alias)
                    total = qs.count()
                    published_qs = qs.filter(status='published')
                    published = published_qs.count()
                    drafts = qs.filter(status='draft').count()
                    total_views = sum(
                        published_qs.values_list('view_count', flat=True)
                    ) or 0
                    last_pub = (
                        published_qs.order_by('-published_at')
                        .values_list('published_at', flat=True)
                        .first()
                    )
                    lang_counter = Counter(
                        published_qs.values_list('language', flat=True)
                    )

                tracked_keywords = TrackedKeyword.objects.filter(
                    site=site, is_active=True
                ).count()
                redirects_count = Redirect.objects.filter(
                    site=site, is_active=True
                ).count()

                results.append({
                    'id': site.id,
                    'name': site.name,
                    'domain': site.domain,
                    'is_hosted': site.is_hosted,
                    'is_active': site.is_active,
                    'default_language': site.default_language,
                    'available_languages': site.effective_languages,
                    'total_articles': total,
                    'published_articles': published,
                    'drafts': drafts,
                    'total_views': int(total_views),
                    'last_published_at': last_pub.isoformat() if last_pub else None,
                    'language_breakdown': dict(lang_counter),
                    'tracked_keywords': tracked_keywords,
                    'redirects_count': redirects_count,
                    'gsc_configured': bool(
                        site.gsc_property_url and site.gsc_refresh_token
                    ),
                    'has_eeat_profile': bool(site.author_bio or site.author_role),
                })
            except Exception as e:
                logger.warning('multi-domain stats failed for site %s: %s', site.id, e)
                results.append({
                    'id': site.id,
                    'name': site.name,
                    'domain': site.domain,
                    'error': str(e)[:100],
                })

        # Aggregate totals
        totals = {
            'sites_count': len(results),
            'active_sites': sum(1 for r in results if r.get('is_active')),
            'total_articles': sum(r.get('published_articles', 0) for r in results),
            'total_views': sum(r.get('total_views', 0) for r in results),
            'total_tracked_keywords': sum(r.get('tracked_keywords', 0) for r in results),
            'sites_with_gsc': sum(1 for r in results if r.get('gsc_configured')),
            'sites_with_eeat': sum(1 for r in results if r.get('has_eeat_profile')),
        }

        return Response({
            'sites': results,
            'totals': totals,
        })


class PersonSchemaView(APIView):
    """Return the Schema.org Person JSON-LD built from the site's EEAT fields.

    GET /sites/<id>/person-schema/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, site_id):
        site = get_site_for_user(request, site_id)
        schema = _generate_person_schema(site)
        return Response({'schema': schema})


def _count_syllables_en(word):
    """Heuristic English syllable count. Good enough for Flesch - not perfect."""
    word = word.lower().strip(".,!?;:'\"()[]{}---")
    if len(word) <= 3:
        return 1
    word = re.sub(r'(?:[^laeiouy]es|ed|[^laeiouy]e)$', '', word)
    word = re.sub(r'^y', '', word)
    matches = re.findall(r'[aeiouy]+', word)
    return max(1, len(matches))


def _count_syllables_fr(word):
    """Heuristic French syllable count."""
    word = word.lower().strip(".,!?;:'\"()[]{}---")
    if len(word) <= 2:
        return 1
    # Remove silent terminal 'e' (very common in French)
    if word.endswith('e') and len(word) > 2 and word[-2] not in 'aeiouéèêë':
        word = word[:-1]
    # Vowel groups (FR diphthongs treated as single)
    matches = re.findall(r'[aeiouyàâäéèêëîïôöùûüœ]+', word)
    return max(1, len(matches))


def _compute_readability(text, language='fr'):
    """Compute Flesch-Kincaid Reading Ease + ARI for a text. Language-aware
    syllable counting. Returns a dict with metrics and a qualitative level.
    """
    import re as _re

    if not text or not text.strip():
        return {
            'words': 0, 'sentences': 0, 'syllables': 0, 'characters': 0,
            'flesch': None, 'ari': None, 'level': None, 'level_label': '',
        }

    # Strip markdown / HTML noise
    cleaned = _re.sub(r'```[\s\S]*?```', ' ', text)  # code blocks
    cleaned = _re.sub(r'`[^`]+`', ' ', cleaned)  # inline code
    cleaned = _re.sub(r'!\[[^\]]*\]\([^)]+\)', ' ', cleaned)  # images
    cleaned = _re.sub(r'\[[^\]]*\]\(([^)]+)\)', r'\1', cleaned)  # links
    cleaned = _re.sub(r'<[^>]+>', ' ', cleaned)  # HTML tags
    cleaned = _re.sub(r'#{1,6}\s+', '', cleaned)  # heading markers
    cleaned = _re.sub(r'[*_~]+', '', cleaned)  # bold/italic markers

    # Sentences
    sentences = [s for s in _re.split(r'[.!?]+\s+', cleaned) if s.strip()]
    sentence_count = max(1, len(sentences))

    # Words
    words = _re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ']+", cleaned)
    word_count = len(words)
    if word_count == 0:
        return {
            'words': 0, 'sentences': sentence_count, 'syllables': 0,
            'characters': 0, 'flesch': None, 'ari': None, 'level': None,
            'level_label': '',
        }

    # Syllables
    counter = _count_syllables_fr if language == 'fr' else _count_syllables_en
    syllables = sum(counter(w) for w in words)

    # Characters (letters only)
    chars = sum(len(w) for w in words)

    # Flesch Reading Ease
    if language == 'fr':
        # Kandel & Moles French adaptation
        flesch = 207 - 1.015 * (word_count / sentence_count) - 73.6 * (syllables / word_count)
    else:
        flesch = 206.835 - 1.015 * (word_count / sentence_count) - 84.6 * (syllables / word_count)
    flesch = round(flesch, 1)

    # ARI (Automated Readability Index)
    ari = 4.71 * (chars / word_count) + 0.5 * (word_count / sentence_count) - 21.43
    ari = round(ari, 1)

    # Qualitative level (5 buckets)
    if flesch >= 80:
        level, label = 'very_easy', 'Très facile'
    elif flesch >= 70:
        level, label = 'easy', 'Facile'
    elif flesch >= 60:
        level, label = 'standard', 'Standard'
    elif flesch >= 50:
        level, label = 'fairly_difficult', 'Assez difficile'
    elif flesch >= 30:
        level, label = 'difficult', 'Difficile'
    else:
        level, label = 'very_difficult', 'Très difficile'

    return {
        'words': word_count,
        'sentences': sentence_count,
        'syllables': syllables,
        'characters': chars,
        'avg_words_per_sentence': round(word_count / sentence_count, 1),
        'avg_syllables_per_word': round(syllables / word_count, 2),
        'flesch': flesch,
        'ari': ari,
        'level': level,
        'level_label': label,
    }


class ReadabilityView(APIView):
    """Compute Flesch-Kincaid Reading Ease + ARI for a text.

    POST /readability/ {content: str, language: 'fr'|'en'}
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        content = request.data.get('content', '') or ''
        language = (request.data.get('language') or 'fr').strip().lower()
        if language not in ('fr', 'en', 'es'):
            language = 'fr'
        # Spanish: not specifically tuned, fall back to FR-style syllable rules.
        if language == 'es':
            language = 'fr'
        return Response(_compute_readability(content, language=language))


class LinkGraphView(APIView):
    """Build the internal-link graph of a site's published articles.

    Parses each article's content (markdown + raw HTML) for links pointing to
    another article on the same site (via slug match). Returns nodes with
    in/out-degree and a sorted list of orphans, hubs, and dead-ends.

    GET /sites/<site_id>/link-graph/?language=fr&limit=200
    """
    permission_classes = [IsAuthenticated]

    LINK_RE = None  # compiled lazily

    def get(self, request, site_id):
        import re

        site = get_site_for_user(request, site_id)
        language = (request.query_params.get('language') or '').strip().lower() or None
        try:
            limit = max(5, min(int(request.query_params.get('limit', 200)), 500))
        except (TypeError, ValueError):
            limit = 200

        # Fetch published articles
        if site.is_hosted:
            qs = HostedPost.objects.filter(site=site, status='published')
            if language:
                qs = qs.filter(language=language)
            qs = qs.order_by('-published_at')[:limit]
            articles = [
                {'slug': p.slug, 'title': p.title, 'content': p.content or ''}
                for p in qs
            ]
        else:
            try:
                alias = ensure_site_connection(site)
            except ValueError:
                return Response(
                    {'error': "Cette action nécessite une base de données externe configurée pour ce site."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            qs = BlogPost.objects.using(alias).filter(status='published')
            if language:
                qs = qs.filter(language=language)
            qs = qs.order_by('-published_at')[:limit]
            articles = [
                {'slug': p.slug, 'title': p.title,
                 'content': getattr(p, 'content', '') or ''}
                for p in qs
            ]

        slug_set = {a['slug'] for a in articles}
        title_by_slug = {a['slug']: a['title'] for a in articles}

        # Patterns: [text](/blog/slug) or [text](/blog/slug/) or <a href="/blog/slug">
        # Also match relative slugs and absolute URLs containing the site domain.
        domain = (site.domain or '').lower().replace('https://', '').replace('http://', '').rstrip('/')
        md_link_re = re.compile(r'\[[^\]]*\]\(([^)]+)\)')
        html_link_re = re.compile(r'<a\b[^>]*\bhref=["\']([^"\']+)["\']', re.IGNORECASE)

        edges = []  # list of (from_slug, to_slug)
        edges_set = set()  # dedupe (from, to) pairs

        def _extract_target_slug(href):
            href = (href or '').strip()
            if not href:
                return None
            # Strip absolute URL prefix if it points to this site
            if href.startswith('http'):
                lower = href.lower()
                if domain and domain in lower:
                    # strip protocol + domain
                    idx = lower.find(domain) + len(domain)
                    href = href[idx:]
                else:
                    return None  # external link
            # Now href should be like /blog/slug or /slug or /post/slug
            href = href.lstrip('/').rstrip('/')
            # Strip query/fragment
            href = href.split('?')[0].split('#')[0]
            # Strip common prefixes: blog/, post/, posts/, articles/
            for prefix in ('blog/', 'post/', 'posts/', 'articles/'):
                if href.startswith(prefix):
                    href = href[len(prefix):]
                    break
            return href if href in slug_set else None

        for art in articles:
            content = art['content']
            for m in md_link_re.finditer(content):
                target = _extract_target_slug(m.group(1))
                if target and target != art['slug']:
                    pair = (art['slug'], target)
                    if pair not in edges_set:
                        edges_set.add(pair)
                        edges.append({'from': pair[0], 'to': pair[1]})
            for m in html_link_re.finditer(content):
                target = _extract_target_slug(m.group(1))
                if target and target != art['slug']:
                    pair = (art['slug'], target)
                    if pair not in edges_set:
                        edges_set.add(pair)
                        edges.append({'from': pair[0], 'to': pair[1]})

        # Compute degrees
        in_degree = {a['slug']: 0 for a in articles}
        out_degree = {a['slug']: 0 for a in articles}
        for e in edges:
            out_degree[e['from']] = out_degree.get(e['from'], 0) + 1
            in_degree[e['to']] = in_degree.get(e['to'], 0) + 1

        nodes = [
            {
                'slug': a['slug'],
                'title': a['title'],
                'in_degree': in_degree.get(a['slug'], 0),
                'out_degree': out_degree.get(a['slug'], 0),
            }
            for a in articles
        ]

        orphans = sorted(
            [n for n in nodes if n['in_degree'] == 0],
            key=lambda n: (n['out_degree'], n['title'].lower()),
        )
        hubs = sorted(
            [n for n in nodes if n['in_degree'] >= 5],
            key=lambda n: -n['in_degree'],
        )
        dead_ends = sorted(
            [n for n in nodes if n['out_degree'] == 0],
            key=lambda n: (n['in_degree'], n['title'].lower()),
        )

        return Response({
            'site_id': site.id,
            'language': language,
            'article_count': len(articles),
            'edge_count': len(edges),
            'nodes': nodes,
            'edges': edges,
            'orphans': orphans,
            'orphans_count': len(orphans),
            'hubs': hubs,
            'hubs_count': len(hubs),
            'dead_ends': dead_ends,
            'dead_ends_count': len(dead_ends),
        })


class TopicClusterView(APIView):
    """Group the site's published articles into thematic clusters via Gemini.
    For each cluster: pick a pillar candidate, list spokes, suggest 2-3 new
    article titles to fill content gaps.

    POST /sites/<site_id>/topic-clusters/?language=fr&limit=80
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    throttle_scope = 'ai_generate'

    def post(self, request, site_id):
        import json

        site = get_site_for_user(request, site_id)
        language = (
            request.data.get('language')
            or request.query_params.get('language')
            or site.default_language
            or 'fr'
        ).lower()
        try:
            limit = max(5, min(int(
                request.data.get('limit') or request.query_params.get('limit') or 80
            ), 150))
        except (TypeError, ValueError):
            limit = 80

        # Gemini is preferred for clustering, but we fall back to the shared
        # LLM (Claude -> DeepSeek) if it's missing/unavailable, so clustering
        # survives any single provider being down.
        gemini_key = os.environ.get('GEMINI_API_KEY')

        # Fetch published articles
        if site.is_hosted:
            qs = HostedPost.objects.filter(site=site, status='published')
            if language:
                qs = qs.filter(language=language)
            qs = qs.order_by('-published_at')[:limit]
            articles = [
                {'slug': p.slug, 'title': p.title, 'excerpt': p.excerpt or '',
                 'snippet': (p.content or '')[:600]}
                for p in qs
            ]
        else:
            try:
                alias = ensure_site_connection(site)
            except ValueError:
                return Response(
                    {'error': "Cette action nécessite une base de données externe configurée pour ce site."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            qs = BlogPost.objects.using(alias).filter(status='published')
            if language:
                qs = qs.filter(language=language)
            qs = qs.order_by('-published_at')[:limit]
            articles = [
                {'slug': p.slug, 'title': p.title,
                 'excerpt': getattr(p, 'excerpt', '') or '',
                 'snippet': (getattr(p, 'content', '') or '')[:600]}
                for p in qs
            ]

        if len(articles) < 3:
            return Response({
                'site_id': site.id,
                'language': language,
                'article_count': len(articles),
                'clusters': [],
                'unassigned': [],
                'message': 'Pas assez d\'articles pour clusterer (3 minimum).',
            })

        cache_signature = ','.join(sorted(a['slug'] for a in articles))
        cache_key = _seo_cache_key(
            'topic-clusters:', str(site.id), language, str(len(articles)), cache_signature[:200]
        )
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)

        # Build the article corpus block for Gemini
        corpus_lines = []
        for i, a in enumerate(articles):
            corpus_lines.append(
                f"[{i+1}] slug={a['slug']} | title={a['title']}\n"
                f"    excerpt: {a['excerpt'][:200]}\n"
                f"    opening: {a['snippet'][:300]}"
            )
        corpus = '\n'.join(corpus_lines)

        lang_label = {
            'fr': 'French (Quebec)',
            'en': 'English',
            'es': 'Spanish',
        }.get(language, 'French')

        prompt = f"""You are an SEO content strategist. Analyze the {len(articles)}
articles below from a single blog and group them into 3-8 THEMATIC CLUSTERS.

For each cluster:
- Pick a clear theme name in {lang_label}.
- Identify ONE pillar_candidate_slug - the article that best summarizes the theme
  and could be expanded into a comprehensive pillar page. Use the slug exactly
  as written below.
- List the spokes (other articles in the cluster) by their slugs.
- Suggest 2-4 new article titles in {lang_label} to fill content gaps within the
  cluster, each with a 1-sentence rationale.

Articles:
{corpus}

Respond with JSON only, no markdown:
{{
  "clusters": [
    {{
      "theme": "<theme name in {lang_label}>",
      "summary": "<1-2 sentences in {lang_label} explaining the cluster>",
      "pillar_candidate_slug": "<slug>",
      "spoke_slugs": ["<slug1>", "<slug2>", ...],
      "suggested_new_articles": [
        {{"title": "<title>", "rationale": "<1 sentence>"}},
        ...
      ]
    }}
  ]
}}

Use slugs EXACTLY as provided. Don't invent slugs. Every article should be
assigned to one cluster (pillar OR spoke). Skip the article if it's truly off-topic."""

        text = ''
        if gemini_key:
            try:
                from google import genai
                client = genai.Client(api_key=gemini_key)
                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=[prompt],
                )
                text = (response.text or '').strip()
            except Exception as e:
                logger.warning('Gemini clustering failed, trying LLM fallback: %s', e)
                text = ''
        if not text:
            from .llm import call_llm
            text = call_llm(prompt, max_tokens=2000, timeout=90)  # Claude -> DeepSeek
        if not text:
            return Response(
                {'error': 'Clustering indisponible (Gemini + fallback LLM).'},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        try:
            if text.startswith('```'):
                text = text.split('\n', 1)[1]
                if text.endswith('```'):
                    text = text[:-3]
                text = text.strip()
            data = json.loads(text)
        except Exception as e:
            logger.warning('Clustering parse failed: %s', e)
            return Response(
                {'error': f'Erreur clustering (parse): {str(e)}'},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        # Build a lookup so we can enrich each slug with its title
        title_by_slug = {a['slug']: a['title'] for a in articles}

        def _enrich_slug(slug):
            return {
                'slug': slug,
                'title': title_by_slug.get(slug, slug),
                'exists': slug in title_by_slug,
            }

        clusters = []
        for c in data.get('clusters') or []:
            theme = (c.get('theme') or '').strip()
            if not theme:
                continue
            pillar_slug = (c.get('pillar_candidate_slug') or '').strip()
            spoke_slugs = [s for s in (c.get('spoke_slugs') or []) if s]
            suggested = []
            for sn in c.get('suggested_new_articles') or []:
                if isinstance(sn, dict) and sn.get('title'):
                    suggested.append({
                        'title': sn['title'],
                        'rationale': sn.get('rationale', ''),
                    })
            clusters.append({
                'theme': theme,
                'summary': (c.get('summary') or '').strip(),
                'pillar': _enrich_slug(pillar_slug) if pillar_slug else None,
                'spokes': [_enrich_slug(s) for s in spoke_slugs],
                'suggested_new_articles': suggested,
            })

        # Find articles not assigned to any cluster
        all_assigned = set()
        for c in clusters:
            if c['pillar']:
                all_assigned.add(c['pillar']['slug'])
            for sp in c['spokes']:
                all_assigned.add(sp['slug'])
        unassigned = [
            {'slug': a['slug'], 'title': a['title']}
            for a in articles if a['slug'] not in all_assigned
        ]

        result = {
            'site_id': site.id,
            'language': language,
            'article_count': len(articles),
            'clusters': clusters,
            'unassigned': unassigned,
        }
        cache.set(cache_key, result, timeout=SEO_CACHE_TTL)
        return Response(result)


class ContentDecayView(APIView):
    """Detect articles whose GSC impressions / clicks dropped significantly
    over the last `days` window compared to the previous one.

    GET /sites/<site_id>/content-decay/?days=30

    Requires GSC configured (gsc_property_url + gsc_refresh_token). Returns
    a sorted list of decaying pages with their before/after numbers,
    delta percentages, and a suggested action (refresh / expand / redirect).

    Two GSC API calls (current period + previous period). No cache for now -
    Darius can launch on demand; aggregating ~50 articles takes <15s.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, site_id):
        site = get_site_for_user(request, site_id)
        try:
            days = max(7, min(int(request.query_params.get('days', 30)), 90))
        except (TypeError, ValueError):
            days = 30

        if not site.gsc_property_url:
            return Response(
                {'error': 'GSC property URL not configured for this site.',
                 'code': 'gsc_not_configured'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not site.gsc_refresh_token:
            return Response(
                {'error': 'Reconnecte GSC', 'code': 'gsc_reauth_required'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        config = _gsc_client_config()
        if not config:
            return Response(
                {'error': 'GSC OAuth client not configured on the server.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        try:
            from datetime import date as _date, timedelta
            from google.oauth2.credentials import Credentials
            from google.auth.exceptions import RefreshError
            from googleapiclient.discovery import build
            from googleapiclient.errors import HttpError
        except ImportError:
            return Response(
                {'error': 'Google API libraries are not installed.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        end = _date.today()
        cur_start = end - timedelta(days=days)
        prev_end = cur_start - timedelta(days=1)
        prev_start = prev_end - timedelta(days=days - 1)

        try:
            creds = Credentials(
                token=None,
                refresh_token=site.gsc_refresh_token,
                token_uri=GSC_TOKEN_URI,
                client_id=config['web']['client_id'],
                client_secret=config['web']['client_secret'],
                # Pas de scopes= : voir proof_loop._build_gsc_service. Le scope vient du
                # consentement ; le passer ici ne fait que declencher un WARNING sur les
                # jetons emis avant l'elargissement du scope.
            )
            service = build(
                'searchconsole', 'v1',
                credentials=creds,
                cache_discovery=False,
            )
            from .proof_loop import resolve_gsc_property
            gsc_site_url = resolve_gsc_property(service, site)  # owned property for siteUrl

            def _query_period(start_d, end_d):
                body = {
                    'startDate': start_d.isoformat(),
                    'endDate': end_d.isoformat(),
                    'dimensions': ['page'],
                    'rowLimit': 1000,
                }
                return (
                    service.searchanalytics()
                    .query(siteUrl=gsc_site_url, body=body)
                    .execute()
                )

            cur_resp = _query_period(cur_start, end)
            prev_resp = _query_period(prev_start, prev_end)
        except RefreshError:
            return Response(
                {'error': 'Reconnecte GSC', 'code': 'gsc_reauth_required'},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        except HttpError as e:
            status_code = getattr(getattr(e, 'resp', None), 'status', 500)
            if status_code in (401, 403):
                return Response(
                    {'error': 'Reconnecte GSC', 'code': 'gsc_reauth_required'},
                    status=status.HTTP_401_UNAUTHORIZED,
                )
            return Response(
                {'error': f'Erreur GSC: {str(e)}'},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except Exception as e:
            return Response(
                {'error': f'Erreur GSC: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # Index responses by page URL
        def _index(resp):
            out = {}
            for row in (resp or {}).get('rows', []) or []:
                keys = row.get('keys') or []
                if not keys:
                    continue
                url = keys[0]
                out[url] = {
                    'clicks': int(row.get('clicks') or 0),
                    'impressions': int(row.get('impressions') or 0),
                    'ctr': float(row.get('ctr') or 0),
                    'position': float(row.get('position') or 0),
                }
            return out

        cur_data = _index(cur_resp)
        prev_data = _index(prev_resp)

        # Resolve slug from URL by stripping the canonical site URL prefix.
        # _gsc_canonical_site_url handles both URL-prefix properties (uses
        # the property as-is) and Domain properties (sc-domain:...) where
        # we fall back to Site.domain to build the real URL.
        property_prefix = _gsc_canonical_site_url(site)

        def _slug_from_url(url):
            if url.startswith(property_prefix):
                tail = url[len(property_prefix):].rstrip('/')
                return tail
            return url

        decaying = []
        healthy = 0
        new_pages = 0
        all_urls = set(cur_data.keys()) | set(prev_data.keys())
        for url in all_urls:
            cur = cur_data.get(url, {'clicks': 0, 'impressions': 0})
            prev = prev_data.get(url, {'clicks': 0, 'impressions': 0})

            if prev['impressions'] == 0 and cur['impressions'] > 0:
                new_pages += 1
                continue
            if prev['impressions'] == 0:
                continue

            imp_delta = (
                (cur['impressions'] - prev['impressions']) / prev['impressions']
            ) * 100
            clk_delta_pct = None
            if prev['clicks'] > 0:
                clk_delta_pct = (
                    (cur['clicks'] - prev['clicks']) / prev['clicks']
                ) * 100

            # Decay: impressions -30%+, OR clicks -40%+ when we had clicks before
            is_decay = imp_delta <= -30 or (
                clk_delta_pct is not None and clk_delta_pct <= -40
            )

            if not is_decay:
                healthy += 1
                continue

            # Suggest action based on severity
            if cur['impressions'] == 0 or imp_delta <= -80:
                action = 'redirect_or_remove'
            elif imp_delta <= -50 or (clk_delta_pct is not None and clk_delta_pct <= -60):
                action = 'major_refresh'
            else:
                action = 'minor_refresh'

            decaying.append({
                'url': url,
                'slug': _slug_from_url(url),
                'impressions_now': cur['impressions'],
                'impressions_before': prev['impressions'],
                'clicks_now': cur['clicks'],
                'clicks_before': prev['clicks'],
                'impressions_delta_pct': round(imp_delta, 1),
                'clicks_delta_pct': (
                    round(clk_delta_pct, 1) if clk_delta_pct is not None else None
                ),
                'position_now': round(cur.get('position', 0), 1) if cur else None,
                'position_before': round(prev.get('position', 0), 1) if prev else None,
                'suggested_action': action,
            })

        # Sort by worst impressions delta first
        decaying.sort(key=lambda d: d['impressions_delta_pct'])

        return Response({
            'site_id': site.id,
            'days': days,
            'period_current': {'start': cur_start.isoformat(), 'end': end.isoformat()},
            'period_previous': {'start': prev_start.isoformat(), 'end': prev_end.isoformat()},
            'decaying_count': len(decaying),
            'healthy_count': healthy,
            'new_pages_count': new_pages,
            'decaying': decaying[:50],
        })


# ==========================================================================
# RANK TRACKING - TrackedKeyword + SerpRank snapshots
# ==========================================================================

class RedirectsView(APIView):
    """List or create 301 redirects for a site."""
    permission_classes = [IsAuthenticated]

    def get(self, request, site_id):
        site = get_site_for_user(request, site_id)
        items = list(
            Redirect.objects.filter(site=site).order_by('-updated_at')[:500]
        )
        return Response({
            'results': [
                {
                    'id': r.id,
                    'from_slug': r.from_slug,
                    'to_slug': r.to_slug,
                    'language': r.language,
                    'hit_count': r.hit_count,
                    'is_active': r.is_active,
                    'created_at': r.created_at.isoformat(),
                    'updated_at': r.updated_at.isoformat(),
                }
                for r in items
            ],
        })

    def post(self, request, site_id):
        site = get_site_for_user(request, site_id)
        from_slug = (request.data.get('from_slug') or '').strip().strip('/')
        to_slug = (request.data.get('to_slug') or '').strip().strip('/')
        language = (request.data.get('language') or site.default_language or 'fr').lower()

        if not from_slug or not to_slug:
            return Response(
                {'error': 'from_slug et to_slug requis'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if from_slug == to_slug:
            return Response(
                {'error': 'from_slug et to_slug doivent etre differents'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if language not in ('fr', 'en', 'es'):
            return Response(
                {'error': 'Langue invalide (fr, en, es)'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        r, created = Redirect.objects.update_or_create(
            site=site, from_slug=from_slug, language=language,
            defaults={'to_slug': to_slug, 'is_active': True},
        )
        return Response({
            'id': r.id,
            'from_slug': r.from_slug,
            'to_slug': r.to_slug,
            'language': r.language,
            'hit_count': r.hit_count,
            'is_active': r.is_active,
            'created_at': r.created_at.isoformat(),
            'updated_at': r.updated_at.isoformat(),
        }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class RedirectDetailView(APIView):
    """Delete a redirect."""
    permission_classes = [IsAuthenticated]

    def delete(self, request, site_id, pk):
        site = get_site_for_user(request, site_id)
        try:
            r = Redirect.objects.get(site=site, id=pk)
        except Redirect.DoesNotExist:
            return Response(
                {'error': 'Redirect introuvable'},
                status=status.HTTP_404_NOT_FOUND,
            )
        r.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


def _serialize_tracked_keyword(tk, latest=None, snapshots=None):
    """Serialize a TrackedKeyword with its latest snapshot for list views.

    `latest` (the single most-recent snapshot) is kept untouched for backward
    compatibility. On top of it we expose a stability-aware rank
    (`stable_position` / `is_stable` / `found_ratio` / `last_checked` /
    `best_seen` / `samples`) so the UI can avoid presenting one noisy reading as
    a stable fact. Pass `snapshots` (newest-first) from a bulk query in list
    views to skip the per-keyword lookup.
    """
    base = {
        'id': tk.id,
        'keyword': tk.keyword,
        'language': tk.language,
        'intent': tk.intent,
        'target_url': tk.target_url,
        'is_active': tk.is_active,
        'created_at': tk.created_at.isoformat(),
    }
    if latest:
        base['latest'] = {
            'position': latest.position,
            'url': latest.url,
            'title': latest.title,
            'is_target_match': latest.is_target_match,
            'recorded_at': latest.recorded_at.isoformat(),
        }
    else:
        base['latest'] = None
    base.update(keyword_display_rank(tk, snapshots=snapshots))
    return base


class TrackedKeywordsView(APIView):
    """List or create tracked keywords for a site."""
    permission_classes = [IsAuthenticated]

    def get(self, request, site_id):
        site = get_site_for_user(request, site_id)
        keywords = list(
            TrackedKeyword.objects.filter(site=site).order_by('-created_at')
        )
        # Fetch the recent snapshot window per keyword in a single query, so
        # both the latest reading AND the stability computation stay N+1-free.
        latest_map = {}
        snaps_map = {}
        if keywords:
            ids = [k.id for k in keywords]
            for snap in (
                SerpRank.objects.filter(tracked_id__in=ids)
                .order_by('tracked_id', '-recorded_at')
            ):
                if snap.tracked_id not in latest_map:
                    latest_map[snap.tracked_id] = snap
                bucket = snaps_map.setdefault(snap.tracked_id, [])
                if len(bucket) < DEFAULT_WINDOW:
                    bucket.append(snap)
        return Response({
            'results': [
                _serialize_tracked_keyword(
                    k, latest_map.get(k.id), snaps_map.get(k.id)
                )
                for k in keywords
            ],
        })

    def post(self, request, site_id):
        from .keyword_intent import classify_intent_heuristic

        site = get_site_for_user(request, site_id)
        keyword = (request.data.get('keyword') or '').strip()
        language = (request.data.get('language') or site.default_language or 'fr').lower()
        target_url = (request.data.get('target_url') or '').strip()
        # Intent can be provided explicitly (e.g. bulk-add from IA suggestions
        # already knows the label) or omitted (manual add via the form) - in
        # which case the regex heuristic guesses it. 'info' is the safest
        # fallback when nothing matches.
        raw_intent = (request.data.get('intent') or '').strip().lower()
        if raw_intent in ('info', 'commercial', 'transactional', 'local'):
            intent = raw_intent
        else:
            intent = classify_intent_heuristic(keyword)

        if not keyword:
            return Response(
                {'error': 'Le mot-cle est requis'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if language not in ('fr', 'en', 'es'):
            return Response(
                {'error': 'Langue invalide (fr, en, es)'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Enforce keywords_max from the user's plan, but only when adding NEW.
        # If the keyword already exists (even inactive), reactivating it doesn't
        # consume an extra slot beyond what the user already has counted.
        existing = TrackedKeyword.objects.filter(
            site=site, keyword=keyword, language=language
        ).first()
        if existing is None or not existing.is_active:
            from .quota import check_keyword_quota
            try:
                check_keyword_quota(request.user)
            except DRFPermissionDenied as e:
                return Response(
                    {'error': str(e), 'quota_exceeded': True, 'limit_type': 'keywords'},
                    status=status.HTTP_402_PAYMENT_REQUIRED,
                )

        tk, created = TrackedKeyword.objects.get_or_create(
            site=site, keyword=keyword, language=language,
            defaults={'target_url': target_url, 'is_active': True, 'intent': intent},
        )
        if not created:
            # Reactivate / update target if existed. Don't overwrite the
            # stored intent silently - the user may have edited it.
            tk.is_active = True
            if target_url:
                tk.target_url = target_url
            tk.save()
        return Response(
            _serialize_tracked_keyword(tk),
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class TrackedKeywordDetailView(APIView):
    """Update or delete a tracked keyword.

    PATCH lets the user edit intent inline from the table (badge click);
    other writable fields could be added here later (target_url, is_active).
    """
    permission_classes = [IsAuthenticated]

    def patch(self, request, site_id, pk):
        site = get_site_for_user(request, site_id)
        try:
            tk = TrackedKeyword.objects.get(site=site, id=pk)
        except TrackedKeyword.DoesNotExist:
            return Response(
                {'error': 'Mot-cle introuvable'},
                status=status.HTTP_404_NOT_FOUND,
            )

        updated = []
        if 'intent' in request.data:
            new_intent = (request.data.get('intent') or '').strip().lower()
            if new_intent not in ('info', 'commercial', 'transactional', 'local'):
                return Response(
                    {'error': 'Intent invalide (info, commercial, transactional, local)'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            tk.intent = new_intent
            updated.append('intent')
        if 'target_url' in request.data:
            tk.target_url = (request.data.get('target_url') or '').strip()
            updated.append('target_url')
        if 'is_active' in request.data:
            tk.is_active = bool(request.data.get('is_active'))
            updated.append('is_active')

        if updated:
            tk.save(update_fields=updated)
        return Response(_serialize_tracked_keyword(tk))

    def delete(self, request, site_id, pk):
        site = get_site_for_user(request, site_id)
        try:
            tk = TrackedKeyword.objects.get(site=site, id=pk)
        except TrackedKeyword.DoesNotExist:
            return Response(
                {'error': 'Mot-cle introuvable'},
                status=status.HTTP_404_NOT_FOUND,
            )
        tk.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class TrackedKeywordReclassifyView(APIView):
    """Re-classify all tracked keywords of a site via Claude in a single batch.

    POST /api/sites/<id>/keywords/reclassify/
    Body: {only_default?: bool}  - if true (default), only reclass keywords
    that still have intent='info' (the migration's safe fallback). False =
    reclass everything, overwriting prior values.

    One Claude call total per site (~$0.02-0.05 depending on keyword count).
    Returns the updated keyword list so the frontend can refresh in one shot.
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    throttle_scope = 'ai_generate'

    def post(self, request, site_id):
        import json as _json
        import re

        site = get_site_for_user(request, site_id)
        only_default = request.data.get('only_default', True)

        anthropic_key = os.environ.get('ANTHROPIC_API_KEY')
        if not anthropic_key:
            return Response(
                {'error': 'ANTHROPIC_API_KEY non configuree.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        qs = TrackedKeyword.objects.filter(site=site, is_active=True)
        if only_default:
            qs = qs.filter(intent='info')
        keywords = list(qs.only('id', 'keyword', 'intent'))
        if not keywords:
            return Response({'updated_count': 0, 'message': 'Rien a reclasser'})

        kw_block = '\n'.join(f'- [{tk.id}] {tk.keyword}' for tk in keywords[:200])

        prompt = f"""Tu es un expert SEO. Classifie l'intent de chaque mot-cle.

Labels possibles (un seul par mot-cle):
- info: question, definition, comment faire, guide
- commercial: comparaison, "meilleur X", "vs", avis pour informer un achat
- transactional: pret a acheter ("acheter X", "prix X", "X pas cher")
- local: ancre geographiquement (ville, "pres de moi")

MOTS-CLES A CLASSER:
{kw_block}

Reponds UNIQUEMENT en JSON, schema strict, dans le meme ordre que la liste:
{{"classifications": [{{"id": <id>, "intent": "info|commercial|transactional|local"}}]}}
"""

        from .llm import call_llm
        text = call_llm(prompt, max_tokens=2000, timeout=45)  # Anthropic -> DeepSeek
        if not text:
            return Response(
                {'error': 'Aucune reponse LLM (Anthropic + fallback DeepSeek indisponibles).'},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        match = re.search(r'\{[\s\S]*\}', text)
        if not match:
            return Response(
                {'error': 'Reponse Claude non parsable', 'raw': text[:500]},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        try:
            parsed = _json.loads(match.group())
        except _json.JSONDecodeError:
            return Response(
                {'error': 'JSON Claude invalide', 'raw': text[:500]},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        valid_intents = {'info', 'commercial', 'transactional', 'local'}
        by_id = {tk.id: tk for tk in keywords}
        updates = []
        for item in (parsed.get('classifications') or []):
            if not isinstance(item, dict):
                continue
            try:
                kid = int(item.get('id'))
            except (TypeError, ValueError):
                continue
            new_intent = (item.get('intent') or '').strip().lower()
            if new_intent not in valid_intents:
                continue
            tk = by_id.get(kid)
            if not tk or tk.intent == new_intent:
                continue
            tk.intent = new_intent
            updates.append(tk)

        if updates:
            TrackedKeyword.objects.bulk_update(updates, ['intent'], batch_size=200)

        return Response({
            'updated_count': len(updates),
            'total_processed': len(keywords),
        })


class RankSnapshotView(APIView):
    """Crawl Google SERP via Serper for all active tracked keywords of a site,
    record one SerpRank snapshot per keyword. Designed to be called from a
    cron / scheduled agent (daily). Returns counts.

    Body: {keyword_ids?: [int]} - optional filter to only crawl specific
    keywords (default: all active for the site).
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, site_id):
        site = get_site_for_user(request, site_id)
        keyword_ids = request.data.get('keyword_ids') or []

        api_key = os.environ.get('SERPER_API_KEY')
        if not api_key:
            return Response(
                {'error': 'SERPER_API_KEY non configuree'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        qs = TrackedKeyword.objects.filter(site=site, is_active=True)
        if keyword_ids:
            qs = qs.filter(id__in=keyword_ids)

        snapshots_created = 0
        not_found_count = 0
        site_domain = (site.domain or '').lower().replace('https://', '').replace('http://', '').rstrip('/')

        for tk in qs:
            hl, gl = ('en', 'us') if tk.language == 'en' else (
                ('es', 'es') if tk.language == 'es' else ('fr', 'ca')
            )
            try:
                resp = http_requests.post(
                    'https://google.serper.dev/search',
                    headers={
                        'X-API-KEY': api_key,
                        'Content-Type': 'application/json',
                    },
                    json={'q': tk.keyword, 'num': 100, 'hl': hl, 'gl': gl},
                    timeout=15,
                )
            except Exception as e:
                logger.warning('Serper rank snapshot failed for %s: %s', tk.keyword, e)
                continue

            if resp.status_code != 200:
                logger.warning('Serper rank snapshot status %s for %s', resp.status_code, tk.keyword)
                continue

            organic = (resp.json() or {}).get('organic') or []

            # Find first occurrence of target_url OR site_domain
            target_url_norm = (tk.target_url or '').lower().rstrip('/')
            best_hit = None
            for idx, item in enumerate(organic, start=1):
                url = (item.get('link') or '').lower()
                if not url:
                    continue
                if target_url_norm and url.rstrip('/') == target_url_norm:
                    best_hit = (idx, item, True)
                    break
                if site_domain and site_domain in url:
                    best_hit = best_hit or (idx, item, False)

            if best_hit:
                pos, item, is_target = best_hit
                SerpRank.objects.create(
                    tracked=tk,
                    position=pos,
                    url=item.get('link') or '',
                    title=item.get('title') or '',
                    is_target_match=is_target,
                    source='serper',
                )
                snapshots_created += 1
            else:
                # Not in top 100
                SerpRank.objects.create(
                    tracked=tk,
                    position=None,
                    url='',
                    title='',
                    is_target_match=False,
                    source='serper',
                )
                not_found_count += 1

        return Response({
            'site_id': site.id,
            'snapshots_created': snapshots_created,
            'not_found_count': not_found_count,
            'total_processed': snapshots_created + not_found_count,
        })


class RankHistoryView(APIView):
    """Return snapshot history for a tracked keyword.

    GET /sites/<site_id>/rank-history/?tracked_id=<id>&days=90
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, site_id):
        site = get_site_for_user(request, site_id)
        tracked_id = request.query_params.get('tracked_id')
        try:
            days = max(1, min(int(request.query_params.get('days', 90)), 365))
        except (TypeError, ValueError):
            days = 90

        if not tracked_id:
            return Response(
                {'error': 'tracked_id requis'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            tk = TrackedKeyword.objects.get(site=site, id=tracked_id)
        except TrackedKeyword.DoesNotExist:
            return Response(
                {'error': 'Mot-cle introuvable'},
                status=status.HTTP_404_NOT_FOUND,
            )

        from datetime import timedelta
        from django.utils import timezone

        cutoff = timezone.now() - timedelta(days=days)
        snaps = list(
            SerpRank.objects.filter(tracked=tk, recorded_at__gte=cutoff)
            .order_by('recorded_at')
        )

        # Decay detection: compare latest snapshot to median of previous ones
        decay_alert = None
        if len(snaps) >= 3:
            latest = snaps[-1]
            previous = snaps[:-1]
            # only consider snapshots that had a position
            ranked = [s.position for s in previous if s.position is not None]
            if ranked:
                from statistics import median
                med = median(ranked)
                if latest.position is None and ranked:
                    decay_alert = {
                        'severity': 'critical',
                        'message': 'Article tombe hors top 100',
                        'previous_median': int(med),
                    }
                elif latest.position is not None and latest.position - med >= 5:
                    decay_alert = {
                        'severity': 'warning',
                        'message': f'Position chute de {int(latest.position - med)} places vs mediane',
                        'previous_median': int(med),
                        'current': latest.position,
                    }

        return Response({
            'tracked': _serialize_tracked_keyword(tk),
            'days': days,
            'snapshots': [
                {
                    'position': s.position,
                    'url': s.url,
                    'title': s.title,
                    'is_target_match': s.is_target_match,
                    'recorded_at': s.recorded_at.isoformat(),
                }
                for s in snaps
            ],
            'decay_alert': decay_alert,
        })


# ==========================================================================
# PUBLIC API - consumed by site frontends (no auth, optional API key check)
# ==========================================================================

def _public_get_site(site_id, request):
    """Fetch a site and optionally verify its API key header."""
    site = get_object_or_404(Site, id=site_id)
    # Optional: verify API key if provided via header
    provided_key = request.headers.get('X-Api-Key', '')
    if provided_key and site.api_key and provided_key != site.api_key:
        return None
    return site


def _lang_score(lang, preferred, default):
    """Higher = better candidate to represent a translation_group."""
    if preferred and lang == preferred:
        return 2
    if default and lang == default:
        return 1
    return 0


def _dedupe_by_translation_group(posts, preferred_language=None, default_language=None):
    """Materialize an iterable of posts and keep ONE per translation_group.

    Selection priority within a group: preferred_language match > default_language
    match > first encountered (caller is expected to pre-sort by recency).
    Posts without a translation_group are kept as-is, in their original order.
    """
    chosen = {}        # tg_str -> post
    chosen_order = {}  # tg_str -> position index for stable output ordering
    extras = []        # (position, post) for posts without tg
    pos = 0
    for p in posts:
        tg = getattr(p, 'translation_group', None)
        if not tg:
            extras.append((pos, p))
            pos += 1
            continue
        key = str(tg)
        if key not in chosen:
            chosen[key] = p
            chosen_order[key] = pos
            pos += 1
        else:
            cur_score = _lang_score(chosen[key].language, preferred_language, default_language)
            new_score = _lang_score(p.language, preferred_language, default_language)
            if new_score > cur_score:
                chosen[key] = p  # keep original slot in chosen_order
    # Merge by original position so ordering matches the input sort
    merged = [(chosen_order[k], v) for k, v in chosen.items()] + extras
    merged.sort(key=lambda t: t[0])
    return [p for _, p in merged]


def _serialize_public_site(site):
    """Shared serialization for the public Site endpoint and the
    site-by-domain lookup. Includes EEAT author + theme_config."""
    return {
        'id': site.id,
        'name': site.name,
        'domain': site.domain,
        'public_blog_domain': site.public_blog_domain,
        'description': site.description,
        'og_image_url': site.og_image_url,
        'default_language': site.default_language,
        'available_languages': site.effective_languages,
        'theme_config': site.theme_config or None,
        'indexnow_key': site.indexnow_key or '',
        'author': {
            'name': site.default_author or 'Admin',
            'role': site.author_role,
            'bio': site.author_bio,
            'credentials': site.author_credentials,
            'image_url': site.author_image_url,
            'linkedin': site.author_linkedin,
            'twitter': site.author_twitter,
            'website': site.author_website,
        },
        'person_schema': _generate_person_schema(site),
    }


class PublicSiteView(APIView):
    """GET /api/public/sites/<id>/ - basic site info + EEAT author profile."""
    permission_classes = []

    def get(self, request, site_id):
        site = _public_get_site(site_id, request)
        if not site:
            return Response({'error': 'Invalid API key'}, status=status.HTTP_403_FORBIDDEN)
        return Response(_serialize_public_site(site))


class PublicSiteByDomainView(APIView):
    """GET /api/public/site-by-domain/?domain=<host>

    Used by the public-blog Next.js app to resolve the current site from
    the request Host header. Match priority: `public_blog_domain` exact match
    first, then `domain` exact match. Both stored without scheme.
    No auth - this is intentionally public so the Next.js SSR can fetch it.
    """
    permission_classes = []

    def get(self, request):
        domain = (request.query_params.get('domain') or '').strip().lower()
        if not domain:
            return Response(
                {'error': 'Le parametre "domain" est requis'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Strip scheme/port if a frontend mistakenly passes them
        domain = domain.replace('https://', '').replace('http://', '')
        domain = domain.split('/')[0].split(':')[0]

        site = (
            Site.objects.filter(public_blog_domain__iexact=domain, is_active=True).first()
            or Site.objects.filter(domain__iexact=domain, is_active=True).first()
        )
        if not site:
            return Response(
                {'error': f'Aucun site associé au domaine "{domain}".'},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(_serialize_public_site(site))


class PublicPostsView(APIView):
    """GET /api/public/sites/<id>/posts/ - list published articles."""
    permission_classes = []

    def get(self, request, site_id):
        site = _public_get_site(site_id, request)
        if not site:
            return Response({'error': 'Invalid API key'}, status=status.HTTP_403_FORBIDDEN)

        featured = request.query_params.get('featured')
        category = request.query_params.get('category')
        language = request.query_params.get('language')
        search = request.query_params.get('search', '')
        page = int(request.query_params.get('page', 1))
        page_size = min(int(request.query_params.get('page_size', 20)), 100)

        default_language = getattr(site, 'default_language', None) or 'fr'

        if site.is_hosted:
            posts = HostedPost.objects.filter(site=site, status='published').select_related('category').prefetch_related('tags')
            if featured == 'true':
                posts = posts.filter(featured=True)
            if category:
                posts = posts.filter(category__slug=category)
            if language:
                posts = posts.filter(language=language)
            if search:
                posts = posts.filter(title__icontains=search)
            posts = posts.order_by('-published_at')
            deduped = _dedupe_by_translation_group(
                posts, preferred_language=language, default_language=default_language
            )
            total = len(deduped)
            start = (page - 1) * page_size
            end = start + page_size
            return Response({
                'count': total,
                'results': [_serialize_hosted_post(p, detail=False) for p in deduped[start:end]],
                'next': page + 1 if end < total else None,
                'previous': page - 1 if page > 1 else None,
            })

        try:
            alias = ensure_site_connection(site)
        except ValueError:
            return Response(
                {'error': "Cette action nécessite une base de données externe configurée pour ce site."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        posts = (
            BlogPost.objects.using(alias)
            .filter(status='published')
            .select_related('category')
            .prefetch_related('tags')
            .order_by('-published_at')
        )
        if featured == 'true':
            posts = posts.filter(featured=True)
        if category:
            posts = posts.filter(category__slug=category)
        if language:
            posts = posts.filter(language=language)
        if search:
            posts = posts.filter(title__icontains=search)
        deduped = _dedupe_by_translation_group(
            posts, preferred_language=language, default_language=default_language
        )
        total = len(deduped)
        start = (page - 1) * page_size
        end = start + page_size
        serializer = BlogPostListSerializer(deduped[start:end], many=True)
        return Response({
            'count': total,
            'results': serializer.data,
            'next': page + 1 if end < total else None,
            'previous': page - 1 if page > 1 else None,
        })


class PublicPostDetailView(APIView):
    """GET /api/public/sites/<id>/posts/<slug>/ - single article.

    If the slug doesn't exist as a current article, look up an active
    Redirect entry (per-language) and return a 301-style payload pointing
    to the canonical slug, so the frontend can issue a proper redirect.
    """
    permission_classes = []

    def _resolve_redirect(self, site, slug, language=None):
        """Return the new slug if `slug` is a known redirect, else None."""
        qs = Redirect.objects.filter(
            site=site, from_slug=slug, is_active=True
        )
        if language:
            r = qs.filter(language=language).first()
            if r:
                Redirect.objects.filter(pk=r.pk).update(hit_count=r.hit_count + 1)
                return r.to_slug
        # Fallback: any language match
        r = qs.first()
        if r:
            Redirect.objects.filter(pk=r.pk).update(hit_count=r.hit_count + 1)
            return r.to_slug
        return None

    def get(self, request, site_id, slug):
        site = _public_get_site(site_id, request)
        if not site:
            return Response({'error': 'Invalid API key'}, status=status.HTTP_403_FORBIDDEN)

        language = request.query_params.get('language')

        if site.is_hosted:
            post = HostedPost.objects.select_related('category').prefetch_related('tags').filter(
                site=site, slug=slug, status='published'
            ).first()
            if post is None:
                # Try redirect
                target = self._resolve_redirect(site, slug, language)
                if target:
                    return Response(
                        {'redirect_to': target, 'status': 301},
                        status=status.HTTP_301_MOVED_PERMANENTLY,
                        headers={'Location': f'/blog/{target}'},
                    )
                from django.http import Http404
                raise Http404
            HostedPost.objects.filter(pk=post.pk).update(view_count=post.view_count + 1)
            return Response(_serialize_hosted_post(post))

        try:
            alias = ensure_site_connection(site)
        except ValueError:
            return Response(
                {'error': "Cette action nécessite une base de données externe configurée pour ce site."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        post = (
            BlogPost.objects.using(alias)
            .select_related('category').prefetch_related('tags')
            .filter(slug=slug, status='published').first()
        )
        if post is None:
            target = self._resolve_redirect(site, slug, language)
            if target:
                return Response(
                    {'redirect_to': target, 'status': 301},
                    status=status.HTTP_301_MOVED_PERMANENTLY,
                    headers={'Location': f'/blog/{target}'},
                )
            from django.http import Http404
            raise Http404
        BlogPost.objects.using(alias).filter(pk=post.pk).update(view_count=post.view_count + 1)
        serializer = BlogPostDetailSerializer(post)
        return Response(serializer.data)


class PublicTranslationsView(APIView):
    """GET /api/public/sites/<id>/posts/<slug>/translations/ - all language versions of an article.

    Returns every published article sharing the same translation_group, INCLUDING
    the current one. This lets the frontend render a complete language switcher
    by indexing on `language`. Each entry includes a relative URL ready to use
    (e.g. `/blog/<slug>`).
    """
    permission_classes = []

    def get(self, request, site_id, slug):
        site = _public_get_site(site_id, request)
        if not site:
            return Response({'error': 'Invalid API key'}, status=status.HTTP_403_FORBIDDEN)

        def serialize(p, is_current):
            return {
                'slug': p.slug,
                'language': p.language,
                'title': p.title,
                'url': f'/blog/{p.slug}',
                'is_current': is_current,
            }

        if site.is_hosted:
            post = get_object_or_404(HostedPost, site=site, slug=slug, status='published')
            translations = HostedPost.objects.filter(
                site=site,
                translation_group=post.translation_group,
                status='published',
            )
            return Response({
                'current_language': post.language,
                'translation_group': str(post.translation_group),
                'translations': [serialize(p, p.pk == post.pk) for p in translations],
            })

        try:
            alias = ensure_site_connection(site)
        except ValueError:
            return Response(
                {'error': "Cette action nécessite une base de données externe configurée pour ce site."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        post = get_object_or_404(BlogPost.objects.using(alias), slug=slug, status='published')
        translations = BlogPost.objects.using(alias).filter(
            translation_group=post.translation_group,
            status='published',
        )
        return Response({
            'current_language': post.language,
            'translation_group': str(post.translation_group),
            'translations': [serialize(p, p.pk == post.pk) for p in translations],
        })


def _serialize_hosted_landing(landing):
    """Public-shape serializer for a HostedLanding. Used by the marketing
    Next.js catch-all to render a landing at the site root."""
    return {
        'id': landing.id,
        'title': landing.title,
        'slug': landing.slug,
        'h1': landing.h1,
        'hero_subtitle': landing.hero_subtitle,
        'hero_cta_text': landing.hero_cta_text,
        'hero_cta_url': landing.hero_cta_url,
        'value_props': landing.value_props or [],
        'social_proof': landing.social_proof or [],
        'faq': landing.faq or [],
        'cta_bottom_text': landing.cta_bottom_text,
        'cta_bottom_url': landing.cta_bottom_url,
        'body_markdown': landing.body_markdown,
        'target_keyword': landing.target_keyword,
        'schema_type': landing.schema_type,
        'page_subtype': landing.page_subtype,
        'language': landing.language,
        'translation_group': str(landing.translation_group),
        'cover_image': landing.cover_image,
        'meta_description': landing.meta_description,
        'schema_jsonld': landing.schema_jsonld or {},
        'published_at': landing.published_at.isoformat() if landing.published_at else None,
        'created_at': landing.created_at.isoformat(),
        'updated_at': landing.updated_at.isoformat(),
    }


class PublicLandingsView(APIView):
    """GET /api/public/sites/<id>/landings/ - list published landings (slugs only).

    Used by the marketing Next.js sitemap.ts to enumerate landing URLs Google
    should index. Returns minimal payload (slug + updated_at + language) -
    full content is fetched per-page via PublicLandingDetailView.
    """
    permission_classes = []

    def get(self, request, site_id):
        site = _public_get_site(site_id, request)
        if not site:
            return Response({'error': 'Invalid API key'},
                            status=status.HTTP_403_FORBIDDEN)
        landings = HostedLanding.objects.filter(
            site=site, status='published',
        ).only('slug', 'language', 'updated_at')
        return Response({
            'results': [
                {
                    'slug': l.slug,
                    'language': l.language,
                    'updated_at': l.updated_at.isoformat(),
                }
                for l in landings
            ],
            'count': landings.count(),
        })


class PublicLandingDetailView(APIView):
    """GET /api/public/sites/<id>/landings/<slug>/ - single published landing.

    Used by the marketing Next.js catch-all route to render a landing at the
    site root (e.g. gridar.app/audit-seo-gratuit-quebec). Only returns
    landings with status='published' to keep drafts out of public reach.
    """
    permission_classes = []

    def get(self, request, site_id, slug):
        site = _public_get_site(site_id, request)
        if not site:
            return Response({'error': 'Invalid API key'},
                            status=status.HTTP_403_FORBIDDEN)
        landing = HostedLanding.objects.filter(
            site=site, slug=slug, status='published',
        ).first()
        if landing is None:
            from django.http import Http404
            raise Http404('Landing introuvable.')
        return Response(_serialize_hosted_landing(landing))


class PublicCategoriesView(APIView):
    """GET /api/public/sites/<id>/categories/"""
    permission_classes = []

    def get(self, request, site_id):
        site = _public_get_site(site_id, request)
        if not site:
            return Response({'error': 'Invalid API key'}, status=status.HTTP_403_FORBIDDEN)

        if site.is_hosted:
            cats = HostedCategory.objects.filter(site=site)
            return Response([
                {
                    'id': c.id,
                    'name': c.name,
                    'slug': c.slug,
                    'description': c.description,
                    'posts_count': c.posts.filter(status='published').count(),
                }
                for c in cats
            ])

        try:
            alias = ensure_site_connection(site)
        except ValueError:
            return Response(
                {'error': "Cette action nécessite une base de données externe configurée pour ce site."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        cats = Category.objects.using(alias).all()
        return Response([
            {
                'id': c.id,
                'name': c.name,
                'slug': c.slug,
                'description': c.description,
                'posts_count': c.posts.using(alias).filter(status='published').count(),
            }
            for c in cats
        ])


# --- Google Search Console integration -------------------------------------
#
# These views let a user link a Site to a Google Search Console property via
# OAuth2 and then pull real impressions/clicks/CTR/position per query for any
# article slug.
#
# Minimal setup (reuses the existing Google login OAuth client):
#   - In Google Cloud Console, add the scope
#     `https://www.googleapis.com/auth/webmasters` to the OAuth
#     consent screen of the SAME client used for Google login.
#   - Add `<frontend_origin>/gsc/callback` to its Authorized Redirect URIs.
#   - No new env vars are needed: GSC will reuse GOOGLE_OAUTH_CLIENT_ID /
#     GOOGLE_OAUTH_CLIENT_SECRET, and derive the redirect URI from
#     settings.GOOGLE_OAUTH_CALLBACK_URL by swapping the path segment.
#
# Advanced setup (separate OAuth client just for GSC) - optional override:
#   GSC_CLIENT_ID       Google Cloud OAuth2 client ID (overrides login client)
#   GSC_CLIENT_SECRET   Google Cloud OAuth2 client secret
#   GSC_REDIRECT_URI    Must match an authorized redirect URI on that client.
#
# See backend/sites_mgmt/GSC_SETUP.md for full setup instructions.

# Scope COMPLET : voir le commentaire de proof_loop.GSC_SCOPES. `webmasters`
# inclut tout ce que `webmasters.readonly` couvrait ; les jetons deja emis
# restent valides en LECTURE, seule l'ECRITURE (sitemaps.submit) exige une
# reconnexion, et le code le signale explicitement au lieu d'echouer sec.
GSC_SCOPES = ['https://www.googleapis.com/auth/webmasters']
GSC_TOKEN_URI = 'https://oauth2.googleapis.com/token'
GSC_AUTH_URI = 'https://accounts.google.com/o/oauth2/auth'


def _gsc_default_redirect_uri():
    """Derive the GSC redirect URI from the Google login callback URL.

    Replaces the trailing `/auth/google/callback` segment with `/gsc/callback`
    so the SPA route stays consistent across environments. Returns '' if the
    login callback isn't configured.
    """
    login_cb = getattr(settings, 'GOOGLE_OAUTH_CALLBACK_URL', '') or ''
    if not login_cb:
        return ''
    if login_cb.endswith('/auth/google/callback'):
        return login_cb[: -len('/auth/google/callback')] + '/gsc/callback'
    # Fallback: best-effort substitution if the path differs.
    return login_cb.replace('/auth/google/callback', '/gsc/callback')


def _gsc_client_config():
    """Return the OAuth2 client config dict, or None if not configured.

    Reads dedicated GSC_* env vars first (advanced override). Falls back to
    the existing Google-login client (GOOGLE_OAUTH_CLIENT_ID /
    GOOGLE_OAUTH_CLIENT_SECRET) and a redirect URI derived from
    settings.GOOGLE_OAUTH_CALLBACK_URL. This means an existing Google-login
    deployment works for GSC with zero new env vars.
    """
    client_id = (
        os.environ.get('GSC_CLIENT_ID', '').strip()
        or os.environ.get('GOOGLE_OAUTH_CLIENT_ID', '').strip()
    )
    client_secret = (
        os.environ.get('GSC_CLIENT_SECRET', '').strip()
        or os.environ.get('GOOGLE_OAUTH_CLIENT_SECRET', '').strip()
    )
    redirect_uri = (
        os.environ.get('GSC_REDIRECT_URI', '').strip()
        or _gsc_default_redirect_uri()
    )
    if not (client_id and client_secret and redirect_uri):
        return None
    return {
        'web': {
            'client_id': client_id,
            'client_secret': client_secret,
            'auth_uri': GSC_AUTH_URI,
            'token_uri': GSC_TOKEN_URI,
            'redirect_uris': [redirect_uri],
        }
    }


def _gsc_canonical_site_url(site):
    """Return the canonical https URL prefix used to BUILD page URLs and
    extract slugs from rows GSC returns.

    Search Console supports two property types we need to handle:
      - URL prefix property: e.g. `https://gridar.app/`. The property string
        IS the page URL prefix - we can use it directly.
      - Domain property: e.g. `sc-domain:gridar.app`. This covers all
        subdomains and both http/https. The property string is NOT a real
        URL, so we fall back to `Site.domain` (just the hostname) wrapped
        as `https://<host>/` to build page-URL filters.

    `siteUrl` parameter sent to the Google API is always `gsc_property_url`
    as-is (the API accepts both formats). Only the page URL filter and the
    slug-extraction prefix need this canonical form.
    """
    prop = (site.gsc_property_url or '').strip()
    if prop.startswith('sc-domain:'):
        host = (site.domain or '').strip()
        # Strip leading scheme + trailing slash if user pasted them
        host = host.replace('https://', '').replace('http://', '').rstrip('/')
        if not host:
            # No domain set on the Site - fall back to the bare host from the
            # sc-domain property so we at least try to build a URL.
            host = prop[len('sc-domain:'):]
        return f'https://{host}/'
    return prop.rstrip('/') + '/' if prop else ''


def _gsc_encode_state(site_id):
    """Encode the site_id in a URL-safe base64 token."""
    raw = str(site_id).encode('utf-8')
    return base64.urlsafe_b64encode(raw).decode('utf-8').rstrip('=')


def _gsc_decode_state(state):
    """Decode a state token back to a site_id (int), or None on failure."""
    if not state:
        return None
    try:
        padded = state + '=' * (-len(state) % 4)
        raw = base64.urlsafe_b64decode(padded.encode('utf-8')).decode('utf-8')
        return int(raw)
    except Exception:
        return None


class GSCOAuthUrlView(APIView):
    """GET /api/sites/<site_id>/gsc/oauth-url/

    Returns the Google OAuth2 consent URL the user should open in order to
    authorize the dashboard to read their Search Console data.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, site_id):
        site = get_site_for_user(request, site_id)
        config = _gsc_client_config()
        if not config:
            return Response(
                {'error': 'GSC OAuth client not configured on the server.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        try:
            from google_auth_oauthlib.flow import Flow
        except ImportError:
            return Response(
                {'error': 'google-auth-oauthlib is not installed.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        try:
            # See GSCOAuthCallbackView for why this is set - same reasoning
            # applies here so the auth URL phase doesn't trip on the same
            # check if oauthlib decides to peek at it.
            os.environ.setdefault('OAUTHLIB_RELAX_TOKEN_SCOPE', '1')

            flow = Flow.from_client_config(
                config,
                scopes=GSC_SCOPES,
                redirect_uri=config['web']['redirect_uris'][0],
            )
            auth_url, _ = flow.authorization_url(
                access_type='offline',
                include_granted_scopes='true',
                prompt='consent',
                state=_gsc_encode_state(site.id),
            )
            # oauthlib 3.3+ auto-generates a PKCE code_verifier. We MUST replay
            # it in the callback fetch_token call or Google returns
            # 'invalid_grant: Missing code verifier'. Persist on the Site row
            # (DB) rather than cache so it survives across gunicorn workers
            # (LocMemCache is per-worker on Railway).
            if getattr(flow, 'code_verifier', None):
                site.gsc_oauth_verifier_pending = flow.code_verifier
                site.save(update_fields=['gsc_oauth_verifier_pending'])
            return Response({'url': auth_url})
        except Exception as e:
            logger.exception("GSC oauth-url failed")
            return Response(
                {'error': f'Failed to build OAuth URL: {e}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class GSCOAuthCallbackView(APIView):
    """POST /api/sites/<site_id>/gsc/oauth-callback/

    Body: {code, state}. Exchanges the code for tokens and stores the
    refresh_token on the Site.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, site_id):
        site = get_site_for_user(request, site_id)
        code = (request.data or {}).get('code', '').strip()
        state = (request.data or {}).get('state', '').strip()
        if not code:
            return Response({'error': 'Missing code.'}, status=status.HTTP_400_BAD_REQUEST)

        expected_site_id = _gsc_decode_state(state)
        if expected_site_id is not None and expected_site_id != site.id:
            return Response({'error': 'State mismatch.'}, status=status.HTTP_400_BAD_REQUEST)

        config = _gsc_client_config()
        if not config:
            return Response(
                {'error': 'GSC OAuth client not configured on the server.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        try:
            from google_auth_oauthlib.flow import Flow
        except ImportError:
            return Response(
                {'error': 'google-auth-oauthlib is not installed.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        try:
            # When the GSC OAuth client is the same as the Google login
            # client (recommended setup), Google returns the union of all
            # scopes already granted to the user (openid + profile + email
            # from login PLUS webmasters we just requested).
            # oauthlib's strict scope-equality check rejects this. Telling
            # oauthlib to relax via env flag is the supported workaround -
            # the granted-scope set is still validated by Google itself on
            # subsequent API calls, so we don't lose security.
            os.environ.setdefault('OAUTHLIB_RELAX_TOKEN_SCOPE', '1')

            flow = Flow.from_client_config(
                config,
                scopes=GSC_SCOPES,
                redirect_uri=config['web']['redirect_uris'][0],
            )
            # Replay the PKCE code_verifier we generated when building the
            # auth URL. Without this Google returns
            # 'invalid_grant: Missing code verifier' on the token exchange.
            if site.gsc_oauth_verifier_pending:
                flow.code_verifier = site.gsc_oauth_verifier_pending
            flow.fetch_token(code=code)
            creds = flow.credentials
            if not creds.refresh_token:
                # Clear the verifier even on this controlled failure so the
                # next attempt starts clean.
                site.gsc_oauth_verifier_pending = ''
                site.save(update_fields=['gsc_oauth_verifier_pending'])
                return Response(
                    {'error': 'No refresh token returned. Revoke app access on Google and retry.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            site.gsc_refresh_token = creds.refresh_token
            site.gsc_oauth_verifier_pending = ''
            site.save(update_fields=['gsc_refresh_token', 'gsc_oauth_verifier_pending'])
            # Renseigner la PROPRIETE tout de suite. Sans ca, le site restait
            # "connecte" avec un jeton mais sans propriete, et tout ce qui gate
            # sur gsc_property_url mourait en silence (constate le 2026-07-29
            # sur qrstudio.agency : audit d'index, proof loop, decay, positions
            # tous inertes alors que Darius avait bien connecte GSC).
            propriete = ''
            try:
                from .proof_loop import _build_gsc_service, resolve_gsc_property
                svc = _build_gsc_service(site)
                if svc is not None:
                    propriete = resolve_gsc_property(svc, site)  # decouvre ET persiste
                    site.refresh_from_db(fields=['gsc_property_url'])
            except Exception:
                logger.exception('GSC callback: decouverte de la propriete impossible (site %s)', site.id)
            return Response({
                'success': True,
                'gsc_property_url': site.gsc_property_url or '',
                'propriete_resolue': propriete,
                'avertissement': (
                    "Jeton enregistre, mais aucune propriete Search Console verifiee ne "
                    "correspond a ce domaine. Verifie la propriete dans Search Console avec "
                    "le meme compte Google, puis reconnecte."
                ) if not site.gsc_property_url else '',
            })
        except Exception as e:
            # Clear the verifier on failure so the next attempt gets a fresh
            # one (the existing verifier is now associated with a consumed or
            # invalid code).
            site.gsc_oauth_verifier_pending = ''
            site.save(update_fields=['gsc_oauth_verifier_pending'])
            logger.exception("GSC oauth-callback failed")
            return Response(
                {'error': f'Token exchange failed: {e}'},
                status=status.HTTP_400_BAD_REQUEST,
            )


class GSCDisconnectView(APIView):
    """DELETE /api/sites/<site_id>/gsc/

    Clears the stored OAuth refresh token so the integration card flips back
    to the "not connected" state. The gsc_property_url string the user typed
    is left intact (it's not sensitive and is annoying to retype); only the
    Google grant is removed, letting them re-link a different account.
    """
    permission_classes = [IsAuthenticated]

    def delete(self, request, site_id):
        site = get_site_for_user(request, site_id)
        site.gsc_refresh_token = ''
        site.gsc_oauth_verifier_pending = ''
        site.save(update_fields=['gsc_refresh_token', 'gsc_oauth_verifier_pending'])
        return Response({'success': True})


class GSCQueriesView(APIView):
    """GET /api/sites/<site_id>/gsc/queries/?slug=<slug>&days=28

    Returns top queries for a given article (slug) from Search Console.
    On auth failure returns 401 with code 'gsc_reauth_required'.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, site_id):
        site = get_site_for_user(request, site_id)
        slug = request.query_params.get('slug', '').strip()
        try:
            days = int(request.query_params.get('days', '28'))
        except (TypeError, ValueError):
            days = 28
        days = max(1, min(days, 90))

        if not slug:
            return Response({'error': 'slug is required.'}, status=status.HTTP_400_BAD_REQUEST)
        # Gate sur le JETON seul. Exiger aussi gsc_property_url ici est la 3e
        # porte de la meme famille que _build_gsc_service (proof_loop.py) et
        # _gsc_inspect_urls (index_coverage.py) : le callback OAuth sauve le
        # jeton mais jamais la propriete, et resolve_gsc_property sait
        # desormais la decouvrir ET la persister. La bloquer ici avant que
        # resolve_gsc_property ait pu tourner laissait un site connecte
        # (qrstudio.agency) repondre 400 sur /gsc/queries/.
        if not site.gsc_refresh_token:
            return Response(
                {'error': 'Reconnecte GSC', 'code': 'gsc_reauth_required'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        config = _gsc_client_config()
        if not config:
            return Response(
                {'error': 'GSC OAuth client not configured on the server.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        try:
            from datetime import date as _date, timedelta
            from google.oauth2.credentials import Credentials
            from google.auth.exceptions import RefreshError
            from googleapiclient.discovery import build
            from googleapiclient.errors import HttpError
        except ImportError:
            return Response(
                {'error': 'Google API libraries are not installed.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        end = _date.today()
        start = end - timedelta(days=days)

        try:
            creds = Credentials(
                token=None,
                refresh_token=site.gsc_refresh_token,
                token_uri=GSC_TOKEN_URI,
                client_id=config['web']['client_id'],
                client_secret=config['web']['client_secret'],
                # Pas de scopes= : voir proof_loop._build_gsc_service. Le scope vient du
                # consentement ; le passer ici ne fait que declencher un WARNING sur les
                # jetons emis avant l'elargissement du scope.
            )
            service = build(
                'searchconsole', 'v1',
                credentials=creds,
                cache_discovery=False,
            )
            from .proof_loop import resolve_gsc_property
            gsc_site_url = resolve_gsc_property(service, site)  # discovers AND persists when empty

            # Build a full page URL = canonical site URL + slug/. Compute this
            # AFTER resolve_gsc_property: the stored field may have been EMPTY
            # coming in (the OAuth callback bug) and resolve_gsc_property just
            # discovered and persisted it in-place on `site`. Last-resort
            # fallback to Site.domain if no verified property was found at
            # all, same safety net as _post_public_url in proof_loop.py.
            property_url = _gsc_canonical_site_url(site)
            if not property_url and site.domain:
                property_url = f'https://{site.domain.strip("/")}/'
            if not property_url:
                return Response(
                    {'error': (
                        "Aucune propriete Search Console verifiee ne correspond a ce "
                        "site pour le compte Google connecte, et aucun domaine n'est "
                        "configure pour construire l'URL de page. Verifie la propriete "
                        "dans Search Console avec le meme compte Google, puis reconnecte."
                    )},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            # The page filter must match the URL Google actually indexed.
            # property_url + slug misses blogs living under a path
            # (/blog/<slug>) and forces a trailing slash Next.js canonicals
            # don't have; build the URL like the public sitemap does instead.
            # WordPress keeps the historical guess (default /%postname%/
            # permalink): _public_article_url needs wp_link there.
            if site.is_wordpress:
                page_url = property_url + slug.strip('/') + '/'
            else:
                article = {'slug': slug}
                if site.is_hosted:
                    hp = HostedPost.objects.filter(
                        site=site, slug=slug,
                    ).only('language').first()
                    if hp:
                        article['language'] = hp.language
                page_url = _public_article_url(site, article) or (
                    property_url + slug.strip('/') + '/'
                )

            body = {
                'startDate': start.isoformat(),
                'endDate': end.isoformat(),
                'dimensions': ['query'],
                'rowLimit': 25,
                'dimensionFilterGroups': [{
                    'filters': [{
                        'dimension': 'page',
                        'operator': 'equals',
                        'expression': page_url,
                    }],
                }],
            }
            resp = service.searchanalytics().query(
                siteUrl=gsc_site_url,
                body=body,
            ).execute()
        except RefreshError:
            return Response(
                {'error': 'Reconnecte GSC', 'code': 'gsc_reauth_required'},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        except HttpError as e:
            status_code = getattr(getattr(e, 'resp', None), 'status', 500)
            if status_code in (401, 403):
                return Response(
                    {'error': 'Reconnecte GSC', 'code': 'gsc_reauth_required'},
                    status=status.HTTP_401_UNAUTHORIZED,
                )
            logger.exception("GSC searchanalytics HttpError")
            return Response(
                {'error': f'Search Console API error: {e}'},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except Exception as e:
            logger.exception("GSC searchanalytics failed")
            return Response(
                {'error': f'Unexpected error: {e}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        rows = resp.get('rows', []) or []
        queries = []
        for row in rows:
            keys = row.get('keys') or []
            query = keys[0] if keys else ''
            queries.append({
                'query': query,
                'clicks': int(row.get('clicks', 0) or 0),
                'impressions': int(row.get('impressions', 0) or 0),
                'ctr': float(row.get('ctr', 0.0) or 0.0),
                'position': float(row.get('position', 0.0) or 0.0),
            })
        queries.sort(key=lambda r: r['clicks'], reverse=True)
        return Response({'page_url': page_url, 'days': days, 'queries': queries})


# ============================================================================
# Shopify connection endpoints
# ============================================================================

class ShopifyDiscoverView(APIView):
    """Probe a Shopify domain + token to confirm credentials work and list blogs.

    POST /shopify/discover/ {domain, token}
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        domain = (request.data.get('domain') or '').strip()
        token = (request.data.get('token') or '').strip()
        if not domain or not token:
            return Response(
                {'error': 'domain et token requis'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        from .shopify_adapter import ShopifyClient
        result = ShopifyClient.discover(domain, token)
        if not result.get('valid'):
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
        return Response(result)


class ShopifyConnectView(APIView):
    """Authenticate with a Shopify store and create/update a Site row for it.

    POST /shopify/connect/ {domain, token, blog_id?, name?}
    On success returns the Site dict - frontend can then redirect to the dashboard.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        domain = (request.data.get('domain') or '').strip()
        token = (request.data.get('token') or '').strip()
        blog_id = (request.data.get('blog_id') or '').strip()
        explicit_name = (request.data.get('name') or '').strip()
        theme_config = request.data.get('theme_config')
        if not isinstance(theme_config, dict):
            theme_config = None

        if not domain or not token:
            return Response(
                {'error': 'domain et token requis'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from .shopify_adapter import ShopifyClient, ShopifyError

        # Discovery validates the token and returns the list of blogs.
        discovery = ShopifyClient.discover(domain, token)
        if not discovery.get('valid'):
            return Response(
                {'error': discovery.get('error') or 'Boutique Shopify non détectée.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        normalized_domain = discovery['normalized_domain']
        # If user didn't pick a blog_id, default to the primary one.
        if not blog_id:
            blog_id = discovery.get('primary_blog_id') or ''
        if not blog_id:
            return Response(
                {'error': "Cette boutique n'a aucun blog. Crée-en un dans Shopify Admin → Online Store → Blog posts."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Validate that the blog_id is one of the discovered blogs.
        valid_blog_ids = {b['id'] for b in discovery.get('blogs') or []}
        if str(blog_id) not in valid_blog_ids:
            return Response(
                {'error': "Le blog_id sélectionné n'existe pas dans cette boutique."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        site_name = (
            explicit_name
            or discovery.get('shop_name')
            or normalized_domain.replace('.myshopify.com', '')
            or 'Boutique Shopify'
        )

        try:
            site = Site.objects.filter(
                owner=request.user, shopify_domain=normalized_domain
            ).first()
            if not site:
                # New connection - enforce sites_max
                from .quota import check_site_quota
                try:
                    check_site_quota(request.user)
                except DRFPermissionDenied as e:
                    return Response(
                        {'error': str(e), 'quota_exceeded': True, 'limit_type': 'sites'},
                        status=status.HTTP_402_PAYMENT_REQUIRED,
                    )
                custom_domain = (discovery.get('custom_domain') or '').strip()
                site = Site(
                    owner=request.user,
                    name=site_name,
                    domain=custom_domain or normalized_domain,
                    description=f"Boutique Shopify : {site_name}",
                )
            site.shopify_domain = normalized_domain
            site.shopify_access_token = token
            site.shopify_blog_id = str(blog_id)
            # Refresh the visible domain to the custom one if Shopify reports it.
            custom_domain = (discovery.get('custom_domain') or '').strip()
            if custom_domain:
                site.domain = custom_domain
            if theme_config:
                site.theme_config = theme_config
            site.save()

            # Confirm the credentials still work post-save.
            ShopifyClient(site).test_auth()
        except ShopifyError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception('Shopify connect failed')
            return Response(
                {'error': f'Erreur inattendue : {str(e)[:120]}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response({
            'site': {
                'id': site.id,
                'name': site.name,
                'domain': site.domain,
                'shopify_domain': site.shopify_domain,
                'shopify_blog_id': site.shopify_blog_id,
                'is_shopify': True,
            },
            'shop': {
                'name': discovery.get('shop_name'),
                'email': discovery.get('shop_email'),
                'currency': discovery.get('shop_currency'),
                'primary_locale': discovery.get('shop_primary_locale'),
                'custom_domain': discovery.get('custom_domain'),
            },
            'blogs': discovery.get('blogs') or [],
        }, status=status.HTTP_201_CREATED)


# ============================================================================
# Public sitemap.xml + rss.xml per site
# ============================================================================

def _public_article_url(site, article):
    """Return the canonical public URL for an article on the user's site.
    Best-effort across all modes. Returns '' if we genuinely can't compute it.
    """
    domain = (site.domain or '').strip().rstrip('/')
    if not domain.startswith('http'):
        domain = f'https://{domain}'

    # WordPress already gives us the canonical link
    if site.is_wordpress and article.get('wp_link'):
        return article['wp_link']
    # Shopify: /blogs/{blog_handle}/{slug}
    if site.is_shopify:
        slug = article.get('slug', '')
        # We don't store the blog handle on Site; default to 'news' (Shopify default).
        return f"{domain}/blogs/news/{slug}".rstrip('/')
    # Webflow: needs a collection-specific path; site.domain is best-effort
    if site.is_webflow:
        slug = article.get('slug', '')
        return f"{domain}/blog/{slug}".rstrip('/')
    # Hosted (our public-blog Next.js)
    if site.public_blog_domain:
        slug = article.get('slug', '')
        lang = article.get('language', 'fr')
        # Hosted blog renders as / for FR or /<lang>/ for non-FR
        prefix = '' if lang == 'fr' else f'/{lang}'
        return f"https://{site.public_blog_domain}{prefix}/{slug}".rstrip('/')
    # External / hosted-fallback: assume /blog/<slug>
    slug = article.get('slug', '')
    return f"{domain}/blog/{slug}".rstrip('/')


def _collect_published_articles(site, limit=2000):
    """Return a flat list of published article dicts {slug, title, excerpt,
    published_at, updated_at, language} for the given site, regardless of mode."""
    out = []
    if site.is_wordpress:
        try:
            from .wordpress_adapter import WordPressClient, WordPressError
            page = WordPressClient(site).list_posts(status='published', per_page=min(100, limit))
            for p in page.get('results', []):
                out.append({
                    'slug': p.get('slug', ''),
                    'title': p.get('title', ''),
                    'excerpt': p.get('excerpt', ''),
                    'published_at': p.get('published_at') or p.get('created_at'),
                    'updated_at': p.get('updated_at') or p.get('published_at'),
                    'language': p.get('language', 'fr'),
                    'wp_link': p.get('wp_link', ''),
                    'cover_image': p.get('cover_image', ''),
                })
        except Exception:
            pass
        return out
    if site.is_shopify:
        try:
            from .shopify_adapter import ShopifyClient, ShopifyError
            page = ShopifyClient(site).list_posts(status='published', per_page=min(250, limit))
            for p in page.get('results', []):
                out.append({
                    'slug': p.get('slug', ''),
                    'title': p.get('title', ''),
                    'excerpt': p.get('excerpt', ''),
                    'published_at': p.get('published_at') or p.get('created_at'),
                    'updated_at': p.get('updated_at') or p.get('published_at'),
                    'language': p.get('language', 'fr'),
                    'cover_image': p.get('cover_image', ''),
                })
        except Exception:
            pass
        return out
    if site.is_webflow:
        try:
            from .webflow_adapter import WebflowClient, WebflowError
            page = WebflowClient(site).list_posts(status='published', per_page=min(100, limit))
            for p in page.get('results', []):
                out.append({
                    'slug': p.get('slug', ''),
                    'title': p.get('title', ''),
                    'excerpt': p.get('excerpt', ''),
                    'published_at': p.get('published_at') or p.get('created_at'),
                    'updated_at': p.get('updated_at') or p.get('published_at'),
                    'language': p.get('language', 'fr'),
                    'cover_image': p.get('cover_image', ''),
                })
        except Exception:
            pass
        return out
    if site.is_hosted:
        from .models import HostedPost
        qs = HostedPost.objects.filter(site=site, status='published').order_by('-published_at')[:limit]
        for p in qs:
            out.append({
                'slug': p.slug,
                'title': p.title,
                'excerpt': p.excerpt or '',
                'published_at': p.published_at.isoformat() if p.published_at else '',
                'updated_at': p.updated_at.isoformat() if p.updated_at else '',
                'language': p.language or 'fr',
                'cover_image': p.cover_image or '',
            })
        return out
    # External Postgres
    try:
        alias = ensure_site_connection(site)
        qs = (
            BlogPost.objects.using(alias)
            .filter(status='published')
            .order_by('-published_at')[:limit]
        )
        for p in qs:
            out.append({
                'slug': p.slug,
                'title': p.title,
                'excerpt': getattr(p, 'excerpt', '') or '',
                'published_at': p.published_at.isoformat() if p.published_at else '',
                'updated_at': p.updated_at.isoformat() if p.updated_at else '',
                'language': getattr(p, 'language', 'fr'),
                'cover_image': getattr(p, 'cover_image', '') or '',
            })
    except Exception:
        pass
    return out


def _xml_escape(s):
    return (
        (s or '')
        .replace('&', '&amp;')
        .replace('<', '&lt;')
        .replace('>', '&gt;')
        .replace('"', '&quot;')
        .replace("'", '&apos;')
    )


class SiteSitemapView(APIView):
    """Public sitemap.xml for a site. No auth - must be reachable by Googlebot.
    GET /sites/<int:site_id>/sitemap.xml
    """
    authentication_classes = []
    permission_classes = []

    def get(self, request, site_id):
        from django.http import HttpResponse, Http404
        try:
            site = Site.objects.get(id=int(site_id), is_active=True)
        except (Site.DoesNotExist, ValueError, TypeError):
            raise Http404
        articles = _collect_published_articles(site, limit=10000)

        urls_xml = []
        for a in articles:
            loc = _public_article_url(site, a)
            if not loc:
                continue
            lastmod = (a.get('updated_at') or a.get('published_at') or '')[:10]
            urls_xml.append(
                f'  <url><loc>{_xml_escape(loc)}</loc>'
                + (f'<lastmod>{_xml_escape(lastmod)}</lastmod>' if lastmod else '')
                + '<changefreq>weekly</changefreq><priority>0.7</priority></url>'
            )

        body = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            + '\n'.join(urls_xml)
            + '\n</urlset>'
        )
        resp = HttpResponse(body, content_type='application/xml; charset=utf-8')
        resp['Cache-Control'] = 'public, max-age=3600, s-maxage=3600'
        return resp


class SiteRSSView(APIView):
    """Public RSS feed for a site. GET /sites/<int:site_id>/rss.xml"""
    authentication_classes = []
    permission_classes = []

    def get(self, request, site_id):
        from django.http import HttpResponse, Http404
        try:
            site = Site.objects.get(id=int(site_id), is_active=True)
        except (Site.DoesNotExist, ValueError, TypeError):
            raise Http404

        articles = _collect_published_articles(site, limit=50)
        domain = (site.domain or '').strip().rstrip('/')
        if not domain.startswith('http'):
            domain = f'https://{domain}'
        feed_title = _xml_escape(site.name or 'Blog')
        feed_desc = _xml_escape(site.description or '')

        items_xml = []
        for a in articles:
            link = _public_article_url(site, a)
            if not link:
                continue
            pub = a.get('published_at') or ''
            items_xml.append(
                '<item>'
                f'<title>{_xml_escape(a.get("title", ""))}</title>'
                f'<link>{_xml_escape(link)}</link>'
                f'<guid>{_xml_escape(link)}</guid>'
                + (f'<pubDate>{_xml_escape(pub)}</pubDate>' if pub else '')
                + f'<description>{_xml_escape(a.get("excerpt", ""))}</description>'
                + '</item>'
            )

        body = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">\n'
            '<channel>\n'
            f'  <title>{feed_title}</title>\n'
            f'  <link>{_xml_escape(domain)}</link>\n'
            f'  <description>{feed_desc}</description>\n'
            '  <language>fr-CA</language>\n'
            f'  <atom:link href="{_xml_escape(domain)}/rss.xml" rel="self" type="application/rss+xml"/>\n'
            + '\n'.join('  ' + x for x in items_xml)
            + '\n</channel>\n</rss>'
        )
        resp = HttpResponse(body, content_type='application/rss+xml; charset=utf-8')
        resp['Cache-Control'] = 'public, max-age=3600, s-maxage=3600'
        return resp


class MarketingSitemapView(APIView):
    """Public sitemap for gridar.app itself (marketing surface).

    Aggregates 3 sources:
      - Hard-coded static routes (/, /blog, /docs, /api-docs, /privacy, /terms)
      - HostedPost rows for the Gridar marketing site (status=published)
      - docs/*.md files walked from the repo root

    Served at GET /sitemap.xml (top-level, not under /api/). Vercel rewrites
    the same path to api.gridar.app/sitemap.xml so Googlebot reaches Django
    directly without hitting the SPA fallback.
    """
    authentication_classes = []
    permission_classes = []

    SITE = 'https://gridar.app'
    STATIC_ROUTES = [
        ('/', 'weekly', '1.0'),
        ('/blog', 'daily', '0.9'),
        ('/docs', 'weekly', '0.9'),
        ('/api-docs', 'monthly', '0.7'),
        ('/privacy', 'yearly', '0.3'),
        ('/terms', 'yearly', '0.3'),
    ]

    def get(self, request):
        import os
        from pathlib import Path
        from django.conf import settings
        from django.http import HttpResponse

        urls = []

        for path, changefreq, priority in self.STATIC_ROUTES:
            urls.append(self._url_block(
                f'{self.SITE}{path}',
                changefreq=changefreq,
                priority=priority,
            ))

        marketing_site_id = int(os.environ.get('MARKETING_SITE_ID', '6'))
        try:
            from .models import HostedPost
            posts = HostedPost.objects.filter(
                site_id=marketing_site_id,
                status='published',
            ).values('slug', 'updated_at', 'published_at')[:1000]
            for p in posts:
                slug = (p.get('slug') or '').strip()
                if not slug:
                    continue
                lm = p.get('updated_at') or p.get('published_at')
                lastmod = lm.date().isoformat() if lm else None
                urls.append(self._url_block(
                    f'{self.SITE}/blog/{slug}',
                    lastmod=lastmod,
                    changefreq='monthly',
                    priority='0.7',
                ))
        except Exception:
            logger.exception('MarketingSitemapView: HostedPost fetch failed')

        try:
            docs_dir = Path(settings.BASE_DIR).parent / 'docs'
            if docs_dir.is_dir():
                for md in sorted(docs_dir.rglob('*.md')):
                    rel = md.relative_to(docs_dir).as_posix()
                    slug = rel[:-3]
                    if slug.endswith('/README'):
                        slug = slug[:-len('/README')]
                    elif slug == 'README':
                        slug = ''
                    loc = f'{self.SITE}/docs/{slug}' if slug else f'{self.SITE}/docs'
                    if loc == f'{self.SITE}/docs':
                        continue
                    urls.append(self._url_block(
                        loc,
                        changefreq='monthly',
                        priority='0.6',
                    ))
        except Exception:
            logger.exception('MarketingSitemapView: docs walk failed')

        body = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            + '\n'.join(urls)
            + '\n</urlset>\n'
        )
        resp = HttpResponse(body, content_type='application/xml; charset=utf-8')
        resp['Cache-Control'] = 'public, max-age=3600, s-maxage=3600'
        return resp

    @staticmethod
    def _url_block(loc, lastmod=None, changefreq=None, priority=None):
        parts = [f'    <loc>{_xml_escape(loc)}</loc>']
        if lastmod:
            parts.append(f'    <lastmod>{_xml_escape(lastmod)}</lastmod>')
        if changefreq:
            parts.append(f'    <changefreq>{_xml_escape(changefreq)}</changefreq>')
        if priority:
            parts.append(f'    <priority>{_xml_escape(priority)}</priority>')
        return '  <url>\n' + '\n'.join(parts) + '\n  </url>'


# ============================================================================
# Autopilot - scheduled hands-off article generation per site
# Scheduling: Railway native cron service runs `python manage.py run_autopilot`
# hourly. No HTTP tick endpoint - the management command is called directly
# by Railway's cron infra. See SCHEDULED_JOBS.md for the full setup.
# ============================================================================


class AutopilotConfigView(APIView):
    """GET / PUT the autopilot config for a site.

    Body shape: {enabled: bool, weekly_count: int}. weekly_count is clamped
    to [1, 7]. The response also exposes computed read-only fields so the UI
    can show "Prochain run prevu: X" and the last error without a separate
    endpoint.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, site_id):
        site = get_site_for_user(request, site_id)
        return Response(self._serialize(site))

    def put(self, request, site_id):
        site = get_site_for_user(request, site_id)
        data = request.data or {}

        update_fields = []
        if 'enabled' in data:
            site.autopilot_enabled = bool(data.get('enabled'))
            update_fields.append('autopilot_enabled')
        if 'weekly_count' in data:
            try:
                wc = int(data.get('weekly_count'))
            except (TypeError, ValueError):
                wc = 2
            site.autopilot_weekly_count = max(1, min(7, wc))
            update_fields.append('autopilot_weekly_count')
        if 'auto_publish' in data:
            site.autopilot_auto_publish = bool(data.get('auto_publish'))
            update_fields.append('autopilot_auto_publish')
        if 'mode' in data:
            mode = str(data.get('mode') or '').strip()
            allowed = {choice[0] for choice in Site.AUTOPILOT_MODE_CHOICES}
            if mode in allowed:
                site.autopilot_mode = mode
                update_fields.append('autopilot_mode')
        if 'min_refresh_interval_days' in data:
            try:
                mri = int(data.get('min_refresh_interval_days'))
            except (TypeError, ValueError):
                mri = 30
            site.min_refresh_interval_days = max(1, min(365, mri))
            update_fields.append('min_refresh_interval_days')

        if update_fields:
            site.save(update_fields=update_fields)
        return Response(self._serialize(site))

    @staticmethod
    def _serialize(site):
        from datetime import timedelta
        from django.utils import timezone
        from .autopilot import is_due
        from .models import TrackedKeyword

        next_run_at = None
        if site.autopilot_enabled and site.autopilot_last_run_at:
            weekly = max(1, int(site.autopilot_weekly_count or 1))
            gap = timedelta(days=7) / weekly
            next_run_at = site.autopilot_last_run_at + gap
        elif site.autopilot_enabled:
            next_run_at = timezone.now()

        kw_count = TrackedKeyword.objects.filter(site=site, is_active=True).count()

        return {
            'enabled': site.autopilot_enabled,
            'weekly_count': site.autopilot_weekly_count,
            'auto_publish': site.autopilot_auto_publish,
            'mode': getattr(site, 'autopilot_mode', 'balanced') or 'balanced',
            'min_refresh_interval_days': getattr(site, 'min_refresh_interval_days', 30) or 30,
            'last_run_at': site.autopilot_last_run_at.isoformat() if site.autopilot_last_run_at else None,
            'last_error': site.autopilot_last_error or '',
            'next_run_at': next_run_at.isoformat() if next_run_at else None,
            'is_due': is_due(site),
            'tracked_keywords_count': kw_count,
            'ready_to_run': site.autopilot_enabled and kw_count > 0,
        }


class AutopilotRunView(APIView):
    """POST to trigger one autopilot run NOW for this site (force=True).

    Used by the "Lancer maintenant" button in the dashboard so the user can
    test the autopilot without waiting for the cron interval. Also bypasses
    the user's monthly article quota (autopilot is intentionally separate
    from manual generation accounting).
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    throttle_scope = 'ai_generate'

    def post(self, request, site_id):
        site = get_site_for_user(request, site_id)
        from .autopilot import run_one
        result = run_one(site, force=True, user=request.user)

        if result.ok:
            return Response({
                'ok': True,
                'topic': result.topic,
                'keyword_id': result.keyword_id,
                'post_id': result.post_id,
                'post_title': result.post_title,
                'article_type': result.article_type,
                'length': result.length,
            })

        status_code = status.HTTP_400_BAD_REQUEST
        if result.skipped_reason == 'no_keyword':
            status_code = status.HTTP_409_CONFLICT
        elif result.error:
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return Response({
            'ok': False,
            'skipped_reason': result.skipped_reason,
            'error': result.error,
        }, status=status_code)


# ============================================================================
# Branding extractor - scan a domain and return colors/logo/fonts
# ============================================================================

class BrandingScanView(APIView):
    """Scan a public URL and infer theme_config (colors, logo, fonts).

    POST /branding/scan/ {url, save_to_site_id?}
    If save_to_site_id is provided, the result is saved to that site's theme_config.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        url = (request.data.get('url') or '').strip()
        save_to = request.data.get('save_to_site_id')
        if not url:
            return Response(
                {'error': 'url requise'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from .branding_scanner import scan
        result = scan(url)
        if not result.get('success'):
            return Response(
                {'error': result.get('error') or 'Scan échoué.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if save_to:
            try:
                site = Site.objects.get(id=int(save_to), owner=request.user)
                site.theme_config = result['theme_config']
                # Also update domain if not already set, since we just confirmed it.
                if not site.domain:
                    parsed = urlparse(result['normalized_url'])
                    if parsed.netloc:
                        site.domain = parsed.netloc
                site.save(update_fields=['theme_config', 'domain', 'updated_at'])
                result['saved_to_site_id'] = site.id
            except (Site.DoesNotExist, ValueError, TypeError):
                return Response(
                    {'error': 'Site introuvable ou non autorisé.'},
                    status=status.HTTP_404_NOT_FOUND,
                )

        return Response(result)


# ============================================================================
# Webflow connection endpoints
# ============================================================================

class WebflowDiscoverView(APIView):
    """Validate a Webflow API token by listing sites the user has access to.
    POST /webflow/discover/ {token}
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        token = (request.data.get('token') or '').strip()
        if not token:
            return Response(
                {'error': 'token requis'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        from .webflow_adapter import WebflowClient
        result = WebflowClient.discover(token)
        if not result.get('valid'):
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
        return Response(result)


class WebflowCollectionsView(APIView):
    """List CMS collections for a chosen Webflow site.
    POST /webflow/collections/ {token, site_id}
    Returns the list with auto-detected field maps so the frontend can preview.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        token = (request.data.get('token') or '').strip()
        site_id = (request.data.get('site_id') or '').strip()
        if not token or not site_id:
            return Response(
                {'error': 'token et site_id requis'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        from .webflow_adapter import WebflowClient, WebflowError, detect_field_map
        try:
            collections = WebflowClient.list_collections(token, site_id)
        except WebflowError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        # Enrich each collection with its field map (best-effort).
        enriched = []
        for c in collections:
            entry = {
                'id': c.get('id'),
                'displayName': c.get('displayName'),
                'singularName': c.get('singularName'),
                'slug': c.get('slug'),
            }
            try:
                schema = WebflowClient.get_collection_schema(token, c.get('id'))
                entry['field_map'] = detect_field_map(schema)
                entry['fields'] = [
                    {'slug': f.get('slug'), 'displayName': f.get('displayName'), 'type': f.get('type'), 'required': f.get('isRequired')}
                    for f in (schema.get('fields') or [])
                ]
                # Flag whether the auto-mapping found a body field - this is the
                # main signal that "this collection looks like a blog".
                entry['looks_like_blog'] = bool(entry['field_map'].get('body'))
            except WebflowError:
                entry['field_map'] = None
                entry['fields'] = []
                entry['looks_like_blog'] = False
            enriched.append(entry)

        return Response({'collections': enriched})


class WebflowConnectView(APIView):
    """Connect a Webflow CMS collection as a Site for blog publishing.
    POST /webflow/connect/ {token, site_id, collection_id, field_map?, name?}
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        token = (request.data.get('token') or '').strip()
        wf_site_id = (request.data.get('site_id') or '').strip()
        collection_id = (request.data.get('collection_id') or '').strip()
        field_map = request.data.get('field_map')
        explicit_name = (request.data.get('name') or '').strip()
        theme_config = request.data.get('theme_config')
        if not isinstance(theme_config, dict):
            theme_config = None

        if not token or not wf_site_id or not collection_id:
            return Response(
                {'error': 'token, site_id et collection_id requis'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from .webflow_adapter import (
            WebflowClient, WebflowError, detect_field_map, DEFAULT_FIELD_MAP,
        )

        # Confirm token works and gather site metadata.
        discovery = WebflowClient.discover(token)
        if not discovery.get('valid'):
            return Response(
                {'error': discovery.get('error') or 'Token Webflow invalide.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        wf_site = next(
            (s for s in (discovery.get('sites') or []) if s.get('id') == wf_site_id),
            None,
        )
        if not wf_site:
            return Response(
                {'error': "Le site_id ne correspond à aucun site accessible avec ce token."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate the collection exists for this site.
        try:
            collections = WebflowClient.list_collections(token, wf_site_id)
        except WebflowError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        if not any(c.get('id') == collection_id for c in collections):
            return Response(
                {'error': "La collection_id ne correspond à aucune collection de ce site."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Auto-detect field map if not provided.
        if not isinstance(field_map, dict) or not field_map:
            try:
                schema = WebflowClient.get_collection_schema(token, collection_id)
                field_map = detect_field_map(schema)
            except WebflowError:
                field_map = dict(DEFAULT_FIELD_MAP)

        # Confirm the mapping has at least a body field, otherwise the AI's
        # generated content wouldn't go anywhere visible.
        if not field_map.get('body'):
            return Response(
                {
                    'error': "Cette collection n'a pas de champ de type RichText pour le corps de l'article. Crée un champ Rich Text dans Webflow ou choisis une autre collection.",
                    'field_map': field_map,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        site_name = (
            explicit_name
            or wf_site.get('displayName')
            or wf_site.get('shortName')
            or 'Site Webflow'
        )
        primary_domain = ''
        if wf_site.get('customDomains'):
            primary_domain = wf_site['customDomains'][0]
        elif wf_site.get('shortName'):
            primary_domain = f"{wf_site['shortName']}.webflow.io"

        try:
            site = Site.objects.filter(
                owner=request.user, webflow_site_id=wf_site_id, webflow_collection_id=collection_id
            ).first()
            if not site:
                # New connection - enforce sites_max
                from .quota import check_site_quota
                try:
                    check_site_quota(request.user)
                except DRFPermissionDenied as e:
                    return Response(
                        {'error': str(e), 'quota_exceeded': True, 'limit_type': 'sites'},
                        status=status.HTTP_402_PAYMENT_REQUIRED,
                    )
                site = Site(
                    owner=request.user,
                    name=site_name,
                    domain=primary_domain or site_name,
                    description=f"Site Webflow : {site_name}",
                )
            site.webflow_token = token
            site.webflow_site_id = wf_site_id
            site.webflow_collection_id = collection_id
            site.webflow_field_map = field_map
            if primary_domain:
                site.domain = primary_domain
            if theme_config:
                site.theme_config = theme_config
            site.save()

            # Final auth check via the constructed client.
            WebflowClient(site).test_auth()
        except WebflowError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception('Webflow connect failed')
            return Response(
                {'error': f'Erreur inattendue : {str(e)[:120]}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response({
            'site': {
                'id': site.id,
                'name': site.name,
                'domain': site.domain,
                'webflow_site_id': site.webflow_site_id,
                'webflow_collection_id': site.webflow_collection_id,
                'is_webflow': True,
            },
            'webflow_site': {
                'displayName': wf_site.get('displayName'),
                'shortName': wf_site.get('shortName'),
                'customDomains': wf_site.get('customDomains') or [],
            },
            'field_map': field_map,
        }, status=status.HTTP_201_CREATED)


class PostFeedbackView(APIView):
    """Route user feedback on an AI-generated post back to the SiteMemory
    chunks that contributed to its generation.

    POST /api/sites/<site_id>/posts/<slug>/feedback/
        Body: {rating: 1 | -1 | 0}
            1  = "good article, boost these chunks"
            -1 = "bad article, penalize these chunks"
            0  = "reset (undo previous rating)"

    Updates SiteMemory.feedback_score by the delta between the post's prior
    rating and the new rating, on every chunk in HostedPost.memory_chunks_used.
    Idempotent: clicking thumbs-up twice doesn't double-count.

    Effect: retrieve() subtracts feedback_score*0.01 from cosine distance, so
    chunks repeatedly involved in "good" articles surface earlier. Effect is
    capped by retrieve() at ±0.5 equivalent so a few hot chunks can't drown
    out semantic match.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, site_id, slug):
        from django.db.models import F
        from .models import HostedPost, SiteMemory

        site = get_object_or_404(Site, pk=site_id, owner=request.user)
        post = get_object_or_404(HostedPost, site=site, slug=slug)

        try:
            new_rating = int(request.data.get('rating', 0))
        except (TypeError, ValueError):
            return Response(
                {'error': 'rating doit etre 1, -1 ou 0'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if new_rating not in (-1, 0, 1):
            return Response(
                {'error': 'rating doit etre 1, -1 ou 0'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        chunk_ids = post.memory_chunks_used or []
        if not chunk_ids:
            return Response(
                {'error': "Cet article n'a pas ete genere avec la memoire RAG, "
                          "aucun chunk a feedback-er."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Apply delta: subtract the OLD rating, then add the NEW one, so the
        # operation is idempotent and reversible.
        delta = new_rating - post.feedback_rating
        if delta == 0:
            return Response({
                'rating': new_rating,
                'chunks_affected': 0,
                'message': 'Pas de changement (meme rating).',
            })

        updated = SiteMemory.objects.filter(
            site=site, id__in=chunk_ids,
        ).update(feedback_score=F('feedback_score') + delta)

        post.feedback_rating = new_rating
        post.save(update_fields=['feedback_rating', 'updated_at'])

        return Response({
            'rating': new_rating,
            'delta': delta,
            'chunks_affected': updated,
            'chunk_ids': chunk_ids,
        })


class SiteMemoryView(APIView):
    """List + manage SiteMemory rows for a site.

    GET  /api/sites/<id>/memories/?kind=manual
        Returns paginated rows + counts by kind. Strips the raw embedding
        (huge, never needed client-side).
    POST /api/sites/<id>/memories/
        Body: {content: str, title?: str, kind?: 'manual'}
        Creates a manual memory + auto-embeds.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, site_id):
        site = get_object_or_404(Site, pk=site_id, owner=request.user)
        kind = request.query_params.get('kind')
        from .models import SiteMemory
        from collections import Counter

        qs = SiteMemory.objects.filter(site=site).order_by('-updated_at')
        # counts_by_kind = number of chunks (rows) per kind.
        # sources_by_kind = number of distinct source_ref per kind (e.g. 1
        # HostedPost = 1 source = N chunks). This separation matters in the
        # UI so users don't think "101 articles" = 101 distinct posts.
        all_pairs = list(qs.values_list('kind', 'source_ref'))
        counts = dict(Counter(k for k, _ in all_pairs))
        seen_sources = {}
        for k, sref in all_pairs:
            seen_sources.setdefault(k, set()).add(sref or '')
        sources = {k: len(v) for k, v in seen_sources.items()}
        if kind:
            qs = qs.filter(kind=kind)

        rows = []
        for m in qs[:100]:
            rows.append({
                'id': m.id,
                'kind': m.kind,
                'title': m.title,
                'content_preview': m.content[:200],
                'token_count': m.token_count,
                'source_ref': m.source_ref,
                'has_embedding': m.embedding is not None,
                'updated_at': m.updated_at.isoformat(),
            })
        return Response({
            'memories': rows,
            'counts_by_kind': counts,
            'sources_by_kind': sources,
            'total': sum(counts.values()),
        })

    def post(self, request, site_id):
        site = get_object_or_404(Site, pk=site_id, owner=request.user)
        content = (request.data.get('content') or '').strip()
        title = (request.data.get('title') or '').strip()
        kind = (request.data.get('kind') or 'manual').strip()

        if kind not in ('manual', 'decision'):
            return Response(
                {'error': "Seuls 'manual' et 'decision' sont autorises en creation manuelle."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not content:
            return Response(
                {'error': 'Content vide.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Use indexer so we get chunking + dedup + embedding consistently.
        # source_ref includes a timestamp so the user can create multiple
        # manual notes without one overwriting the other.
        from datetime import datetime as _dt
        from .memory_index import index_source

        ref = f'{kind}:{_dt.utcnow().strftime("%Y%m%d%H%M%S")}'
        result = index_source(
            site=site, kind=kind, content=content,
            source_ref=ref, title=title,
        )
        return Response({
            'created': result.get('created', 0),
            'source_ref': ref,
            'error': result.get('error'),
        }, status=status.HTTP_201_CREATED if not result.get('error') else status.HTTP_502_BAD_GATEWAY)


class SiteMemoryDetailView(APIView):
    """DELETE /api/sites/<id>/memories/<memory_id>/ - remove one memory."""
    permission_classes = [IsAuthenticated]

    def delete(self, request, site_id, pk):
        from .models import SiteMemory
        site = get_object_or_404(Site, pk=site_id, owner=request.user)
        m = get_object_or_404(SiteMemory, pk=pk, site=site)
        m.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class SiteMemoryRebuildView(APIView):
    """POST /api/sites/<id>/memories/rebuild/ - trigger full re-index of
    HostedPost + Site.knowledge_base.

    Runs synchronously (blocking) since the user clicked a button and expects
    feedback. For sites with >50 articles, will take ~30-60s.
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    throttle_scope = 'ai_generate'

    def post(self, request, site_id):
        site = get_object_or_404(Site, pk=site_id, owner=request.user)
        from .memory_index import index_source
        from .models import HostedPost, SiteMemory

        wipe = bool(request.data.get('wipe'))
        if wipe:
            SiteMemory.objects.filter(site=site).delete()

        # 1. KB
        kb_result = {'created': 0, 'reused': 0}
        if site.knowledge_base:
            kb_result = index_source(
                site=site, kind='kb', content=site.knowledge_base,
                source_ref='site-kb', title='Knowledge base',
            )

        # 2. Articles
        articles_processed = 0
        articles_errors = []
        for p in HostedPost.objects.filter(site=site, status='published'):
            full = f"# {p.title}\n\n{p.content or ''}"
            r = index_source(
                site=site, kind='article', content=full,
                source_ref=f'hosted:{p.slug}', title=p.title,
            )
            if r.get('error'):
                articles_errors.append({'slug': p.slug, 'error': r['error']})
            else:
                articles_processed += 1

        from collections import Counter
        counts = Counter(SiteMemory.objects.filter(site=site).values_list('kind', flat=True))
        return Response({
            'kb': kb_result,
            'articles_processed': articles_processed,
            'articles_errors': articles_errors,
            'counts_by_kind': dict(counts),
            'total_memories': sum(counts.values()),
        })


class SuggestCompetitorsView(APIView):
    """Suggest competitor brand names for a Site so the user can pre-fill the
    Site.competitors field.

    Method: Serper SERP scrape of "{name} alternatives" + "{name} competitors"
    -> Claude shrinks the noisy SERP titles/domains/snippets into a clean JSON
    list of 5-10 plausible competitor brand names, scoped to the site's niche.

    Why both: Serper anchors the answer in real market data (Claude alone
    hallucinates plausible-sounding brands that don't exist); Claude cleans up
    the SERP noise (self-listings, listicles, generic words).

    Output: {competitors: [str, ...]} - one name per line, ready to paste into
    the Site.competitors textarea. The user reviews and edits before saving.
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    throttle_scope = 'ai_generate'

    def post(self, request, site_id):
        import json as _json
        import re

        site = get_object_or_404(Site, pk=site_id, owner=request.user)
        if not site.name:
            return Response(
                {'error': "Le site doit avoir un nom pour suggerer des concurrents."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serper_key = os.environ.get('SERPER_API_KEY')
        anthropic_key = os.environ.get('ANTHROPIC_API_KEY')
        if not anthropic_key:
            return Response(
                {'error': 'ANTHROPIC_API_KEY non configuree.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # Hint from the site's own domain so we filter out self-listings.
        own_domain = (site.domain or '').lower().strip().rstrip('/')

        serp_lines = []
        if serper_key:
            queries = [
                f'"{site.name}" alternatives',
                f'"{site.name}" competitors',
            ]
            for q in queries:
                try:
                    r = http_requests.post(
                        'https://google.serper.dev/search',
                        headers={'X-API-KEY': serper_key, 'Content-Type': 'application/json'},
                        json={'q': q, 'num': 8, 'hl': 'fr', 'gl': 'ca'},
                        timeout=10,
                    )
                    if r.status_code == 200:
                        for item in (r.json().get('organic') or [])[:8]:
                            link = (item.get('link') or '').lower()
                            if own_domain and own_domain in link:
                                continue
                            title = (item.get('title') or '').strip()
                            snippet = (item.get('snippet') or '').strip()
                            if title:
                                serp_lines.append(f'- {title} | {link} | {snippet[:160]}')
                except Exception:
                    pass

        serp_block = '\n'.join(serp_lines[:25]) if serp_lines else '(pas de donnees Serper disponibles)'

        prompt = f"""Tu es un analyste marketing. Liste les concurrents directs de la marque suivante.

MARQUE:
- Nom: {site.name}
- Domaine: {site.domain or '(non renseigne)'}
- Description: {site.description or '(non renseignee)'}

CONTEXTE SERP (resultats Google pour "{site.name} alternatives" et "{site.name} competitors"):
{serp_block}

Ta tache: identifie 5 a 10 concurrents directs. Sois STRICT:
- Uniquement des marques/produits qui s'adressent au meme public avec une offre similaire.
- IGNORE les listicles ("Top 10 ..."), articles de blog, agences generalistes, et la marque elle-meme.
- IGNORE les noms generiques (ex: "logiciel de SEO", "outil SaaS").
- Si tu n'es pas sur qu'un nom soit un vrai concurrent, ne le mets pas.

Reponds UNIQUEMENT en JSON valide, sans markdown:
{{"competitors": ["NomMarque1", "NomMarque2", ...]}}
"""

        from .llm import call_llm
        text = call_llm(prompt, max_tokens=600, timeout=30)  # Anthropic -> DeepSeek
        if not text:
            return Response(
                {'error': 'Aucune reponse LLM (Anthropic + fallback DeepSeek indisponibles).'},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        match = re.search(r'\{[\s\S]*\}', text)
        if not match:
            return Response(
                {'error': 'Reponse Claude non parsable', 'raw': text[:500]},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        try:
            parsed = _json.loads(match.group())
        except _json.JSONDecodeError:
            return Response(
                {'error': 'JSON Claude invalide', 'raw': text[:500]},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        raw_list = parsed.get('competitors') or []
        # Dedup case-insensitively, strip, cap at 10.
        seen = set()
        cleaned = []
        for item in raw_list:
            if not isinstance(item, str):
                continue
            name = item.strip()
            key = name.lower()
            if not name or key in seen:
                continue
            # Skip self
            if site.name.lower() == key:
                continue
            seen.add(key)
            cleaned.append(name)
            if len(cleaned) >= 10:
                break

        return Response({
            'competitors': cleaned,
            'serp_sources_used': len(serp_lines),
        })


def _fetch_homepage_meta(domain):
    """GET the site's homepage and pull title + meta description + first H1/H2s.

    Returns {'title', 'description', 'headings', 'body_excerpt'} or {} on
    any failure. Used as anchoring context for keyword suggestions so Claude
    doesn't guess the site's niche from the brand name alone.
    """
    import re
    from urllib.parse import urlparse

    if not domain:
        return {}
    domain = domain.strip().rstrip('/')
    if not domain.startswith('http'):
        domain = f'https://{domain}'
    parsed = urlparse(domain)
    if not parsed.netloc:
        return {}

    try:
        resp = http_requests.get(
            domain,
            headers={
                'User-Agent': 'Mozilla/5.0 (compatible; GridarBot/1.0; +https://gridar.app)',
                'Accept': 'text/html,*/*;q=0.8',
            },
            timeout=8,
            allow_redirects=True,
        )
        if not resp.ok:
            return {}
        html = resp.text or ''
    except Exception:
        return {}

    def _strip_tags(s):
        s = re.sub(r'<script[^>]*>.*?</script>', '', s, flags=re.DOTALL | re.IGNORECASE)
        s = re.sub(r'<style[^>]*>.*?</style>', '', s, flags=re.DOTALL | re.IGNORECASE)
        s = re.sub(r'<[^>]+>', ' ', s)
        return re.sub(r'\s+', ' ', s).strip()

    title_m = re.search(r'<title[^>]*>(.*?)</title>', html, flags=re.DOTALL | re.IGNORECASE)
    title = _strip_tags(title_m.group(1)) if title_m else ''

    desc_m = re.search(
        r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']',
        html, flags=re.IGNORECASE,
    )
    if not desc_m:
        desc_m = re.search(
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']description["\']',
            html, flags=re.IGNORECASE,
        )
    description = _strip_tags(desc_m.group(1)) if desc_m else ''

    headings = []
    for tag in ('h1', 'h2'):
        for m in re.finditer(fr'<{tag}[^>]*>(.*?)</{tag}>', html, flags=re.DOTALL | re.IGNORECASE):
            txt = _strip_tags(m.group(1))
            if txt and txt not in headings:
                headings.append(txt)
            if len(headings) >= 8:
                break
        if len(headings) >= 8:
            break

    body_excerpt = _strip_tags(html)[:1200]

    return {
        'title': title[:200],
        'description': description[:400],
        'headings': headings[:8],
        'body_excerpt': body_excerpt,
    }


class SuggestKeywordsView(APIView):
    """Suggest tracked keywords for a Site via IA, anchored on real context.

    Pipeline:
    1. Pull top-8 RAG chunks from SiteMemory (article excerpts, KB, manual
       notes) using semantic search on the site's brand+description query.
    2. Fetch the site's homepage and extract <title>, meta description, H1/H2.
    3. Serper SERP scrape on brand + description-derived seeds (max 3),
       harvesting organic titles + relatedSearches.
    4. Claude shrinks all of that into 12-18 keyword candidates with intent
       labels (info/commercial/transactional/local). The prompt explicitly
       tells Claude to ignore the brand name and anchor on the context, since
       brand names alone are ambiguous (Gridar -> "grid AR" hallucination).
    5. Existing TrackedKeyword keywords for this site are excluded server-
       side - no need for the user to dedupe.

    Output: {keywords: [{keyword, language, intent, why}], serp_sources_used,
    rag_chunks_used, homepage_fetched}
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    throttle_scope = 'ai_generate'

    def post(self, request, site_id):
        import json as _json
        import re

        site = get_object_or_404(Site, pk=site_id, owner=request.user)
        if not site.name and not site.domain:
            return Response(
                {'error': "Le site doit avoir un nom ou un domaine pour suggerer des mots-cles."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        anthropic_key = os.environ.get('ANTHROPIC_API_KEY')
        if not anthropic_key:
            return Response(
                {'error': 'ANTHROPIC_API_KEY non configuree.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        language = (request.data.get('language') or site.default_language or 'fr').lower()
        if language not in ('fr', 'en', 'es'):
            language = 'fr'

        # Default geo from locale (e.g. fr-CA -> CA) else fallback by language.
        locale = (getattr(site, 'locale', '') or '').lower()
        gl = 'ca'
        if '-' in locale:
            gl = locale.split('-', 1)[1][:2]
        elif language == 'es':
            gl = 'es'
        elif language == 'en':
            gl = 'us'
        hl = language

        # Seed queries: brand + first 2 noun-phrases from description.
        seeds = []
        if site.name:
            seeds.append(site.name)
        desc = (site.description or '').strip()
        if desc:
            tokens = re.findall(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\-']{3,}", desc)
            seen_t = set()
            chunk = []
            for tok in tokens:
                k = tok.lower()
                if k in seen_t:
                    continue
                seen_t.add(k)
                chunk.append(tok)
                if len(chunk) == 3:
                    seeds.append(' '.join(chunk))
                    chunk = []
                if len(seeds) >= 3:
                    break

        # Existing keywords - shown to Claude so it picks fresh ones.
        existing_kw = list(
            TrackedKeyword.objects.filter(site=site, is_active=True)
            .values_list('keyword', flat=True)[:50]
        )

        own_domain = (site.domain or '').lower().strip().rstrip('/')

        serper_key = os.environ.get('SERPER_API_KEY')
        serp_titles = []
        related_queries = []
        if serper_key and seeds:
            for q in seeds[:3]:
                try:
                    r = http_requests.post(
                        'https://google.serper.dev/search',
                        headers={'X-API-KEY': serper_key, 'Content-Type': 'application/json'},
                        json={'q': q, 'num': 10, 'hl': hl, 'gl': gl},
                        timeout=10,
                    )
                    if r.status_code != 200:
                        continue
                    payload = r.json()
                    for item in (payload.get('organic') or [])[:8]:
                        link = (item.get('link') or '').lower()
                        if own_domain and own_domain in link:
                            continue
                        title = (item.get('title') or '').strip()
                        if title:
                            serp_titles.append(title)
                    for rel in (payload.get('relatedSearches') or [])[:8]:
                        q_rel = (rel.get('query') or '').strip()
                        if q_rel:
                            related_queries.append(q_rel)
                except Exception:
                    pass

        serp_block = '\n'.join(f'- {t}' for t in serp_titles[:30]) or '(pas de donnees SERP)'
        related_block = '\n'.join(f'- {q}' for q in related_queries[:20]) or '(pas de related searches)'
        existing_block = '\n'.join(f'- {k}' for k in existing_kw) or '(aucun)'

        competitors_lines = [
            l.strip() for l in (site.competitors or '').splitlines() if l.strip()
        ][:8]
        competitors_block = '\n'.join(f'- {c}' for c in competitors_lines) or '(non renseignes)'

        # 1) RAG: pull representative chunks of what this site is actually about
        #    (published articles, manual notes, KB). Anchors the suggestion in
        #    real content instead of guessing from the brand name.
        from .memory_index import retrieve, format_memory_block
        rag_query = (site.description or site.knowledge_base or site.name or site.domain or '').strip()
        rag_chunks = []
        if rag_query:
            try:
                rag_chunks = retrieve(site, query=rag_query, k=8)
            except Exception:
                logger.exception('SuggestKeywords: RAG retrieve failed for site %s', site.id)
        rag_block = format_memory_block(rag_chunks, max_chars=3500) if rag_chunks else ''

        # 2) Homepage fetch: real meta from the live site (title, description,
        #    headings). Often filled in even when site.description is empty.
        homepage = _fetch_homepage_meta(site.domain) if site.domain else {}
        homepage_block = ''
        if homepage:
            headings_str = '\n'.join(f'  - {h}' for h in homepage.get('headings', []))
            homepage_block = (
                f"## PAGE D'ACCUEIL (scrappee live)\n"
                f"- <title>: {homepage.get('title', '') or '(vide)'}\n"
                f"- <meta description>: {homepage.get('description', '') or '(vide)'}\n"
                f"- H1/H2 visibles:\n{headings_str or '  (aucune)'}\n"
                f"- Extrait du body (premiers 1200 caracteres):\n  {homepage.get('body_excerpt', '')[:1200]}\n"
            )

        # Visible warning to Claude when context is empty so it doesn't
        # hallucinate a niche from the brand name.
        context_thin = (
            not (site.description or '').strip()
            and not (site.knowledge_base or '').strip()
            and not rag_chunks
            and not homepage_block
        )

        # Build optional fallback blocks outside the f-string (Python forbids
        # backslashes inside f-string expression parts).
        rag_section = rag_block or "## MEMOIRE DU SITE\n(aucun contenu indexe pour le moment)"
        homepage_section = homepage_block or "## PAGE D-ACCUEIL\n(impossible de scraper - domaine inaccessible ou non renseigne)"
        thin_warning = (
            "ATTENTION : aucun contexte exploitable (description vide, RAG vide, homepage inaccessible). "
            "Renvoie une liste VIDE: {\"keywords\": []} et c-est tout."
            if context_thin else ""
        )

        prompt = f"""Tu es un expert SEO {language.upper()}. Propose des mots-cles que ce site devrait tracker dans Google Search Console.

## REGLE CRITIQUE
Le NOM de marque seul est ambigu et peut induire en erreur (ex: "Gridar" pourrait sonner comme "grid AR" mais c'est faux). Tu DOIS deduire la niche depuis le CONTEXTE ci-dessous (memoire du site, page d'accueil, description, knowledge base). N'utilise JAMAIS la consonance du nom pour deviner ce que fait le produit. Si le contexte est vide, dis-le dans `why` plutot que d'inventer.

## SITE
- Nom: {site.name or '(non renseigne)'}
- Domaine: {site.domain or '(non renseigne)'}
- Description (champ Site): {site.description or '(non renseignee)'}
- Knowledge base (champ Site): {(site.knowledge_base or '')[:400] or '(vide)'}
- Langue cible: {language}
- Pays cible (Google): {gl.upper()}

## CONCURRENTS DECLARES
{competitors_block}

{rag_section}

{homepage_section}

## MOTS-CLES DEJA TRACKES (ne PAS reproposer)
{existing_block}

## SIGNAL SERP (Google {hl}/{gl}) - peut etre bruite, utiliser avec prudence
Seeds utilisees: {seeds[:3]}

SERP titles:
{serp_block}

Related searches:
{related_block}

## TA TACHE
Propose 12 a 18 mots-cles a tracker, alignes avec ce que fait *reellement* ce site (lis le contexte ci-dessus AVANT d'ecrire):
- Mix d'intents: informationnel (questions, "comment", "qu'est-ce que"), commercial ("meilleur X", comparaisons), transactionnel ("acheter X", "prix X"), local ("X {gl.upper()}" si pertinent).
- Realistes (longue-traine privilegiee, evite les ultra-competitifs sans angle local).
- 100% dans la langue {language}.
- Eviter le nom de la marque seule (ce n'est pas un mot-cle a tracker).
- Eviter les doublons et les variantes triviales.
- Si le contexte est trop maigre pour decider, propose MOINS de mots-cles plutot que d'inventer.

{thin_warning}

Reponds UNIQUEMENT en JSON valide, sans markdown, schema strict:
{{"keywords": [{{"keyword": "<mot-cle>", "intent": "info|commercial|transactional|local", "why": "<1 phrase courte qui cite le contexte utilise>"}}]}}
"""

        from .llm import call_llm
        text = call_llm(prompt, max_tokens=1500, timeout=45)  # Anthropic -> DeepSeek
        if not text:
            return Response(
                {'error': 'Aucune reponse LLM (Anthropic + fallback DeepSeek indisponibles).'},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        match = re.search(r'\{[\s\S]*\}', text)
        if not match:
            return Response(
                {'error': 'Reponse Claude non parsable', 'raw': text[:500]},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        try:
            parsed = _json.loads(match.group())
        except _json.JSONDecodeError:
            return Response(
                {'error': 'JSON Claude invalide', 'raw': text[:500]},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        raw_list = parsed.get('keywords') or []
        existing_lower = {k.lower() for k in existing_kw}
        seen = set()
        cleaned = []
        for item in raw_list:
            if not isinstance(item, dict):
                continue
            kw = (item.get('keyword') or '').strip()
            if not kw:
                continue
            key = kw.lower()
            if key in seen or key in existing_lower:
                continue
            seen.add(key)
            intent = (item.get('intent') or '').strip().lower()
            if intent not in ('info', 'commercial', 'transactional', 'local'):
                intent = 'info'
            cleaned.append({
                'keyword': kw,
                'language': language,
                'intent': intent,
                'why': (item.get('why') or '').strip()[:200],
            })
            if len(cleaned) >= 20:
                break

        return Response({
            'keywords': cleaned,
            'serp_sources_used': len(serp_titles),
            'related_searches_used': len(related_queries),
            'rag_chunks_used': len(rag_chunks),
            'homepage_fetched': bool(homepage_block),
            'context_thin': context_thin,
        })


class SiteAuditAggregatorView(APIView):
    """One-shot site-level audit dashboard. Aggregates several existing
    capabilities in parallel and returns a single payload + composite score.

    GET /api/sites/<id>/site-audit/

    Combines (parallel ThreadPoolExecutor, fail-safe):
      - PageSpeed mobile + desktop on the site's homepage
      - TrackedKeywords + their latest SerpRank position
      - Backlinks count (Serper)
      - SiteStats (post counts, recent activity)
      - ContentDecay (GSC, optional)
      - Top 3 GSC queries summary (if GSC connected)

    Score composite (0-100) blends:
      - PageSpeed: avg(perf, seo, a11y) × 0.30
      - Rankings: % of tracked keywords in top 10 × 0.30
      - Backlinks: log10(referring_domains+1) × 30 (capped at 100) × 0.15
      - Content freshness: 100 - decaying_pct × 0.25  (only if GSC connected,
        otherwise the freshness weight is redistributed proportionally)

    Cached 10 min per site (data refresh cadence is daily at best).
    Each subtask is wrapped in its own try/except so one failure (missing
    API key, GSC reauth, slow response) never blocks the whole audit.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, site_id):
        import math
        from concurrent.futures import ThreadPoolExecutor, as_completed

        from .models import TrackedKeyword, SerpRank

        site = get_object_or_404(Site, pk=site_id, owner=request.user)

        cache_key = f'site-audit:{site.id}'
        cached = cache.get(cache_key)
        if cached and not request.query_params.get('refresh'):
            return Response(cached)

        # The full audit blocks on PageSpeed (up to 30s) + Serper backlinks
        # (~10s). `?fast=1` runs only the DB-backed signals (keywords, stats,
        # decay) and returns in ~1s, so the dashboard can paint immediately;
        # the frontend fires the full request in parallel to fill in PageSpeed
        # and backlinks. A warm cache (handled above) short-circuits both.
        wants_fast = request.query_params.get('fast') in ('1', 'true', 'yes')

        # Homepage URL for PageSpeed + backlinks. Some sites don't have a
        # domain set (e.g. brand-new hosted site without subdomain yet) -
        # gracefully skip PageSpeed in that case.
        homepage_url = None
        if site.domain:
            domain_clean = site.domain.strip().rstrip('/')
            if not domain_clean.startswith('http'):
                homepage_url = f'https://{domain_clean}'
            else:
                homepage_url = domain_clean

        # ── Subtasks (each returns a dict or {'error': '...'}) ─────────────

        def task_pagespeed():
            if not homepage_url:
                return {'error': 'Pas de domaine renseigne sur ce site.'}
            api_key = os.environ.get('PAGESPEED_API_KEY')
            if not api_key:
                return {'error': 'PAGESPEED_API_KEY non configuree.'}
            try:
                r = http_requests.get(
                    'https://www.googleapis.com/pagespeedonline/v5/runPagespeed',
                    params={
                        'url': homepage_url,
                        'key': api_key,
                        'strategy': 'mobile',
                        'category': ['performance', 'seo', 'accessibility'],
                    },
                    timeout=30,
                )
                if r.status_code != 200:
                    return {'error': f'PageSpeed {r.status_code}'}
                data = r.json()
                cats = data.get('lighthouseResult', {}).get('categories', {})
                perf = int((cats.get('performance', {}).get('score') or 0) * 100)
                seo = int((cats.get('seo', {}).get('score') or 0) * 100)
                a11y = int((cats.get('accessibility', {}).get('score') or 0) * 100)
                return {
                    'performance': perf,
                    'seo': seo,
                    'accessibility': a11y,
                    'avg': (perf + seo + a11y) // 3,
                    'url': homepage_url,
                }
            except Exception as e:
                return {'error': f'PageSpeed: {str(e)[:80]}'}

        def task_keywords():
            try:
                tracked_list = list(
                    TrackedKeyword.objects.filter(site=site, is_active=True)
                )
                # One bulk query for the recent snapshot window of every keyword.
                snaps_map = {}
                latest_overall = None
                if tracked_list:
                    ids = [t.id for t in tracked_list]
                    for snap in (
                        SerpRank.objects.filter(tracked_id__in=ids)
                        .order_by('tracked_id', '-recorded_at')
                    ):
                        bucket = snaps_map.setdefault(snap.tracked_id, [])
                        if len(bucket) < DEFAULT_WINDOW:
                            bucket.append(snap)
                        if latest_overall is None or snap.recorded_at > latest_overall:
                            latest_overall = snap.recorded_at

                rows = []
                top_10_count = 0
                stable_ranked_count = 0
                for tk in tracked_list:
                    snaps = snaps_map.get(tk.id) or []
                    latest = snaps[0] if snaps else None
                    disp = keyword_display_rank(tk, snapshots=snaps)
                    pos = latest.position if latest else None
                    # Honest top-10: count a keyword ONLY when it is consistently
                    # ranked (is_stable) AND its stable position is <= 10 - a
                    # single noisy #1 snapshot no longer inflates the score.
                    if disp['is_stable'] and disp['stable_position'] is not None:
                        stable_ranked_count += 1
                        if disp['stable_position'] <= 10:
                            top_10_count += 1
                    row = {
                        'id': tk.id,
                        'keyword': tk.keyword,
                        'language': tk.language,
                        'position': pos,
                        'is_target_match': latest.is_target_match if latest else None,
                        'recorded_at': latest.recorded_at.isoformat() if latest else None,
                    }
                    row.update(disp)
                    rows.append(row)
                # Sort: consistently-ranked keywords first (by stable position),
                # then the unstable/unranked ones (fall back to latest position).
                rows.sort(key=lambda r: (
                    not (r['is_stable'] and r['stable_position'] is not None),
                    r['stable_position'] if r['stable_position'] is not None
                    else (r['position'] if r['position'] is not None else 999),
                ))
                total = len(rows)
                return {
                    'total': total,
                    'top_10_count': top_10_count,
                    'top_10_pct': (top_10_count / total * 100) if total else 0,
                    'stable_ranked_count': stable_ranked_count,
                    'last_checked': latest_overall.isoformat() if latest_overall else None,
                    'rows': rows[:20],  # cap for prompt size
                }
            except Exception as e:
                return {'error': f'Keywords: {str(e)[:80]}'}

        def task_backlinks():
            if not homepage_url:
                return {'error': 'Pas de domaine'}
            api_key = os.environ.get('SERPER_API_KEY')
            if not api_key:
                return {'error': 'SERPER_API_KEY non configuree.'}
            try:
                domain_only = urlparse(homepage_url).netloc
                # This searches for the domain as a string, so it counts pages
                # that MENTION the site, linked or not. It is not a backlink
                # measure and must never be reported as one. Google retired the
                # `link:` operator, and a real link graph needs Common Crawl or
                # a paid index. Serper also caps `num` at 10 on this plan, so
                # the count saturates at 10 whatever the site's real profile.
                r = http_requests.post(
                    'https://google.serper.dev/search',
                    headers={
                        'X-API-KEY': api_key,
                        'Content-Type': 'application/json',
                    },
                    json={'q': f'"{domain_only}" -site:{domain_only}', 'num': 10},
                    timeout=10,
                )
                if r.status_code != 200:
                    return {'error': "Analyse des liens non disponible (limite de l'API de recherche)."}
                data = r.json()
                organic = data.get('organic', []) or []
                referring = {}
                for item in organic:
                    link = item.get('link') or ''
                    if not link:
                        continue
                    netloc = urlparse(link).netloc.replace('www.', '')
                    if netloc and netloc != domain_only.replace('www.', ''):
                        referring[netloc] = referring.get(netloc, 0) + 1
                return {
                    # Named for what it is. The old key was
                    # `total_referring_domains`, which claimed a link where
                    # there was only a mention, and fed 15 % of the composite
                    # score on that claim.
                    'total_mentioning_domains': len(referring),
                    'top_domains': sorted(
                        referring.items(), key=lambda kv: -kv[1]
                    )[:5],
                    'is_link_data': False,
                    'saturates_at': 10,
                    'note': (
                        'Nombre de domaines qui mentionnent le site dans les 10 '
                        'premiers resultats Google. Ce ne sont pas des liens '
                        'entrants et le compte plafonne a 10.'
                    ),
                }
            except Exception as e:
                return {'error': f'Mentions: {str(e)[:80]}'}

        def task_sitestats():
            try:
                if site.is_hosted:
                    from .models import HostedPost
                    qs = HostedPost.objects.filter(site=site)
                    return {
                        'total_posts': qs.count(),
                        'published': qs.filter(status='published').count(),
                        'drafts': qs.filter(status='draft').count(),
                        'mode': 'hosted',
                    }
                # External / CMS modes - skip; SiteStatsView handles those.
                return {
                    'total_posts': None,
                    'mode': 'external_or_cms',
                    'note': 'Stats détaillées disponibles dans la page Articles.',
                }
            except Exception as e:
                return {'error': f'SiteStats: {str(e)[:80]}'}

        def task_decay():
            # ContentDecay needs GSC. Skip if not connected to avoid 401.
            if not site.gsc_refresh_token:
                return {'gsc_not_connected': True}
            try:
                from .views import ContentDecayView  # self-reference fine
                # Reuse the view's internal logic by calling it directly.
                # The view's `get(request, site_id)` handles auth, GSC client,
                # diff, and returns Response. Cheaper than re-implementing.
                cdv = ContentDecayView()
                cdv.request = request
                # request.query_params already has whatever; we want a fresh dict
                # but DRF Request is immutable - emulate by passing default 30.
                resp = cdv.get(request, site_id)
                if resp.status_code != 200:
                    return {'error': f'Decay {resp.status_code}'}
                d = resp.data
                return {
                    'days': d.get('days'),
                    'decaying_count': d.get('decaying_count'),
                    'healthy_count': d.get('healthy_count'),
                    'new_pages_count': d.get('new_pages_count'),
                    'top_decaying': (d.get('decaying') or [])[:5],
                }
            except Exception as e:
                return {'error': f'Decay: {str(e)[:80]}'}

        # ── Run the relevant subtasks in parallel ───────────────────────────
        # Fast mode skips the two slow external calls (PageSpeed, Serper) and
        # marks them pending so the UI shows a per-card spinner instead of a
        # blank card.
        task_map = {
            'keywords': task_keywords,
            'stats': task_sitestats,
            'decay': task_decay,
        }
        if not wants_fast:
            task_map['pagespeed'] = task_pagespeed
            task_map['backlinks'] = task_backlinks

        results = {}
        with ThreadPoolExecutor(max_workers=len(task_map)) as pool:
            futures = {pool.submit(fn): key for key, fn in task_map.items()}
            for fut in as_completed(futures):
                key = futures[fut]
                try:
                    results[key] = fut.result()
                except Exception as e:
                    results[key] = {'error': str(e)[:80]}

        if wants_fast:
            # Placeholders: no 'avg' / 'total_referring_domains' key means the
            # score + recos logic below skips them (weight redistributed), and
            # the `pending` flag tells the frontend to show a spinner.
            results.setdefault('pagespeed', {'pending': True})
            results.setdefault('backlinks', {'pending': True})

        # ── Composite score (0-100) ────────────────────────────────────────
        # Weights: PageSpeed 0.30, Rankings 0.30, Backlinks 0.15, Freshness 0.25.
        # If a component is missing (error or no data), redistribute its weight
        # proportionally over the available ones.
        components = []
        ps = results.get('pagespeed', {})
        if 'avg' in ps:
            components.append(('pagespeed', ps['avg'], 0.30))
        kw = results.get('keywords', {})
        if kw.get('total', 0) > 0:
            components.append(('rankings', kw['top_10_pct'], 0.30))
        bl = results.get('backlinks', {})
        # Backlinks deliberately no longer feed the composite. The only signal
        # available here counts mentions, not links, and Serper's 10-result cap
        # held the sub-score to log10(11) * 30 = 31/100, so its 15 % weight
        # could never contribute more than 4.7 of its 15 points and every site
        # was scored under a ceiling it had no way to reach. `weight_sum` below
        # redistributes the freed weight over the components that do measure
        # something. Restore this once backlinks_commoncrawl gives real link
        # data, and gate it on data sufficiency, one source not being enough.
        decay = results.get('decay', {})
        if 'decaying_count' in decay and 'healthy_count' in decay:
            total_pages = (decay.get('decaying_count') or 0) + (decay.get('healthy_count') or 0)
            if total_pages > 0:
                fresh_score = 100 - ((decay.get('decaying_count') or 0) / total_pages * 100)
                components.append(('freshness', fresh_score, 0.25))

        if components:
            weight_sum = sum(w for _, _, w in components)
            composite = sum(score * (w / weight_sum) for _, score, w in components)
            composite_score = round(composite)
        else:
            composite_score = None  # nothing measurable yet

        # ── Recos prioritaires (actionable, capped at 5) ──────────────────
        recos = []
        if kw.get('total', 0) == 0:
            recos.append({
                'severity': 'high',
                'message': "Aucun mot-cle suivi. Ajoute tes 5-10 mots-cles cibles pour mesurer ton SEO.",
                'cta_label': 'Ajouter des mots-cles',
                'cta_href': f'/dashboard/{site.id}/positions',
            })
        elif kw.get('top_10_pct', 0) < 30:
            recos.append({
                'severity': 'medium',
                'message': f"Seulement {int(kw['top_10_pct'])}% de tes mots-cles ranquent top 10.",
                'cta_label': 'Voir les mots-cles',
                'cta_href': f'/dashboard/{site.id}/positions',
            })
        if decay.get('decaying_count', 0) >= 3:
            recos.append({
                'severity': 'high',
                'message': f"{decay['decaying_count']} articles perdent du trafic - a refresh.",
                'cta_label': 'Voir le declin',
                'cta_href': f'/dashboard/{site.id}/decay',
            })
        if 'avg' in ps and ps['avg'] < 70:
            recos.append({
                'severity': 'medium',
                'message': f"Score PageSpeed mobile = {ps['avg']}/100. Vise 80+ pour rester competitif.",
                'cta_label': 'Voir PageSpeed',
                'cta_href': f'/dashboard/{site.id}/audit-global',
            })
        # No backlink recommendation here on purpose. The old one fired below
        # 10 referring domains on a counter that saturates at 10, so it told
        # nearly every client "relance ton outreach" using a number that
        # counted mentions in the first page of Google. Telling a client
        # something false about their own site is the one thing a report
        # cannot afford. It comes back with backlinks_commoncrawl.
        if bl.get('total_mentioning_domains') == 0 and not bl.get('error'):
            recos.append({
                'severity': 'low',
                'message': (
                    "Aucun site ne mentionne ton domaine dans les premiers "
                    "resultats Google. C'est un signal de notoriete, pas une "
                    "mesure de tes liens entrants."
                ),
                'cta_label': 'Voir l audit',
                'cta_href': f'/dashboard/{site.id}/audit-global',
            })
        if not site.gsc_refresh_token:
            recos.append({
                'severity': 'medium',
                'message': "Google Search Console non connecte - tu rates les vraies positions.",
                'cta_label': 'Connecter GSC',
                'cta_href': f'/dashboard/{site.id}/parametres/gsc',
            })

        payload = {
            'site_id': site.id,
            'site_name': site.name,
            'site_domain': site.domain,
            'composite_score': composite_score,
            'score_components': [
                {'name': name, 'score': round(score), 'weight': w}
                for name, score, w in components
            ],
            'pagespeed': ps,
            'keywords': kw,
            'backlinks': bl,
            'stats': results.get('stats', {}),
            'decay': decay,
            'recos': recos[:5],
            'gsc_connected': bool(site.gsc_refresh_token),
            'partial': wants_fast,
        }

        # Only the complete audit is cached (10 min - audits update at daily
        # cadence at best). A partial payload must never populate the shared
        # cache, or the full request would short-circuit to incomplete data.
        if not wants_fast:
            cache.set(cache_key, payload, timeout=600)
        return Response(payload)


# ── Phase 2: Blog subdomain plug-and-play via Vercel API ────────────────────


def _vercel_headers():
    token = os.environ.get('VERCEL_API_TOKEN')
    if not token:
        return None
    return {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
    }


def _vercel_url(path):
    """Build a Vercel API URL with optional teamId query param."""
    team_id = os.environ.get('VERCEL_TEAM_ID')
    url = f'https://api.vercel.com{path}'
    if team_id:
        sep = '&' if '?' in path else '?'
        url = f'{url}{sep}teamId={team_id}'
    return url


class BlogDomainProvisionView(APIView):
    """POST /api/sites/<id>/blog-domain/provision/

    Adds the user's chosen subdomain (e.g. `blog.tondomaine.com`) to the
    public-blog Vercel project. Returns DNS instructions (CNAME target) the
    user copies into their DNS provider. SSL is auto-provisioned by Vercel
    once the DNS resolves.

    Body: {domain: str}
    Response: {
        domain, verified: bool, cname_target: str,
        verification: [...optional records...], next_step: str
    }

    Requires env vars VERCEL_API_TOKEN and VERCEL_PROJECT_ID (the project that
    hosts the public blog frontend). VERCEL_TEAM_ID is optional.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, site_id):
        site = get_object_or_404(Site, pk=site_id, owner=request.user)
        raw = (request.data.get('domain') or '').strip().lower()
        # Strip scheme + trailing slash if user paste it sloppy.
        raw = raw.replace('https://', '').replace('http://', '').rstrip('/')
        if not raw or '.' not in raw or ' ' in raw:
            return Response(
                {'error': 'Domaine invalide. Ex: blog.tondomaine.com'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        headers = _vercel_headers()
        project_id = os.environ.get('VERCEL_PROJECT_ID')
        if not headers or not project_id:
            return Response(
                {'error': 'VERCEL_API_TOKEN ou VERCEL_PROJECT_ID non configure '
                          'sur le serveur. Contacte le support.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        url = _vercel_url(f'/v10/projects/{project_id}/domains')
        try:
            r = http_requests.post(
                url, headers=headers, json={'name': raw}, timeout=15,
            )
        except http_requests.RequestException as e:
            return Response(
                {'error': f'Vercel API injoignable: {e}'},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        # Vercel returns 200/201 on success, 409 if domain already attached.
        if r.status_code in (200, 201, 409):
            data = r.json() if r.text else {}
            verified = bool(data.get('verified', False))
            # On 409 the response has a different shape - fetch the domain to
            # get verification records.
            if r.status_code == 409:
                check = http_requests.get(
                    _vercel_url(f'/v9/projects/{project_id}/domains/{raw}'),
                    headers=headers, timeout=10,
                )
                if check.status_code == 200:
                    data = check.json()
                    verified = bool(data.get('verified', False))

            # Persist the chosen subdomain so we know it later.
            site.public_blog_domain = raw
            site.save(update_fields=['public_blog_domain', 'updated_at'])
            # Bust the audit cache so the user sees the change immediately.
            cache.delete(f'site-audit:{site.id}')

            return Response({
                'domain': raw,
                'verified': verified,
                'cname_target': 'cname.vercel-dns.com',
                'verification': data.get('verification') or [],
                'next_step': (
                    'Cree un enregistrement CNAME chez ton registrar pointant '
                    f'{raw} vers cname.vercel-dns.com. La propagation prend '
                    '5 a 30 min. Le SSL est genere automatiquement.'
                ),
            })

        # Other error - surface message from Vercel for debugging.
        try:
            body = r.json()
            msg = (body.get('error') or {}).get('message') or r.text[:200]
        except Exception:
            msg = r.text[:200]
        return Response(
            {'error': f'Vercel {r.status_code}: {msg}'},
            status=status.HTTP_502_BAD_GATEWAY,
        )


class BlogDomainStatusView(APIView):
    """GET /api/sites/<id>/blog-domain/status/

    Polls Vercel to check whether the subdomain DNS has propagated and SSL
    is provisioned. Frontend polls this every 5-10s while showing a spinner
    until verified=true.

    Response: {domain, verified, ssl_ready, message}
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, site_id):
        site = get_object_or_404(Site, pk=site_id, owner=request.user)
        domain = site.public_blog_domain
        if not domain:
            return Response(
                {'error': 'Pas de domaine de blog configure pour ce site.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        headers = _vercel_headers()
        project_id = os.environ.get('VERCEL_PROJECT_ID')
        if not headers or not project_id:
            return Response(
                {'error': 'Vercel API non configure cote serveur.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        # First, ask Vercel to verify (idempotent - just re-checks DNS).
        try:
            v = http_requests.post(
                _vercel_url(f'/v9/projects/{project_id}/domains/{domain}/verify'),
                headers=headers, timeout=10,
            )
        except http_requests.RequestException:
            v = None

        # Then read full state.
        try:
            r = http_requests.get(
                _vercel_url(f'/v9/projects/{project_id}/domains/{domain}'),
                headers=headers, timeout=10,
            )
        except http_requests.RequestException as e:
            return Response(
                {'error': f'Vercel API injoignable: {e}'},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        if r.status_code != 200:
            return Response(
                {'error': f'Vercel {r.status_code}', 'verified': False},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        data = r.json()
        verified = bool(data.get('verified', False))
        # Vercel auto-provisions SSL once verified. We treat "verified" as
        # "ready to serve" since SSL follows within seconds.
        return Response({
            'domain': domain,
            'verified': verified,
            'ssl_ready': verified,
            'verification': data.get('verification') or [],
            'message': (
                f'Blog en ligne sur https://{domain}'
                if verified
                else 'DNS pas encore propage. Patiente 5-30 min apres avoir '
                     'ajoute le CNAME chez ton registrar.'
            ),
        })


class BlogDomainRemoveView(APIView):
    """DELETE /api/sites/<id>/blog-domain/

    Removes the subdomain from the Vercel project (free-up for re-use) and
    clears Site.public_blog_domain. Used when the user wants to switch
    to a different domain or stop hosting.
    """
    permission_classes = [IsAuthenticated]

    def delete(self, request, site_id):
        site = get_object_or_404(Site, pk=site_id, owner=request.user)
        domain = site.public_blog_domain
        if not domain:
            return Response(status=status.HTTP_204_NO_CONTENT)

        headers = _vercel_headers()
        project_id = os.environ.get('VERCEL_PROJECT_ID')
        # Best-effort: even if Vercel API is misconfigured, we still clear the
        # local field so the user can retry the wizard with a new domain.
        if headers and project_id:
            try:
                http_requests.delete(
                    _vercel_url(f'/v9/projects/{project_id}/domains/{domain}'),
                    headers=headers, timeout=10,
                )
            except http_requests.RequestException:
                pass  # swallow - local clear is what matters

        site.public_blog_domain = ''
        site.save(update_fields=['public_blog_domain', 'updated_at'])
        cache.delete(f'site-audit:{site.id}')
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Phase 3: Public audit page (lead magnet) ────────────────────────────────


from rest_framework.throttling import AnonRateThrottle as _AnonRateThrottle


class PublicAuditThrottle(_AnonRateThrottle):
    """6 audits per IP per minute - prevents abuse on the public endpoint
    while staying generous enough for real users running multiple audits."""
    rate = '6/min'


def _normalize_audit_domain(raw: str) -> str | None:
    """Accept loose user input ('https://www.foo.com/', 'foo.com', etc.) and
    return a clean hostname, or None if unparseable."""
    if not raw:
        return None
    raw = raw.strip().lower()
    raw = raw.replace('https://', '').replace('http://', '')
    raw = raw.rstrip('/').split('/')[0]
    raw = raw.replace('www.', '', 1) if raw.startswith('www.') else raw
    if '.' not in raw or ' ' in raw:
        return None
    return raw


def _validate_generated_schema(jsonld) -> dict:
    """Check JSON-LD before handing it to the user, never raising.

    Returns {issues, blocking}. A validator that can break schema generation
    is worse than no validator, so any failure here reports empty.
    """
    try:
        from .schema_validator import has_blocking_errors, validate_jsonld
        issues = validate_jsonld(jsonld)
        return {'issues': issues, 'blocking': has_blocking_errors(issues)}
    except Exception:  # noqa: BLE001
        logger.exception('schema validation failed')
        return {'issues': [], 'blocking': False}


def _encodage_indecodable(reponse) -> str | None:
    """Rend un message d'erreur si le corps de la reponse n'est pas decodable.

    Certains sites derriere un WAF repondent dans un encodage que nous n'avons
    pas demande. Verifie en prod le 2026-08-25 :
    www.berkshirehathaway.com rend `content-encoding: br` alors que notre
    Accept-Encoding ne demandait que gzip et deflate. Sans decodeur brotli,
    `r.text` etait du binaire, aucun `<title>` n'y etait trouvable, et le site
    ressortait de l'audit sans titre, sans H1 et sans meta description. Un
    verdict catastrophique et faux, montre a un prospect, sans la moindre
    erreur dans les logs.

    Le paquet `brotli` est desormais dans requirements.txt, donc `br` se
    decode. Ce garde-fou couvre ce qui reste (zstd notamment) : mieux vaut une
    erreur franche qu'une page declaree vide.
    """
    brut = reponse.headers.get('content-encoding')
    # On n'agit que sur un encodage POSITIVEMENT identifie comme inconnu. Une
    # valeur absente, vide ou d'un type inattendu se lit comme "pas
    # d'encodage" : bloquer un crawl parce qu'un en-tete est bizarre serait
    # pire que le probleme qu'on corrige.
    if not isinstance(brut, str):
        return None
    encodage = brut.lower().strip()
    connus = ('', 'identity', 'gzip', 'x-gzip', 'deflate', 'br')
    if encodage and encodage not in connus:
        return f'Encodage non decodable : {encodage}'
    return None


def _crawl_homepage(url: str, timeout: int = 8) -> dict:
    """Fetch a URL once and pull out the SEO signals we need to discover
    candidate keywords + render the audit result.

    Extracted: title, h1, meta description, list of h2 (capped 10), list of
    h3 (capped 10), meta keywords (rare in 2026 but still seen), and a clean
    body-text snippet (~2000 chars, scripts/styles stripped) so the keyword
    extractor can run n-gram frequency analysis on the actual content.

    Best-effort: any failure returns {'error': ...} and the audit pipeline
    keeps going with the partial signals it has.
    """
    import re
    try:
        # safe_get, not http_requests.get: `url` comes straight from a public
        # unauthenticated caller and its body comes back in body_snippet, so an
        # unchecked fetch turns this into an SSRF read primitive against the
        # Railway network. safe_get refuses private/loopback/metadata targets
        # and re-checks every redirect hop.
        r = safe_get(
            url, timeout=timeout,
            headers={'User-Agent': 'Mozilla/5.0 GridarAudit/1.0 (+https://gridar.app)'},
        )
        if not r.ok:
            return {'error': f'HTTP {r.status_code}'}
        erreur_encodage = _encodage_indecodable(r)
        if erreur_encodage:
            return {'error': erreur_encodage}
        html = r.text
        title_m = re.search(r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE)

        # Le contenu des <script> et <style> n'est pas du texte de page, et il
        # doit partir AVANT toute extraction de titre. react-wrap-balancer
        # injecte un <script> a l'interieur meme du <h1> : sans ce nettoyage,
        # son code JavaScript se retrouvait dans le H1 lu, puis dans les
        # mots-cles envoyes a Serper ("self wrap", "supports text").
        html_texte = re.sub(r'<script[^>]*>.*?</script>', ' ', html,
                            flags=re.IGNORECASE | re.DOTALL)
        html_texte = re.sub(r'<style[^>]*>.*?</style>', ' ', html_texte,
                            flags=re.IGNORECASE | re.DOTALL)

        def _texte_balise(motif: str) -> list[str]:
            """Contenu textuel des balises correspondantes, balises internes
            retirees. `[^<]+` exigeait un titre sans une seule balise dedans,
            or un hero moderne en contient presque toujours : un <span> pour
            colorer un mot, un <br> pour casser la ligne. Le H1 de gridar.app
            lui-meme n'etait pas vu, donc declare absent dans son propre audit
            et absent de l'extraction de mots-cles, dont il est la source la
            plus intentionnelle."""
            return [
                re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', m)).strip()
                for m in re.findall(motif, html_texte, re.IGNORECASE | re.DOTALL)
            ]

        h1_list = [h for h in _texte_balise(r'<h1[^>]*>(.*?)</h1>') if h]
        meta_m = re.search(
            r'<meta\s+name=["\']description["\']\s+content=["\']([^"\']+)',
            html, re.IGNORECASE,
        )
        meta_kw_m = re.search(
            r'<meta\s+name=["\']keywords["\']\s+content=["\']([^"\']+)',
            html, re.IGNORECASE,
        )

        # All h2 and h3 - useful for n-gram extraction.
        h2_list = [h for h in _texte_balise(r'<h2[^>]*>(.*?)</h2>') if h]
        h3_list = [h for h in _texte_balise(r'<h3[^>]*>(.*?)</h3>') if h]

        # Clean body text snippet: drop tags, collapse ws.
        cleaned = re.sub(r'<[^>]+>', ' ', html_texte)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()

        # Regex extraction leaves HTML entities raw, so an apostrophe reached
        # the report as "t&#x27;empeche" and a prospect read that in their own
        # audit. Decode once, here, before anything is stored or displayed.
        from html import unescape as _unescape

        def _clean(s: str, limite: int) -> str:
            return _unescape(s or '').strip()[:limite]

        return {
            'title': _clean(title_m.group(1) if title_m else '', 200),
            'h1': _clean(h1_list[0] if h1_list else '', 200),
            # Le compte reel : un gabarit qui pose deux H1 est une erreur
            # classique, et le premier seul ne permet pas de la voir.
            'h1_count': len(h1_list),
            'meta_description': _clean(meta_m.group(1) if meta_m else '', 300),
            'meta_keywords': _clean(meta_kw_m.group(1) if meta_kw_m else '', 500),
            'h2_list': [_clean(h, 120) for h in h2_list if h][:10],
            'h3_list': [_clean(h, 120) for h in h3_list if h][:10],
            'body_snippet': _unescape(cleaned)[:2000],
            'final_url': r.url,
            # Underscore-prefixed: for callers that want to run further checks
            # on the same fetch instead of hitting the site again. Pop it
            # before serializing, it is the whole page.
            '_html': html,
        }
    except Exception as e:
        return {'error': f'Crawl: {str(e)[:80]}'}


# Bilingual stopwords (FR + EN) - strip these from candidate keywords so we
# don't query Serper for "comment", "the", "avec", etc.
_STOPWORDS = frozenset({
    # FR
    'avec', 'sans', 'pour', 'dans', 'cette', 'cette', 'sont', 'tres', 'plus',
    'mais', 'comme', 'leur', 'leurs', 'votre', 'vos', 'notre', 'nos', 'mon',
    'mes', 'ton', 'tes', 'son', 'ses', 'les', 'des', 'aux', 'une', 'qui',
    'que', 'quoi', 'dont', 'tout', 'tous', 'toute', 'toutes', 'peut', 'tres',
    'bien', 'aussi', 'fait', 'faire', 'faites', 'voir', 'savoir', 'pouvoir',
    'avoir', 'etre', 'etes', 'sera', 'sont', 'etait', 'comment', 'pourquoi',
    'quand', 'puis', 'donc', 'alors', 'aussi', 'encore', 'meme', 'memes',
    'site', 'page', 'pages', 'web', 'ligne', 'click', 'cliquez', 'lire',
    'plus', 'menu', 'accueil', 'contact', 'contactez',
    # EN
    'with', 'without', 'from', 'into', 'about', 'this', 'that', 'these',
    'those', 'your', 'yours', 'their', 'theirs', 'our', 'ours', 'his',
    'hers', 'have', 'has', 'had', 'been', 'being', 'will', 'would', 'should',
    'could', 'might', 'must', 'shall', 'what', 'when', 'where', 'which',
    'while', 'because', 'before', 'after', 'over', 'under', 'just', 'only',
    'also', 'than', 'then', 'them', 'they', 'were', 'click', 'read', 'home',
    'menu', 'contact', 'about', 'page', 'site',
})

# Site furniture: words a CMS or a template puts on every page. They recur, so
# frequency ranks them highly, but nobody types them into Google. Left out of
# _STOPWORDS on purpose: a stopword is dropped from every phrase, while these
# only disqualify a phrase made of them ("sujet article", "importe blog"), and
# must not kill a real one that happens to contain one.
_BOILERPLATE = frozenset({
    # FR
    'article', 'articles', 'blog', 'blogue', 'blogues', 'billet', 'billets',
    'sujet', 'sujets', 'publie', 'publiee', 'publies', 'publier', 'publication',
    'publications', 'actualite', 'actualites', 'nouvelle', 'nouvelles',
    'categorie', 'categories', 'archive', 'archives', 'commentaire',
    'commentaires', 'partager', 'suivant', 'suivante', 'precedent',
    'precedente', 'propos', 'temoignage', 'temoignages', 'galerie',
    'portfolio', 'mentions', 'legales', 'confidentialite', 'cookies',
    'infolettre', 'newsletter', 'abonner', 'abonnez', 'inscription',
    'inscrire', 'connexion', 'compte', 'panier', 'resultats', 'chargement',
    'bienvenue', 'cliquez', 'suivez', 'rejoignez', 'decouvrez', 'importe',
    'copyright', 'reserves', 'navigation', 'rechercher', 'recherche',
    # EN
    'post', 'posts', 'category', 'categories', 'archive', 'archives',
    'comment', 'comments', 'share', 'next', 'previous', 'testimonial',
    'testimonials', 'gallery', 'privacy', 'policy', 'subscribe', 'signup',
    'login', 'account', 'cart', 'results', 'loading', 'welcome', 'follow',
    'join', 'search', 'navigation', 'copyright', 'reserved',
})

# Sources 1 to 3 name the trade; 4 and 5 only guess from recurrence.
_STRONG_KEYWORD_SOURCES = ('meta_keywords', 'h1', 'title')


# Les huit controles de la composante on-page, avec leur part des 100 points.
# Ils se lisent tous dans la page deja telechargee : aucun appel externe, donc
# aucun timeout, aucun quota, et une note disponible sur 100 % des sites.
_CONTROLES_ONPAGE = (
    ('title_present', 'Balise title', 15),
    ('title_longueur', 'Longueur du title', 10),
    ('meta_description_presente', 'Meta description', 15),
    ('meta_description_longueur', 'Longueur de la meta description', 10),
    ('h1_present', 'Balise H1', 15),
    ('h1_unique', 'Un seul H1', 10),
    ('hierarchie', 'Sous-titres H2', 10),
    ('donnees_structurees', 'Donnees structurees JSON-LD', 15),
)

# Google tronque le title autour de 60 caracteres et la description autour de
# 160. En dessous du plancher, la balise existe mais ne dit rien.
_TITLE_MIN, _TITLE_MAX = 30, 65
_DESC_MIN, _DESC_MAX = 70, 160


def _score_onpage(crawl: dict, page_html: str = '') -> dict | None:
    """Note sur 100 les signaux on-page de la page d'accueil.

    Rend None quand le crawl a echoue : sans page, il n'y a rien a mesurer et
    un zero se lirait comme un verdict.

    Cette composante existe parce que les deux autres sont conditionnelles.
    PageSpeed depend d'une API tierce qui peut expirer, les positions dependent
    d'un quota Serper et d'un site assez age pour ranker. Les signaux on-page,
    eux, sont lisibles sur la page qu'on vient de telecharger, pour tout le
    monde, du premier jour. C'est aussi la seule partie sur laquelle le
    visiteur peut agir le jour meme.
    """
    import re

    if not crawl or crawl.get('error'):
        return None
    html = page_html or ''

    title = (crawl.get('title') or '').strip()
    desc = (crawl.get('meta_description') or '').strip()
    h1 = (crawl.get('h1') or '').strip()
    h2 = [h for h in (crawl.get('h2_list') or []) if h]

    # Le crawl compte lui-meme les H1 apres avoir retire les <script>. On ne
    # recompte sur le HTML brut que pour les appelants qui n'ont pas ce champ.
    nb_h1 = crawl.get('h1_count')
    if nb_h1 is None:
        nb_h1 = len(re.findall(r'<h1[\s>]', html, re.IGNORECASE)) if html else (1 if h1 else 0)

    resultats = {
        'title_present': bool(title),
        'title_longueur': bool(title) and _TITLE_MIN <= len(title) <= _TITLE_MAX,
        'meta_description_presente': bool(desc),
        'meta_description_longueur': bool(desc) and _DESC_MIN <= len(desc) <= _DESC_MAX,
        'h1_present': bool(h1),
        'h1_unique': nb_h1 == 1,
        'hierarchie': len(h2) >= 1,
        'donnees_structurees': bool(
            html and re.search(r'application/ld\+json', html, re.IGNORECASE)
        ),
    }

    gagnes = sum(poids for cle, _, poids in _CONTROLES_ONPAGE if resultats[cle])
    return {
        'score': gagnes,
        'controles': [
            {'cle': cle, 'libelle': libelle, 'poids': poids, 'reussi': resultats[cle]}
            for cle, libelle, poids in _CONTROLES_ONPAGE
        ],
    }


_SYSTEME_MOTS_CLES = (
    "Tu es analyste SEO. On te donne le contenu d'une page d'accueil. Tu rends "
    "UNIQUEMENT un tableau JSON des requetes que de vrais clients taperaient "
    "dans Google pour trouver cette entreprise. Rien d'autre, aucun texte "
    "autour."
)

_GABARIT_MOTS_CLES = """\
Voici la page d'accueil de {domaine}.

Titre : {title}
H1 : {h1}
Meta description : {description}
Sous-titres : {h2}
Extrait du contenu : {extrait}

Rends entre 5 et {maximum} requetes de recherche, en JSON, dans cette forme
exacte : ["requete un", "requete deux"]

Regles :
- Ecris ce qu'un CLIENT tape, pas ce que l'entreprise dit d'elle-meme. "sablage
  de plancher montreal", pas "notre savoir-faire depuis 1998".
- Meme langue que la page.
- Deux a six mots par requete.
- Aucune requete de marque, sauf si le nom de l'entreprise est ce qu'on
  chercherait vraiment.
- Pas de slogan, pas de nom de section du site, pas de mot de navigation.
- Si la page ne dit pas assez clairement ce que vend l'entreprise, rends un
  tableau vide plutot que d'inventer.
"""


def _mots_cles_par_llm(crawl: dict, domaine: str, maximum: int = 10,
                       timeout: int = 15) -> list[str] | None:
    """Demande a DeepSeek les requetes qu'un client taperait pour ce site.

    Rend None des que le resultat n'est pas exploitable, et l'appelant reprend
    l'extraction par n-grammes. Aucune dependance dure a un LLM sur une route
    publique.

    Pourquoi : l'extraction par n-grammes decoupe le H1 et le title en tranches
    de deux ou trois mots. Sur un slogan, ca produit "seule interface" ou
    "gridar quebec", que personne ne tape. Ces chaines partaient ensuite chez
    Serper et la part de mots-cles dans le top 10 devenait la composante
    `rankings` du score. Le site etait donc note sur des requetes inventees.

    La validation est volontairement severe : ce que rend le modele part dans
    des appels Serper factures et entre dans un score montre a un prospect.
    """
    import json
    import re

    from .llm import call_deepseek

    if not crawl or crawl.get('error'):
        return None

    prompt = _GABARIT_MOTS_CLES.format(
        domaine=domaine,
        title=(crawl.get('title') or '')[:200],
        h1=(crawl.get('h1') or '')[:200],
        description=(crawl.get('meta_description') or '')[:300],
        h2=' | '.join((crawl.get('h2_list') or [])[:8])[:400],
        extrait=(crawl.get('body_snippet') or '')[:1200],
        maximum=maximum,
    )

    try:
        brut = call_deepseek(prompt, max_tokens=400, system=_SYSTEME_MOTS_CLES,
                             timeout=timeout)
    except Exception:  # noqa: BLE001 - call_deepseek avale deja tout, ceinture
        logger.exception('mots-cles par LLM indisponibles')
        return None
    if not brut:
        return None

    # Le modele encadre parfois sa reponse d'un bloc markdown ou d'une phrase.
    bloc = re.search(r'\[.*?\]', brut, re.DOTALL)
    if not bloc:
        return None
    try:
        brut_liste = json.loads(bloc.group(0))
    except (ValueError, TypeError):
        return None
    if not isinstance(brut_liste, list):
        return None

    propres: list[str] = []
    vus: set[str] = set()
    for item in brut_liste:
        if not isinstance(item, str):
            continue
        mot = ' '.join(item.split()).strip(' "\'.,;:!?')
        if not (3 <= len(mot) <= 80):
            continue
        if not (2 <= len(mot.split()) <= 6):
            continue
        # Une URL, une balise ou un saut de ligne n'est pas une requete.
        if re.search(r'https?://|www\.|[<>{}]', mot):
            continue
        cle = mot.lower()
        if cle in vus:
            continue
        vus.add(cle)
        propres.append(mot)
        if len(propres) >= maximum:
            break

    # Moins de trois requetes exploitables, ce n'est pas un gain sur
    # l'heuristique : on la laisse faire son travail.
    return propres if len(propres) >= 3 else None


_POIDS_SCORE_PUBLIC = {'pagespeed': 40, 'onpage': 35, 'rankings': 25}


def _composer_score_public(ps: dict, positions: list, onpage: dict | None = None) -> dict:
    """Assemble le score de l'audit public et dit sur quoi il repose.

    Rend {composite_score, composantes, absentes, partiel, onpage}.

    Trois composantes : les signaux on-page de la page d'accueil (35 %), la
    moyenne PageSpeed (40 %) et la part des mots-cles verifies qui sortent dans
    le top 10 (25 %).

    L'on-page pese autant parce qu'il est le seul des trois a etre mesurable
    partout et tout de suite : PageSpeed depend d'une API tierce qui expire,
    les positions d'un quota Serper et d'un site assez age pour ranker. Avant
    son arrivee, un PageSpeed en timeout faisait porter 100 % du score aux
    positions, et un site correct qui ne rank pas encore ressortait a 10/100.
    Constate le 2026-08-23 sur gridar.app, dont le PageSpeed reel vaut 90 mais
    repond en 17 a 23 s contre une coupure a 25 s.

    Quand une composante manque, les poids sont renormalises sur celles qui
    restent, et `partiel` le dit.

    Un mot-cle dont la verification a echoue ne compte pas : le compter zero
    revenait a punir le visiteur d'un quota Serper epuise.
    """
    composantes: list[tuple[str, float, float]] = []

    if 'avg' in ps:
        composantes.append(('pagespeed', float(ps['avg']), 0.40))

    if onpage and onpage.get('score') is not None:
        composantes.append(('onpage', float(onpage['score']), 0.35))

    verifies = [p for p in (positions or []) if p.get('checked')]
    if verifies:
        top_10 = sum(1 for p in verifies if p.get('position') and p['position'] <= 10)
        composantes.append(('rankings', (top_10 / len(verifies)) * 100, 0.25))

    composite = None
    if composantes:
        somme_poids = sum(w for _, _, w in composantes)
        composite = round(sum(v * (w / somme_poids) for _, v, w in composantes))

    somme_poids = sum(w for _, _, w in composantes) or 1
    detail = [
        {
            'cle': nom,
            'valeur': round(valeur),
            'poids_nominal': _POIDS_SCORE_PUBLIC[nom],
            'poids_effectif': round(poids / somme_poids * 100),
        }
        for nom, valeur, poids in composantes
    ]
    presentes = {nom for nom, _, _ in composantes}
    _RAISONS = {
        'pagespeed': ps.get('error') or 'mesure indisponible',
        'onpage': 'page d accueil illisible',
        'rankings': 'aucun mot-cle verifiable',
    }
    absentes = [
        {'cle': cle, 'raison': _RAISONS[cle]}
        for cle in _POIDS_SCORE_PUBLIC
        if cle not in presentes
    ]
    return {
        'composite_score': composite,
        'composantes': detail,
        'absentes': absentes,
        'partiel': bool(absentes) and composite is not None,
        # Le detail des huit controles, pour que le rapport puisse nommer ce
        # qui manque au lieu d'afficher un chiffre nu.
        'onpage': onpage,
    }


def _keyword_confidence(crawl: dict) -> str:
    """'strong' when the page names a trade, 'weak' otherwise.

    Counting substantive words is not enough: a slogan has plenty of them.
    "Le SEO en francais qui comprend le Quebec" and "Courtiere hypothecaire au
    Quebec" both survive a stopword filter, yet only the second says what the
    business sells. So the test is lexical, against the trade vocabulary
    `local_seo` already carries for its six verticals.

    Weak does not mean the extraction failed. It means the keywords are our
    guess rather than the site's own words, and the report has to say so
    instead of scoring the visitor on a guess.
    """
    texte = _strip_accents_lower(' '.join(
        (crawl.get(champ) or '') for champ in _STRONG_KEYWORD_SOURCES
    ))
    if not texte.strip():
        return 'weak'
    try:
        from .local_seo import VERTICALES
    except Exception:  # noqa: BLE001 - never let this break an audit
        logger.exception('lexique local_seo indisponible')
        return 'weak'
    # Prefix matching on words, not substring on the whole phrase: the lexicon
    # is written masculine singular ("courtier hypothecaire") and a Quebec site
    # writes "courtiere hypothecaire". The trailing "e" breaks a plain `in`.
    # Same reason plombier has to reach plomberie.
    jetons = re.findall(r"[a-z0-9]+", texte)
    for entree in VERTICALES:
        # (cle, libelle, schema_type, termes_forts, termes_faibles)
        for terme in list(entree[3]) + list(entree[4]):
            mots = re.findall(r"[a-z0-9]+", _strip_accents_lower(terme))
            if not mots:
                continue
            if all(
                any(
                    j.startswith(m) if len(m) >= 4 else j == m
                    for j in jetons
                )
                for m in mots
            ):
                return 'strong'
    return 'weak'


def _strip_accents_lower(s: str) -> str:
    import unicodedata
    return ''.join(
        c for c in unicodedata.normalize('NFD', (s or '').lower())
        if unicodedata.category(c) != 'Mn'
    )


def _extract_candidate_keywords(crawl: dict, max_kws: int = 10) -> list[str]:
    """Return up to `max_kws` deduplicated candidate keywords from the crawled
    homepage signals.

    Strategy (in priority order, dedup case-insensitive):
      1. Comma-separated meta keywords (high signal, near-zero false positive)
      2. 2-3 word slices of h1 (front of page = top intent)
      3. 2-3 word slices of title (with brand suffix stripped)
      4. h2 short phrases (2-3 words)
      5. Top frequent 2-word phrases in body_snippet (n-gram frequency)

    Filters: drop stopwords, drop tokens shorter than 4 chars, drop pure
    digits, keep only phrases of 2-3 words, normalize lowercase + accents.
    """
    import re
    import unicodedata
    from collections import Counter

    def _normalize(s: str) -> str:
        # Lowercase + strip accents for stopword matching, but keep accents in
        # the returned phrase since Google ranks them as distinct.
        return ''.join(
            c for c in unicodedata.normalize('NFD', s.lower())
            if unicodedata.category(c) != 'Mn'
        )

    def _tokenize(s: str) -> list[str]:
        # Strip common separators that split the title (|, -, ·, etc.)
        s = re.sub(r'[\|\-·•\u2014\u2013:]', ' ', s)
        # Keep letters + digits + accents; drop punctuation.
        words = re.findall(r"[A-Za-zÀ-ÿ0-9]+", s.lower())
        return [w for w in words if len(w) >= 4 and _normalize(w) not in _STOPWORDS and not w.isdigit()]

    def _phrases_from(s: str, ngram_sizes=(2, 3)) -> list[str]:
        tokens = _tokenize(s or '')
        out = []
        for n in ngram_sizes:
            for i in range(len(tokens) - n + 1):
                phrase = ' '.join(tokens[i:i + n])
                if phrase.strip():
                    out.append(phrase)
        return out

    candidates: list[str] = []
    seen: set[str] = set()

    def _push(phrase: str) -> bool:
        key = _normalize(phrase.strip())
        if not key or key in seen:
            return False
        # A phrase built only of site furniture is never a search query,
        # whichever source produced it.
        mots = key.split()
        if mots and all(m in _BOILERPLATE for m in mots):
            return False
        seen.add(key)
        candidates.append(phrase.strip())
        return len(candidates) >= max_kws

    # 1. Meta keywords - already comma-separated, treat each as a candidate.
    if crawl.get('meta_keywords'):
        for kw in (crawl['meta_keywords'].split(',') if crawl.get('meta_keywords') else []):
            kw = kw.strip()
            if len(kw.split()) <= 4 and len(kw) >= 5:
                if _push(kw):
                    return candidates

    # 2. H1 (highest intent signal on the page).
    for phrase in _phrases_from(crawl.get('h1') or ''):
        if _push(phrase):
            return candidates

    # 3. Title (often "Brand - Tagline" pattern, separators normalized above).
    for phrase in _phrases_from(crawl.get('title') or ''):
        if _push(phrase):
            return candidates

    # 4. H2 list - sub-themes the page covers.
    for h2 in (crawl.get('h2_list') or []):
        for phrase in _phrases_from(h2):
            if _push(phrase):
                return candidates

    # 5. Body n-gram frequency: top bigrams that appear 2+ times in the
    # body snippet (forces real recurrence, not random word pair).
    body = crawl.get('body_snippet') or ''
    if body and len(candidates) < max_kws:
        tokens = _tokenize(body)
        bigrams = Counter(
            f'{tokens[i]} {tokens[i + 1]}'
            for i in range(len(tokens) - 1)
        )
        for phrase, count in bigrams.most_common(20):
            if count < 2:
                break
            # Stricter here than in _push: frequency is the weakest signal we
            # have, so a single furniture word disqualifies the pair rather
            # than only a pair made entirely of them.
            if any(_normalize(m) in _BOILERPLATE for m in phrase.split()):
                continue
            if _push(phrase):
                return candidates

    return candidates


def _enrich_public_audit_payload(domain: str, payload: dict) -> dict:
    """Run the 7 expensive enrichments that turn the partial public audit into
    a real full report - called from PublicLeadCaptureView after the visitor
    leaves their email.

    Each section is best-effort: any exception is caught and reported as
    {error, fallback_data} on that section so a single failure never blanks
    the whole report. All HTTP-bound sections run in parallel under a single
    ThreadPoolExecutor so we stay under ~20s wall-clock.

    Returns a dict to merge into payload['full_report'] - the caller is
    responsible for persisting + cache-invalidating.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    serper_key = os.environ.get('SERPER_API_KEY')
    pagespeed_key = (
        os.environ.get('PAGESPEED_API_KEY')
        or os.environ.get('GOOGLE_PAGESPEED_API_KEY')
    )
    anthropic_key = os.environ.get('ANTHROPIC_API_KEY')

    positions = payload.get('top_keywords_estimated') or []
    recos = payload.get('recos_partial') or []
    homepage_url = f'https://{domain}'

    # Top 3 keywords (priority: existing rankings first since they already
    # have SERP intel, then unranked) used by competitors + untapped sections.
    seed_keywords = [p['keyword'] for p in positions if p.get('keyword')][:5]

    # ---------- 1. Competitors ----------
    def section_competitors():
        if not serper_key or not seed_keywords:
            return {'error': 'Pas de clés ou keywords disponibles', 'items': []}
        try:
            competitor_domains: list[str] = []
            competitor_meta: dict[str, dict] = {}
            for kw in seed_keywords[:3]:
                r = http_requests.post(
                    'https://google.serper.dev/search',
                    headers={'X-API-KEY': serper_key,
                             'Content-Type': 'application/json'},
                    json={'q': kw, 'num': 10, 'hl': 'fr', 'gl': 'ca'},
                    timeout=8,
                )
                if r.status_code != 200:
                    continue
                for item in (r.json().get('organic') or [])[:10]:
                    link = (item.get('link') or '').lower()
                    if not link:
                        continue
                    try:
                        host = urlparse(link).netloc.replace('www.', '')
                    except Exception:
                        continue
                    if not host or domain in host or host in domain:
                        continue
                    # Skip well-known aggregators that aren't real competitors.
                    if any(s in host for s in (
                        'wikipedia.', 'youtube.com', 'facebook.com',
                        'instagram.com', 'linkedin.com', 'reddit.com',
                        'amazon.', 'pinterest.com', 'tiktok.com',
                    )):
                        continue
                    if host not in competitor_meta:
                        competitor_meta[host] = {
                            'domain': host,
                            'title': item.get('title', '')[:160],
                            'sample_url': item.get('link'),
                            'position_count': 0,
                        }
                    competitor_meta[host]['position_count'] += 1
                    if host not in competitor_domains:
                        competitor_domains.append(host)
            ranked = sorted(
                competitor_meta.values(),
                key=lambda c: -c['position_count'],
            )[:3]
            # PageSpeed on competitor #1 only - keeps the wall-clock budget.
            if ranked and pagespeed_key:
                top = ranked[0]
                try:
                    r = http_requests.get(
                        'https://www.googleapis.com/pagespeedonline/v5/runPagespeed',
                        params={
                            'url': f"https://{top['domain']}",
                            'key': pagespeed_key,
                            'strategy': 'mobile',
                            'category': ['performance', 'seo'],
                        },
                        timeout=25,
                    )
                    if r.status_code == 200:
                        cats = r.json().get('lighthouseResult', {}).get('categories', {})
                        perf = int((cats.get('performance', {}).get('score') or 0) * 100)
                        seo = int((cats.get('seo', {}).get('score') or 0) * 100)
                        top['pagespeed_score'] = (perf + seo) // 2
                    else:
                        top['pagespeed_score'] = None
                except Exception:
                    top['pagespeed_score'] = None
            for c in ranked:
                c.setdefault('pagespeed_score', None)
            return {'items': ranked}
        except Exception as e:
            return {'error': f'Competitors: {str(e)[:120]}', 'items': []}

    # ---------- 2. Untapped keywords ----------
    def section_untapped():
        if not serper_key or not seed_keywords:
            return {'error': 'Pas de clés ou keywords disponibles', 'items': []}
        try:
            suggestions: dict[str, dict] = {}
            for kw in seed_keywords[:3]:
                r = http_requests.post(
                    'https://google.serper.dev/search',
                    headers={'X-API-KEY': serper_key,
                             'Content-Type': 'application/json'},
                    json={'q': kw, 'num': 10, 'hl': 'fr', 'gl': 'ca'},
                    timeout=8,
                )
                if r.status_code != 200:
                    continue
                body = r.json()
                # PAA + related searches as candidate untapped queries.
                cands = []
                for paa in (body.get('peopleAlsoAsk') or []):
                    q = (paa.get('question') or '').strip()
                    if q:
                        cands.append(q)
                for rel in (body.get('relatedSearches') or []):
                    q = (rel.get('query') or '').strip()
                    if q:
                        cands.append(q)
                # Top organic competitor that ranks for the seed - used as
                # competitor_in_top10 hint for any sibling untapped query.
                organic = body.get('organic') or []
                top_comp = None
                for item in organic[:10]:
                    link = (item.get('link') or '').lower()
                    try:
                        host = urlparse(link).netloc.replace('www.', '')
                    except Exception:
                        continue
                    if host and domain not in host:
                        top_comp = host
                        break
                # Heuristic 3-tier "volume" based on how prominently PAA
                # surfaced it (no real volume API in this tier).
                for idx, q in enumerate(cands):
                    if q.lower() in suggestions:
                        continue
                    stars = 3 if idx < 2 else (2 if idx < 5 else 1)
                    suggestions[q.lower()] = {
                        'keyword': q,
                        'volume_estimate': stars,
                        'competitor_in_top10': top_comp,
                    }
            # Drop any suggestion the visitor's domain already ranks for.
            ranked_kws = {
                (p['keyword'] or '').lower()
                for p in positions if p.get('position') and p['position'] <= 50
            }
            items = [
                s for k, s in suggestions.items() if k not in ranked_kws
            ][:10]
            return {'items': items}
        except Exception as e:
            return {'error': f'Untapped: {str(e)[:120]}', 'items': []}

    # ---------- 3. Schema.org audit ----------
    def section_schema():
        try:
            crawl = _crawl_homepage(homepage_url)
            if crawl.get('error'):
                return {
                    'error': crawl['error'],
                    'present': [], 'missing_recommended': [], 'score': 0,
                }
            # Re-fetch raw HTML (cheap, same URL, but _crawl_homepage strips it).
            r = http_requests.get(
                homepage_url, timeout=8,
                headers={'User-Agent': 'Mozilla/5.0 GridarAudit/1.0'},
                allow_redirects=True,
            )
            html = r.text if r.ok else ''
            known = [
                'Article', 'BlogPosting', 'FAQPage', 'Product',
                'Organization', 'BreadcrumbList', 'Person', 'LocalBusiness',
                'WebSite', 'WebPage',
            ]
            present = []
            html_lower = html.lower()
            for schema in known:
                # Match both JSON-LD ("@type": "Article") and microdata
                # (itemtype="https://schema.org/Article").
                if (
                    f'"{schema.lower()}"' in html_lower
                    or f'schema.org/{schema.lower()}' in html_lower
                ):
                    present.append(schema)
            # Heuristic site-type detection -> recommended schemas.
            site_type_hint = ' '.join([
                (crawl.get('title') or ''),
                (crawl.get('meta_description') or ''),
                (crawl.get('body_snippet') or '')[:500],
            ]).lower()
            recommended = ['Organization', 'WebSite']
            if any(k in site_type_hint for k in ('blog', 'article', 'guide')):
                recommended += ['BlogPosting', 'Article', 'FAQPage', 'BreadcrumbList']
            if any(k in site_type_hint for k in ('boutique', 'shop', 'achat',
                                                  'panier', 'product', 'buy')):
                recommended += ['Product', 'BreadcrumbList']
            if any(k in site_type_hint for k in ('restaurant', 'adresse',
                                                  'horaire', 'local')):
                recommended += ['LocalBusiness']
            recommended = list(dict.fromkeys(recommended))
            missing = [s for s in recommended if s not in present]
            score = (
                int((len(present) / len(recommended)) * 100)
                if recommended else 0
            )
            score = min(score, 100)
            return {
                'present': present,
                'missing_recommended': missing,
                'score': score,
            }
        except Exception as e:
            return {
                'error': f'Schema: {str(e)[:120]}',
                'present': [], 'missing_recommended': [], 'score': 0,
            }

    # ---------- 4. CWV desktop vs mobile ----------
    def section_cwv():
        mobile = payload.get('pagespeed') or {}
        if not pagespeed_key:
            return {'error': 'PAGESPEED_API_KEY non configuree',
                    'mobile': mobile, 'desktop': {}, 'gap_pp': None,
                    'advice': ''}
        try:
            r = http_requests.get(
                'https://www.googleapis.com/pagespeedonline/v5/runPagespeed',
                params={
                    'url': homepage_url, 'key': pagespeed_key,
                    'strategy': 'desktop',
                    'category': ['performance', 'seo', 'accessibility'],
                },
                timeout=25,
            )
            if r.status_code != 200:
                return {'error': f'PageSpeed desktop {r.status_code}',
                        'mobile': mobile, 'desktop': {}, 'gap_pp': None,
                        'advice': ''}
            cats = r.json().get('lighthouseResult', {}).get('categories', {})
            perf = int((cats.get('performance', {}).get('score') or 0) * 100)
            seo = int((cats.get('seo', {}).get('score') or 0) * 100)
            a11y = int((cats.get('accessibility', {}).get('score') or 0) * 100)
            desktop = {
                'performance': perf, 'seo': seo, 'accessibility': a11y,
                'avg': (perf + seo + a11y) // 3,
            }
            gap = None
            advice = ''
            if 'avg' in mobile:
                gap = desktop['avg'] - (mobile.get('avg') or 0)
                if gap >= 20:
                    advice = (
                        "Ton site est nettement plus rapide sur desktop. "
                        "Optimise les images mobile, défère le JS non critique, "
                        "et active la compression Brotli/gzip."
                    )
                elif gap >= 5:
                    advice = (
                        "Écart modéré desktop vs mobile. "
                        "Vise un perf mobile 80+ pour matcher l'expérience desktop."
                    )
                elif gap <= -5:
                    advice = (
                        "Surprise : ton mobile bat ton desktop. Vérifie "
                        "ce qui se passe sur desktop (assets non-optimisés, "
                        "scripts tiers lourds)."
                    )
                else:
                    advice = "Bon équilibre mobile/desktop. Continue comme ça."
            return {'mobile': mobile, 'desktop': desktop, 'gap_pp': gap,
                    'advice': advice}
        except Exception as e:
            return {'error': f'CWV: {str(e)[:120]}',
                    'mobile': mobile, 'desktop': {}, 'gap_pp': None,
                    'advice': ''}

    # ---------- 5. Decay candidates ----------
    def section_decay():
        try:
            year_re = re.compile(r'\b20(1[5-9]|2[0-3])\b')
            items = []
            for p in positions:
                kw = (p.get('keyword') or '')
                m = year_re.search(kw)
                if not m:
                    continue
                items.append({
                    'keyword': kw,
                    'year_detected': f'20{m.group(1)}',
                    'advice': "Mettre à jour la date dans le titre + "
                              "rafraîchir le contenu (cible 2026).",
                })
            return {'items': items}
        except Exception as e:
            return {'error': f'Decay: {str(e)[:120]}', 'items': []}

    # ---------- 6. Article plan (5 articles) ----------
    def section_article_plan(untapped_items: list[dict]):
        # Build seed list of target keywords from untapped + visitor's own
        # high-position ones (refresh angle).
        targets = [u['keyword'] for u in (untapped_items or [])][:5]
        if len(targets) < 5:
            for p in positions:
                kw = p.get('keyword')
                if kw and kw not in targets:
                    targets.append(kw)
                if len(targets) >= 5:
                    break
        targets = targets[:5]
        if not targets:
            return {'error': 'Pas de keywords disponibles', 'items': []}

        # Anthropic path - punchier titles.
        if anthropic_key:
            try:
                prompt = (
                    "Tu es un éditeur SEO FR-CA. Pour chaque keyword ci-dessous, "
                    "propose un titre d'article percutant (max 70 caractères, "
                    "ton direct, valeur explicite). Réponds en JSON pur, sans "
                    "markdown, sous la forme [{\"keyword\":\"...\","
                    "\"title\":\"...\",\"why\":\"...une phrase...\"}].\n\n"
                    f"Keywords: {targets}"
                )
                from .llm import call_llm
                text = call_llm(prompt, max_tokens=1024, timeout=20)  # Anthropic -> DeepSeek
                if text:
                    import json as _json
                    text = text.strip()
                    if text.startswith('```'):
                        text = re.sub(r'^```(?:json)?', '', text).strip()
                        text = re.sub(r'```$', '', text).strip()
                    parsed = _json.loads(text)
                    items = []
                    priorities = ['high', 'high', 'medium', 'medium', 'low']
                    word_counts = [2400, 1800, 1800, 1200, 1200]
                    for i, p in enumerate(parsed[:5]):
                        items.append({
                            'title': p.get('title', '')[:160],
                            'target_keyword': p.get('keyword', targets[i] if i < len(targets) else ''),
                            'why': p.get('why', '')[:200],
                            'priority': priorities[i] if i < len(priorities) else 'low',
                            'estimated_words': word_counts[i] if i < len(word_counts) else 1200,
                        })
                    if items:
                        return {'items': items}
            except Exception as e:
                logger.warning('Article plan Anthropic fallback: %s', e)

        # Heuristic fallback.
        templates = [
            ("Comment {kw} en 2026 : le guide complet",
             "Cible un mot-clé à forte intention informationnelle.",
             'high', 2400),
            ("Le meilleur {kw} : 7 options comparées",
             "Format comparatif idéal pour capturer l'intention commerciale.",
             'high', 1800),
            ("{kw} : erreurs courantes et comment les éviter",
             "Article pratique qui capte les recherches longue-traîne.",
             'medium', 1800),
            ("{kw} : FAQ pour débutants",
             "Format FAQ aimanté par Google + bon pour la position zéro.",
             'medium', 1200),
            ("Étude de cas : résultats avec {kw}",
             "Preuves sociales + témoignages, taux de conversion élevé.",
             'low', 1200),
        ]
        items = []
        for i, target in enumerate(targets[:5]):
            tmpl, why, pri, wc = templates[i % len(templates)]
            items.append({
                'title': tmpl.format(kw=target)[:160],
                'target_keyword': target,
                'why': why,
                'priority': pri,
                'estimated_words': wc,
            })
        return {'items': items}

    # ---------- 7. Backlinks proxy ----------
    def section_backlinks():
        if not serper_key:
            return {
                'estimated_mentions': None,
                'top_referring_domains': [],
                'advice': "Connecte ton GSC dans Gridar pour analyser tes "
                          "vrais backlinks.",
            }
        try:
            r = http_requests.post(
                'https://google.serper.dev/search',
                headers={'X-API-KEY': serper_key,
                         'Content-Type': 'application/json'},
                json={'q': f'"{domain}" -site:{domain}',
                      'num': 30, 'hl': 'fr', 'gl': 'ca'},
                timeout=8,
            )
            if r.status_code != 200:
                return {
                    'estimated_mentions': None,
                    'top_referring_domains': [],
                    'advice': "Connecte ton GSC dans Gridar pour analyser tes "
                              "vrais backlinks.",
                }
            body = r.json()
            organic = body.get('organic') or []
            # Serper exposes the total result count under searchInformation
            # for some queries; fall back to len(organic) otherwise.
            total = (
                body.get('searchInformation', {}).get('totalResults')
                or body.get('credits') and None
            )
            try:
                estimated = int(total) if total else len(organic)
            except (TypeError, ValueError):
                estimated = len(organic)
            referring: dict[str, int] = {}
            for item in organic:
                link = (item.get('link') or '').lower()
                try:
                    host = urlparse(link).netloc.replace('www.', '')
                except Exception:
                    continue
                if not host or domain in host:
                    continue
                referring[host] = referring.get(host, 0) + 1
            top_refs = [
                {'domain': h, 'mention_count': c}
                for h, c in sorted(referring.items(),
                                   key=lambda kv: -kv[1])[:5]
            ]
            return {
                'estimated_mentions': estimated,
                'top_referring_domains': top_refs,
                'advice': ('' if top_refs else
                           "On a besoin de ton GSC pour analyser tes vrais "
                           "backlinks."),
            }
        except Exception as e:
            return {
                'error': f'Backlinks: {str(e)[:120]}',
                'estimated_mentions': None,
                'top_referring_domains': [],
                'advice': "Connecte ton GSC dans Gridar pour analyser tes "
                          "vrais backlinks.",
            }

    # Parallel fan-out for sections 1-5 + 7. Article plan runs after
    # untapped resolves because it consumes those keywords.
    enrich: dict = {}
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {
            pool.submit(section_competitors): 'competitors',
            pool.submit(section_untapped): 'untapped_keywords',
            pool.submit(section_schema): 'schema_audit',
            pool.submit(section_cwv): 'cwv_breakdown',
            pool.submit(section_decay): 'decay_candidates',
            pool.submit(section_backlinks): 'backlinks_proxy',
        }
        for fut in as_completed(futures):
            key = futures[fut]
            try:
                enrich[key] = fut.result()
            except Exception as e:
                logger.warning('Enrichment %s failed: %s', key, e)
                enrich[key] = {'error': f'{key}: {str(e)[:120]}'}

    # Article plan depends on untapped_keywords.
    untapped_items = (enrich.get('untapped_keywords') or {}).get('items') or []
    try:
        enrich['article_plan'] = section_article_plan(untapped_items)
    except Exception as e:
        logger.warning('Article plan failed: %s', e)
        enrich['article_plan'] = {'error': f'Article plan: {str(e)[:120]}',
                                  'items': []}

    return enrich


class PublicAuditView(APIView):
    """POST /api/public/audit/ {domain}

    Public lead-magnet endpoint - no auth required. Runs a lightweight audit
    on the visitor's domain so they see immediate value, then we email-gate
    the detailed report via the Lead model.

    Returns ALWAYS a partial audit even if some signals fail. Frontend keeps
    the most engaging signals (score + top keywords + PageSpeed) and gates
    the full report (competitors + recos + decay) behind the email.

    Cached 1h per domain so repeated visits don't re-spend API budget.
    """
    # authentication_classes = [] kills DRF SessionAuthentication which would
    # otherwise enforce its own CSRF check on this POST (independent of
    # Django's CsrfViewMiddleware) and return 403 "CSRF Failed: CSRF token
    # missing" for unauthenticated visitors. Same bug we fixed on the OAuth
    # views - see commit 4c31b82.
    authentication_classes = []
    permission_classes = []  # public
    throttle_classes = [PublicAuditThrottle]

    def post(self, request):
        from concurrent.futures import ThreadPoolExecutor

        domain = _normalize_audit_domain(request.data.get('domain') or '')
        if not domain:
            return Response(
                {'error': 'Domaine invalide. Ex: tondomaine.com'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Cache key includes a version so we invalidate everyone the day we
        # change the audit shape (e.g. v2 = 7-10 keywords vs old v1 = 1-2).
        cache_key = f'public-audit:v2:{domain}'
        cached = cache.get(cache_key)
        if cached:
            return Response(cached)

        homepage_url = f'https://{domain}'

        def task_crawl():
            return _crawl_homepage(homepage_url)

        def task_pagespeed():
            api_key = os.environ.get('PAGESPEED_API_KEY')
            if not api_key:
                return {'error': 'PAGESPEED_API_KEY non configuree'}
            try:
                r = http_requests.get(
                    'https://www.googleapis.com/pagespeedonline/v5/runPagespeed',
                    params={
                        'url': homepage_url, 'key': api_key,
                        'strategy': 'mobile',
                        'category': ['performance', 'seo', 'accessibility'],
                    },
                    timeout=45,
                )
                if r.status_code != 200:
                    return {'error': f'PageSpeed {r.status_code}'}
                cats = r.json().get('lighthouseResult', {}).get('categories', {})
                perf = int((cats.get('performance', {}).get('score') or 0) * 100)
                seo = int((cats.get('seo', {}).get('score') or 0) * 100)
                a11y = int((cats.get('accessibility', {}).get('score') or 0) * 100)
                return {
                    'performance': perf, 'seo': seo, 'accessibility': a11y,
                    'avg': (perf + seo + a11y) // 3,
                }
            except Exception as e:
                return {'error': f'PageSpeed: {str(e)[:80]}'}

        # PageSpeed part sur son propre fil et n'est recolte qu'au moment de
        # calculer le score. Il ne depend de rien, alors que la recherche de
        # positions attend le crawl : les attendre ensemble ici additionnait
        # les deux durees au lieu de les superposer. Mesure du 2026-08-23 sur
        # gridar.app : PageSpeed repond en 17 a 23 s, les positions prennent
        # une quinzaine de secondes derriere. En serie on frolait la minute.
        import threading

        ps: dict = {}

        def _pagespeed_task():
            try:
                ps.update(task_pagespeed())
            except Exception as e:  # noqa: BLE001 - un audit partiel part quand meme
                ps['error'] = str(e)[:80]

        ps_thread = threading.Thread(target=_pagespeed_task, daemon=True)
        ps_thread.start()

        try:
            crawl = task_crawl()
        except Exception as e:  # noqa: BLE001
            crawl = {'error': str(e)[:80]}

        # Two more reads off the page we already downloaded, so they cost one
        # fetch, not three. Both fail soft: a partial audit still ships.
        page_html = crawl.pop('_html', '') or ''
        agent_readability = {}
        gbp_deprecations = []
        if page_html:
            try:
                from .agent_ux import check_agent_readability
                agent_readability = check_agent_readability(page_html, homepage_url)
            except Exception:  # noqa: BLE001
                logger.exception('agent readability check failed')
            try:
                from .gbp_lint import lint_gbp_references
                gbp_deprecations = lint_gbp_references(page_html, homepage_url)
            except Exception:  # noqa: BLE001
                logger.exception('gbp deprecation lint failed')

        # Google Business Profile verdict, in parallel with the keyword position
        # checks below (both only need the crawl to be done). Read-only via
        # Serper Maps; for a local trade the profile is often the real ceiling.
        gbp_result = {}

        def _gbp_task():
            try:
                gbp_result.update(_gbp_diagnosis(domain, crawl))
            except Exception as e:  # noqa: BLE001
                gbp_result['error'] = str(e)[:80]

        gbp_thread = threading.Thread(target=_gbp_task, daemon=True)
        gbp_thread.start()

        # Extract 7-10 candidate keywords from all the crawled signals.
        # DeepSeek lit la page et propose les requetes qu'un client taperait.
        # L'extraction par n-grammes reste le repli : elle ne depend de rien et
        # cette route est publique, elle ne doit jamais dependre d'un LLM.
        keywords_to_check = _mots_cles_par_llm(crawl, domain, maximum=10)
        keywords_source = 'llm'
        if not keywords_to_check:
            keywords_to_check = _extract_candidate_keywords(crawl, max_kws=10)
            keywords_source = 'heuristique'

        # Whether the page actually named its trade, or we fell through to word
        # frequency. The visitor must not read a guess as a measured finding.
        # Quand les requetes viennent du modele, elles sortent d'une lecture de
        # la page et non d'un decoupage en tranches : la reserve ne tient plus.
        keywords_confidence = (
            'strong' if keywords_source == 'llm' else _keyword_confidence(crawl)
        )

        # Parallel Serper position checks - bounded by the existing
        # ThreadPoolExecutor pattern. Each call ~1-3s, so 10 sequentially
        # would blow our timeout. With 8 workers in parallel we get the
        # full set in ~3s wall-clock.
        positions = []
        serper_key = os.environ.get('SERPER_API_KEY')
        if serper_key and keywords_to_check:

            def _check_position(kw: str) -> dict:
                try:
                    r = http_requests.post(
                        'https://google.serper.dev/search',
                        headers={
                            'X-API-KEY': serper_key,
                            'Content-Type': 'application/json',
                        },
                        json={'q': kw, 'num': 50, 'hl': 'fr', 'gl': 'ca'},
                        timeout=8,
                    )
                    # `checked` separates "we looked and it is not there" from
                    # "we could not look". Both used to collapse into
                    # position=None, which the UI renders as "hors top 50": a
                    # quota error therefore told the visitor their site ranks
                    # nowhere. Same failure mode as counting mentions as
                    # backlinks, and it lands on a stranger's site.
                    if r.status_code != 200:
                        detail = 'quota' if r.status_code == 400 else f'http_{r.status_code}'
                        return {'keyword': kw, 'position': None,
                                'checked': False, 'reason': detail}
                    organic = (r.json().get('organic') or [])
                    pos = None
                    dom = domain[4:] if domain.startswith('www.') else domain
                    for idx, item in enumerate(organic):
                        link = (item.get('link') or '').lower()
                        host = link.split('://', 1)[-1].split('/', 1)[0]
                        if host.startswith('www.'):
                            host = host[4:]
                        if host and host == dom:
                            pos = item.get('position') or idx + 1
                            break
                    return {'keyword': kw, 'position': pos, 'checked': True,
                            'depth': len(organic)}
                except Exception:
                    return {'keyword': kw, 'position': None,
                            'checked': False, 'reason': 'erreur_reseau'}

            with ThreadPoolExecutor(max_workers=8) as pool:
                positions = list(pool.map(_check_position, keywords_to_check))

            # Sort: ranking keywords first (best position first), then
            # unranked ones at the bottom so the user sees their wins first.
            positions.sort(key=lambda r: (r['position'] is None, r['position'] or 999))

        # PageSpeed a tourne pendant le crawl et les positions. On le recolte
        # maintenant seulement, avec ce qui reste du budget de la requete.
        ps_thread.join(timeout=20)

        # page_html a ete retire du crawl plus haut pour ne pas serialiser toute
        # la page ; la note on-page en a besoin pour compter les H1 et reperer
        # le JSON-LD.
        onpage = _score_onpage(crawl, page_html)

        score = _composer_score_public(ps, positions, onpage)
        composite_score = score['composite_score']
        score_composantes = score['composantes']
        score_absentes = score['absentes']
        score_partiel = score['partiel']

        # `verifies` sert aussi aux recommandations ci-dessous : recalcule ici
        # plutot que fait ressortir de `_composer_score_public`, qui reste une
        # fonction pure sur ses seuls arguments.
        verifies = [p for p in (positions or []) if p.get('checked')]

        # Build recos (partial set for the public view - rest gated).
        recos = []
        if 'avg' in ps and ps['avg'] < 70:
            recos.append({
                'severity': 'high' if ps['avg'] < 50 else 'medium',
                'message': f"Score PageSpeed mobile = {ps['avg']}/100. Vise 80+.",
            })
        if verifies and all(p['position'] is None for p in verifies):
            if keywords_confidence == 'strong':
                recos.append({
                    'severity': 'high',
                    'message': (
                        f"Aucun de tes {len(verifies)} mots-cles verifies n'apparait "
                        "dans les premiers resultats Google."
                    ),
                })
            else:
                # The keywords were guessed from word frequency, so "you rank
                # nowhere" would be a verdict on our own guess, not on the site.
                recos.append({
                    'severity': 'medium',
                    'message': (
                        "Ta page d'accueil ne nomme pas ton metier, alors on a "
                        "devine tes mots-cles a partir du texte. Dis-nous les "
                        "tiens pour une mesure fiable."
                    ),
                })
        elif positions and not verifies:
            # Say the measure failed. Announcing "you rank nowhere" because our
            # own quota ran out is a false statement about someone else's site.
            recos.append({
                'severity': 'low',
                'message': (
                    "Positions Google non verifiees pour cet audit : la source "
                    "de donnees n'a pas repondu. Ce n'est pas un constat sur "
                    "ton site."
                ),
            })
        if crawl.get('error'):
            recos.append({
                'severity': 'medium',
                'message': f"Impossible de crawler ton site : {crawl['error']}. Verifie qu'il est en ligne.",
            })

        # Collect the GBP verdict (started in parallel above) before we build
        # the payload. Bounded join so a slow Serper Maps never hangs the audit.
        gbp_thread.join(timeout=22)

        payload = {
            'domain': domain,
            'audited_at': datetime.utcnow().isoformat(),
            'composite_score': composite_score,
            'score_partiel': score_partiel,
            'score_composantes': score_composantes,
            'score_absentes': score_absentes,
            'onpage': onpage,
            'pagespeed': ps,
            'gbp': gbp_result or None,
            'crawl': {
                'title': crawl.get('title'),
                'h1': crawl.get('h1'),
                'meta_description': crawl.get('meta_description'),
                'error': crawl.get('error'),
            },
            'top_keywords_estimated': positions,
            # 'strong' = read from the page's own title/h1/meta; 'weak' = we
            # fell through to word frequency and these are guesses.
            'keywords_confidence': keywords_confidence,
            'keywords_source': keywords_source,
            'recos_partial': recos,
            # Read off the same fetch as the crawl. Agent readability is the
            # 2026 angle almost nobody audits: whether an AI agent can make
            # sense of the page without running its JavaScript.
            'agent_readability': agent_readability or None,
            'gbp_deprecations': gbp_deprecations or None,
            'full_report_gated': True,
            # The full report (competitors + decay + backlinks + 10+ recos) is
            # revealed after the visitor leaves their email.
        }

        # Persist a permanent, shareable copy of this audit. The cache above is
        # per-domain and expires in 1h; this row gives the audit a stable URL
        # (gridar.app/rapport/<token>) that the J+0 email links to and that the
        # visitor can share. report_token rides along in the cached payload so
        # the lead-capture step and the SPA both know the share URL.
        from .models import PublicAuditReport
        report = PublicAuditReport.objects.create(domain=domain, payload=payload)
        payload['report_token'] = str(report.token)

        cache.set(cache_key, payload, timeout=3600)
        return Response(payload)


def _strip_accents(text: str) -> str:
    """montréal -> montreal. Lets us match user-typed city names regardless
    of accents/casing against the ASCII keys of the QC city table."""
    import unicodedata
    return ''.join(
        c for c in unicodedata.normalize('NFKD', text or '')
        if not unicodedata.combining(c)
    )


# Quebec cities -> Serper `location` string. Keys are accent-stripped + lower
# so 'Montréal', 'montreal', 'MONTREAL' all resolve. Value = (location, label).
# The label is echoed back to the caller as the normalised city. Quebec City
# uses Google's canonical geo name ('Quebec City, ...') since a bare 'Quebec,
# Quebec, Canada' is not a recognised Google location and would be ignored.
_QC_CITY_LOCATIONS = {
    'montreal': ('Montreal, Quebec, Canada', 'Montreal'),
    'quebec': ('Quebec City, Quebec, Canada', 'Quebec'),
    'quebec city': ('Quebec City, Quebec, Canada', 'Quebec'),
    'ville de quebec': ('Quebec City, Quebec, Canada', 'Quebec'),
    'gatineau': ('Gatineau, Quebec, Canada', 'Gatineau'),
    'laval': ('Laval, Quebec, Canada', 'Laval'),
    'longueuil': ('Longueuil, Quebec, Canada', 'Longueuil'),
    'sherbrooke': ('Sherbrooke, Quebec, Canada', 'Sherbrooke'),
    'trois-rivieres': ('Trois-Rivieres, Quebec, Canada', 'Trois-Rivieres'),
    'trois rivieres': ('Trois-Rivieres, Quebec, Canada', 'Trois-Rivieres'),
    'saguenay': ('Saguenay, Quebec, Canada', 'Saguenay'),
    'levis': ('Levis, Quebec, Canada', 'Levis'),
    'terrebonne': ('Terrebonne, Quebec, Canada', 'Terrebonne'),
}
# Fallback when the city is empty/unknown: province-wide SERP.
_QC_DEFAULT_LOCATION = ('Quebec, Canada', 'Quebec')


def _resolve_qc_location(raw_city: str):
    """(location, label, key) for a user-typed QC city, or the province-wide
    default. `key` is used in the cache key."""
    key = _strip_accents(raw_city or '').strip().lower()
    if key in _QC_CITY_LOCATIONS:
        loc, label = _QC_CITY_LOCATIONS[key]
        return loc, label, key
    loc, label = _QC_DEFAULT_LOCATION
    return loc, label, 'quebec-ca'


def _result_host(link: str) -> str:
    """Registrable host of a SERP result URL: strip scheme, path and www."""
    h = (link or '').lower().strip()
    h = h.split('://', 1)[-1]
    h = h.split('/', 1)[0]
    return h[4:] if h.startswith('www.') else h


# ---------------------------------------------------------------------------
# Google Business Profile diagnosis (read-only, via Serper Maps).
# No GBP access needed: we read the public local pack. Finds the site's own
# listing by matching the listing website to the audited domain, then
# benchmarks it against the local pack for its own category + city. This is the
# "verdict de ta fiche" block of the public audit - for a local trade the
# profile is usually the real ceiling, before any content.
# ---------------------------------------------------------------------------

def _gbp_search_queries(crawl: dict, domain: str) -> list:
    """Ordered Serper Maps queries to locate the site's own listing.

    We do NOT trust a single 'business name' guess: QC titles read
    'Trade City | Brand' and a naive split mangles hyphenated names
    (Saint-Hyacinthe becomes 'Hyacinthe'). Instead we try the full title, then
    each strong-separator segment longest-first (the brand is usually the long
    one, not the short one), then the bare domain label. _gbp_diagnosis matches
    the returned listings by website, so a fuzzy query is fine.
    """
    import re
    src = (crawl.get('title') or '').strip() or (crawl.get('h1') or '').strip()
    # Strong separators only: pipe, en/em dash, middot, colon, and a SPACED
    # hyphen (' - '). Never a bare hyphen, so 'Saint-Hyacinthe' stays intact.
    segs = [s.strip() for s in re.split(r'[|–—·:]', src.replace(' - ', '|')) if s.strip()]
    segs.sort(key=len, reverse=True)
    dom = domain[4:] if domain.startswith('www.') else domain
    label = dom.rsplit('.', 1)[0].split('.')[-1]  # constructioncbrodeur
    out = []
    for q in [src] + segs + [label]:
        q = (q or '').strip()
        if q and q.lower() not in [o.lower() for o in out]:
            out.append(q)
    return out[:4]


def _gbp_city_from_address(address: str) -> str:
    """'123 rue X, Saint-Hyacinthe, QC J2S 0A3, Canada' -> 'Saint-Hyacinthe'.

    Canonical CA form is [..., City, 'PROV POSTAL', 'Country'], so the city is
    the third-last comma segment.
    """
    parts = [p.strip() for p in (address or '').split(',') if p.strip()]
    return parts[-3] if len(parts) >= 3 else ''


def _serper_maps(query: str, serper_key: str, gl: str = 'ca', hl: str = 'fr',
                 tries: int = 2) -> list:
    """Local places for a Serper Maps query, or [] on any failure."""
    for _ in range(tries):
        try:
            r = http_requests.post(
                'https://google.serper.dev/maps',
                headers={'X-API-KEY': serper_key, 'Content-Type': 'application/json'},
                json={'q': query, 'gl': gl, 'hl': hl},
                timeout=10,
            )
            if r.status_code == 200:
                return (r.json() or {}).get('places') or []
        except Exception:  # noqa: BLE001
            continue
    return []


def _gbp_diagnosis(domain: str, crawl: dict) -> dict:
    """Read-only Google Business Profile verdict for the audited domain.

    Returns {'available': False} when Serper is not configured. Never invents:
    when no local listing links back to the site, returns found=False so the UI
    says 'we could not locate your profile' honestly (that itself is a signal).
    """
    serper_key = os.environ.get('SERPER_API_KEY')
    if not serper_key:
        return {'available': False}
    dom = domain[4:] if domain.startswith('www.') else domain

    own = None
    for q in _gbp_search_queries(crawl, domain):
        for p in _serper_maps(q, serper_key):
            if _result_host(p.get('website') or '') == dom:
                own = p
                break
        if own:
            break

    if not own:
        return {
            'available': True, 'found': False, 'verdict': 'absent',
            'verdict_text': (
                "On n'a pas trouve de fiche Google Business reliee a ton site. "
                "Soit tu n'en as pas de verifiee, soit elle ne pointe pas vers "
                "ton site. Pour un metier local, c'est souvent le vrai plafond, "
                "avant meme une ligne de contenu."
            ),
        }

    city = _gbp_city_from_address(own.get('address') or '')
    category = own.get('type') or (own.get('types') or [''])[0] or ''
    own_rating = own.get('rating') or 0
    own_reviews = own.get('ratingCount') or 0

    pack = []
    if category and city:
        for p in _serper_maps(f'{category} {city}', serper_key):
            if _result_host(p.get('website') or '') == dom:
                continue
            pack.append({
                'name': p.get('title'),
                'rating': p.get('rating'),
                'reviews': p.get('ratingCount') or 0,
            })
            if len(pack) >= 3:
                break
    pack_top_reviews = max([c['reviews'] for c in pack], default=0)

    signals = [{'key': 'found', 'status': 'ok', 'label': 'Fiche trouvee',
                'detail': own.get('title') or ''}]
    if pack_top_reviews and own_reviews < pack_top_reviews * 0.5:
        signals.append({'key': 'reviews', 'status': 'bad', 'label': 'Avis',
                        'detail': f"{own_reviews} avis, contre jusqu'a {pack_top_reviews} pour le pack local."})
    elif own_reviews < 10:
        signals.append({'key': 'reviews', 'status': 'warn', 'label': 'Avis',
                        'detail': f"{own_reviews} avis, c'est mince pour convaincre."})
    else:
        signals.append({'key': 'reviews', 'status': 'ok', 'label': 'Avis',
                        'detail': f"{own_reviews} avis."})
    if own_rating and own_rating < 4.0:
        signals.append({'key': 'rating', 'status': 'warn', 'label': 'Note',
                        'detail': f"{own_rating}/5, sous la barre de confiance de 4.0."})
    else:
        signals.append({'key': 'rating', 'status': 'ok', 'label': 'Note',
                        'detail': f"{own_rating or '-'}/5."})
    signals.append({'key': 'photo',
                    'status': 'ok' if own.get('thumbnailUrl') else 'warn',
                    'label': 'Photos',
                    'detail': 'Photo presente.' if own.get('thumbnailUrl') else 'Aucune photo detectee.'})
    signals.append({'key': 'hours',
                    'status': 'ok' if own.get('openingHours') else 'warn',
                    'label': 'Heures',
                    'detail': 'Heures affichees.' if own.get('openingHours') else 'Heures manquantes.'})

    n_bad = sum(1 for s in signals if s['status'] == 'bad')
    n_warn = sum(1 for s in signals if s['status'] == 'warn')
    if n_bad or n_warn >= 2:
        verdict, verdict_text = 'weak', (
            "Ta fiche existe mais elle est sous le pack local. C'est ton vrai "
            "plafond : on regle la fiche avant une ligne de contenu."
        )
    else:
        verdict, verdict_text = 'strong', (
            "Ta fiche tient la route. Le contenu devient alors ta prochaine "
            "marche pour capter les recherches que la fiche ne prend pas."
        )

    return {
        'available': True, 'found': True, 'verdict': verdict,
        'verdict_text': verdict_text,
        'business': {'name': own.get('title'), 'rating': own_rating,
                     'reviews': own_reviews, 'category': category, 'city': city},
        'pack': pack,
        'signals': signals,
    }


def _serper_geo_organic(keyword: str, location: str, api_key: str, tries: int = 3):
    """Largest organic result set from up to `tries` geolocated Serper calls,
    plus an ok flag.

    Serper intermittently returns a TRUNCATED SERP (e.g. 3 results instead of
    100). A single call then misses a genuinely-ranking site. Retrying while
    the set looks short (<10) and keeping the largest response makes the check
    a faithful read instead of noise. `ok` is True as soon as one call returns
    200, so a real empty SERP is distinguishable from an API failure.
    """
    best, ok = [], False
    for _ in range(tries):
        try:
            resp = http_requests.post(
                'https://google.serper.dev/search',
                headers={'X-API-KEY': api_key, 'Content-Type': 'application/json'},
                json={
                    'q': keyword,
                    'gl': 'ca',
                    'hl': 'fr',
                    'num': 100,
                    'location': location,
                },
                timeout=15,
            )
        except Exception:
            continue
        if resp.status_code != 200:
            continue
        ok = True
        org = (resp.json() or {}).get('organic') or []
        if len(org) > len(best):
            best = org
        if len(org) >= 10:  # a healthy set; stop early
            break
    return best, ok


class PublicPositionCheckView(APIView):
    """POST /api/public/position-check/ {url, keyword, city}

    Public lead-gen engine for the free "où je me classe sur Google" tool on
    gridar.app. Given a URL, a keyword and a Quebec city, returns the site's
    geolocated Google.ca organic rank (1-100) and the top-3 competitors that
    show up for that keyword in that city.

    No auth (public), throttled per IP, and cached 10 min per (host, keyword,
    city) so repeated checks don't re-spend Serper credits.
    """
    # authentication_classes = [] kills DRF SessionAuthentication which would
    # otherwise enforce its own CSRF check on this POST and 403 unauthenticated
    # visitors. Same pattern as PublicAuditView.
    authentication_classes = []
    permission_classes = []  # public
    throttle_classes = [PublicAuditThrottle]

    def post(self, request):
        raw_url = (request.data.get('url') or '').strip()
        keyword = (request.data.get('keyword') or '').strip()
        raw_city = (request.data.get('city') or '').strip()

        if not raw_url:
            return Response(
                {'error': 'URL manquante. Ex: tondomaine.com'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not keyword:
            return Response(
                {'error': 'Mot-cle manquant.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        host = _normalize_audit_domain(raw_url)
        if not host:
            return Response(
                {'error': 'URL invalide. Ex: tondomaine.com'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        location, city_label, city_key = _resolve_qc_location(raw_city)

        cache_key = f'public-poscheck:v1:{host}:{keyword.lower()}:{city_key}'
        cached = cache.get(cache_key)
        if cached:
            return Response(cached)

        api_key = os.environ.get('SERPER_API_KEY')
        if not api_key:
            return Response(
                {'error': 'Verification temporairement indisponible, reessaie dans un instant.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        organic, ok = _serper_geo_organic(keyword, location, api_key)
        if not ok:
            return Response(
                {'error': 'Verification temporairement indisponible, reessaie dans un instant.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        # Find the submitted site by EXACT host match (strip www) so a mere
        # mention of the domain in another result's path never counts.
        position = None
        matched_url = ''
        for idx, item in enumerate(organic):
            link = item.get('link') or ''
            if _result_host(link) == host:
                position = item.get('position') or (idx + 1)
                matched_url = link
                break

        top3 = []
        for idx, item in enumerate(organic[:3]):
            link = item.get('link') or ''
            top3.append({
                'position': item.get('position') or (idx + 1),
                'domain': _result_host(link),
                'url': link,
                'title': item.get('title') or '',
            })

        payload = {
            'found': position is not None,
            'position': position,
            'keyword': keyword,
            'city': city_label,
            'checked_domain': host,
            'matched_url': matched_url,
            'total_results': len(organic),
            'top3': top3,
        }

        # Cache only successful reads (10 min) to cap Serper spend.
        cache.set(cache_key, payload, timeout=600)
        return Response(payload)


class PublicLeadCaptureView(APIView):
    """POST /api/public/leads/ {email, domain, consented_marketing?}

    Saves the visitor's email to unlock the full audit report. The "full
    report" here is just the same audit cached payload - the gating is purely
    a marketing checkpoint, not a real access control. SPA reads the full
    payload immediately after capture so the user gets instant value.
    """
    authentication_classes = []  # see PublicAuditView for the reason
    permission_classes = []  # public
    throttle_classes = [PublicAuditThrottle]

    def post(self, request):
        from .models import Lead

        email = (request.data.get('email') or '').strip().lower()
        domain = _normalize_audit_domain(request.data.get('domain') or '')
        consented = bool(request.data.get('consented_marketing'))

        # Basic email shape check.
        import re
        if not email or not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
            return Response(
                {'error': 'Email invalide.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Reach into the cache for the score (cohort analysis) and the
        # report_token, so the J+0 email can link to the shareable report page.
        # Cache has a 1h TTL; if the visitor types their email later (or after a
        # server restart), fall back to the persisted PublicAuditReport row so
        # the email always carries a working /rapport/<token> link instead of
        # bouncing the reader back to the audit form.
        score = None
        report_token = None
        if domain:
            cached = cache.get(f'public-audit:v2:{domain}')
            if cached:
                score = cached.get('composite_score')
                report_token = cached.get('report_token')
            if not report_token:
                from .models import PublicAuditReport
                report = (
                    PublicAuditReport.objects
                    .filter(domain=domain)
                    .order_by('-created_at')
                    .first()
                )
                if report:
                    report_token = str(report.token)
                    if score is None:
                        score = (report.payload or {}).get('composite_score')

        lead = Lead.objects.create(
            email=email,
            domain_audited=domain or '',
            source='public_audit',
            ip=(request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip()
                or request.META.get('REMOTE_ADDR') or None),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
            locale=request.headers.get('Accept-Language', '')[:10],
            consented_marketing=consented,
            score_at_capture=score,
            report_token=report_token,
        )

        # Fire the transactional J+0 ("here's your full report") email
        # synchronously - it's the only step that's not gated by marketing
        # consent (Resend categorizes it as transactional). Failure here is
        # logged but doesn't break the SPA flow - the marketing sequence
        # cron will retry on its next tick.
        try:
            from .email_service import SEQUENCE_STEPS, send_lead_step
            j0 = next((s for s in SEQUENCE_STEPS if s.code == 'j0_audit_report'), None)
            if j0:
                send_lead_step(lead, j0)
        except Exception as e:
            logger.warning('J+0 send failed for lead %s: %s', lead.id, e)

        # Enrich the report with real data for the 7 "full report" sections
        # the SPA used to fake with hardcoded teasers. Best-effort: failure
        # here doesn't break the lead capture.
        enriched_payload = None
        if domain and report_token:
            try:
                from .models import PublicAuditReport
                report = PublicAuditReport.objects.filter(token=report_token).first()
                if report:
                    base_payload = dict(report.payload or {})
                    enrich = _enrich_public_audit_payload(domain, base_payload)
                    base_payload['full_report'] = enrich
                    base_payload['full_report_gated'] = False
                    report.payload = base_payload
                    report.save(update_fields=['payload'])
                    # Refresh the 1h domain cache so anyone who re-hits
                    # /api/public/audit/ for the same domain in the next
                    # hour also sees the enriched version.
                    cache.set(
                        f'public-audit:v2:{domain}',
                        base_payload, timeout=3600,
                    )
                    enriched_payload = base_payload
            except Exception as e:
                logger.warning(
                    'Enrichment failed for lead %s (domain=%s): %s',
                    lead.id, domain, e,
                )

        response_body = {
            'ok': True,
            'message': 'Email enregistre. Le rapport complet est maintenant visible.',
            'report_token': report_token,
        }
        if enriched_payload is not None:
            response_body['payload'] = enriched_payload
        return Response(response_body, status=status.HTTP_201_CREATED)


class PublicReportView(APIView):
    """GET /api/public/report/<token>/

    Returns a persisted public-audit report by its shareable token. No auth so
    the link works for anyone the visitor shares it with (the token is a random
    UUID, not enumerable). Backs the gridar.app/rapport/<token> page.
    """
    authentication_classes = []  # public, mirror PublicAuditView
    permission_classes = []
    throttle_classes = [PublicAuditThrottle]

    def get(self, request, token):
        from .models import PublicAuditReport

        report = PublicAuditReport.objects.filter(token=token).first()
        if not report:
            return Response(
                {'error': 'Rapport introuvable.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        data = dict(report.payload or {})
        # Authoritative values from the row (the stored payload predates the
        # token, and its audited_at is the compute time - close enough, but we
        # return the row's identity explicitly).
        data['domain'] = report.domain
        data['report_token'] = str(report.token)
        data['audited_at'] = report.created_at.isoformat()
        return Response(data)


class PublicUnsubscribeView(APIView):
    """POST /api/public/unsubscribe/ {token} or {email}

    Opt-out endpoint behind the gridar.app/unsubscribe confirmation page.

    Two accepted credentials:
      - `token`: signed (django.core.signing) - authoritative, unforgeable.
      - `email`: plain - kept because every email sent before 2026-06-11
        carries a plain ?email= footer link that must keep working. An
        unverified opt-out is the compliant failure mode: the worst case is
        a third party unsubscribing someone, the inverse (a person who
        cannot opt out) is the Loi 25 / RGPD violation.

    Always returns 200 with {ok: true} when input is well-formed, whether
    or not the address matched any lead - no email enumeration oracle.
    """
    authentication_classes = []  # public, mirror PublicLeadCaptureView
    permission_classes = []
    throttle_classes = [PublicAuditThrottle]

    def post(self, request):
        from .email_service import apply_unsubscribe, read_unsubscribe_token

        token = (request.data.get('token') or '').strip()
        email = None
        if token:
            email = read_unsubscribe_token(token)
            if email is None:
                return Response(
                    {'error': 'Lien de desinscription invalide.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            raw = (request.data.get('email') or '').strip().lower()
            import re
            if not raw or not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', raw):
                return Response(
                    {'error': 'Email invalide.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            email = raw

        updated = apply_unsubscribe(email)
        logger.info('Unsubscribe request for %s (rows updated: %s)', email, updated)
        return Response({'ok': True})


@method_decorator(csrf_exempt, name='dispatch')
class PublicUnsubscribeOneClickView(APIView):
    """POST /api/public/unsubscribe/one-click/?t=<token>

    RFC 8058 List-Unsubscribe-Post target. Gmail / Yahoo / Outlook POST
    here (form body `List-Unsubscribe=One-Click`, no cookies, no JS) when
    the user clicks their mail client's native unsubscribe button. Token
    only - this URL is machine-generated per recipient, never typed.
    """
    authentication_classes = []
    permission_classes = []
    # No throttle: mailbox providers batch their POSTs from shared IPs;
    # throttling them would silently drop legitimate opt-outs.

    def post(self, request):
        from .email_service import apply_unsubscribe, read_unsubscribe_token

        token = (request.query_params.get('t') or '').strip()
        email = read_unsubscribe_token(token) if token else None
        if email is None:
            return Response(
                {'error': 'invalid token'}, status=status.HTTP_400_BAD_REQUEST,
            )
        apply_unsubscribe(email)
        return Response({'ok': True})


class PublicAuditStatsView(APIView):
    """GET /api/public/audit-stats/

    Tiny public endpoint used by the audit landing page to render live social
    proof above the fold ("X audits ce mois-ci · Y entreprises ont demande
    un compte cette semaine"). Cached 5 min so we don't hit the DB on every
    visitor of a high-traffic landing.

    Returns: {audits_this_month, leads_this_month, leads_this_week, total_leads}
    """
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        from datetime import timedelta
        from django.utils import timezone
        from .models import Lead

        cache_key = 'public-audit-stats:v1'
        cached = cache.get(cache_key)
        if cached:
            return Response(cached)

        now = timezone.now()
        start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        start_of_week = now - timedelta(days=now.weekday())
        start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)

        # We don't actually log every public audit - the cache hits don't go
        # through the DB. As a rough proxy we count Leads x ~5 (assuming ~20%
        # email capture rate) to give a believable "audits run this month".
        # When we add proper audit logging later this becomes exact.
        leads_qs = Lead.objects.filter(source='public_audit')
        total_leads = leads_qs.count()
        leads_this_month = leads_qs.filter(created_at__gte=start_of_month).count()
        leads_this_week = leads_qs.filter(created_at__gte=start_of_week).count()

        # Audits ~= leads x 5 (conservative estimate). Floor at 12 so a fresh
        # landing doesn't show "0 audits ce mois-ci" which kills social proof.
        audits_this_month = max(12, leads_this_month * 5)

        payload = {
            'audits_this_month': audits_this_month,
            'leads_this_month': leads_this_month,
            'leads_this_week': leads_this_week,
            'total_leads': total_leads,
        }
        cache.set(cache_key, payload, timeout=300)  # 5 min
        return Response(payload)


# ── Phase 4: WordPress 1-click connector ────────────────────────────────────


from .api_v1 import BaseV1View


class WPConnectorView(BaseV1View):
    """POST /api/v1/wp-connector/connect/

    Receives credentials FROM the gridar-connector WordPress plugin running
    in the user's WP admin. The plugin auto-generates an Application Password
    server-side, sends it here over HTTPS, and we create the Site in
    WordPress mode without the user ever copy-pasting anything.

    Auth: Bearer ApiToken (the user pastes their Gridar API token ONCE in the
    plugin admin page, the plugin uses it for this single connect call).
    Inherits BaseV1View which already validates the token and rate-limits.

    Body: {wp_url, username, app_password, name?}
        - wp_url: https://monsite.ca (without /wp-admin)
        - username: WP user owning the App Password
        - app_password: 24-char generated by WP_Application_Passwords::create_new
        - name: optional human label, defaults to the WP site name detected
                via the WP REST /info endpoint

    Response: {site_id, name, domain, dashboard_url}
    """

    def post(self, request):
        from .wordpress_adapter import WordPressClient, WordPressError

        user = request.user  # Set by BaseV1View / ApiTokenAuthentication

        wp_url = (request.data.get('wp_url') or '').strip().rstrip('/')
        username = (request.data.get('username') or '').strip()
        app_password = (request.data.get('app_password') or '').strip()
        name = (request.data.get('name') or '').strip()

        if not wp_url or not username or not app_password:
            return Response(
                {'error': 'wp_url, username et app_password sont requis.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not wp_url.startswith(('http://', 'https://')):
            return Response(
                {'error': 'wp_url doit commencer par https:// ou http://'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Build a transient Site-shaped object to test creds without committing.
        class _Probe:
            pass
        probe = _Probe()
        probe.wp_url = wp_url
        probe.wp_username = username
        probe.wp_app_password = app_password

        try:
            client = WordPressClient(probe)
            info = client.test_auth()
        except WordPressError as e:
            return Response(
                {'error': f'Credentials WordPress invalides: {e}'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            return Response(
                {'error': f'Erreur connexion WP: {str(e)[:120]}'},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        # Reuse existing site if same wp_url + same owner.
        from urllib.parse import urlparse
        parsed = urlparse(wp_url)
        host = parsed.netloc or parsed.path
        site = Site.objects.filter(owner=user, wp_url=wp_url).first()
        if not site:
            site = Site.objects.create(
                owner=user,
                name=name or info.get('site_name') or host,
                domain=host.replace('www.', '', 1) if host.startswith('www.') else host,
                wp_url=wp_url,
                wp_username=username,
                wp_app_password=app_password,
            )
        else:
            site.wp_username = username
            site.wp_app_password = app_password
            if name:
                site.name = name
            site.save()

        return Response({
            'site_id': site.id,
            'name': site.name,
            'domain': site.domain,
            'dashboard_url': f'https://gridar.app/dashboard/{site.id}',
        }, status=status.HTTP_201_CREATED)


class SiteSeoScoreView(APIView):
    """GET /api/sites/<id>/seo-score/

    JWT-authenticated equivalent of V1SiteSeoScoreView. Returns the same
    composite SEO score payload so the dashboard UI can render the score
    card without needing an API token.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, site_id):
        from .api_v1 import _compute_site_seo_score
        site = get_site_for_user(request, site_id)
        return Response(_compute_site_seo_score(site))


class AIOverviewReadinessView(APIView):
    """GET /api/sites/<id>/posts/<slug>/ai-overview-readiness/

    JWT-authenticated equivalent of V1AIOverviewReadinessView. Returns
    a 0-100 score + breakdown + suggestions describing how well the
    article is structured for AI Overview / SGE pickup.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, site_id, slug):
        from .api_v1 import (
            _compute_ai_overview_readiness,
            _fetch_article_for_readiness,
        )
        site = get_site_for_user(request, site_id)
        article = _fetch_article_for_readiness(site, slug)
        if not article:
            from django.http import Http404
            raise Http404('Article introuvable.')
        return Response(_compute_ai_overview_readiness(site, article))


class CheckRenderabilityView(APIView):
    """POST /api/check-renderability/ {url}

    JWT-authenticated equivalent of V1CheckRenderabilityView. Returns
    {url, is_prerendered, html_contains_main_text, word_count, warning,
    suggestion} so the dashboard UI can warn the user when their site
    ships as an unprerendered SPA.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from .api_v1 import _check_renderability
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


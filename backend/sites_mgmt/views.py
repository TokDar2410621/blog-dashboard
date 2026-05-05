import os
import uuid
import base64
import hashlib
import logging
from urllib.parse import quote

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import UserRateThrottle
from django.shortcuts import get_object_or_404
from django.conf import settings
from django.core.cache import cache
from django.db.models import Sum
from django.utils.text import slugify
from django.core.management import call_command
from datetime import date
from io import StringIO
import requests as http_requests

from django.http import HttpResponse

import markdown as md_lib

from .models import (
    Site, UploadedImage, HostedPost, HostedCategory, HostedTag,
    TrackedKeyword, SerpRank,
)
from .db_utils import ensure_site_connection, test_site_connection
from .blog_adapter import detect_blog_tables, setup_blog_views

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
        pass  # Non-blocking — don't fail the request if deploy hook fails


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

    @action(detail=True, methods=['post'])
    def test(self, request, pk=None):
        site = self.get_object()
        success, message = test_site_connection(site)
        return Response({'success': success, 'message': message})

    @action(detail=True, methods=['post'])
    def init_db(self, request, pk=None):
        """Create blog tables in the site's database."""
        site = self.get_object()
        alias = ensure_site_connection(site)
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
        alias = ensure_site_connection(site)
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
        alias = ensure_site_connection(site)

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
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({
            'username': request.user.username,
            'email': request.user.email,
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

        if site.is_hosted:
            hosted_qs = HostedPost.objects.filter(site=site, slug=slug)
            if language:
                hosted_qs = hosted_qs.filter(language=language)
            post = hosted_qs.first()
            if not post:
                from django.http import Http404
                raise Http404
            for field in ['title', 'slug', 'excerpt', 'content', 'author',
                          'cover_image', 'reading_time', 'featured', 'status',
                          'scheduled_at', 'published_at', 'language', 'translation_group']:
                if field in data:
                    setattr(post, field, data[field])
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

        for field in ['title', 'slug', 'excerpt', 'content', 'author',
                      'cover_image', 'reading_time', 'featured', 'status',
                      'scheduled_at', 'published_at', 'language', 'translation_group']:
            if field in data:
                setattr(post, field, data[field])

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
            alias = ensure_site_connection(site)
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

        alias = ensure_site_connection(site)
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


class SiteCategoriesView(APIView):
    """List categories for a site."""
    permission_classes = [IsAuthenticated]

    def get(self, request, site_id):
        site = get_site_for_user(request, site_id)
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

        try:
            from .article_generator import ArticleGenerator

            generator = ArticleGenerator(alias, knowledge_base=site.knowledge_base or '')
            result = generator.generate(
                search_method=search_method,
                topic=topic,
                title=title,
                article_type=article_type,
                length=length,
                keywords=keywords,
                dry_run=dry_run,
                language=language,
            )

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
    """Generate article content and return it without saving — fills the editor."""
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    throttle_scope = 'ai_generate'

    def post(self, request, site_id):
        site = get_site_for_user(request, site_id)
        alias = ensure_site_connection(site)

        topic = request.data.get('topic') or None
        title = request.data.get('title') or None
        article_type = request.data.get('type', 'news')
        length = request.data.get('length', 'medium')
        keywords = request.data.get('keywords') or None
        context_urls = request.data.get('context_urls') or []
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
                knowledge_base=(site.knowledge_base or '') + url_context
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

            return Response({
                'title': gen_title,
                'slug': gen_slug,
                'content': gen_content,
                'excerpt': gen_excerpt,
                'tags': gen_tags,
                'cover_image': gen_cover,
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
    permission_classes = []  # Public — images are referenced in articles

    def get(self, request, uid):
        img = get_object_or_404(UploadedImage, uid=uid)
        response = HttpResponse(bytes(img.data), content_type=img.mime_type)
        response['Cache-Control'] = 'public, max-age=31536000, immutable'
        return response


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

            response = client.models.generate_images(
                model="imagen-3.0-generate-002",
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

    cache_key = _seo_cache_key(
        'seo-audit:', title, excerpt, content[:5000], keyword, language
    )
    cached = cache.get(cache_key)
    if cached is not None:
        return cached, True  # (result, from_cache)

    lang = 'French' if language == 'fr' else 'English'
    kw_section = f'Primary keyword: {keyword}\n' if keyword else ''

    prompt = f"""You are a senior SEO expert. Audit this blog article holistically.
Focus on REAL SEO signals, not checklists. Write feedback in {lang}.

{kw_section}Title: {title}
Meta description: {excerpt}
Content (first 5000 chars):
{content[:5000]}

Evaluate:
- Search intent alignment (does the article answer what someone would Google?)
- Keyword placement (title, intro, H2s, natural density — NOT stuffing)
- Content depth & originality (is this the same as 100 other articles?)
- E-E-A-T signals (experience, expertise, authority, trust cues)
- Readability (sentence length, active voice, scannability)
- Engagement hooks (intro, CTA, internal links)
- Technical basics (meta description quality, H2 hierarchy, image alt if mentioned)

Be honest and specific. Numbers and examples > platitudes.

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
    return result, False


class SEOAuditView(APIView):
    """Full SEO audit via Gemini — returns score + strengths + weaknesses + actions."""
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
- Do NOT stuff it — one occurrence per zone is enough.
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
- Only return fields that actually need changes — null for fields already good
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

        # Cache results for 30 min — PSI is slow and quota-limited
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
            # Common: 429 quota exceeded — guide the user
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
            'Serper results are approximations — for real data use Ahrefs/SEMrush'
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

        # 1) Serper — SERP top 10 + People Also Ask (best-effort)
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
                serp_lines.append(f"{idx}. {title} — {snippet}")
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
actionable — a writer should be able to start writing from it without further research.

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

        rows = _all_published()

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
        # whose group has no siblings — candidates for translation.
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
            alias = ensure_site_connection(site)
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

        per_article = []
        cache_hits = 0
        for art in articles:
            if not art['title'] or not art['content']:
                continue
            try:
                result, from_cache = _run_seo_audit(
                    art['title'], art['excerpt'], art['content'],
                    keyword='', language=art['language'], api_key=api_key,
                )
                if from_cache:
                    cache_hits += 1
                per_article.append({
                    'slug': art['slug'],
                    'title': art['title'],
                    'language': art['language'],
                    'score': result['score'],
                    'verdict': result['verdict'],
                    'weaknesses': result['weaknesses'],
                    'actions': result['actions'],
                })
            except Exception as e:
                logger.warning('Bulk audit failed for %s: %s', art['slug'], e)
                per_article.append({
                    'slug': art['slug'],
                    'title': art['title'],
                    'language': art['language'],
                    'score': None,
                    'error': str(e),
                })

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

        # 1) Serper — peopleAlsoAsk
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

        # 2) Gemini — short answers (best-effort; if it fails, fall back to snippet)
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
            alias = ensure_site_connection(site)
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

        gemini_key = os.environ.get('GEMINI_API_KEY')
        if not gemini_key:
            return Response(
                {'error': 'GEMINI_API_KEY non configuree'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

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
            alias = ensure_site_connection(site)
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
- Identify ONE pillar_candidate_slug — the article that best summarizes the theme
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
            data = json.loads(text)
        except Exception as e:
            logger.warning('Gemini topic clustering failed: %s', e)
            return Response(
                {'error': f'Erreur clustering: {str(e)}'},
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

    Two GSC API calls (current period + previous period). No cache for now —
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
                scopes=GSC_SCOPES,
            )
            service = build(
                'searchconsole', 'v1',
                credentials=creds,
                cache_discovery=False,
            )

            def _query_period(start_d, end_d):
                body = {
                    'startDate': start_d.isoformat(),
                    'endDate': end_d.isoformat(),
                    'dimensions': ['page'],
                    'rowLimit': 1000,
                }
                return (
                    service.searchanalytics()
                    .query(siteUrl=site.gsc_property_url, body=body)
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

        # Resolve slug from URL by stripping the property URL prefix
        property_prefix = site.gsc_property_url.rstrip('/') + '/'

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
# RANK TRACKING — TrackedKeyword + SerpRank snapshots
# ==========================================================================

def _serialize_tracked_keyword(tk, latest=None):
    """Serialize a TrackedKeyword with its latest snapshot for list views."""
    base = {
        'id': tk.id,
        'keyword': tk.keyword,
        'language': tk.language,
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
    return base


class TrackedKeywordsView(APIView):
    """List or create tracked keywords for a site."""
    permission_classes = [IsAuthenticated]

    def get(self, request, site_id):
        site = get_site_for_user(request, site_id)
        keywords = list(
            TrackedKeyword.objects.filter(site=site).order_by('-created_at')
        )
        # Fetch latest snapshot per keyword in a single query
        latest_map = {}
        if keywords:
            ids = [k.id for k in keywords]
            for snap in (
                SerpRank.objects.filter(tracked_id__in=ids)
                .order_by('tracked_id', '-recorded_at')
            ):
                if snap.tracked_id not in latest_map:
                    latest_map[snap.tracked_id] = snap
        return Response({
            'results': [
                _serialize_tracked_keyword(k, latest_map.get(k.id))
                for k in keywords
            ],
        })

    def post(self, request, site_id):
        site = get_site_for_user(request, site_id)
        keyword = (request.data.get('keyword') or '').strip()
        language = (request.data.get('language') or site.default_language or 'fr').lower()
        target_url = (request.data.get('target_url') or '').strip()

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

        tk, created = TrackedKeyword.objects.get_or_create(
            site=site, keyword=keyword, language=language,
            defaults={'target_url': target_url, 'is_active': True},
        )
        if not created:
            # Reactivate / update target if existed
            tk.is_active = True
            if target_url:
                tk.target_url = target_url
            tk.save()
        return Response(
            _serialize_tracked_keyword(tk),
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class TrackedKeywordDetailView(APIView):
    """Delete a tracked keyword."""
    permission_classes = [IsAuthenticated]

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


class RankSnapshotView(APIView):
    """Crawl Google SERP via Serper for all active tracked keywords of a site,
    record one SerpRank snapshot per keyword. Designed to be called from a
    cron / scheduled agent (daily). Returns counts.

    Body: {keyword_ids?: [int]} — optional filter to only crawl specific
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
# PUBLIC API — consumed by site frontends (no auth, optional API key check)
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


class PublicSiteView(APIView):
    """GET /api/public/sites/<id>/ — basic site info."""
    permission_classes = []

    def get(self, request, site_id):
        site = _public_get_site(site_id, request)
        if not site:
            return Response({'error': 'Invalid API key'}, status=status.HTTP_403_FORBIDDEN)
        return Response({
            'id': site.id,
            'name': site.name,
            'domain': site.domain,
        })


class PublicPostsView(APIView):
    """GET /api/public/sites/<id>/posts/ — list published articles."""
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

        alias = ensure_site_connection(site)
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
    """GET /api/public/sites/<id>/posts/<slug>/ — single article."""
    permission_classes = []

    def get(self, request, site_id, slug):
        site = _public_get_site(site_id, request)
        if not site:
            return Response({'error': 'Invalid API key'}, status=status.HTTP_403_FORBIDDEN)

        if site.is_hosted:
            post = get_object_or_404(
                HostedPost.objects.select_related('category').prefetch_related('tags'),
                site=site, slug=slug, status='published'
            )
            # Increment view count
            HostedPost.objects.filter(pk=post.pk).update(view_count=post.view_count + 1)
            return Response(_serialize_hosted_post(post))

        alias = ensure_site_connection(site)
        post = get_object_or_404(
            BlogPost.objects.using(alias).select_related('category').prefetch_related('tags'),
            slug=slug, status='published'
        )
        BlogPost.objects.using(alias).filter(pk=post.pk).update(view_count=post.view_count + 1)
        serializer = BlogPostDetailSerializer(post)
        return Response(serializer.data)


class PublicTranslationsView(APIView):
    """GET /api/public/sites/<id>/posts/<slug>/translations/ — all language versions of an article.

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

        alias = ensure_site_connection(site)
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

        alias = ensure_site_connection(site)
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
# article slug. The OAuth client is configured via environment variables:
#
#   GSC_CLIENT_ID       Google Cloud OAuth2 client ID
#   GSC_CLIENT_SECRET   Google Cloud OAuth2 client secret
#   GSC_REDIRECT_URI    Must match an authorized redirect URI configured in
#                       the Google Cloud console (ex: the frontend callback
#                       page that POSTs {code, state} to /oauth-callback/).
#
# See backend/sites_mgmt/GSC_SETUP.md for setup instructions.

GSC_SCOPES = ['https://www.googleapis.com/auth/webmasters.readonly']
GSC_TOKEN_URI = 'https://oauth2.googleapis.com/token'
GSC_AUTH_URI = 'https://accounts.google.com/o/oauth2/auth'


def _gsc_client_config():
    """Return the OAuth2 client config dict from env vars, or None if missing."""
    client_id = os.environ.get('GSC_CLIENT_ID', '').strip()
    client_secret = os.environ.get('GSC_CLIENT_SECRET', '').strip()
    redirect_uri = os.environ.get('GSC_REDIRECT_URI', '').strip()
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
            flow = Flow.from_client_config(
                config,
                scopes=GSC_SCOPES,
                redirect_uri=config['web']['redirect_uris'][0],
            )
            flow.fetch_token(code=code)
            creds = flow.credentials
            if not creds.refresh_token:
                return Response(
                    {'error': 'No refresh token returned. Revoke app access on Google and retry.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            site.gsc_refresh_token = creds.refresh_token
            site.save(update_fields=['gsc_refresh_token'])
            return Response({'success': True})
        except Exception as e:
            logger.exception("GSC oauth-callback failed")
            return Response(
                {'error': f'Token exchange failed: {e}'},
                status=status.HTTP_400_BAD_REQUEST,
            )


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
        if not site.gsc_property_url:
            return Response(
                {'error': 'No GSC property URL configured for this site.'},
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

        # Build a full page URL = property + slug/
        property_url = site.gsc_property_url
        if not property_url.endswith('/'):
            property_url += '/'
        page_url = property_url + slug.strip('/') + '/'

        end = _date.today()
        start = end - timedelta(days=days)

        try:
            creds = Credentials(
                token=None,
                refresh_token=site.gsc_refresh_token,
                token_uri=GSC_TOKEN_URI,
                client_id=config['web']['client_id'],
                client_secret=config['web']['client_secret'],
                scopes=GSC_SCOPES,
            )
            service = build(
                'searchconsole', 'v1',
                credentials=creds,
                cache_discovery=False,
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
                siteUrl=site.gsc_property_url,
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

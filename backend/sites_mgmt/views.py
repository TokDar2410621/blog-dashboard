import os
import uuid
import base64
import logging

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import UserRateThrottle
from django.shortcuts import get_object_or_404
from django.conf import settings
from django.db.models import Sum
from django.utils.text import slugify
from django.core.management import call_command
from datetime import date
from io import StringIO
import requests as http_requests

from django.http import HttpResponse

import markdown as md_lib

from .models import Site, UploadedImage, HostedPost, HostedCategory, HostedTag
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
            return Response({'tags': data.get('tags', [])})

        except Exception as e:
            return Response(
                {'error': f'Erreur generation tags: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class SEOFixView(APIView):
    """Fix SEO issues in an article using Gemini."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        title = request.data.get('title', '')
        excerpt = request.data.get('excerpt', '')
        content = request.data.get('content', '')
        issues = request.data.get('issues', '')
        language = request.data.get('language', 'fr')

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

        try:
            from google import genai
            import json

            client = genai.Client(api_key=api_key)
            lang = 'French' if language == 'fr' else 'English'
            prompt = f"""You are an SEO expert. Fix the following issues in this blog article.
Write in {lang}.

Current title: {title}
Current excerpt (meta description): {excerpt}
Current content (first 3000 chars): {content[:3000]}

SEO issues to fix:
{issues}

Rules:
- Title should be 50-60 characters, compelling, with keywords
- Excerpt/meta description should be 120-160 characters
- If content is too short, expand it with relevant paragraphs (keep markdown format)
- Keep the same tone and style as the original
- Only return fields that need changes

Respond in JSON only (no markdown blocks):
{{
  "title": "optimized title or null if already good",
  "excerpt": "optimized excerpt or null if already good",
  "content": "full improved content in markdown or null if only title/excerpt changed"
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

            return Response(result)

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
            return Response(data)

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
            total = posts.count()
            start = (page - 1) * page_size
            end = start + page_size
            return Response({
                'count': total,
                'results': [_serialize_hosted_post(p, detail=False) for p in posts[start:end]],
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
    """GET /api/public/sites/<id>/posts/<slug>/translations/ — all translations of an article."""
    permission_classes = []

    def get(self, request, site_id, slug):
        site = _public_get_site(site_id, request)
        if not site:
            return Response({'error': 'Invalid API key'}, status=status.HTTP_403_FORBIDDEN)

        if site.is_hosted:
            post = get_object_or_404(HostedPost, site=site, slug=slug, status='published')
            translations = HostedPost.objects.filter(
                site=site,
                translation_group=post.translation_group,
                status='published',
            ).exclude(pk=post.pk)
            return Response([
                {'slug': p.slug, 'language': p.language, 'title': p.title}
                for p in translations
            ])

        alias = ensure_site_connection(site)
        post = get_object_or_404(BlogPost.objects.using(alias), slug=slug, status='published')
        translations = BlogPost.objects.using(alias).filter(
            translation_group=post.translation_group,
            status='published',
        ).exclude(pk=post.pk)
        return Response([
            {'slug': p.slug, 'language': p.language, 'title': p.title}
            for p in translations
        ])


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

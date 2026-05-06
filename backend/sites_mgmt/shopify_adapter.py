"""Shopify Admin API adapter — wraps `/admin/api/.../articles.json` calls so the
rest of the dashboard can treat a Shopify store like any other backend.

Authentication uses Shopify **custom app** Admin API access tokens. The store
owner creates a custom app in their Shopify admin (Settings → Apps and sales
channels → Develop apps → Create app), grants it `write_content` scope, and
copies the Admin API access token into our dashboard. We store domain + token
on `Site.shopify_domain` and `Site.shopify_access_token`.

Each method returns dicts shaped like a `BlogPost` row so existing serializers
and views can consume them without changes.

Reference: https://shopify.dev/docs/api/admin-rest/latest/resources/article
"""
from __future__ import annotations

import logging
import re
from urllib.parse import urlparse

import requests as http_requests

logger = logging.getLogger(__name__)

# Shopify Admin REST API version. Pin a stable version; Shopify deprecates
# quarterly so we'll bump this in maintenance updates.
API_VERSION = '2024-10'

USER_AGENT = 'BlogDashboard/1.0 (+https://blog-dashboard.ca)'


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _strip_html(html):
    if not html:
        return ''
    no_scripts = re.sub(r'<(script|style)[^>]*>.*?</\1>', ' ', html, flags=re.IGNORECASE | re.DOTALL)
    txt = re.sub(r'<[^>]+>', ' ', no_scripts)
    return re.sub(r'\s+', ' ', txt).strip()


def _normalize_shopify_domain(raw):
    """Accept anything the user pastes and return `xxx.myshopify.com`.
    Examples:
      - `monstore.myshopify.com` → as-is
      - `https://monstore.myshopify.com/admin` → `monstore.myshopify.com`
      - `monstore` → `monstore.myshopify.com`
    """
    if not raw:
        return ''
    s = raw.strip().lower()
    if '://' in s:
        s = urlparse(s).netloc or s
    s = s.split('/')[0]
    if not s.endswith('.myshopify.com') and '.' not in s:
        s = f'{s}.myshopify.com'
    return s


def _shopify_to_dashboard_status(article):
    """Shopify uses `published_at` (ISO timestamp or null). null = draft."""
    if article.get('published_at'):
        return 'published'
    return 'draft'


# --------------------------------------------------------------------------
# Client
# --------------------------------------------------------------------------

class ShopifyError(Exception):
    """Raised when the Shopify Admin API rejects a request."""


class ShopifyClient:
    """Thin wrapper around `/admin/api/<version>/blogs/<blog_id>/articles*`."""

    def __init__(self, site):
        self.site = site
        self.domain = (site.shopify_domain or '').strip().lower()
        self.token = site.shopify_access_token
        self.blog_id = (site.shopify_blog_id or '').strip()
        if not self.domain or not self.token:
            raise ShopifyError("Site n'est pas configuré pour Shopify.")
        self.base_url = f'https://{self.domain}/admin/api/{API_VERSION}'
        self.headers = {
            'X-Shopify-Access-Token': self.token,
            'Content-Type': 'application/json',
            'User-Agent': USER_AGENT,
            'Accept': 'application/json',
        }

    # ── Discovery & auth ──────────────────────────────────────────────

    @staticmethod
    def discover(domain, token):
        """Validate that the token works against the given Shopify domain.
        Returns:
          on success: {valid: True, shop_name, shop_email, blogs: [{id, title, handle}], primary_blog_id}
          on failure: {valid: False, error}
        """
        normalized = _normalize_shopify_domain(domain)
        if not normalized:
            return {'valid': False, 'error': 'Domaine Shopify invalide.'}
        if not token or len(token) < 20:
            return {'valid': False, 'error': 'Token Shopify trop court — colle bien le Admin API access token.'}

        base = f'https://{normalized}/admin/api/{API_VERSION}'
        headers = {
            'X-Shopify-Access-Token': token,
            'Accept': 'application/json',
            'User-Agent': USER_AGENT,
        }

        # Step 1: hit /shop.json to validate token
        try:
            resp = http_requests.get(f'{base}/shop.json', headers=headers, timeout=10)
        except http_requests.RequestException as e:
            return {'valid': False, 'error': f'Boutique injoignable : {str(e)[:120]}'}
        if resp.status_code == 401:
            return {'valid': False, 'error': "Token invalide ou révoqué — vérifie le Admin API access token."}
        if resp.status_code == 404:
            return {'valid': False, 'error': "Domaine Shopify introuvable — vérifie l'orthographe du sous-domaine .myshopify.com."}
        if not resp.ok:
            return {'valid': False, 'error': f'Erreur Shopify {resp.status_code}: {resp.text[:200]}'}

        try:
            shop = (resp.json() or {}).get('shop') or {}
        except ValueError:
            return {'valid': False, 'error': 'Réponse Shopify invalide.'}

        # Step 2: list blogs to find one to publish into
        try:
            blogs_resp = http_requests.get(
                f'{base}/blogs.json?fields=id,title,handle&limit=50',
                headers=headers, timeout=10,
            )
        except http_requests.RequestException as e:
            return {'valid': False, 'error': f'Liste des blogs injoignable : {str(e)[:120]}'}
        if blogs_resp.status_code == 403:
            return {
                'valid': False,
                'error': "Token sans la permission 'write_content' — re-créé la custom app avec le scope write_content.",
            }
        if not blogs_resp.ok:
            return {'valid': False, 'error': f'Erreur Shopify {blogs_resp.status_code}: {blogs_resp.text[:200]}'}

        blogs = (blogs_resp.json() or {}).get('blogs') or []
        primary_blog_id = str(blogs[0]['id']) if blogs else ''

        return {
            'valid': True,
            'normalized_domain': normalized,
            'shop_name': shop.get('name', ''),
            'shop_email': shop.get('email', ''),
            'shop_primary_locale': shop.get('primary_locale', ''),
            'shop_currency': shop.get('currency', ''),
            'myshopify_domain': shop.get('myshopify_domain', normalized),
            'custom_domain': shop.get('domain', ''),
            'blogs': [
                {'id': str(b['id']), 'title': b.get('title', ''), 'handle': b.get('handle', '')}
                for b in blogs
            ],
            'primary_blog_id': primary_blog_id,
        }

    def test_auth(self):
        """Quick auth check — used after connection to confirm credentials still work."""
        try:
            resp = http_requests.get(f'{self.base_url}/shop.json', headers=self.headers, timeout=10)
        except http_requests.RequestException as e:
            raise ShopifyError(f'Boutique injoignable : {str(e)[:120]}')
        if resp.status_code == 401:
            raise ShopifyError('Token Shopify révoqué — re-connecte la boutique.')
        if not resp.ok:
            raise ShopifyError(f'Shopify {resp.status_code}: {resp.text[:200]}')
        return (resp.json() or {}).get('shop') or {}

    # ── Blog management ───────────────────────────────────────────────

    def list_blogs(self):
        try:
            resp = http_requests.get(
                f'{self.base_url}/blogs.json?fields=id,title,handle&limit=50',
                headers=self.headers, timeout=15,
            )
        except http_requests.RequestException as e:
            raise ShopifyError(f'Shopify unreachable: {str(e)[:120]}')
        if not resp.ok:
            raise ShopifyError(f'Shopify {resp.status_code}: {resp.text[:200]}')
        return (resp.json() or {}).get('blogs') or []

    def _require_blog_id(self):
        if not self.blog_id:
            raise ShopifyError("Aucun blog Shopify sélectionné. Reconnecte la boutique pour choisir un blog.")
        return self.blog_id

    # ── CRUD on articles ──────────────────────────────────────────────

    def list_posts(self, *, status=None, language=None, search='', page=1, per_page=20):
        """List articles in the configured blog.
        - status: 'published' / 'draft' / None (all)
        - language: ignored (Shopify doesn't have built-in i18n on articles; if
          the store uses Shopify Markets / Translate & Adapt, those translations
          live elsewhere)
        - search: client-side filter on title (Shopify article API has no search param)
        """
        blog_id = self._require_blog_id()
        params = {
            'limit': min(max(per_page, 1), 250),
            'fields': 'id,title,handle,body_html,summary_html,author,tags,published_at,created_at,updated_at,image',
        }
        if status == 'published':
            params['published_status'] = 'published'
        elif status == 'draft':
            params['published_status'] = 'unpublished'
        else:
            params['published_status'] = 'any'

        try:
            resp = http_requests.get(
                f'{self.base_url}/blogs/{blog_id}/articles.json',
                headers=self.headers, params=params, timeout=15,
            )
        except http_requests.RequestException as e:
            raise ShopifyError(f'Shopify unreachable: {str(e)[:120]}')
        if not resp.ok:
            raise ShopifyError(f'Shopify {resp.status_code}: {resp.text[:200]}')

        articles = (resp.json() or {}).get('articles') or []
        if search:
            s = search.lower()
            articles = [a for a in articles if s in (a.get('title') or '').lower()]

        results = [self._serialize(a) for a in articles]
        return {'count': len(results), 'results': results}

    def get_post(self, slug_or_id):
        """Fetch a single article. Shopify uses `handle` as the slug.
        Numeric slug_or_id → direct GET; string → list + filter on handle.
        """
        blog_id = self._require_blog_id()
        if str(slug_or_id).isdigit():
            try:
                resp = http_requests.get(
                    f'{self.base_url}/blogs/{blog_id}/articles/{slug_or_id}.json',
                    headers=self.headers, timeout=15,
                )
            except http_requests.RequestException as e:
                raise ShopifyError(f'Shopify unreachable: {str(e)[:120]}')
            if resp.status_code == 404:
                return None
            if not resp.ok:
                raise ShopifyError(f'Shopify {resp.status_code}: {resp.text[:200]}')
            return self._serialize((resp.json() or {}).get('article') or {})
        # Handle (slug) lookup — we list with handle filter
        try:
            resp = http_requests.get(
                f'{self.base_url}/blogs/{blog_id}/articles.json',
                headers=self.headers,
                params={'handle': slug_or_id, 'limit': 1, 'published_status': 'any'},
                timeout=15,
            )
        except http_requests.RequestException as e:
            raise ShopifyError(f'Shopify unreachable: {str(e)[:120]}')
        if not resp.ok:
            raise ShopifyError(f'Shopify {resp.status_code}: {resp.text[:200]}')
        items = (resp.json() or {}).get('articles') or []
        if not items:
            return None
        return self._serialize(items[0])

    def create_post(self, *, title, content, excerpt='', slug='', status='draft',
                    author='', tags=None, featured_image_url=''):
        """Create a new article. Returns serialized article on success."""
        blog_id = self._require_blog_id()
        body = {
            'title': title,
            'body_html': content,
        }
        if excerpt:
            body['summary_html'] = excerpt
        if slug:
            body['handle'] = slug
        if author:
            body['author'] = author
        if tags:
            if isinstance(tags, (list, tuple)):
                body['tags'] = ', '.join(str(t) for t in tags)
            else:
                body['tags'] = str(tags)
        if featured_image_url:
            body['image'] = {'src': featured_image_url}
        # Shopify uses published_at to mark publication state.
        if status == 'published':
            from django.utils import timezone
            body['published_at'] = timezone.now().isoformat()
        else:
            body['published_at'] = None

        try:
            resp = http_requests.post(
                f'{self.base_url}/blogs/{blog_id}/articles.json',
                headers=self.headers,
                json={'article': body},
                timeout=20,
            )
        except http_requests.RequestException as e:
            raise ShopifyError(f'Shopify unreachable: {str(e)[:120]}')
        if not resp.ok:
            raise ShopifyError(f'Shopify {resp.status_code}: {resp.text[:300]}')
        return self._serialize((resp.json() or {}).get('article') or {})

    def update_post(self, post_id, **fields):
        """Update an existing article. `fields` may contain title, content,
        excerpt, slug, status, author, tags, featured_image_url."""
        blog_id = self._require_blog_id()
        body = {}
        if 'title' in fields:
            body['title'] = fields['title']
        if 'content' in fields:
            body['body_html'] = fields['content']
        if 'excerpt' in fields:
            body['summary_html'] = fields['excerpt']
        if 'slug' in fields:
            body['handle'] = fields['slug']
        if 'author' in fields:
            body['author'] = fields['author']
        if 'tags' in fields:
            t = fields['tags']
            if isinstance(t, (list, tuple)):
                body['tags'] = ', '.join(str(x) for x in t)
            elif t is not None:
                body['tags'] = str(t)
        if 'featured_image_url' in fields and fields['featured_image_url']:
            body['image'] = {'src': fields['featured_image_url']}
        if 'status' in fields:
            if fields['status'] == 'published':
                from django.utils import timezone
                body['published_at'] = timezone.now().isoformat()
            elif fields['status'] == 'draft':
                body['published_at'] = None

        try:
            resp = http_requests.put(
                f'{self.base_url}/blogs/{blog_id}/articles/{post_id}.json',
                headers=self.headers,
                json={'article': body},
                timeout=20,
            )
        except http_requests.RequestException as e:
            raise ShopifyError(f'Shopify unreachable: {str(e)[:120]}')
        if not resp.ok:
            raise ShopifyError(f'Shopify {resp.status_code}: {resp.text[:300]}')
        return self._serialize((resp.json() or {}).get('article') or {})

    def delete_post(self, post_id, force=False):
        """Delete an article. Shopify deletes are always permanent (no trash)."""
        blog_id = self._require_blog_id()
        try:
            resp = http_requests.delete(
                f'{self.base_url}/blogs/{blog_id}/articles/{post_id}.json',
                headers=self.headers, timeout=15,
            )
        except http_requests.RequestException as e:
            raise ShopifyError(f'Shopify unreachable: {str(e)[:120]}')
        return resp.ok

    # ── Categories & Tags ─────────────────────────────────────────────

    def list_categories(self):
        """Shopify articles don't have categories — only tags. Return empty so
        existing UIs that call list_categories() degrade gracefully."""
        return []

    def list_tags(self):
        """Shopify exposes /admin/api/<v>/blogs/<id>/articles/tags.json."""
        blog_id = self._require_blog_id()
        try:
            resp = http_requests.get(
                f'{self.base_url}/blogs/{blog_id}/articles/tags.json?limit=250',
                headers=self.headers, timeout=15,
            )
        except http_requests.RequestException:
            return []
        if not resp.ok:
            return []
        tags = (resp.json() or {}).get('tags') or []
        return [{'id': t, 'name': t} for t in tags]

    # ── Internal: serialize Shopify article → blog-dashboard shape ────

    def _serialize(self, article, detail=True):
        """Convert a Shopify article dict to the dashboard's blog-post shape."""
        if not article:
            return None
        body_html = article.get('body_html') or ''
        summary_html = article.get('summary_html') or ''
        excerpt_plain = _strip_html(summary_html)[:300]
        published_at = article.get('published_at') or ''
        cover = (article.get('image') or {}).get('src') or ''
        tags_str = article.get('tags') or ''
        tag_list = [t.strip() for t in tags_str.split(',') if t.strip()] if tags_str else []
        # Compute the public URL on the storefront. Shopify routes blog
        # articles at `/blogs/<blog-handle>/<article-handle>` on the custom
        # domain; we don't always know the custom domain here, so we return
        # the myshopify.com URL as fallback. The connect endpoint can update
        # site.public_blog_domain with the custom domain.
        public_url = ''
        # We don't have blog handle here without an extra fetch; best-effort
        # using the article handle alone.
        handle = article.get('handle') or ''
        return {
            'id': article.get('id'),
            'shopify_id': article.get('id'),
            'title': article.get('title') or '',
            'slug': handle,
            'excerpt': excerpt_plain,
            'content': body_html if detail else '',
            'author': article.get('author') or '',
            'category': None,
            'category_slug': None,
            'tags': tag_list,
            'cover_image': cover,
            'reading_time': max(1, len(_strip_html(body_html).split()) // 200) if body_html else 1,
            'featured': False,
            'status': _shopify_to_dashboard_status(article),
            'view_count': 0,
            'language': 'fr',
            'translation_group': '',
            'scheduled_at': None,
            'published_at': published_at[:10] if published_at else None,
            'created_at': article.get('created_at') or '',
            'updated_at': article.get('updated_at') or article.get('created_at') or '',
            'shopify_handle': handle,
            'public_url': public_url,
        }

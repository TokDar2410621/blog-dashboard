"""WordPress REST API adapter — wraps `/wp-json/wp/v2/posts` calls so the rest
of the dashboard can treat a WordPress site like any other backend.

Authentication uses WordPress Application Passwords (built-in since WP 5.6).
The user creates one in their WP profile and pastes username + app password
into Settings; we store them on Site.wp_username and Site.wp_app_password.

Each method returns dicts shaped like a `BlogPost` row so existing serializers
and views can consume them without changes.
"""
from __future__ import annotations

import re
from urllib.parse import urljoin

import requests as http_requests


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _strip_html(html):
    """Best-effort HTML → plain text. Used to derive excerpt / search text."""
    if not html:
        return ''
    no_scripts = re.sub(r'<(script|style)[^>]*>.*?</\1>', ' ', html, flags=re.IGNORECASE | re.DOTALL)
    txt = re.sub(r'<[^>]+>', ' ', no_scripts)
    return re.sub(r'\s+', ' ', txt).strip()


def _wp_to_dashboard_status(wp_status):
    """Map WordPress post status → blog-dashboard status."""
    if wp_status == 'publish':
        return 'published'
    if wp_status == 'future':
        return 'scheduled'
    return 'draft'


def _dashboard_to_wp_status(status):
    if status == 'published':
        return 'publish'
    if status == 'scheduled':
        return 'future'
    return 'draft'


# --------------------------------------------------------------------------
# Client
# --------------------------------------------------------------------------

class WordPressError(Exception):
    """Raised when the WP REST API rejects a request."""


class WordPressClient:
    """Thin wrapper around `/wp-json/wp/v2/`."""

    def __init__(self, site):
        self.site = site
        self.base_url = (site.wp_url or '').rstrip('/')
        self.username = site.wp_username
        self.app_password = site.wp_app_password
        if not self.base_url or not self.username or not self.app_password:
            raise WordPressError('Site n\'est pas configuré pour WordPress.')
        self.auth = (self.username, self.app_password)

    # ── Public API: discovery & auth check ────────────────────────────

    @staticmethod
    def discover(url):
        """Probe a URL to detect if it's a WordPress site.
        Returns {valid_wp: bool, name: str, description: str, post_count: int|None,
                 namespaces: [str]} or {valid_wp: False, error: str}.
        """
        url = url.strip().rstrip('/')
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        try:
            resp = http_requests.get(
                urljoin(url + '/', 'wp-json/'),
                timeout=10,
                headers={'User-Agent': 'BlogDashboard/1.0'},
            )
        except http_requests.RequestException as e:
            return {'valid_wp': False, 'error': f'Site injoignable : {str(e)[:120]}'}

        if not resp.ok:
            return {'valid_wp': False, 'error': f'WP REST API non disponible (HTTP {resp.status_code}). Vérifiez que /wp-json/ est accessible.'}

        try:
            data = resp.json()
        except ValueError:
            return {'valid_wp': False, 'error': 'Réponse invalide — ce ne semble pas être WordPress.'}

        # Confirm it has the wp/v2 namespace
        namespaces = data.get('namespaces') or []
        if 'wp/v2' not in namespaces:
            return {'valid_wp': False, 'error': 'Ce site n\'expose pas wp/v2 — REST API désactivée ?'}

        # Try to count posts (HEAD to list endpoint)
        post_count = None
        try:
            count_resp = http_requests.get(
                urljoin(url + '/', 'wp-json/wp/v2/posts?per_page=1'),
                timeout=10,
                headers={'User-Agent': 'BlogDashboard/1.0'},
            )
            if count_resp.ok:
                post_count = int(count_resp.headers.get('X-WP-Total', '0') or 0)
        except Exception:
            pass

        return {
            'valid_wp': True,
            'normalized_url': url,
            'name': data.get('name') or '',
            'description': data.get('description') or '',
            'post_count': post_count,
            'namespaces': namespaces[:10],
        }

    def test_auth(self):
        """Hit /wp/v2/users/me to confirm the credentials work. Returns user dict
        on success, raises WordPressError on failure."""
        try:
            resp = http_requests.get(
                f'{self.base_url}/wp-json/wp/v2/users/me',
                auth=self.auth,
                timeout=10,
                headers={'User-Agent': 'BlogDashboard/1.0'},
            )
        except http_requests.RequestException as e:
            raise WordPressError(f'Site injoignable : {str(e)[:120]}')
        if resp.status_code == 401:
            raise WordPressError('Identifiants WordPress invalides — vérifie l\'username + Application Password.')
        if not resp.ok:
            raise WordPressError(f'Erreur WP {resp.status_code}: {resp.text[:200]}')
        return resp.json()

    # ── CRUD on posts ─────────────────────────────────────────────────

    def list_posts(self, *, status=None, language=None, search='', page=1, per_page=20):
        """List posts. WordPress doesn't have language by default; if a Polylang
        / WPML plugin is installed, language filtering would need their REST
        endpoints. For MVP we ignore `language` filter on WP side and let the
        caller filter client-side.
        """
        params = {
            'page': page,
            'per_page': min(max(per_page, 1), 100),
            '_fields': 'id,date,modified,slug,status,title,excerpt,content,categories,tags,featured_media,link,author',
        }
        if status:
            wp_status = _dashboard_to_wp_status(status)
            params['status'] = wp_status
        else:
            # By default, WP REST returns only 'publish'. Ask for everything.
            params['status'] = ['publish', 'draft', 'future', 'pending']
        if search:
            params['search'] = search

        try:
            resp = http_requests.get(
                f'{self.base_url}/wp-json/wp/v2/posts',
                auth=self.auth,
                params=params,
                timeout=15,
                headers={'User-Agent': 'BlogDashboard/1.0'},
            )
        except http_requests.RequestException as e:
            raise WordPressError(f'WP unreachable: {str(e)[:120]}')

        if not resp.ok:
            raise WordPressError(f'WP {resp.status_code}: {resp.text[:200]}')

        items = resp.json() or []
        total = int(resp.headers.get('X-WP-Total', len(items)) or len(items))
        results = [self._serialize(p) for p in items]
        return {'count': total, 'results': results}

    def get_post(self, slug_or_id):
        """Fetch a single post by slug (preferred) or numeric ID."""
        if str(slug_or_id).isdigit():
            url = f'{self.base_url}/wp-json/wp/v2/posts/{slug_or_id}'
            try:
                resp = http_requests.get(
                    url, auth=self.auth, timeout=15,
                    params={'_fields': 'id,date,modified,slug,status,title,excerpt,content,categories,tags,featured_media,link,author'},
                    headers={'User-Agent': 'BlogDashboard/1.0'},
                )
            except http_requests.RequestException as e:
                raise WordPressError(f'WP unreachable: {str(e)[:120]}')
            if resp.status_code == 404:
                return None
            if not resp.ok:
                raise WordPressError(f'WP {resp.status_code}: {resp.text[:200]}')
            return self._serialize(resp.json())
        # Slug lookup
        try:
            resp = http_requests.get(
                f'{self.base_url}/wp-json/wp/v2/posts',
                auth=self.auth,
                params={
                    'slug': slug_or_id,
                    'status': ['publish', 'draft', 'future', 'pending', 'private'],
                    '_fields': 'id,date,modified,slug,status,title,excerpt,content,categories,tags,featured_media,link,author',
                },
                timeout=15,
                headers={'User-Agent': 'BlogDashboard/1.0'},
            )
        except http_requests.RequestException as e:
            raise WordPressError(f'WP unreachable: {str(e)[:120]}')
        if not resp.ok:
            raise WordPressError(f'WP {resp.status_code}: {resp.text[:200]}')
        items = resp.json() or []
        if not items:
            return None
        return self._serialize(items[0])

    def create_post(self, *, title, content, excerpt='', slug='', status='draft',
                    categories=None, tags=None, featured_media=None):
        """Create a new post. Returns the created post (serialized)."""
        body = {
            'title': title,
            'content': content,
            'excerpt': excerpt or '',
            'status': _dashboard_to_wp_status(status),
        }
        if slug:
            body['slug'] = slug
        if categories:
            body['categories'] = categories  # array of category IDs
        if tags:
            body['tags'] = tags  # array of tag IDs
        if featured_media:
            body['featured_media'] = featured_media
        try:
            resp = http_requests.post(
                f'{self.base_url}/wp-json/wp/v2/posts',
                auth=self.auth, json=body, timeout=20,
                headers={'User-Agent': 'BlogDashboard/1.0'},
            )
        except http_requests.RequestException as e:
            raise WordPressError(f'WP unreachable: {str(e)[:120]}')
        if not resp.ok:
            raise WordPressError(f'WP {resp.status_code}: {resp.text[:300]}')
        return self._serialize(resp.json())

    def update_post(self, post_id, **fields):
        """Update an existing post. `fields` may contain title, content, excerpt,
        slug, status. Other keys are ignored."""
        body = {}
        for k in ('title', 'content', 'excerpt', 'slug'):
            if k in fields:
                body[k] = fields[k]
        if 'status' in fields:
            body['status'] = _dashboard_to_wp_status(fields['status'])
        try:
            resp = http_requests.post(
                f'{self.base_url}/wp-json/wp/v2/posts/{post_id}',
                auth=self.auth, json=body, timeout=20,
                headers={'User-Agent': 'BlogDashboard/1.0'},
            )
        except http_requests.RequestException as e:
            raise WordPressError(f'WP unreachable: {str(e)[:120]}')
        if not resp.ok:
            raise WordPressError(f'WP {resp.status_code}: {resp.text[:300]}')
        return self._serialize(resp.json())

    def delete_post(self, post_id, force=False):
        """Delete a post (force=True for permanent). Returns True on success."""
        try:
            resp = http_requests.delete(
                f'{self.base_url}/wp-json/wp/v2/posts/{post_id}',
                auth=self.auth,
                params={'force': 'true'} if force else {},
                timeout=15,
                headers={'User-Agent': 'BlogDashboard/1.0'},
            )
        except http_requests.RequestException as e:
            raise WordPressError(f'WP unreachable: {str(e)[:120]}')
        return resp.ok

    # ── Categories & Tags ─────────────────────────────────────────────

    def list_categories(self):
        try:
            resp = http_requests.get(
                f'{self.base_url}/wp-json/wp/v2/categories',
                auth=self.auth,
                params={'per_page': 100, '_fields': 'id,name,slug,count'},
                timeout=15,
                headers={'User-Agent': 'BlogDashboard/1.0'},
            )
        except http_requests.RequestException as e:
            raise WordPressError(f'WP unreachable: {str(e)[:120]}')
        if not resp.ok:
            return []
        return [
            {'id': c['id'], 'name': c['name'], 'slug': c['slug'],
             'description': '', 'posts_count': c.get('count', 0)}
            for c in (resp.json() or [])
        ]

    def list_tags(self):
        try:
            resp = http_requests.get(
                f'{self.base_url}/wp-json/wp/v2/tags',
                auth=self.auth,
                params={'per_page': 100, '_fields': 'id,name,slug'},
                timeout=15,
                headers={'User-Agent': 'BlogDashboard/1.0'},
            )
        except http_requests.RequestException as e:
            raise WordPressError(f'WP unreachable: {str(e)[:120]}')
        if not resp.ok:
            return []
        return [{'id': t['id'], 'name': t['name']} for t in (resp.json() or [])]

    # ── Internal: serialize WP post → blog-dashboard shape ────────────

    def _serialize(self, wp_post, detail=True):
        """Convert a WP post dict into the shape our serializers/views expect."""
        if not wp_post:
            return None

        title = (wp_post.get('title') or {}).get('rendered') or ''
        # WP wraps content in <p> by default and may include shortcodes.
        # We keep the rendered HTML as content; the editor displays it.
        content_obj = wp_post.get('content') or {}
        excerpt_obj = wp_post.get('excerpt') or {}
        content_html = content_obj.get('rendered') or ''
        # Some WP installs return raw also (when context=edit). Our /wp/v2/posts
        # by default doesn't include raw without edit context, so we use rendered.
        excerpt_html = excerpt_obj.get('rendered') or ''
        excerpt_plain = _strip_html(excerpt_html)[:300]

        return {
            'id': wp_post.get('id'),
            'wp_id': wp_post.get('id'),  # explicit so frontends know it's WP
            'title': title,
            'slug': wp_post.get('slug') or '',
            'excerpt': excerpt_plain,
            'content': content_html if detail else '',
            'author': '',  # WP returns author as user ID; we'd need a separate fetch
            'category': None,
            'category_slug': None,
            'tags': [],
            'cover_image': '',  # featured_media is an ID; resolving to URL needs a fetch
            'reading_time': max(1, len(_strip_html(content_html).split()) // 200) if content_html else 1,
            'featured': False,
            'status': _wp_to_dashboard_status(wp_post.get('status') or 'draft'),
            'view_count': 0,
            'language': 'fr',  # WP doesn't have a default language field
            'translation_group': '',
            'scheduled_at': wp_post.get('date') if wp_post.get('status') == 'future' else None,
            'published_at': (wp_post.get('date') or '')[:10] if wp_post.get('status') == 'publish' else None,
            'created_at': wp_post.get('date') or '',
            'updated_at': wp_post.get('modified') or wp_post.get('date') or '',
            'wp_link': wp_post.get('link') or '',
        }

"""Webflow CMS API v2 adapter — wraps `/v2/collections/{id}/items` calls.

Authentication uses a Webflow **Site Token** (Project Settings → Apps &
Integrations → API access → Generate API token). We store it on
`Site.webflow_token` along with the chosen `webflow_site_id` and
`webflow_collection_id`.

Webflow's CMS is fully custom: every collection has its own field schema with
project-specific slugs. To make this work for any user, we auto-detect the
typical "Blog Posts" template fields (`name`, `slug`, `post-body`,
`post-summary`, `main-image`) at connect time and store the mapping on
`Site.webflow_field_map`. The mapping can be customized later per-site if a
user has a non-standard schema.

Reference: https://developers.webflow.com/data/reference/cms/collection-items/staged-items/list-items
"""
from __future__ import annotations

import logging
import re

import requests as http_requests

logger = logging.getLogger(__name__)

API_BASE = 'https://api.webflow.com/v2'
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


# Default mapping for the Webflow "Blog" boilerplate template.
DEFAULT_FIELD_MAP = {
    'title': 'name',
    'slug': 'slug',
    'body': 'post-body',
    'summary': 'post-summary',
    'image': 'main-image',
}


def detect_field_map(collection_schema):
    """Given a Webflow collection schema (the `fields` list from the API),
    auto-detect which slug to use for each of our internal roles.
    Returns a dict like DEFAULT_FIELD_MAP, with auto-fallbacks.
    """
    if not collection_schema:
        return dict(DEFAULT_FIELD_MAP)

    fields = collection_schema.get('fields') or []
    by_slug = {f.get('slug'): f for f in fields}
    by_type = {}
    for f in fields:
        by_type.setdefault(f.get('type'), []).append(f)

    mapping = {}

    # Title: 'name' is always present and required in every Webflow collection.
    mapping['title'] = 'name'
    mapping['slug'] = 'slug'

    # Body: prefer common slugs, fall back to first RichText/HTML field.
    for slug in ('post-body', 'body', 'content', 'article-body', 'rich-text'):
        if slug in by_slug:
            mapping['body'] = slug
            break
    if 'body' not in mapping:
        rich = by_type.get('RichText') or by_type.get('rich-text') or []
        if rich:
            mapping['body'] = rich[0].get('slug')

    # Summary: prefer common slugs, fall back to first PlainText.
    for slug in ('post-summary', 'summary', 'excerpt', 'description'):
        if slug in by_slug:
            mapping['summary'] = slug
            break
    if 'summary' not in mapping:
        plain = [f for f in fields if f.get('type') in ('PlainText', 'plain-text')
                 and f.get('slug') not in ('name', 'slug')]
        if plain:
            mapping['summary'] = plain[0].get('slug')

    # Image: prefer common slugs, fall back to first ImageRef.
    for slug in ('main-image', 'thumbnail-image', 'cover-image', 'featured-image', 'image'):
        if slug in by_slug:
            mapping['image'] = slug
            break
    if 'image' not in mapping:
        imgs = [f for f in fields if f.get('type') in ('Image', 'ImageRef', 'image')]
        if imgs:
            mapping['image'] = imgs[0].get('slug')

    return mapping


# --------------------------------------------------------------------------
# Client
# --------------------------------------------------------------------------

class WebflowError(Exception):
    """Raised when the Webflow CMS API rejects a request."""


class WebflowClient:
    """Thin wrapper around `/v2/collections/<id>/items*`."""

    def __init__(self, site):
        self.site = site
        self.token = site.webflow_token
        self.site_id = site.webflow_site_id
        self.collection_id = site.webflow_collection_id
        if not self.token or not self.site_id or not self.collection_id:
            raise WebflowError("Site n'est pas configuré pour Webflow.")
        self.field_map = (
            site.webflow_field_map
            if isinstance(site.webflow_field_map, dict) and site.webflow_field_map
            else dict(DEFAULT_FIELD_MAP)
        )
        self.headers = {
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json',
            'User-Agent': USER_AGENT,
            'accept-version': '2.0.0',
        }

    # ── Discovery ─────────────────────────────────────────────────────

    @staticmethod
    def discover(token):
        """Validate the token by listing sites the user has access to.
        Returns {valid, sites: [{id, displayName, shortName, customDomains}], error?}.
        """
        if not token or len(token) < 30:
            return {'valid': False, 'error': 'Token Webflow trop court — colle bien le Site Token.'}
        headers = {
            'Authorization': f'Bearer {token}',
            'accept-version': '2.0.0',
            'User-Agent': USER_AGENT,
            'Accept': 'application/json',
        }
        try:
            resp = http_requests.get(f'{API_BASE}/sites', headers=headers, timeout=15)
        except http_requests.RequestException as e:
            return {'valid': False, 'error': f'Webflow injoignable : {str(e)[:120]}'}
        if resp.status_code == 401:
            return {'valid': False, 'error': "Token Webflow invalide ou expiré."}
        if not resp.ok:
            return {'valid': False, 'error': f'Erreur Webflow {resp.status_code}: {resp.text[:200]}'}
        try:
            data = resp.json()
        except ValueError:
            return {'valid': False, 'error': 'Réponse Webflow invalide.'}
        sites = data.get('sites') or []
        return {
            'valid': True,
            'sites': [
                {
                    'id': s.get('id'),
                    'displayName': s.get('displayName') or s.get('shortName') or '',
                    'shortName': s.get('shortName') or '',
                    'customDomains': [d.get('url') for d in (s.get('customDomains') or []) if d.get('url')],
                    'previewUrl': s.get('previewUrl', ''),
                }
                for s in sites
            ],
        }

    @staticmethod
    def list_collections(token, site_id):
        """List CMS collections for a site."""
        headers = {
            'Authorization': f'Bearer {token}',
            'accept-version': '2.0.0',
            'User-Agent': USER_AGENT,
            'Accept': 'application/json',
        }
        try:
            resp = http_requests.get(
                f'{API_BASE}/sites/{site_id}/collections',
                headers=headers, timeout=15,
            )
        except http_requests.RequestException as e:
            raise WebflowError(f'Webflow injoignable : {str(e)[:120]}')
        if not resp.ok:
            raise WebflowError(f'Webflow {resp.status_code}: {resp.text[:200]}')
        return (resp.json() or {}).get('collections') or []

    @staticmethod
    def get_collection_schema(token, collection_id):
        """Fetch a collection's full schema (including fields list)."""
        headers = {
            'Authorization': f'Bearer {token}',
            'accept-version': '2.0.0',
            'User-Agent': USER_AGENT,
            'Accept': 'application/json',
        }
        try:
            resp = http_requests.get(
                f'{API_BASE}/collections/{collection_id}',
                headers=headers, timeout=15,
            )
        except http_requests.RequestException as e:
            raise WebflowError(f'Webflow injoignable : {str(e)[:120]}')
        if not resp.ok:
            raise WebflowError(f'Webflow {resp.status_code}: {resp.text[:200]}')
        return resp.json() or {}

    def test_auth(self):
        try:
            resp = http_requests.get(
                f'{API_BASE}/sites/{self.site_id}', headers=self.headers, timeout=10,
            )
        except http_requests.RequestException as e:
            raise WebflowError(f'Webflow injoignable : {str(e)[:120]}')
        if resp.status_code == 401:
            raise WebflowError('Token Webflow révoqué — re-connecte le site.')
        if not resp.ok:
            raise WebflowError(f'Webflow {resp.status_code}: {resp.text[:200]}')
        return resp.json() or {}

    # ── CRUD on items ─────────────────────────────────────────────────

    def list_posts(self, *, status=None, language=None, search='', page=1, per_page=20):
        """List items from the configured collection. Status maps:
          'published' → isDraft=false, isArchived=false
          'draft' → isDraft=true
        """
        offset = max(0, (page - 1) * per_page)
        params = {
            'limit': min(max(per_page, 1), 100),
            'offset': offset,
        }
        try:
            resp = http_requests.get(
                f'{API_BASE}/collections/{self.collection_id}/items',
                headers=self.headers, params=params, timeout=20,
            )
        except http_requests.RequestException as e:
            raise WebflowError(f'Webflow unreachable: {str(e)[:120]}')
        if not resp.ok:
            raise WebflowError(f'Webflow {resp.status_code}: {resp.text[:200]}')
        body = resp.json() or {}
        items = body.get('items') or []
        if status == 'published':
            items = [i for i in items if not i.get('isDraft') and not i.get('isArchived')]
        elif status == 'draft':
            items = [i for i in items if i.get('isDraft')]
        if search:
            s = search.lower()
            tit = self.field_map.get('title', 'name')
            items = [i for i in items if s in (i.get('fieldData', {}).get(tit) or '').lower()]
        results = [self._serialize(i) for i in items]
        return {'count': len(results), 'results': results}

    def get_post(self, slug_or_id):
        """Fetch one item. If slug_or_id looks like a Webflow ID (24-char hex),
        do a direct GET. Otherwise list and filter on slug field."""
        if re.fullmatch(r'[0-9a-f]{24}', str(slug_or_id) or '', flags=re.IGNORECASE):
            try:
                resp = http_requests.get(
                    f'{API_BASE}/collections/{self.collection_id}/items/{slug_or_id}',
                    headers=self.headers, timeout=15,
                )
            except http_requests.RequestException as e:
                raise WebflowError(f'Webflow unreachable: {str(e)[:120]}')
            if resp.status_code == 404:
                return None
            if not resp.ok:
                raise WebflowError(f'Webflow {resp.status_code}: {resp.text[:200]}')
            return self._serialize(resp.json() or {})

        slug_field = self.field_map.get('slug', 'slug')
        # Webflow doesn't natively filter by field on GET; list and filter.
        page = self.list_posts(per_page=100)
        for r in page['results']:
            if r['slug'] == slug_or_id or r.get('webflow_id') == slug_or_id:
                # Re-fetch detail (list call may not include all fields — fetch by id)
                return self.get_post(r['webflow_id'])
        return None

    def _build_field_data(self, *, title=None, slug=None, content=None, excerpt=None,
                          featured_image_url=None, partial=False):
        """Translate our internal fields → Webflow fieldData using the mapping."""
        m = self.field_map
        fd = {}
        if title is not None or not partial:
            fd[m.get('title', 'name')] = title or ''
        if slug is not None or not partial:
            fd[m.get('slug', 'slug')] = slug or ''
        if content is not None and m.get('body'):
            fd[m['body']] = content or ''
        if excerpt is not None and m.get('summary'):
            fd[m['summary']] = excerpt or ''
        if featured_image_url and m.get('image'):
            fd[m['image']] = {'url': featured_image_url, 'alt': ''}
        return fd

    def create_post(self, *, title, content, excerpt='', slug='', status='draft',
                    featured_image_url='', **_ignored):
        """Create an item. Uses ?live=true so it appears on the live site.
        status='published' → isDraft=false, otherwise draft."""
        is_draft = (status != 'published')
        body = {
            'isDraft': is_draft,
            'isArchived': False,
            'fieldData': self._build_field_data(
                title=title, slug=slug, content=content, excerpt=excerpt,
                featured_image_url=featured_image_url, partial=False,
            ),
        }
        try:
            # ?live=true publishes to the staged site immediately. Without it,
            # the item only lives in the CMS and won't be visible on the site.
            resp = http_requests.post(
                f'{API_BASE}/collections/{self.collection_id}/items/live',
                headers=self.headers, json=body, timeout=25,
            )
        except http_requests.RequestException as e:
            raise WebflowError(f'Webflow unreachable: {str(e)[:120]}')
        if not resp.ok:
            raise WebflowError(f'Webflow {resp.status_code}: {resp.text[:300]}')
        return self._serialize(resp.json() or {})

    def update_post(self, post_id, **fields):
        body = {'fieldData': self._build_field_data(
            title=fields.get('title'),
            slug=fields.get('slug'),
            content=fields.get('content'),
            excerpt=fields.get('excerpt'),
            featured_image_url=fields.get('featured_image_url'),
            partial=True,
        )}
        if 'status' in fields:
            body['isDraft'] = (fields['status'] != 'published')
        try:
            resp = http_requests.patch(
                f'{API_BASE}/collections/{self.collection_id}/items/{post_id}/live',
                headers=self.headers, json=body, timeout=25,
            )
        except http_requests.RequestException as e:
            raise WebflowError(f'Webflow unreachable: {str(e)[:120]}')
        if not resp.ok:
            raise WebflowError(f'Webflow {resp.status_code}: {resp.text[:300]}')
        return self._serialize(resp.json() or {})

    def delete_post(self, post_id, force=False):
        """Delete an item from both staged and live sites."""
        try:
            resp = http_requests.delete(
                f'{API_BASE}/collections/{self.collection_id}/items/{post_id}/live',
                headers=self.headers, timeout=15,
            )
        except http_requests.RequestException as e:
            raise WebflowError(f'Webflow unreachable: {str(e)[:120]}')
        return resp.ok

    def list_categories(self):
        """Webflow collections don't have a uniform 'categories' concept."""
        return []

    def list_tags(self):
        return []

    # ── Internal: serialize Webflow item → dashboard shape ────────────

    def _serialize(self, item, detail=True):
        if not item:
            return None
        fd = item.get('fieldData') or {}
        m = self.field_map
        title = fd.get(m.get('title', 'name')) or ''
        slug = fd.get(m.get('slug', 'slug')) or ''
        body_html = fd.get(m.get('body', '')) or ''
        summary = fd.get(m.get('summary', '')) or ''
        img_field = fd.get(m.get('image', ''))
        cover = ''
        if isinstance(img_field, dict):
            cover = img_field.get('url') or ''
        elif isinstance(img_field, str):
            cover = img_field
        is_draft = bool(item.get('isDraft'))
        last_updated = item.get('lastUpdated') or item.get('createdOn') or ''
        return {
            'id': item.get('id'),
            'webflow_id': item.get('id'),
            'title': title,
            'slug': slug,
            'excerpt': summary[:300] if summary else '',
            'content': body_html if detail else '',
            'author': '',
            'category': None,
            'category_slug': None,
            'tags': [],
            'cover_image': cover,
            'reading_time': max(1, len(_strip_html(body_html).split()) // 200) if body_html else 1,
            'featured': False,
            'status': 'draft' if is_draft else 'published',
            'view_count': 0,
            'language': 'fr',
            'translation_group': '',
            'scheduled_at': None,
            'published_at': (item.get('lastPublished') or '')[:10] if item.get('lastPublished') else None,
            'created_at': item.get('createdOn') or '',
            'updated_at': last_updated,
        }

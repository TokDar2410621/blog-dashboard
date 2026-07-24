"""Index coverage audit: which of a site's pages Google actually indexed.

Cross-references the pages a site EXPECTS to be indexed (its sitemap, or the
pages Gridar knows about) against what Google shows:

  - `site:<domain>` via Serper: the pages Google surfaces. Works on ANY site,
    no auth, but approximate (Google caps the list it shows).
  - GSC URL Inspection (when GSC is connected): the AUTHORITATIVE per-URL index
    status + the REASON a page is not indexed. Uses the same
    webmasters.readonly scope the site already granted, so no reconnection.

Returns a coverage report: indexed vs not, the reason when known, coverage %.
No LLM call, no quota.
"""
from __future__ import annotations

import logging
import os
from urllib.parse import urlparse

import requests

logger = logging.getLogger(__name__)

_SITEMAP_NS_LOC = 'loc'
_UA = 'GridarIndexAudit/1.0 (+https://gridar.app)'


def _public_base(site):
    """(base_url, host) for the site's public pages. Prefers the public blog
    domain, then the site domain. Returns ('', '') if none."""
    raw = (getattr(site, 'public_blog_domain', '') or site.domain or '').strip()
    if not raw:
        return '', ''
    if not raw.startswith(('http://', 'https://')):
        raw = 'https://' + raw
    parsed = urlparse(raw)
    host = (parsed.netloc or '').lower().split(':')[0]
    if host.startswith('www.'):
        host = host[4:]  # NOT lstrip('www.') - that strips any leading w/. chars
    base = f'{parsed.scheme}://{parsed.netloc}'
    return base.rstrip('/'), host


def _norm_url(url: str) -> str:
    """Normalize for cross-source matching: scheme+host+path, no trailing slash,
    no query/fragment, lowercased host, www-insensitive."""
    try:
        p = urlparse(url.strip())
    except Exception:
        return url.strip()
    host = (p.netloc or '').lower()
    if host.startswith('www.'):
        host = host[4:]
    path = (p.path or '/').rstrip('/') or '/'
    return f'{p.scheme or "https"}://{host}{path}'


def _fetch_sitemap_urls(base_url: str, cap: int = 500) -> list[str]:
    """Fetch and parse <base>/sitemap.xml, following one level of sitemap index.
    Best-effort: returns [] on any failure."""
    if not base_url:
        return []
    import xml.etree.ElementTree as ET

    def _locs(xml_text: str) -> tuple[list[str], bool]:
        """Return (loc values, is_index)."""
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return [], False
        is_index = root.tag.split('}')[-1] == 'sitemapindex'
        locs = [
            (el.text or '').strip()
            for el in root.iter()
            if el.tag.split('}')[-1] == _SITEMAP_NS_LOC and (el.text or '').strip()
        ]
        return locs, is_index

    def _get(url: str) -> str:
        try:
            r = requests.get(url, headers={'User-Agent': _UA}, timeout=10)
            if r.status_code == 200 and r.text:
                return r.text
        except Exception as exc:
            logger.info('index_coverage: sitemap fetch failed %s: %s', url, exc)
        return ''

    text = _get(f'{base_url}/sitemap.xml')
    if not text:
        return []
    locs, is_index = _locs(text)
    urls: list[str] = []
    if is_index:
        for child_sitemap in locs[:10]:  # cap nested sitemaps
            child_text = _get(child_sitemap)
            if not child_text:
                continue
            child_locs, _ = _locs(child_text)
            urls.extend(child_locs)
            if len(urls) >= cap:
                break
    else:
        urls = locs
    # dedup preserving order, cap
    seen, out = set(), []
    for u in urls:
        n = _norm_url(u)
        if n not in seen:
            seen.add(n)
            out.append(u)
        if len(out) >= cap:
            break
    return out


def _serper_site_urls(domain: str, pages: int = 8, num: int = 10) -> set[str]:
    """Collect the URLs Google surfaces for `site:<domain>` (normalized).

    num stays at 10: Serper rejects num>10 on the current plan ("Query pattern
    not allowed for free accounts"), so we page through results instead.
    """
    api_key = os.environ.get('SERPER_API_KEY')
    if not api_key or not domain:
        return set()
    found: set[str] = set()
    for page in range(1, pages + 1):
        try:
            resp = requests.post(
                'https://google.serper.dev/search',
                headers={'X-API-KEY': api_key, 'Content-Type': 'application/json'},
                json={'q': f'site:{domain}', 'num': num, 'page': page},
                timeout=12,
            )
            if resp.status_code != 200:
                break
            organic = (resp.json() or {}).get('organic') or []
        except Exception as exc:
            logger.info('index_coverage: serper site: failed p%s: %s', page, exc)
            break
        if not organic:
            break
        for row in organic:
            link = row.get('link') or ''
            host = (urlparse(link).netloc or '').lower().split(':')[0]
            if host.startswith('www.'):
                host = host[4:]
            if host and (host == domain or host.endswith('.' + domain)):
                found.add(_norm_url(link))
        if len(organic) < num:
            break  # last page
    return found


def _resolve_gsc_property(service, site) -> str:
    """The GSC property (siteUrl) to inspect against, matching how the user
    actually verified it.

    The stored gsc_property_url is often a URL-prefix ('https://site.com/') that
    is NOT a verified property when the user set up a DOMAIN property
    ('sc-domain:site.com'). URL Inspection is strict about ownership, so we map
    to a property the token actually owns (403 'You do not own this site'
    otherwise). Falls back to the stored value if the listing fails.
    """
    stored = (site.gsc_property_url or '').strip()
    try:
        entries = service.sites().list().execute().get('siteEntry', []) or []
    except Exception as exc:
        logger.info('index_coverage: sites().list failed: %s', exc)
        return stored
    owned = {
        e.get('siteUrl') for e in entries
        if e.get('permissionLevel') in ('siteOwner', 'siteFullUser')
    }
    if stored in owned:
        return stored
    host = urlparse(stored if stored.startswith('http') else 'https://' + stored).netloc.lower()
    host = host.split(':')[0]
    if host.startswith('www.'):
        host = host[4:]
    for candidate in (f'sc-domain:{host}', f'https://{host}/', f'http://{host}/'):
        if candidate in owned:
            return candidate
    return stored


def _gsc_inspect_urls(site, urls: list[str], cap: int = 25) -> dict:
    """Authoritative per-URL index status via GSC URL Inspection. Returns
    {norm_url: {verdict, coverage_state, indexed, robots, last_crawl}}. Best
    effort per URL; skips silently when GSC is not connected."""
    from .proof_loop import _build_gsc_service
    service = _build_gsc_service(site)
    if service is None:
        return {}
    site_url = _resolve_gsc_property(service, site)
    out: dict = {}
    for url in urls[:cap]:
        try:
            resp = service.urlInspection().index().inspect(body={
                'inspectionUrl': url,
                'siteUrl': site_url,
            }).execute()
        except Exception as exc:
            logger.info('index_coverage: URL inspect failed %s: %s', url, exc)
            continue
        idx = (resp.get('inspectionResult') or {}).get('indexStatusResult') or {}
        verdict = idx.get('verdict') or ''
        out[_norm_url(url)] = {
            'verdict': verdict,
            'coverage_state': idx.get('coverageState') or '',
            'indexed': verdict == 'PASS',
            'robots': idx.get('robotsTxtState') or '',
            'last_crawl': idx.get('lastCrawlTime') or '',
        }
    return out


def index_coverage(site, max_inspect: int = 25) -> dict:
    """Audit which of the site's expected pages Google has indexed."""
    base, domain = _public_base(site)
    if not domain:
        return {
            'error': "Aucun domaine configure pour ce site.",
            'domain': '', 'expected': [], 'indexed_count': 0,
        }

    # 1) Expected pages: sitemap first, else Gridar-known pages.
    expected_urls = _fetch_sitemap_urls(base)
    sitemap_found = bool(expected_urls)
    if not expected_urls:
        expected_urls = _gridar_known_urls(site, base)
    expected_norm = []
    seen = set()
    for u in expected_urls:
        n = _norm_url(u)
        if n not in seen:
            seen.add(n)
            expected_norm.append((u, n))

    # 2) What Google surfaces (approximate, works everywhere).
    serper_indexed = _serper_site_urls(domain)

    # 3) Authoritative per-URL status (only the expected set, capped).
    gsc = _gsc_inspect_urls(site, [u for u, _ in expected_norm], cap=max_inspect)
    gsc_used = bool(gsc)

    # 4) Cross-reference each expected page.
    rows = []
    indexed_count = 0
    for original, n in expected_norm:
        g = gsc.get(n)
        if g is not None:
            is_indexed = g['indexed']
            reason = g['coverage_state'] or ('Indexee' if is_indexed else 'Non indexee')
            source = 'gsc'
        else:
            is_indexed = n in serper_indexed
            reason = 'Vue dans Google (site:)' if is_indexed else 'Absente de site: (probablement non indexee)'
            source = 'serper'
        if is_indexed:
            indexed_count += 1
        rows.append({
            'url': original,
            'indexed': is_indexed,
            'reason': reason,
            'source': source,
        })

    not_indexed = [r for r in rows if not r['indexed']]

    # Pages Google shows that aren't in the expected set (orphans / untracked).
    expected_set = {n for _, n in expected_norm}
    orphans = sorted(u for u in serper_indexed if u not in expected_set)

    total = len(expected_norm)
    return {
        'domain': domain,
        'sitemap_found': sitemap_found,
        'method': 'gsc+serper' if gsc_used else 'serper',
        'gsc_used': gsc_used,
        'total_expected': total,
        'indexed_count': indexed_count,
        'not_indexed_count': len(not_indexed),
        'coverage_pct': round(100 * indexed_count / total) if total else None,
        'google_knows_count': len(serper_indexed),
        'inspected': min(len(gsc), max_inspect) if gsc_used else 0,
        'pages': rows,
        'not_indexed': not_indexed,
        'orphans': orphans[:50],
        'note': (
            "Statut GSC autoritatif (+ raison) sur les pages inspectees ; "
            "le reste est approxime via site:. Connecte GSC pour le statut exact."
            if not gsc_used else
            "Statut autoritatif via GSC URL Inspection sur les pages inspectees ; "
            "site: complete pour le reste."
        ),
    }


def _gridar_known_urls(site, base: str) -> list[str]:
    """Fallback expected set when there is no sitemap: the public URLs of the
    articles/landings Gridar knows about for this site."""
    from .models import HostedPost, HostedLanding
    if not base:
        return []
    urls = []
    for slug in (HostedPost.objects
                 .filter(site=site, status='published')
                 .values_list('slug', flat=True)[:400]):
        urls.append(f'{base}/blog/{slug}')
    for slug in (HostedLanding.objects
                 .filter(site=site, status='published')
                 .values_list('slug', flat=True)[:200]):
        urls.append(f'{base}/{slug}')
    return urls

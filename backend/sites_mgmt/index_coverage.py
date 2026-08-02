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


def _gsc_inspect_urls(site, urls: list[str], cap: int = 25) -> tuple[dict, str | None, int, int]:
    """Authoritative per-URL index status via GSC URL Inspection.

    Returns (results, error, attempts, failures): results is {norm_url:
    {verdict, coverage_state, indexed, robots, last_crawl}}; error is a short
    human reason when the authoritative status is entirely MISSING, else None.
    attempts/failures let the caller surface PARTIAL degradation too. The
    caller must surface these: a silent fallback to `site:` once made a
    healthy site (82% indexed per GSC) look 13% indexed, and the report
    presented it as fact (vecu le 2026-07-29)."""
    from .proof_loop import _build_gsc_service, resolve_gsc_property
    # Gate sur le JETON seul. Exiger aussi gsc_property_url sortait AVANT que
    # resolve_gsc_property ait pu decouvrir et persister la propriete : un site
    # connecte (jeton present, propriete vide a cause du bug du callback OAuth)
    # restait declare "non connectee" et l'auto-guerison ne tournait jamais.
    # Constate le 2026-07-29 sur qrstudio.agency, apres le fix du callback :
    # cette 2e porte, oubliee, annulait la premiere.
    if not getattr(site, 'gsc_refresh_token', ''):
        return {}, 'GSC non connectee pour ce site (aucun jeton)', 0, 0
    service = _build_gsc_service(site)
    if service is None:
        return {}, 'Client OAuth GSC indisponible cote serveur', 0, 0
    site_url = resolve_gsc_property(service, site)  # owned property for siteUrl
    out: dict = {}
    attempts = 0
    failures = 0
    first_err = ''
    for url in urls[:cap]:
        attempts += 1
        try:
            resp = service.urlInspection().index().inspect(body={
                'inspectionUrl': url,
                'siteUrl': site_url,
            }).execute()
        except Exception as exc:
            failures += 1
            if not first_err:
                first_err = str(exc)[:200]
            logger.warning('index_coverage: URL inspect failed %s: %s', url, exc)
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
    if not out and attempts:
        return {}, (
            'Inspection GSC en echec sur %d URL(s) (propriete "%s") : %s'
            % (attempts, site_url, first_err or 'erreur inconnue')
        ), attempts, failures
    return out, None, attempts, failures


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

    # 3) Authoritative per-URL status (capped). Spend the inspection budget on
    # the DOUBTFUL pages first: a page `site:` already surfaces is indexed with
    # high confidence, inspecting it wastes the quota; the pages site: does NOT
    # show are exactly the ones whose real status (and reason) we need.
    doubtful = [u for u, n in expected_norm if n not in serper_indexed]
    confirmed = [u for u, n in expected_norm if n in serper_indexed]
    gsc, gsc_error, gsc_attempts, gsc_failures = _gsc_inspect_urls(
        site, doubtful + confirmed, cap=max_inspect)
    gsc_used = bool(gsc)
    # "Connecte" = le site a un JETON. La propriete peut etre vide (bug du
    # callback OAuth, corrige) : elle se decouvre a l'appel, ce n'est pas un
    # critere de connexion.
    gsc_connected = bool(getattr(site, 'gsc_refresh_token', ''))
    # Un echec PARTIEL est degrade aussi, jamais silencieux : les pages dont
    # l'inspection a echoue retombent sur site: (sous-comptage) alors que le
    # rapport porterait l'etiquette autoritative (le bug d'origine en miniature).
    if gsc_used and gsc_failures:
        gsc_error = (
            'Inspection GSC partielle : %d echec(s) sur %d tentatives ; '
            'les pages en echec retombent sur site:.' % (gsc_failures, gsc_attempts)
        )

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
    if gsc_used and not gsc_failures:
        confidence = 'autoritatif'
        note = (
            "Statut autoritatif via GSC URL Inspection sur les pages inspectees ; "
            "site: complete pour le reste."
        )
    elif gsc_used:
        confidence = 'partiel'
        note = (
            "Statut autoritatif sur les pages inspectees, MAIS %d inspection(s) "
            "en echec : ces pages-la retombent sur site: (sous-comptage possible)."
            % gsc_failures
        )
    elif gsc_connected and gsc_error:
        confidence = 'approximatif'
        # GSC is connected but the authoritative check FAILED: say it loudly.
        # These numbers rest on `site:` alone, which under-counts massively
        # (site: showed 17 pages on a site GSC knew 141 indexed for).
        note = (
            "ATTENTION : GSC est connectee mais l'inspection a echoue (%s). "
            "Ces chiffres reposent sur site: seulement et SOUS-ESTIMENT fortement "
            "l'indexation reelle : n'en tire AUCUN verdict. Relance l'audit."
            % gsc_error
        )
    elif gsc_connected:
        # Connected, nothing failed: there was simply nothing to inspect
        # (empty expected set, or max_inspect=0). No false alarm.
        confidence = 'approximatif'
        note = (
            "GSC connectee ; aucune URL n'a ete inspectee (rien a inspecter ou "
            "max_inspect=0). Statut estime via site: (approximatif)."
        )
    else:
        confidence = 'approximatif'
        note = (
            "APPROXIMATIF : statut estime via site: uniquement, qui sous-compte. "
            "Connecte GSC pour le statut exact (+ la raison de non-indexation)."
        )
    return {
        'domain': domain,
        'sitemap_found': sitemap_found,
        'method': 'gsc+serper' if gsc_used else 'serper',
        'gsc_used': gsc_used,
        'gsc_connected': gsc_connected,
        'gsc_error': gsc_error,
        'inspection_failures': gsc_failures,
        'confidence': confidence,
        'total_expected': total,
        'indexed_count': indexed_count,
        'not_indexed_count': len(not_indexed),
        'coverage_pct': round(100 * indexed_count / total) if total else None,
        'google_knows_count': len(serper_indexed),
        'inspected': min(len(gsc), max_inspect) if gsc_used else 0,
        'pages': rows,
        'not_indexed': not_indexed,
        'orphans': orphans[:50],
        'note': note,
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

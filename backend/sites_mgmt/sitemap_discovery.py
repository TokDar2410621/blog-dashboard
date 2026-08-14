"""Sitemap discovery: find a site's sitemaps, then read what they declare.

Porte depuis claude-seo v2.2.4 `scripts/sitemap_discovery.py`.
Copyright (c) 2025 Daniel Agrici (AgriciDaniel). MIT.
https://github.com/AgriciDaniel/claude-seo

Adaptations for Gridar. lxml is replaced by `xml.etree.ElementTree` so nothing
has to compile on Railway, and every fetch goes through `url_safety.safe_get`,
which re-validates each redirect hop; the domain comes from the user, so it is
the SSRF vector. Parsing is split out into a pure `parse_sitemap()` that takes
text and returns data, so the audit path can reuse it with no socket and the
tests can run offline. Two things were added for the Quebec market: cross-host
comparison runs on the registrable domain with provincial `.qc.ca` style
suffixes known, since a naive two-label rule reads `montreal.qc.ca` and
`laval.qc.ca` as the same owner and would hide a real hijack, and `xhtml:link`
alternates are collected so a bilingual fr-CA / en-CA sitemap reports its
languages instead of dropping them.
"""
from __future__ import annotations

import re
import time
import zlib
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse, urlunparse
from xml.etree import ElementTree as ET

import requests

from .url_safety import URLSafetyError, safe_get, validate_url

__all__ = [
    'MAX_URLS',
    'MAX_BYTES',
    'MAX_ROBOTS_BYTES',
    'MAX_DECLARED',
    'COMMON_PATHS',
    'SITEMAP_NAMESPACE',
    'discover_sitemaps',
    'fetch_sitemap',
    'parse_sitemap',
]


# Protocol ceilings from sitemaps.org. Google refuses anything above them, so a
# file that crosses one is a finding to report, not a parse to attempt.
MAX_URLS = 50_000
MAX_BYTES = 50 * 1024 * 1024

MAX_ROBOTS_BYTES = 1024 * 1024
MAX_DECLARED = 16
FETCH_TIMEOUT = 15

# Discovery runs inside a web request. Sixteen declared sitemaps plus five
# probes at the per-request timeout would blow past any gateway, so the walk
# stops on a wall-clock budget and says so instead of hanging the caller.
TIME_BUDGET = 25.0
USER_AGENT = 'GridarSitemapDiscovery/1.0 (+https://gridar.app)'
SITEMAP_NAMESPACE = 'http://www.sitemaps.org/schemas/sitemap/0.9'

# Ordered by how often they pay off on the stacks Gridar already adapts to:
# WordPress core and Yoast/RankMath first, then the .gz form that robots.txt
# files of older installs still point at.
COMMON_PATHS = (
    '/sitemap.xml',
    '/sitemap_index.xml',
    '/sitemap-index.xml',
    '/wp-sitemap.xml',
    '/sitemap.xml.gz',
)

# Trailing text after the URL is tolerated: hand-written robots.txt files often
# carry an inline comment, and upstream's anchored form dropped those lines.
_SITEMAP_LINE = re.compile(r'^\s*sitemap\s*:\s*(\S+)', re.IGNORECASE)

# Only the encoding attribute is targeted; the rest of the declaration stays so
# a caller reading the raw text still sees what the server sent.
_XML_ENCODING_DECL = re.compile(
    rb'(<\?xml[^>]*?)\s+encoding\s*=\s*(?:"[^"]*"|\'[^\']*\')', re.IGNORECASE,
)

# Suffixes where the registrable domain is three labels deep. The Canadian
# provincial ones are the reason this list exists: Quebec municipalities,
# school boards and clinics sit under *.qc.ca, and treating that as one
# registrable domain would mark a hijacked sitemap as same-site.
_MULTI_LABEL_SUFFIXES = frozenset({
    'ab.ca', 'bc.ca', 'gc.ca', 'mb.ca', 'nb.ca', 'nf.ca', 'nl.ca', 'ns.ca',
    'nt.ca', 'nu.ca', 'on.ca', 'pe.ca', 'qc.ca', 'sk.ca', 'yk.ca',
    'ac.uk', 'co.uk', 'gov.uk', 'org.uk',
    'com.au', 'net.au', 'org.au',
    'co.nz', 'co.jp', 'co.za', 'com.br', 'com.mx',
})


# --------------------------------------------------------------------------
# URL helpers
# --------------------------------------------------------------------------

def _display_url(url: str) -> tuple[str, bool]:
    """Return a URL safe to show back, with userinfo, query and fragment cut.

    A sitemap URL declared in robots.txt can carry a token in its query string.
    The report is rendered in the dashboard, so it must not echo one.
    """
    parsed = urlparse(url)
    host = parsed.hostname or ''
    try:
        port = parsed.port
    except ValueError:
        port = None
        redacted = True
    else:
        redacted = False
    if port:
        host = f'{host}:{port}'
    clean = urlunparse((parsed.scheme, host, parsed.path or '/', '', '', ''))
    redacted = redacted or bool(
        parsed.username or parsed.password or parsed.query or parsed.fragment
    )
    return clean, redacted


def _origin(url: str) -> str:
    """Scheme and authority only. Raises ValueError on anything unsafe."""
    url = (url or '').strip()
    if '://' not in url:
        url = f'https://{url}'
    if not validate_url(url):
        raise ValueError('Le domaine doit etre une URL publique en http ou https.')
    parsed = urlparse(url)
    netloc = parsed.hostname or ''
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError('Le port de l URL est invalide.') from exc
    if port:
        netloc = f'{netloc}:{port}'
    return urlunparse((parsed.scheme, netloc, '', '', '', ''))


def _registrable_domain(host: str) -> str:
    """Collapse a hostname to the part that identifies its owner."""
    host = (host or '').strip().lower().rstrip('.')
    if not host:
        return ''
    if host.replace('.', '').isdigit() or ':' in host:
        return host  # IP literal, no label structure to collapse
    labels = host.split('.')
    if len(labels) <= 2:
        return host
    if '.'.join(labels[-2:]) in _MULTI_LABEL_SUFFIXES:
        return '.'.join(labels[-3:])
    return '.'.join(labels[-2:])


def _host_of(url: str) -> str:
    try:
        return (urlparse(url).hostname or '').lower()
    except ValueError:
        return ''


def _is_cross_host(url: str, site_host: str) -> bool:
    """True when a sitemap entry belongs to a different owner than the site.

    Subdomains stay same-site because CDN and shop subdomains are legitimate.
    A wholly different registrable domain inside a sitemap is the classic trace
    of an injected sitemap: the site keeps serving, and its sitemap quietly
    feeds spam pages to Google under the victim's authority.
    """
    if not site_host:
        return False
    entry_host = _host_of(url)
    if not entry_host:
        return False
    return _registrable_domain(entry_host) != _registrable_domain(site_host)


def _valid_sitemap_url_syntax(value: str) -> bool:
    """Syntax check for a sitemap entry, with no DNS and no connection."""
    if not value or any(char.isspace() for char in value) or '\\' in value:
        return False
    try:
        parsed = urlparse(value)
        _ = parsed.port
    except ValueError:
        return False
    return (
        parsed.scheme.lower() in {'http', 'https'}
        and bool(parsed.hostname)
        and parsed.username is None
        and parsed.password is None
    )


# --------------------------------------------------------------------------
# Bytes and XML helpers
# --------------------------------------------------------------------------

def _to_bytes(payload: str | bytes) -> bytes:
    """Normalize input to bytes without letting a stale encoding declaration win.

    ElementTree refuses a `str` that declares an encoding, and re-encoding such
    a string to UTF-8 while leaving `encoding="iso-8859-1"` in place turns every
    French accent into mojibake. Dropping the attribute is what keeps a Quebec
    sitemap readable once it has already been decoded upstream.
    """
    if isinstance(payload, bytes):
        return payload
    raw = (payload or '').encode('utf-8')
    return _XML_ENCODING_DECL.sub(rb'\1', raw, count=1)


def _maybe_gunzip(raw: bytes, max_bytes: int) -> tuple[bytes, str]:
    """Inflate a gzipped sitemap under a hard output ceiling.

    `decompress(data, max_length)` never materializes more than the ceiling, so
    a zip bomb is refused on size instead of being expanded first.
    """
    if not raw.startswith(b'\x1f\x8b'):
        return raw, ''
    try:
        out = zlib.decompressobj(16 + zlib.MAX_WBITS).decompress(raw, max_bytes + 1)
    except zlib.error:
        return b'', 'gzip_invalid'
    if len(out) > max_bytes:
        return b'', 'too_large'
    return out, ''


def _local(tag) -> str:
    if not isinstance(tag, str):
        return ''
    return tag.rsplit('}', 1)[-1].lower()


def _namespace(tag) -> str:
    if isinstance(tag, str) and tag.startswith('{'):
        return tag[1:].split('}', 1)[0]
    return ''


def _text(element) -> str:
    return (element.text or '').strip()


def _parse_lastmod(value: str):
    """W3C datetime to an aware datetime, or None when the sitemap is wrong.

    Naive values are read as UTC so a file mixing bare dates and full stamps
    still yields a comparable set.
    """
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.strip())
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _warn(warnings: list, code: str, message: str) -> None:
    if not any(item['code'] == code for item in warnings):
        warnings.append({'code': code, 'message': message})


# --------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------

def _blank_parse_result() -> dict:
    return {
        'kind': None,
        'namespace': '',
        'urls': [],
        'sitemaps': [],
        'url_count': 0,
        'sitemap_count': 0,
        'languages': [],
        'cross_host': [],
        'latest_lastmod': None,
        'truncated': False,
        'byte_size': 0,
        'warnings': [],
        'error': None,
        'error_code': None,
    }


def _fail(result: dict, code: str, message: str) -> dict:
    result['error_code'] = code
    result['error'] = message
    return result


def _finalize(result: dict) -> dict:
    """Counts, cross-host roll-up and freshness, shared by every input shape."""
    if result['error']:
        return result

    result['url_count'] = len(result['urls'])
    result['sitemap_count'] = len(result['sitemaps'])
    entries = list(result['urls']) + list(result['sitemaps'])

    foreign = sorted({
        _registrable_domain(_host_of(item['loc']))
        for item in entries if item.get('cross_host')
    } - {''})
    result['cross_host'] = foreign
    if foreign:
        _warn(
            result['warnings'], 'cross_host_entries',
            'Le sitemap pointe vers des domaines tiers ('
            + ', '.join(foreign[:5])
            + '). Un sitemap injecte qui reference des pages hors domaine est '
            'la signature d un piratage: le site sert du spam a Google sous ton '
            'autorite. A verifier avant toute soumission.',
        )

    if result['truncated']:
        _warn(
            result['warnings'], 'url_cap',
            'Le sitemap depasse la limite d entrees du protocole. Seules les '
            'premieres sont lues, Google ignore le reste.',
        )

    stamps = [
        moment for moment in (
            _parse_lastmod(item.get('lastmod') or '') for item in entries
        ) if moment is not None
    ]
    if stamps:
        result['latest_lastmod'] = max(stamps).isoformat()
    return result


def _parse_text_sitemap(raw: bytes, result: dict, site_host: str, max_urls: int) -> dict:
    lines = [
        line.strip()
        for line in raw.decode('utf-8', errors='replace').splitlines()
        if line.strip() and not line.lstrip().startswith('#')
    ]
    if not lines:
        return _fail(result, 'empty', 'Le sitemap est vide.')
    if not all(_valid_sitemap_url_syntax(line) for line in lines):
        return _fail(
            result, 'invalid_text',
            "Ce fichier n'est ni du XML de sitemap, ni une liste d'URL valides.",
        )
    result['kind'] = 'text'
    if len(lines) > max_urls:
        result['truncated'] = True
        _warn(
            result['warnings'], 'url_cap',
            f'Le sitemap declare plus de {max_urls} URL, la limite du protocole. '
            f'Google ignore le surplus, seules les {max_urls} premieres sont lues.',
        )
        lines = lines[:max_urls]
    result['urls'] = [
        {'loc': line, 'lastmod': None, 'cross_host': _is_cross_host(line, site_host)}
        for line in lines
    ]
    return result


def _entry_from_url_element(element, site_host: str) -> tuple[dict, list, bool]:
    """Read one <url>. Returns (entry, hreflang codes, lastmod was unreadable).

    Only direct children are read. `<image:loc>` and `<video:content_loc>` sit
    one level deeper, and a parser that walks the whole subtree counts them as
    pages, which inflates the URL total and pollutes any coverage comparison.
    """
    entry = {
        'loc': '',
        'lastmod': None,
        'changefreq': None,
        'priority': None,
        'images': 0,
        'alternates': [],
        'cross_host': False,
    }
    languages: list[str] = []
    bad_lastmod = False

    for child in element:
        tag = _local(child.tag)
        if tag == 'loc' and not entry['loc']:
            entry['loc'] = _text(child)
        elif tag == 'lastmod':
            value = _text(child)
            if value:
                entry['lastmod'] = value
                bad_lastmod = _parse_lastmod(value) is None
        elif tag == 'changefreq':
            entry['changefreq'] = _text(child) or None
        elif tag == 'priority':
            entry['priority'] = _text(child) or None
        elif tag == 'image':
            entry['images'] += 1
        elif tag == 'link':
            hreflang = (child.attrib.get('hreflang') or '').strip()
            href = (child.attrib.get('href') or '').strip()
            if hreflang and href:
                entry['alternates'].append({'hreflang': hreflang, 'href': href})
                languages.append(hreflang.lower())

    entry['cross_host'] = _is_cross_host(entry['loc'], site_host)
    return entry, languages, bad_lastmod


def _parse_feed(root, result: dict, site_host: str, max_urls: int) -> None:
    """Read an RSS 2.0 or Atom feed, which Google accepts as a sitemap."""
    kind = result['kind']
    items = [el for el in root.iter() if _local(el.tag) in ('item', 'entry')]
    for item in items[:max_urls]:
        loc, lastmod = '', None
        for child in item:
            tag = _local(child.tag)
            if tag == 'link' and not loc:
                loc = (child.attrib.get('href') or '').strip() or _text(child)
            elif tag in ('pubdate', 'updated', 'lastbuilddate') and lastmod is None:
                lastmod = _text(child) or None
        if loc:
            result['urls'].append({
                'loc': loc,
                'lastmod': lastmod,
                'cross_host': _is_cross_host(loc, site_host),
            })
    if len(items) > max_urls:
        result['truncated'] = True
    if not result['urls']:
        _warn(
            result['warnings'], 'empty_feed',
            f'Le flux {kind} ne contient aucun lien exploitable comme sitemap.',
        )


def parse_sitemap(
    xml_text: str | bytes,
    *,
    site_host: str = '',
    max_urls: int = MAX_URLS,
    max_bytes: int = MAX_BYTES,
) -> dict:
    """Read one sitemap document. Pure function, no network, no ORM.

    Handles `<urlset>`, `<sitemapindex>`, RSS, Atom, the plain text form, and a
    gzipped payload when bytes are passed. `site_host` enables the cross-host
    check; leave it empty to skip it. Never raises on malformed input: the
    failure is returned in `error` / `error_code` so an audit can report it.
    """
    result = _blank_parse_result()
    raw = _to_bytes(xml_text)
    if len(raw) > max_bytes:
        result['byte_size'] = len(raw)
        return _fail(
            result, 'too_large',
            f'Le sitemap depasse la limite de {max_bytes // (1024 * 1024)} Mo du '
            'protocole. Google refuse de le lire, il faut le decouper en '
            'plusieurs fichiers relies par un index.',
        )

    raw, gz_error = _maybe_gunzip(raw, max_bytes)
    if gz_error == 'gzip_invalid':
        return _fail(result, 'gzip_invalid', 'Le fichier .gz est illisible.')
    if gz_error == 'too_large':
        return _fail(
            result, 'too_large',
            f'Une fois decompresse, le sitemap depasse la limite de '
            f'{max_bytes // (1024 * 1024)} Mo du protocole.',
        )

    result['byte_size'] = len(raw)
    if not raw.strip():
        return _fail(result, 'empty', 'Le sitemap est vide.')

    # A DOCTYPE is never legal in a sitemap and is how entity expansion attacks
    # arrive, so the document is refused before the parser touches it.
    if b'<!DOCTYPE' in raw[:4096].upper() or b'<!ENTITY' in raw[:4096].upper():
        return _fail(
            result, 'doctype_refused',
            "Le fichier declare un DOCTYPE ou une entite, interdit dans un sitemap.",
        )

    if not raw.lstrip().startswith(b'<'):
        return _finalize(_parse_text_sitemap(raw, result, site_host, max_urls))

    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        return _fail(result, 'invalid_xml', f'XML invalide: {exc}')

    result['namespace'] = _namespace(root.tag)
    kind = _local(root.tag)
    if kind not in ('urlset', 'sitemapindex', 'rss', 'feed'):
        return _fail(
            result, 'unsupported_root',
            f'Racine XML non supportee: <{kind or "?"}>.',
        )
    result['kind'] = 'atom' if kind == 'feed' else kind

    if kind in ('rss', 'feed'):
        _parse_feed(root, result, site_host, max_urls)
    elif kind == 'urlset':
        if result['namespace'] and result['namespace'] != SITEMAP_NAMESPACE:
            _warn(
                result['warnings'], 'unexpected_namespace',
                'Le sitemap n utilise pas le namespace officiel '
                f'{SITEMAP_NAMESPACE}. Search Console le rejette souvent avec '
                '"impossible de lire le sitemap".',
            )
        languages: set[str] = set()
        bad_lastmod = 0
        missing_loc = 0
        seen = 0
        for element in root:
            if _local(element.tag) != 'url':
                continue
            seen += 1
            if seen > max_urls:
                result['truncated'] = True
                break
            entry, entry_languages, entry_bad_lastmod = _entry_from_url_element(
                element, site_host,
            )
            if not entry['loc']:
                missing_loc += 1
                continue
            languages.update(entry_languages)
            bad_lastmod += 1 if entry_bad_lastmod else 0
            result['urls'].append(entry)
        result['languages'] = sorted(languages)
        if missing_loc:
            _warn(
                result['warnings'], 'entries_without_loc',
                f'{missing_loc} entree(s) <url> sans balise <loc>, ignorees.',
            )
        if bad_lastmod:
            _warn(
                result['warnings'], 'invalid_lastmod',
                f'{bad_lastmod} date <lastmod> illisible(s). Google ignore une '
                'date hors format W3C et perd le signal de fraicheur.',
            )
        if not result['urls'] and not result['truncated']:
            _warn(result['warnings'], 'empty_sitemap', 'Le sitemap ne declare aucune URL.')
    else:
        seen = 0
        for element in root:
            if _local(element.tag) != 'sitemap':
                continue
            seen += 1
            if seen > max_urls:
                result['truncated'] = True
                break
            loc, lastmod = '', None
            for child in element:
                tag = _local(child.tag)
                if tag == 'loc' and not loc:
                    loc = _text(child)
                elif tag == 'lastmod':
                    lastmod = _text(child) or None
            if loc:
                result['sitemaps'].append({
                    'loc': loc,
                    'lastmod': lastmod,
                    'cross_host': _is_cross_host(loc, site_host),
                })
        if not result['sitemaps'] and not result['truncated']:
            _warn(result['warnings'], 'empty_index', "L index ne pointe vers aucun sitemap.")

    if result['truncated']:
        _warn(
            result['warnings'], 'url_cap',
            f'Le sitemap depasse la limite de {max_urls} entrees du protocole. '
            f'Seules les {max_urls} premieres sont lues, Google ignore le reste.',
        )
    return _finalize(result)


# --------------------------------------------------------------------------
# Fetching
# --------------------------------------------------------------------------

def _bounded_fetch(url: str, max_bytes: int) -> dict:
    """GET through the SSRF guard, reading at most max_bytes of body.

    The body is streamed so an oversized or endless response is cut at the
    ceiling instead of being buffered whole into a web worker.
    """
    out = {
        'status_code': None,
        'content': b'',
        'content_type': '',
        'final_url': url,
        'too_large': False,
        'error': None,
        'error_code': None,
    }
    headers = {
        'User-Agent': USER_AGENT,
        'Accept': 'application/xml,text/xml,text/plain,*/*',
    }
    try:
        response = safe_get(url, timeout=FETCH_TIMEOUT, headers=headers, stream=True)
    except URLSafetyError:
        out['error_code'] = 'url_refused'
        out['error'] = "URL refusee par le controle de securite (cible interne ou redirection suspecte)."
        return out
    except requests.exceptions.Timeout:
        out['error_code'] = 'timeout'
        out['error'] = 'Delai depasse.'
        return out
    except requests.exceptions.RequestException:
        out['error_code'] = 'unreachable'
        out['error'] = 'Requete impossible.'
        return out

    try:
        out['status_code'] = response.status_code
        out['content_type'] = response.headers.get('Content-Type', '') or ''
        out['final_url'] = getattr(response, 'url', url) or url
        chunks: list[bytes] = []
        size = 0
        for chunk in response.iter_content(chunk_size=65536):
            if not chunk:
                continue
            size += len(chunk)
            if size > max_bytes:
                out['too_large'] = True
                break
            chunks.append(chunk)
        out['content'] = b''.join(chunks)
    except requests.exceptions.RequestException:
        out['error_code'] = 'truncated_read'
        out['error'] = 'Lecture interrompue.'
    finally:
        response.close()
    return out


def _robots_sitemaps(content: bytes, origin: str) -> list[str]:
    """Sitemap directives from robots.txt, in order, deduplicated.

    A relative target is resolved against the origin. The protocol wants an
    absolute URL, but hand-written robots.txt files on small sites write
    `Sitemap: /sitemap.xml`, and dropping those loses a real sitemap.
    """
    text = content.decode('utf-8', errors='replace')
    found: list[str] = []
    for line in text.splitlines():
        match = _SITEMAP_LINE.match(line)
        if not match:
            continue
        value = match.group(1).strip().rstrip(',;')
        if not value:
            continue
        if value.startswith('/'):
            value = urljoin(origin + '/', value)
        if _valid_sitemap_url_syntax(value) and value not in found:
            found.append(value)
    return found


def fetch_sitemap(url: str, *, site_host: str = '', max_urls: int = MAX_URLS) -> dict:
    """Fetch one sitemap through the SSRF guard and parse it.

    This is the way to resolve the children of a `sitemapindex`: `discover_sitemaps`
    reports the index and its children but does not walk them, so the caller
    decides how deep to go and pays for it explicitly.
    """
    fetched = _bounded_fetch(url, MAX_BYTES)
    display, redacted = _display_url(fetched['final_url'] or url)
    result = _blank_parse_result()
    result['url'] = display
    result['query_redacted'] = redacted
    result['status_code'] = fetched['status_code']

    if fetched['error']:
        result['error_code'] = fetched['error_code']
        result['error'] = fetched['error']
        return result
    if fetched['too_large']:
        result['error_code'] = 'too_large'
        result['error'] = (
            f'Le sitemap depasse la limite de {MAX_BYTES // (1024 * 1024)} Mo du protocole.'
        )
        return result
    status = fetched['status_code']
    if status is None or not 200 <= status < 300:
        result['error_code'] = 'http_error'
        result['error'] = f'HTTP {status}' if status is not None else 'Aucune reponse.'
        return result

    parsed = parse_sitemap(
        fetched['content'], site_host=site_host or _host_of(url), max_urls=max_urls,
    )
    parsed['url'] = display
    parsed['query_redacted'] = redacted
    parsed['status_code'] = status
    return parsed


def discover_sitemaps(
    domain: str, *, max_urls: int = MAX_URLS, time_budget: float = TIME_BUDGET,
) -> dict:
    """Find the sitemaps of a caller-supplied domain.

    Reads robots.txt for `Sitemap:` directives, then probes the usual paths,
    fetches each candidate through the SSRF guard and parses it. Returns counts
    and a sample per sitemap rather than every URL, so the response stays
    bounded on a site with 50 000 pages; use `fetch_sitemap` for a full read.
    """
    started = time.monotonic()
    result = {
        'target': None,
        'robots_url': None,
        'robots_status': None,
        'declared': [],
        'checked': [],
        'found': [],
        'total_urls': 0,
        'warnings': [],
        'error': None,
    }
    try:
        origin = _origin(domain)
    except ValueError as exc:
        result['error'] = str(exc)
        return result

    result['target'] = origin
    site_host = _host_of(origin)
    robots_url = f'{origin}/robots.txt'
    result['robots_url'] = robots_url

    robots = _bounded_fetch(robots_url, MAX_ROBOTS_BYTES)
    result['robots_status'] = robots['status_code']
    declared_raw: list[str] = []
    if robots['error']:
        _warn(result['warnings'], 'robots_unreachable',
              'robots.txt est inaccessible, la decouverte se rabat sur les chemins usuels.')
    elif robots['too_large']:
        _warn(result['warnings'], 'robots_too_large',
              'robots.txt depasse 1 Mo, il n a pas ete lu.')
    elif robots['status_code'] == 200:
        declared_raw = _robots_sitemaps(robots['content'], origin)
        if not declared_raw:
            _warn(result['warnings'], 'robots_no_sitemap',
                  'robots.txt ne declare aucun sitemap. Ajoute une ligne '
                  '"Sitemap: <url>" pour que les moteurs le trouvent seuls.')
    elif robots['status_code'] is not None:
        _warn(result['warnings'], 'robots_http_error',
              f'robots.txt repond HTTP {robots["status_code"]}.')

    if len(declared_raw) > MAX_DECLARED:
        _warn(result['warnings'], 'too_many_declared',
              f'robots.txt declare plus de {MAX_DECLARED} sitemaps, le surplus '
              'n a pas ete recupere.')
        declared_raw = declared_raw[:MAX_DECLARED]

    for item in declared_raw:
        display, redacted = _display_url(item)
        result['declared'].append({
            'url': display,
            'query_redacted': redacted,
            'cross_host': _is_cross_host(item, site_host),
        })
    if any(entry['cross_host'] for entry in result['declared']):
        _warn(result['warnings'], 'cross_host_declared',
              'robots.txt declare un sitemap heberge sur un autre domaine. Le '
              'protocole l autorise, mais c est aussi comme ca qu un site '
              'pirate se met a indexer des pages qui ne sont pas les siennes. '
              'A confirmer avec ton hebergeur.')

    candidates: list[str] = list(declared_raw)
    candidates.extend(f'{origin}{path}' for path in COMMON_PATHS)
    seen: set[str] = set()
    ordered: list[str] = []
    for candidate in candidates:
        if candidate not in seen:
            seen.add(candidate)
            ordered.append(candidate)

    cross_host_found: set[str] = set()
    for candidate in ordered:
        if time.monotonic() - started > time_budget:
            _warn(result['warnings'], 'time_budget',
                  'La decouverte a ete arretee sur son budget de temps, '
                  'certains emplacements n ont pas ete testes.')
            break
        display, redacted = _display_url(candidate)
        entry = {
            'url': display,
            'query_redacted': redacted,
            'source': 'robots.txt' if candidate in declared_raw else 'common_path',
            'status_code': None,
            'kind': None,
            'valid': False,
            'url_count': 0,
            'sitemap_count': 0,
            'sample_urls': [],
            'child_sitemaps': [],
            'languages': [],
            'latest_lastmod': None,
            'truncated': False,
            'cross_host': _is_cross_host(candidate, site_host),
            'cross_host_entries': [],
            'warnings': [],
            'error': None,
            'error_code': None,
        }

        parsed = fetch_sitemap(candidate, site_host=site_host, max_urls=max_urls)
        entry['status_code'] = parsed.get('status_code')
        entry['url'] = parsed.get('url') or entry['url']
        entry['query_redacted'] = entry['query_redacted'] or parsed.get('query_redacted', False)
        entry['error'] = parsed.get('error')
        entry['error_code'] = parsed.get('error_code')
        if not parsed.get('error'):
            entry['kind'] = parsed['kind']
            entry['valid'] = parsed['kind'] is not None
            entry['url_count'] = parsed['url_count']
            entry['sitemap_count'] = parsed['sitemap_count']
            entry['sample_urls'] = [item['loc'] for item in parsed['urls'][:10]]
            entry['child_sitemaps'] = [item['loc'] for item in parsed['sitemaps'][:50]]
            entry['languages'] = parsed['languages']
            entry['latest_lastmod'] = parsed['latest_lastmod']
            entry['truncated'] = parsed['truncated']
            entry['cross_host_entries'] = parsed['cross_host']
            entry['warnings'] = parsed['warnings']
            cross_host_found.update(parsed['cross_host'])

        result['checked'].append(entry)
        if entry['valid']:
            result['found'].append(entry)
            result['total_urls'] += entry['url_count']

    if cross_host_found:
        _warn(result['warnings'], 'cross_host_entries',
              'Des sitemaps du site pointent vers des domaines tiers ('
              + ', '.join(sorted(cross_host_found)[:5])
              + '). Signature classique d un piratage: verifie le contenu avant '
              'de soumettre quoi que ce soit a Google.')
    if not result['found'] and not result['error']:
        _warn(result['warnings'], 'no_sitemap',
              'Aucun sitemap valide trouve. Les moteurs decouvrent alors les '
              'pages uniquement par les liens internes.')
    return result

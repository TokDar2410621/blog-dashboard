"""IndexNow submission - notify Bing / Yandex / Seznam / Naver (NOT Google) of
new or updated URLs.

One POST to the shared endpoint propagates to every participating engine. It
works on ANY site (no OAuth): the site hosts a `<key>.txt` file at its root so
the engine can verify ownership. Google does not participate in IndexNow; the
value here is fast Bing indexing, which feeds ChatGPT Search / Copilot /
DuckDuckGo - i.e. AI visibility, not Google SEO. No LLM, no quota.
"""
from __future__ import annotations

import logging
import secrets
from urllib.parse import urlparse, urlunparse

import requests

logger = logging.getLogger(__name__)

INDEXNOW_ENDPOINT = 'https://api.indexnow.org/indexnow'
_STATUS_REASON = {
    200: 'OK - URLs soumises',
    202: 'Accepte - validation de la cle en cours',
    400: 'Requete invalide',
    403: "Cle introuvable ou invalide - heberge le fichier <cle>.txt a la racine",
    422: 'URLs hors du host declare, ou host/cle incoherents',
    429: 'Trop de requetes - reessaie plus tard',
}


def _host(site) -> str:
    raw = (getattr(site, 'public_blog_domain', '') or site.domain or '').strip()
    if not raw:
        return ''
    if not raw.startswith(('http://', 'https://')):
        raw = 'https://' + raw
    return (urlparse(raw).netloc or '').lower()


def _root(host: str) -> str:
    """Host without the www. prefix and without the port."""
    host = (host or '').lower().split(':')[0]
    return host[4:] if host.startswith('www.') else host  # NOT lstrip('www.')


def _same_site(host_a: str, host_b: str) -> bool:
    """True when two hosts are the same site modulo the www. prefix.

    IndexNow itself matches the host exactly, but `site.domain` stores the brand
    domain (gridar.app) while the site often serves its pages canonically on the
    www variant. Treating the two as one site is what lets us submit the URLs a
    sitemap actually contains.
    """
    root = _root(host_a)
    return bool(root) and root == _root(host_b)


def _resolve_key_host(host: str, key: str) -> str:
    """The host that actually SERVES the key file, redirects followed.

    The apex usually 301/308s to www (or the reverse). IndexNow verifies the key
    file at the host it was handed, so announcing a host whose key file is only
    a redirect gets the whole batch rejected. This matters for the auto-ping on
    delivery, which builds its URL from `site.domain` and would otherwise always
    announce the apex. Fails open: any network trouble keeps the given host.
    """
    try:
        resp = requests.get(f'https://{host}/{key}.txt', allow_redirects=True,
                            timeout=8)
        if resp.status_code == 200:
            final = (urlparse(resp.url).netloc or '').lower()
            if final and _same_site(final, host):
                return final
    except Exception as exc:  # noqa: BLE001
        logger.info('IndexNow key host unresolved for %s: %s', host, exc)
    return host


def get_or_create_key(site) -> str:
    """The site's IndexNow key, generated + persisted on first use."""
    key = (getattr(site, 'indexnow_key', '') or '').strip()
    if not key:
        key = secrets.token_hex(16)  # 32 hex chars, within IndexNow's 8-128 range
        type(site).objects.filter(pk=site.pk).update(indexnow_key=key)
        site.indexnow_key = key
    return key


def hosted_public_url(site, slug: str) -> str:
    """Public URL of a Gridar-hosted post (public-blog serves posts at /<slug>,
    matching the site's sitemap)."""
    host = _host(site)
    return f'https://{host}/{slug}' if host and slug else ''


def key_location(site, key: str = '', host: str = '') -> str:
    """Ownership-file URL, `https://<host>/<key>.txt`.

    IndexNow requires the file to be NAMED after the key. A file under any other
    name is rejected with 403 no matter what `keyLocation` announces. Gridar
    serves it for hosted sites (public-blog rewrites /<key>.txt); external sites
    host it themselves. `host` overrides the site domain when the submitted URLs
    live on the www variant.
    """
    host = (host or _host(site)).lower()
    key = key or get_or_create_key(site)
    return f'https://{host}/{key}.txt' if host and key else ''


def key_file_info(site) -> dict:
    """Everything needed to host the ownership key file."""
    key = get_or_create_key(site)
    host = _host(site)
    url = key_location(site, key)
    return {
        'key': key,
        'host': host,
        'key_file_url': url,
        'key_file_content': key,
        'auto_served': bool(getattr(site, 'public_blog_domain', '')),
        'instructions': (
            "Site heberge par Gridar : le fichier cle est servi automatiquement, "
            "rien a faire."
            if getattr(site, 'public_blog_domain', '') else
            f"Heberge un fichier texte contenant UNIQUEMENT la cle a l'URL "
            f"{url or '<https://ton-domaine/<cle>.txt>'} (public, content-type "
            "text/plain). Le nom du fichier DOIT etre la cle elle-meme. Sers-le "
            "sur le host qui repond en 200 sans redirection (si le site "
            "canonique est www, c'est sur www). Une fois en place, la soumission "
            "IndexNow est validee automatiquement."
        ),
    }


def submit_urls(site, urls) -> dict:
    """Submit URLs to IndexNow. Returns {ok, status, reason, submitted, host}.

    URLs must all be on the site's own host: IndexNow rejects a cross-host list,
    and the announced host has to match `keyLocation`. The www variant counts as
    the same site, and the batch host is taken from the URLs themselves rather
    than from `site.domain`, which stores the brand domain and not necessarily
    the host that serves the pages.
    """
    key = get_or_create_key(site)
    site_host = _host(site)
    if not site_host:
        return {'ok': False, 'error': 'Aucun domaine configure pour ce site.',
                'submitted': 0}

    clean: list[str] = []
    seen = set()
    hosts: dict[str, int] = {}
    skipped_host = 0
    for u in urls or []:
        u = (u or '').strip()
        if not u:
            continue
        h = (urlparse(u if u.startswith('http') else 'https://' + u).netloc or '').lower()
        if not _same_site(h, site_host):
            skipped_host += 1
            continue
        if u not in seen:
            seen.add(u)
            clean.append(u)
            hosts[h] = hosts.get(h, 0) + 1

    if not clean:
        return {
            'ok': False,
            'error': f"Aucune URL valide sur le host '{site_host}'.",
            'submitted': 0, 'skipped_wrong_host': skipped_host, 'host': site_host,
        }

    # One host for the whole batch, and it has to be the one serving the key
    # file. Start from the majority host of the URLs, then follow the key file's
    # redirects to land on the variant that answers 200.
    host = max(hosts, key=hosts.get)  # dict order makes ties deterministic
    host = _resolve_key_host(host, key)
    normalized = 0
    if list(hosts) != [host]:
        rebased = []
        for u in clean:
            parsed = urlparse(u if u.startswith('http') else 'https://' + u)
            if (parsed.netloc or '').lower() != host:
                u = urlunparse(parsed._replace(netloc=host))
                normalized += 1
            rebased.append(u)
        clean = rebased

    try:
        resp = requests.post(
            INDEXNOW_ENDPOINT,
            json={
                'host': host,
                'key': key,
                'keyLocation': key_location(site, key, host),
                'urlList': clean[:10000],
            },
            headers={'Content-Type': 'application/json; charset=utf-8'},
            timeout=15,
        )
        code = resp.status_code
    except Exception as exc:
        logger.info('IndexNow submit failed for site %s: %s', site.id, exc)
        return {'ok': False, 'error': str(exc)[:150], 'submitted': 0, 'host': host}

    out = {
        'ok': code in (200, 202),
        'status': code,
        'reason': _STATUS_REASON.get(code, f'HTTP {code}'),
        'submitted': len(clean),
        'skipped_wrong_host': skipped_host,
        'host': host,
        'key_location': key_location(site, key, host),
        'engines': 'Bing, Yandex, Seznam, Naver (pas Google)',
    }
    if normalized:
        out['normalized_to_host'] = normalized
    return out


def submit_one_safe(site, url: str) -> None:
    """Best-effort, NON-BLOCKING single-URL ping for the auto-submit on delivery.

    Fires the IndexNow POST on a daemon thread so a slow endpoint never delays
    the delivery/publish response. The key is generated in the calling thread
    first (the only DB write); the thread then does just the HTTP POST.
    """
    if not (url or '').strip() or not _host(site):
        return
    get_or_create_key(site)  # ensure the key exists here (DB write in-request)

    import threading

    def _run():
        try:
            submit_urls(site, [url])  # no DB write: key already set on `site`
        except Exception as exc:  # noqa: BLE001
            logger.info('IndexNow auto-submit skipped for site %s: %s',
                        getattr(site, 'id', '?'), exc)

    threading.Thread(target=_run, daemon=True).start()

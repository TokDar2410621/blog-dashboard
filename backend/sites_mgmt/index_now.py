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
from urllib.parse import urlparse

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


def get_or_create_key(site) -> str:
    """The site's IndexNow key, generated + persisted on first use."""
    key = (getattr(site, 'indexnow_key', '') or '').strip()
    if not key:
        key = secrets.token_hex(16)  # 32 hex chars, within IndexNow's 8-128 range
        type(site).objects.filter(pk=site.pk).update(indexnow_key=key)
        site.indexnow_key = key
    return key


def key_file_info(site) -> dict:
    """Everything needed to host the ownership key file."""
    key = get_or_create_key(site)
    host = _host(site)
    key_file_url = f'https://{host}/{key}.txt' if host else ''
    return {
        'key': key,
        'host': host,
        'key_file_url': key_file_url,
        'key_file_content': key,
        'instructions': (
            f"Heberge un fichier texte contenant UNIQUEMENT la cle a l'URL "
            f"{key_file_url or '<https://ton-domaine/<cle>.txt>'} (accessible en "
            "public, content-type text/plain). Une fois en place, la soumission "
            "IndexNow est validee automatiquement."
        ),
    }


def submit_urls(site, urls) -> dict:
    """Submit URLs to IndexNow. Returns {ok, status, reason, submitted, host}.

    URLs must be on the site's own host (IndexNow rejects cross-host lists).
    """
    key = get_or_create_key(site)
    host = _host(site)
    if not host:
        return {'ok': False, 'error': 'Aucun domaine configure pour ce site.',
                'submitted': 0}

    clean: list[str] = []
    seen = set()
    skipped_host = 0
    for u in urls or []:
        u = (u or '').strip()
        if not u:
            continue
        h = (urlparse(u if u.startswith('http') else 'https://' + u).netloc or '').lower()
        if h != host:
            skipped_host += 1
            continue
        if u not in seen:
            seen.add(u)
            clean.append(u)

    if not clean:
        return {
            'ok': False,
            'error': f"Aucune URL valide sur le host '{host}'.",
            'submitted': 0, 'skipped_wrong_host': skipped_host, 'host': host,
        }

    try:
        resp = requests.post(
            INDEXNOW_ENDPOINT,
            json={
                'host': host,
                'key': key,
                'keyLocation': f'https://{host}/{key}.txt',
                'urlList': clean[:10000],
            },
            headers={'Content-Type': 'application/json; charset=utf-8'},
            timeout=15,
        )
        code = resp.status_code
    except Exception as exc:
        logger.info('IndexNow submit failed for site %s: %s', site.id, exc)
        return {'ok': False, 'error': str(exc)[:150], 'submitted': 0, 'host': host}

    return {
        'ok': code in (200, 202),
        'status': code,
        'reason': _STATUS_REASON.get(code, f'HTTP {code}'),
        'submitted': len(clean),
        'skipped_wrong_host': skipped_host,
        'host': host,
        'engines': 'Bing, Yandex, Seznam, Naver (pas Google)',
    }

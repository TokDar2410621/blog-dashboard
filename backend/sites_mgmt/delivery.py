"""Delivery readiness: can generated content actually REACH this site's live
pages, or would it fall into the black hole (stored in Gridar, never delivered)?

The dashboard uses this to gate generation honestly: green = a real path exists,
yellow = a path might exist but we can't confirm it renders, red = no path, so
generating would be a dead end. Detection is explicit - NEVER `is_hosted`, which
is True precisely for the "nothing connected" black-hole case.
"""
from __future__ import annotations


def block_reason(site) -> str:
    """Blocker message if GENERATING for this site would be a dead end (no path
    to the live site), else '' (empty = generation is fine). The single guard
    every generation entry point calls to avoid the black hole."""
    d = delivery_status(site)
    return d['blocker'] if d['status'] == 'blocked' else ''


def delivery_status(site) -> dict:
    """Return {status, method, label, blocker} for how content reaches the site.

    status: 'ready' (a real push/serve path), 'unconfirmed' (mode externe: the
    client may fetch from the API, but we can't confirm it renders), or
    'blocked' (no path - generation would be a dead end).
    """
    # Explicit agent delivery wins over everything (matches save_article's
    # short-circuit): content is built into the client's repo by an agent.
    if getattr(site, 'delivery_mode', 'auto') == 'agent':
        return {
            'status': 'ready',
            'method': 'agent',
            'label': "Livre par un agent dans le repo du client (build-queue)",
            'blocker': '',
        }

    if site.is_wordpress:
        return {'status': 'ready', 'method': 'wordpress',
                'label': 'Publie sur WordPress', 'blocker': ''}
    if site.is_shopify:
        return {'status': 'ready', 'method': 'shopify',
                'label': 'Publie sur Shopify', 'blocker': ''}
    if site.is_webflow:
        return {'status': 'ready', 'method': 'webflow',
                'label': 'Publie sur Webflow', 'blocker': ''}
    if (site.database_url or '').strip():
        return {'status': 'ready', 'method': 'external_db',
                'label': 'Ecrit dans ta base de donnees externe', 'blocker': ''}
    if (getattr(site, 'public_blog_domain', '') or '').strip():
        return {'status': 'ready', 'method': 'hosted',
                'label': 'Heberge et servi par Gridar', 'blocker': ''}

    # Nothing pushes/serves. The only remaining legit path is "mode externe":
    # the client's own site fetches articles from the public API. We can't tell
    # per-site, so an active API token on the account = plausible, unconfirmed.
    from .models import ApiToken
    has_token = ApiToken.objects.filter(
        user_id=site.owner_id, revoked_at__isnull=True
    ).exists()
    if has_token:
        return {
            'status': 'unconfirmed',
            'method': 'api_fetch',
            'label': "Peut-etre recupere via l'API (mode externe)",
            'blocker': "On ne peut pas confirmer que le contenu apparait sur ton "
                       "site. Verifie le rendu d'une page livree.",
        }

    return {
        'status': 'blocked',
        'method': 'none',
        'label': "Aucun chemin de livraison",
        'blocker': "Le contenu genere resterait dans Gridar sans atteindre ton "
                   "site. Connecte un CMS (WordPress/Shopify/Webflow), active le "
                   "mode agent, ajoute une base externe, heberge chez nous, ou "
                   "branche l'API (mode externe).",
    }

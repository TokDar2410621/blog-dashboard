"""Proof loop: baseline + attribution per article via GSC.

Two reads happen here:

  capture_baseline(site)
    Snapshots the last N published posts' GSC metrics at GSC-connect time.
    Idempotent: skips posts that already have a baseline younger than 30d.

  snapshot_attribution(post, days_since_publish)
    Snapshots a single post at a fixed horizon (30/60/90) after publish_at.
    Idempotent via unique_together (post, days_since_publish).

Both anchor on the site's GSC property URL and the post's public URL. The
GSC client builder is duplicated minimally here (rather than imported from
views.py) to avoid a 10k-line module import inside cron and signals.
"""
from __future__ import annotations

import logging
import os
import secrets
from datetime import date, timedelta
from typing import Optional

from django.conf import settings

from .models import (
    ArticleAttribution, ArticleBaseline, HostedPost,
    ProofShareToken, Site,
)

logger = logging.getLogger(__name__)

# Scope COMPLET (lecture + ecriture) : la lecture seule interdisait
# sitemaps.submit, donc re-soumettre un sitemap restait un geste manuel de
# Darius. Constate le 2026-08-02 sur gridar.app (sitemap corrige mais jamais
# relu par Google) et qrstudio.agency (telecharge une seule fois le 14/07).
# `webmasters` couvre tout ce que `webmasters.readonly` couvrait : les sites
# deja connectes continuent de LIRE sans rien changer ; seule l'ECRITURE exige
# une reconnexion (nouveau consentement), et le code le dit explicitement.
GSC_SCOPES = ['https://www.googleapis.com/auth/webmasters']
GSC_TOKEN_URI = 'https://oauth2.googleapis.com/token'

BASELINE_INITIAL_LIMIT = 30
BASELINE_REFRESH_DAYS = 30
BASELINE_WINDOW_DAYS = 28


def _gsc_client_credentials():
    client_id = (
        os.environ.get('GSC_CLIENT_ID', '').strip()
        or os.environ.get('GOOGLE_OAUTH_CLIENT_ID', '').strip()
    )
    client_secret = (
        os.environ.get('GSC_CLIENT_SECRET', '').strip()
        or os.environ.get('GOOGLE_OAUTH_CLIENT_SECRET', '').strip()
    )
    if not (client_id and client_secret):
        return None
    return client_id, client_secret


def _gsc_canonical_site_url(site: Site) -> str:
    prop = (site.gsc_property_url or '').strip()
    if prop.startswith('sc-domain:'):
        host = (site.domain or '').strip()
        host = host.replace('https://', '').replace('http://', '').rstrip('/')
        if not host:
            host = prop[len('sc-domain:'):]
        return f'https://{host}/'
    return prop.rstrip('/') + '/' if prop else ''


def _post_public_url(site: Site, post: HostedPost) -> str:
    """Best-effort public URL for a hosted post.

    Mode hosted (no external CMS): served at `<site.public_blog_domain>/blog/<slug>`
    or fallback to the GSC canonical prefix + `blog/<slug>`. The GSC `page`
    dimension filters on this URL.
    """
    public_domain = (site.public_blog_domain or '').strip()
    if public_domain:
        if not public_domain.startswith('http'):
            public_domain = f'https://{public_domain}'
        return f'{public_domain.rstrip("/")}/blog/{post.slug}'
    prefix = _gsc_canonical_site_url(site)
    if prefix:
        return f'{prefix}blog/{post.slug}'
    return f'https://{site.domain}/blog/{post.slug}' if site.domain else ''


def _build_gsc_service(site: Site):
    """Return an authed GSC v1 client, or None when not configured.

    Raises nothing; caller checks for None and skips gracefully. Library
    import is local so the module is importable without google-api-python-client
    installed (dev / tests).
    """
    # Only the refresh token is needed to AUTHENTICATE; the property (siteUrl)
    # is a per-call argument that resolve_gsc_property discovers and persists.
    # Gating on gsc_property_url here was a silent killer: the OAuth callback
    # saves the token but never the property, so a site the user HAD connected
    # (qrstudio.agency, constate le 2026-07-29) had every GSC feature dead
    # without a word: index coverage, proof loop, decay, positions.
    if not site.gsc_refresh_token:
        return None
    creds_cfg = _gsc_client_credentials()
    if not creds_cfg:
        return None
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
    except ImportError:
        logger.warning('proof_loop: google API client not installed')
        return None
    client_id, client_secret = creds_cfg
    # PAS de scopes= ici. Le scope d'un refresh token est fixe par le
    # consentement, pas par le client : le passer ne l'elargit pas, il sert
    # seulement de reference a google-auth pour comparer. Depuis que GSC_SCOPES
    # vaut `webmasters`, tout site connecte AVANT l'elargissement (jeton
    # readonly) declenchait a chaque rafraichissement un
    # `WARNING ... Not all requested scopes were granted ... missing scopes
    # https://www.googleapis.com/auth/webmasters` (google-auth 2.48,
    # credentials.py:439). Rien de casse, mais un log qui hurle "scope manquant"
    # exactement pendant la surveillance des logs post-deploiement. Le scope
    # reellement accorde reste valide par Google a chaque appel.
    creds = Credentials(
        token=None,
        refresh_token=site.gsc_refresh_token,
        token_uri=GSC_TOKEN_URI,
        client_id=client_id,
        client_secret=client_secret,
    )
    return build('searchconsole', 'v1', credentials=creds, cache_discovery=False)


def resolve_gsc_property(service, site: Site) -> str:
    """Return the GSC property (siteUrl) the token can actually query.

    The stored gsc_property_url is often a URL-prefix ('https://site.com/') that
    is NOT a verified property when the user set up a DOMAIN property
    ('sc-domain:site.com'). Every GSC call (searchanalytics, urlInspection) is
    strict about the property and 403s ("You do not own this site") on a
    mismatch, which silently breaks proof / decay / positions / index coverage.

    Resolution is IN-MEMORY only: it maps to a property the token holds and
    returns it for use as siteUrl. It NEVER overwrites gsc_property_url, which
    stays a valid URL used both for building the 'page' filter (keeps the real
    host, incl. www) and for the writable settings field (an 'sc-domain:' value
    would fail the URLField validator on the next save). Memoized on the
    instance; falls back to the stored value if the listing fails.
    """
    from urllib.parse import urlparse
    memo = getattr(site, '_gsc_resolved_property', None)
    if memo is not None:
        return memo
    # Failure fallback memoized SEPARATELY: a persistent outage (revoked token,
    # API down) must not cost 2 failing HTTP calls per resolve inside per-post
    # loops (capture_baseline resolves once per post: 30 posts = 60 calls).
    # In-memory only, so a fresh request still retries a full resolution.
    echec = getattr(site, '_gsc_resolve_failed_fallback', None)
    if echec is not None:
        return echec
    stored = (site.gsc_property_url or '').strip()
    resolved = stored
    if service is not None:
        try:
            # One retry: a transient sites().list failure used to silently fall
            # back to the stored URL (often not a real property -> every GSC
            # call 403s downstream, notably index_coverage's URL inspection).
            try:
                listing = service.sites().list().execute() or {}
            except Exception as first_exc:
                logger.info('resolve_gsc_property: sites().list failed once, retry: %s', first_exc)
                listing = service.sites().list().execute() or {}
            entries = listing.get('siteEntry') or []
            # Any access level can read Search Analytics; URL Inspection needs
            # owner, but a non-owner call just 403s and degrades to site:.
            owned = {
                e.get('siteUrl') for e in entries
                if isinstance(e, dict) and e.get('permissionLevel') in (
                    'siteOwner', 'siteFullUser', 'siteRestrictedUser')
            }
            if not (stored and stored in owned):
                host_src = stored or (getattr(site, 'domain', '') or '').strip()
                host = urlparse(
                    host_src if host_src.startswith('http') else 'https://' + host_src
                ).netloc.lower().split(':')[0]
                if host.startswith('www.'):
                    host = host[4:]
                for candidate in (f'sc-domain:{host}', f'https://{host}/',
                                  f'https://www.{host}/', f'http://{host}/'):
                    if candidate in owned:
                        resolved = candidate
                        break
                # AUTO-GUERISON : la propriete etait vide (le callback OAuth ne
                # la remplissait pas) et on vient de la decouvrir -> on la
                # PERSISTE, sinon chaque appel la redecouvre et tout ce qui
                # gate sur gsc_property_url (GSCQueriesView, _gsc_canonical_site_url)
                # reste casse. On stocke toujours la forme URL : le champ est un
                # URLField, un 'sc-domain:...' echouerait au prochain save ;
                # resolve_gsc_property remappe vers sc-domain en memoire.
                if not stored and resolved:
                    url_form = resolved if resolved.startswith('http') else f'https://{host}/'
                    try:
                        site.gsc_property_url = url_form
                        site.save(update_fields=['gsc_property_url'])
                        logger.info(
                            'resolve_gsc_property: propriete GSC decouverte et persistee '
                            'pour le site %s : %s (resolue: %s)', site.id, url_form, resolved)
                    except Exception:
                        logger.exception(
                            'resolve_gsc_property: echec de persistance de la propriete site %s',
                            site.id)
        except Exception as exc:
            logger.warning('resolve_gsc_property: sites().list failed (x2): %s', exc)
            resolved = stored
            # A URL-prefix property string ALWAYS ends with '/': "https://x.com"
            # is never a valid siteUrl, so at least normalize it. (May still not
            # be the owned property; callers now surface that error instead of
            # silently degrading.)
            if resolved and not resolved.endswith('/') and not resolved.startswith('sc-domain:'):
                resolved += '/'
            # Memoized in the FAILURE sentinel (not the success memo): repeated
            # resolves in this run reuse it without re-hitting the API, while a
            # fresh request/instance retries the full resolution.
            site._gsc_resolve_failed_fallback = resolved
            return resolved
    site._gsc_resolved_property = resolved
    return resolved


def default_sitemap_url(site: Site) -> str:
    """The sitemap to submit: <public host>/sitemap.xml.

    Goes through _public_base so the host is EXACTLY the one every other GSC
    read uses. The www matters: gridar.app lost two weeks on a sitemap submitted
    to the bare host while its pages live on www."""
    from .index_coverage import _public_base  # late import: avoids the cycle
    base, _ = _public_base(site)
    return (base.rstrip('/') + '/sitemap.xml') if base else ''


def property_covers(prop: str, url: str) -> bool:
    """Does the GSC property `prop` contain `url`?

    Google refuses a sitemap that is not inside the property. A domain property
    (`sc-domain:x.com`) covers the host and every subdomain; a URL-prefix
    property (`https://www.x.com/`) covers only what starts with it."""
    from urllib.parse import urlparse
    if not prop or not url:
        return False
    if prop.startswith('sc-domain:'):
        host = urlparse(url if url.startswith('http') else 'https://' + url).netloc
        host = host.lower().split(':')[0]
        root = prop[len('sc-domain:'):].lower().strip('/')
        return host == root or host.endswith('.' + root)
    return url.startswith(prop.rstrip('/') + '/')


def _property_for_url(service, url: str):
    """(property containing `url`, exception) - the property is '' if none.

    Why: resolve_gsc_property answers "which property do I read this site
    through", and it strips the www and tries the bare host BEFORE the www one.
    That answer is fine for reads and wrong for a write: submitting
    https://www.gridar.app/sitemap.xml against the property https://gridar.app/
    is rejected by Google. The hosted mode makes it worse, blogs live on a
    subdomain (blog.client.ca) while the property is the root domain.

    The exception is returned rather than swallowed: "no property" and "dead
    token" produce the same empty answer, and telling a customer that his
    property does not exist when his token is simply revoked sends him hunting
    in the wrong place."""
    try:
        entries = (service.sites().list().execute() or {}).get('siteEntry') or []
    except Exception as exc:
        logger.warning('_property_for_url: sites().list failed: %s', exc)
        return '', exc
    owned = [e.get('siteUrl') for e in entries
             if isinstance(e, dict) and e.get('permissionLevel') in (
                 'siteOwner', 'siteFullUser', 'siteRestrictedUser')]
    candidates = [p for p in owned if p and property_covers(p, url)]
    if not candidates:
        return '', None
    # Le prefixe d'URL le plus long d'abord (le plus specifique), les proprietes
    # de domaine en dernier : elles couvrent tout, donc elles n'apportent une
    # reponse que si aucun prefixe ne colle.
    candidates.sort(key=lambda p: (p.startswith('sc-domain:'), -len(p)))
    return candidates[0], None


def _classify_gsc_error(exc) -> str:
    """'reauth' | 'readonly' | 'not_owner' | '' for a failed GSC call.

    Reads the STRUCTURED fields (HTTP status, error reason) instead of matching
    substrings on str(exc). str(exc) embeds the request URI, which contains the
    customer's domain and the sitemap path: a client on telescope.io hit
    `'403' in text and 'scope' in text` on any unrelated 403 and got told to
    reconnect Search Console, forever."""
    try:
        from google.auth.exceptions import RefreshError
    except ImportError:
        RefreshError = ()
    # Jeton revoque ou expire : le refresh se produit au premier appel, donc il
    # remonte ici et non a la construction du client. C'est le seul cas ou
    # reconnecter est vraiment la reparation, et c'est le contrat deja etabli
    # ailleurs dans ce fichier de code (401 gsc_reauth_required).
    if RefreshError and isinstance(exc, RefreshError):
        return 'reauth'
    statut = getattr(getattr(exc, 'resp', None), 'status', None)
    reasons = set()
    for d in (getattr(exc, 'error_details', None) or []):
        if isinstance(d, dict):
            for cle in ('reason', 'message'):
                v = d.get(cle)
                if isinstance(v, str):
                    reasons.add(v)
    reasons = {r.lower() for r in reasons}
    if any('permission for site' in r for r in reasons):
        return 'not_owner'
    if reasons & {'insufficientpermissions', 'access_token_scope_insufficient',
                  'forbidden_insufficient_scope'}:
        return 'readonly'
    if statut in (401, 403):
        # Dernier recours quand error_details est vide : on regarde le seul
        # champ de message, jamais l'URI.
        msg = str(getattr(exc, 'reason', '') or '').lower()
        if 'permission for site' in msg:
            return 'not_owner'
        if 'insufficient authentication scopes' in msg or 'insufficient permission' in msg:
            return 'readonly'
    return ''


def submit_sitemap(site: Site, sitemap_url: str = '') -> dict:
    """Submit (or re-submit) the site's sitemap to Search Console.

    Why: re-submitting makes Google RE-READ the sitemap instead of waiting for
    its next pass. Useful whenever a sitemap changes (gridar.app moved from the
    bare host to www on 2026-08-02) or goes stale (qrstudio.agency: downloaded
    once on 07-14, 0 of 80 URLs indexed).

    Needs the FULL `webmasters` scope. A site connected before the widening
    still carries a `webmasters.readonly` token: the call then 403s and we say
    what to do about it (reconnect) instead of leaking a raw error.
    Returns {ok, sitemap, property, needs_reconnect, code, error}."""
    sitemap = (sitemap_url or default_sitemap_url(site)).strip()
    if not sitemap:
        return {'ok': False, 'error': "Aucun domaine configure pour ce site.",
                'sitemap': '', 'needs_reconnect': False}
    service = _build_gsc_service(site)
    if service is None:
        return {'ok': False, 'error': "GSC non connectee (aucun jeton) ou client OAuth absent.",
                'sitemap': sitemap, 'needs_reconnect': False}
    prop = resolve_gsc_property(service, site)
    # La propriete de LECTURE ne contient pas forcement le sitemap : on cherche
    # alors celle qui le contient vraiment, plutot que de laisser Google refuser
    # avec un message que personne ne saura relier au vrai probleme.
    if not prop or not property_covers(prop, sitemap):
        mieux, echec = _property_for_url(service, sitemap)
        if mieux:
            if prop and mieux != prop:
                logger.info('submit_sitemap: propriete %s ne couvre pas %s, bascule sur %s',
                            prop, sitemap, mieux)
            prop = mieux
        elif _classify_gsc_error(echec) == 'reauth':
            return {'ok': False, 'sitemap': sitemap, 'property': prop or '',
                    'needs_reconnect': True, 'code': 'gsc_reauth_required',
                    'error': "Le jeton Search Console de ce site est expire ou revoque. "
                             "Reconnecte Search Console."}
        elif prop:
            return {'ok': False, 'sitemap': sitemap, 'property': prop,
                    'needs_reconnect': False, 'code': 'sitemap_hors_propriete',
                    'error': ("Le sitemap %s n'appartient a aucune propriete Search Console "
                              "verifiee par ce compte (la propriete resolue est %s). Ajoute "
                              "cette propriete dans Search Console, ou passe un sitemap_url "
                              "qui vit dedans." % (sitemap, prop))}
        else:
            return {'ok': False, 'sitemap': sitemap, 'needs_reconnect': False,
                    'error': "Aucune propriete Search Console verifiee ne correspond a ce site."}
    try:
        service.sitemaps().submit(siteUrl=prop, feedpath=sitemap).execute()
    except Exception as exc:
        genre = _classify_gsc_error(exc)
        base = {'ok': False, 'sitemap': sitemap, 'property': prop}
        if genre == 'reauth':
            return dict(base, needs_reconnect=True, code='gsc_reauth_required',
                        error="Le jeton Search Console de ce site est expire ou revoque. "
                              "Reconnecte Search Console.")
        if genre == 'not_owner':
            return dict(base, needs_reconnect=False, code='gsc_not_owner',
                        error="Le compte Google connecte n'est pas proprietaire de la "
                              "propriete %s dans Search Console." % prop)
        if genre == 'readonly':
            return dict(base, needs_reconnect=True, code='gsc_scope_readonly',
                        error="Le jeton de ce site est en LECTURE SEULE (connecte avant "
                              "l'elargissement du scope). Reconnecte Search Console pour "
                              "autoriser la soumission de sitemap.")
        text = str(exc)
        logger.warning('submit_sitemap: failed %s (%s): %s', sitemap, prop, text[:200])
        return dict(base, needs_reconnect=False, error=text[:300])
    logger.info('sitemap re-submitted to GSC: %s (property %s)', sitemap, prop)
    return {'ok': True, 'sitemap': sitemap, 'property': prop, 'needs_reconnect': False}


def _query_page_metrics(service, site: Site, page_url: str,
                        start: date, end: date, top_n_queries: int = 5) -> dict:
    """Two GSC calls for one page: (1) aggregated impressions/clicks/position,
    (2) top N queries by impressions. Returns a dict, or {'indexed': False, ...}
    when the page has no GSC rows in the window.
    """
    site_url = resolve_gsc_property(service, site)
    base_body = {
        'startDate': start.isoformat(),
        'endDate': end.isoformat(),
        'dimensionFilterGroups': [{
            'filters': [{
                'dimension': 'page',
                'operator': 'equals',
                'expression': page_url,
            }],
        }],
    }

    agg_body = dict(base_body, rowLimit=1)
    agg = service.searchanalytics().query(siteUrl=site_url, body=agg_body).execute() or {}
    rows = agg.get('rows') or []
    if not rows:
        return {'indexed': False, 'impressions': 0, 'clicks': 0,
                'avg_position': None, 'top_queries': []}
    row = rows[0]
    impressions = int(row.get('impressions') or 0)
    clicks = int(row.get('clicks') or 0)
    position = row.get('position')
    avg_position = float(position) if position is not None else None

    queries_body = dict(base_body, dimensions=['query'], rowLimit=top_n_queries)
    queries = service.searchanalytics().query(siteUrl=site_url, body=queries_body).execute() or {}
    top_queries = [
        {
            'query': (q.get('keys') or [''])[0],
            'impressions': int(q.get('impressions') or 0),
            'clicks': int(q.get('clicks') or 0),
            'position': float(q.get('position')) if q.get('position') is not None else None,
        }
        for q in (queries.get('rows') or [])
    ]
    return {
        'indexed': impressions > 0,
        'impressions': impressions,
        'clicks': clicks,
        'avg_position': avg_position,
        'top_queries': top_queries,
    }


def capture_baseline_for_post(site: Site, post: HostedPost,
                              service=None, is_pre_gridar: bool = False) -> Optional[ArticleBaseline]:
    """Capture (or refresh, if stale) one post's baseline. Returns the row or None on failure."""
    existing = ArticleBaseline.objects.filter(site=site, post=post).first()
    if existing:
        from django.utils import timezone
        age = (timezone.now() - existing.captured_at).days
        if age < BASELINE_REFRESH_DAYS:
            return existing

    svc = service or _build_gsc_service(site)
    if svc is None:
        return None
    page_url = _post_public_url(site, post)
    if not page_url:
        return None

    end = date.today()
    start = end - timedelta(days=BASELINE_WINDOW_DAYS - 1)
    try:
        metrics = _query_page_metrics(svc, site, page_url, start, end)
    except Exception as e:
        logger.warning('proof_loop.capture_baseline_for_post failed (site=%s post=%s): %s',
                       site.id, post.id, e)
        return None

    if existing:
        existing.delete()
    return ArticleBaseline.objects.create(
        site=site, post=post,
        period_start=start, period_end=end,
        impressions=metrics['impressions'],
        clicks=metrics['clicks'],
        avg_position=metrics['avg_position'],
        top_queries=metrics['top_queries'],
        is_pre_gridar=is_pre_gridar,
    )


def capture_baseline(site: Site, limit: int = BASELINE_INITIAL_LIMIT) -> dict:
    """Snapshot the N most recent published posts. Used at GSC-connect time.

    Returns a summary dict {'captured': int, 'skipped': int, 'failed': int}.
    """
    if not site.gsc_property_url or not site.gsc_refresh_token:
        return {'captured': 0, 'skipped': 0, 'failed': 0, 'reason': 'gsc_not_configured'}

    service = _build_gsc_service(site)
    if service is None:
        return {'captured': 0, 'skipped': 0, 'failed': 0, 'reason': 'gsc_client_unavailable'}

    posts = (HostedPost.objects
             .filter(site=site, status='published', published_at__isnull=False)
             .order_by('-published_at')[:limit])
    captured = skipped = failed = 0
    for post in posts:
        before = ArticleBaseline.objects.filter(site=site, post=post).exists()
        row = capture_baseline_for_post(site, post, service=service, is_pre_gridar=True)
        if row is None:
            failed += 1
        elif before:
            skipped += 1
        else:
            captured += 1
    return {'captured': captured, 'skipped': skipped, 'failed': failed}


def snapshot_attribution(post: HostedPost, days_since_publish: int,
                         service=None) -> Optional[ArticleAttribution]:
    """Snapshot one post at a fixed horizon (30/60/90)."""
    if days_since_publish not in (30, 60, 90):
        raise ValueError('days_since_publish must be 30, 60, or 90')
    existing = ArticleAttribution.objects.filter(
        post=post, days_since_publish=days_since_publish,
    ).first()
    if existing:
        return existing

    site = post.site
    svc = service or _build_gsc_service(site)
    if svc is None:
        return None
    page_url = _post_public_url(site, post)
    if not page_url or not post.published_at:
        return None

    start = post.published_at
    end = date.today()
    try:
        metrics = _query_page_metrics(svc, site, page_url, start, end)
    except Exception as e:
        logger.warning('proof_loop.snapshot_attribution failed (post=%s J+%s): %s',
                       post.id, days_since_publish, e)
        return None

    baseline = ArticleBaseline.objects.filter(site=site, post=post).first()
    delta = {
        'impressions': metrics['impressions'] - (baseline.impressions if baseline else 0),
        'clicks': metrics['clicks'] - (baseline.clicks if baseline else 0),
    }
    if metrics['avg_position'] is not None and baseline and baseline.avg_position is not None:
        delta['avg_position'] = metrics['avg_position'] - baseline.avg_position
    else:
        delta['avg_position'] = None

    return ArticleAttribution.objects.create(
        post=post,
        days_since_publish=days_since_publish,
        period_start=start,
        period_end=end,
        indexed=metrics['indexed'],
        impressions=metrics['impressions'],
        clicks=metrics['clicks'],
        avg_position=metrics['avg_position'],
        top_queries=metrics['top_queries'],
        delta_vs_baseline=delta,
    )


def site_proof_summary(site: Site) -> dict:
    """Aggregate the site-level delta for the dashboard card and public page.

    Honesty invariants (the public proof board depends on these):
      - Pre-Gridar baselines are EXCLUDED: we never count our improvement of a
        page that existed before Gridar as a Gridar-generated gain. The queryset
        used to leak these despite the docstring; now it truly filters them.
      - `posts` is the COMPLETE per-post list (winners, flat AND losers), most
        recent first. The public page renders it in full: a proof board that
        hides its zeros is not proof.
      - `total_*` sum every delta, including negatives.
      - `top_gainers` (winners, top 5) is kept for the owner's dashboard
        highlight only, never as the public evidence.
    """
    pre_gridar_post_ids = set(
        ArticleBaseline.objects
        .filter(site=site, is_pre_gridar=True, post__isnull=False)
        .values_list('post_id', flat=True)
    )
    attributions = (ArticleAttribution.objects
                    .filter(post__site=site)
                    .exclude(post_id__in=pre_gridar_post_ids)
                    .select_related('post')
                    .order_by('post_id', '-days_since_publish'))
    latest_per_post = {}
    for a in attributions:
        if a.post_id not in latest_per_post:
            latest_per_post[a.post_id] = a

    total_impressions_gained = 0
    total_clicks_gained = 0
    posts = []
    for attribution in latest_per_post.values():
        delta = attribution.delta_vs_baseline or {}
        impr_delta = int(delta.get('impressions') or 0)
        click_delta = int(delta.get('clicks') or 0)
        total_impressions_gained += impr_delta
        total_clicks_gained += click_delta
        published_at = attribution.post.published_at
        posts.append({
            'post_id': attribution.post_id,
            'title': attribution.post.title,
            'slug': attribution.post.slug,
            'horizon': attribution.days_since_publish,
            'impressions_gained': impr_delta,
            'clicks_gained': click_delta,
            'indexed': attribution.indexed,
            'published_at': published_at.isoformat() if published_at else None,
            'top_queries': (attribution.top_queries or [])[:3],
        })
    # Complete list, most recent first: winners AND flops, nothing hidden.
    posts.sort(key=lambda x: (x['published_at'] or ''), reverse=True)
    top_gainers = sorted(
        (p for p in posts if p['impressions_gained'] > 0),
        key=lambda x: -x['impressions_gained'],
    )[:5]

    return {
        'site_id': site.id,
        'site_name': site.name,
        'posts_with_attribution': len(latest_per_post),
        'total_impressions_gained': total_impressions_gained,
        'total_clicks_gained': total_clicks_gained,
        'posts': posts,
        'top_gainers': top_gainers,
    }


def ensure_proof_token(site: Site) -> ProofShareToken:
    """Get-or-create the site's share token. Caller controls enabled/revoked."""
    token, _ = ProofShareToken.objects.get_or_create(
        site=site,
        defaults={'token': secrets.token_urlsafe(32), 'enabled': False},
    )
    return token


def regenerate_proof_token(site: Site) -> ProofShareToken:
    """Force a new random token (revokes any leaked one). Keeps enabled state."""
    token = ensure_proof_token(site)
    token.token = secrets.token_urlsafe(32)
    token.save(update_fields=['token'])
    return token

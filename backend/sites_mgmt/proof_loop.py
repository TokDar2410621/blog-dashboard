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

GSC_SCOPES = ['https://www.googleapis.com/auth/webmasters.readonly']
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
    if not site.gsc_property_url or not site.gsc_refresh_token:
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
    creds = Credentials(
        token=None,
        refresh_token=site.gsc_refresh_token,
        token_uri=GSC_TOKEN_URI,
        client_id=client_id,
        client_secret=client_secret,
        scopes=GSC_SCOPES,
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
    stored = (site.gsc_property_url or '').strip()
    resolved = stored
    if service is not None:
        try:
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
        except Exception as exc:
            logger.info('resolve_gsc_property: sites().list failed: %s', exc)
            resolved = stored
    site._gsc_resolved_property = resolved
    return resolved


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

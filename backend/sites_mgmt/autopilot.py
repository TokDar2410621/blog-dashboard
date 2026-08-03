"""Autopilot mode: scheduled, hands-off article generation per site.

The user toggles `Site.autopilot_enabled` and picks a weekly cadence
(`autopilot_weekly_count`). A cron job runs `python manage.py run_autopilot`
hourly; this module decides whether each site is due for a new article and
generates one by picking a topic from the site's TrackedKeyword list.

Generated articles land as **draft** by default. The site owner can opt-in
to auto-publish via `Site.autopilot_auto_publish`, in which case articles
are published directly and a Vercel redeploy is triggered if configured.

The autopilot has three strategies, controlled by `Site.autopilot_mode`:

  - `create_only`   : legacy behaviour, always generate a brand-new article.
  - `refresh_first` : if any HostedPost is in decay (impressions down 20%+
                      over 30 days), refresh it rather than create new.
  - `balanced`      : alternate 1 refresh per 2 creations (default). Falls
                      back to the other branch when one isn't available.
"""
import logging
import random
from dataclasses import dataclass
from datetime import timedelta
from typing import Optional

from django.utils import timezone

from .models import Site, TrackedKeyword

logger = logging.getLogger(__name__)


@dataclass
class RunResult:
    """Outcome of a single autopilot run for one site."""
    ok: bool
    skipped_reason: Optional[str] = None
    topic: Optional[str] = None
    keyword_id: Optional[int] = None
    post_id: Optional[int] = None
    post_title: Optional[str] = None
    article_type: Optional[str] = None
    length: Optional[str] = None
    error: Optional[str] = None
    action: Optional[str] = None  # 'create' | 'refresh'


def is_due(site: Site, now=None) -> bool:
    """A site is due for a new article when:
    - autopilot is enabled, AND
    - we've never run for this site (first run), OR
    - the gap since last run >= 7 days / weekly_count.

    Example: weekly_count=2 -> one article every 3.5 days.
    """
    if not site.autopilot_enabled:
        return False
    if not site.autopilot_last_run_at:
        return True
    now = now or timezone.now()
    weekly = max(1, int(site.autopilot_weekly_count or 1))
    gap = timedelta(days=7) / weekly
    return (now - site.autopilot_last_run_at) >= gap


def pick_next_topic(site: Site) -> Optional[TrackedKeyword]:
    """Pick a tracked keyword that hasn't been used yet (no HostedPost with
    a slug matching it). Returns None if no usable keyword exists - the
    caller should skip the run and surface a warning.

    Strategy is intentionally simple: random sample over keywords that look
    "fresh" (no existing post). When we eventually wire SERP rank in here,
    we can prioritize keywords ranked > 10 (room to climb).
    """
    candidates = list(
        TrackedKeyword.objects.filter(site=site, is_active=True)
    )
    if not candidates:
        return None

    fresh = [k for k in candidates if not _has_existing_post(site, k.keyword)]
    pool = fresh or candidates
    return random.choice(pool)


def _has_existing_post(site: Site, keyword: str) -> bool:
    """Returns True if a HostedPost on this site has a title or slug that
    already covers this keyword (loose match: keyword tokens appear in slug)."""
    from .models import HostedPost

    if not site.is_hosted:
        return False

    norm = (keyword or '').strip().lower()
    if not norm:
        return False

    tokens = [t for t in norm.split() if len(t) > 3]
    if not tokens:
        tokens = [norm]

    qs = HostedPost.objects.filter(site=site)
    for tok in tokens:
        qs = qs.filter(slug__icontains=tok)
    return qs.exists()


def _check_for_decay_candidates(site: Site):
    """Return a list of HostedPost candidates eligible for a refresh.

    "Eligible" = the post's URL appears in GSC with at least a 20% drop in
    impressions over the last 30 days vs the previous 30 days, AND its
    `updated_at` is older than `site.min_refresh_interval_days` so we don't
    refresh the same article in a loop.

    Returns posts sorted by worst impressions decline first (most urgent
    refresh candidate at index 0). Returns [] when GSC is not configured,
    GSC errors out, or no candidate matches.

    Only supports hosted-mode sites: external CMS modes need adapter-specific
    update endpoints we don't have generalised yet.
    """
    from .models import HostedPost

    if not site.is_hosted:
        return []
    if not site.gsc_property_url or not site.gsc_refresh_token:
        return []

    try:
        from datetime import date as _date
        from google.oauth2.credentials import Credentials
        from google.auth.exceptions import RefreshError
        from googleapiclient.discovery import build
        from googleapiclient.errors import HttpError
    except ImportError:
        return []

    # Reuse GSC client config + URL canonicaliser from the views module.
    try:
        from .views import _gsc_client_config, _gsc_canonical_site_url, GSC_TOKEN_URI
    except ImportError:
        return []

    config = _gsc_client_config()
    if not config:
        return []

    end = _date.today()
    cur_start = end - timedelta(days=30)
    prev_end = cur_start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=29)

    try:
        # Pas de scopes= : voir proof_loop._build_gsc_service.
        creds = Credentials(
            token=None,
            refresh_token=site.gsc_refresh_token,
            token_uri=GSC_TOKEN_URI,
            client_id=config['web']['client_id'],
            client_secret=config['web']['client_secret'],
        )
        service = build('searchconsole', 'v1', credentials=creds, cache_discovery=False)
        from .proof_loop import resolve_gsc_property
        gsc_site_url = resolve_gsc_property(service, site)  # owned property for siteUrl

        def _q(start_d, end_d):
            body = {
                'startDate': start_d.isoformat(),
                'endDate': end_d.isoformat(),
                'dimensions': ['page'],
                'rowLimit': 1000,
            }
            return service.searchanalytics().query(
                siteUrl=gsc_site_url, body=body
            ).execute()

        cur_resp = _q(cur_start, end)
        prev_resp = _q(prev_start, prev_end)
    except (RefreshError, HttpError, Exception) as e:
        logger.warning('Autopilot decay check failed for site %s: %s', site.id, e)
        return []

    def _index(resp):
        out = {}
        for row in (resp or {}).get('rows', []) or []:
            keys = row.get('keys') or []
            if not keys:
                continue
            out[keys[0]] = {
                'impressions': int(row.get('impressions') or 0),
                'clicks': int(row.get('clicks') or 0),
            }
        return out

    cur_data = _index(cur_resp)
    prev_data = _index(prev_resp)

    property_prefix = _gsc_canonical_site_url(site)

    def _slug_from_url(url):
        if url.startswith(property_prefix):
            return url[len(property_prefix):].rstrip('/')
        return url

    # Build a list of (slug, drop_pct) for URLs whose impressions dropped 20%+.
    decay_by_slug = {}
    for url, cur in cur_data.items():
        prev = prev_data.get(url)
        if not prev or prev['impressions'] == 0:
            continue
        delta = (cur['impressions'] - prev['impressions']) / prev['impressions'] * 100
        if delta <= -20:
            slug = _slug_from_url(url)
            # Strip leading 'blog/' so we can match HostedPost.slug directly.
            slug = slug.lstrip('/').removeprefix('blog/').strip('/')
            if slug:
                decay_by_slug[slug] = delta

    if not decay_by_slug:
        return []

    refresh_cutoff = timezone.now() - timedelta(days=int(site.min_refresh_interval_days or 30))
    candidates = list(
        HostedPost.objects.filter(
            site=site,
            slug__in=list(decay_by_slug.keys()),
            status__in=['published'],
            updated_at__lt=refresh_cutoff,
        )
    )
    # Worst drop first.
    candidates.sort(key=lambda p: decay_by_slug.get(p.slug, 0))
    return candidates


def _refresh_article(site: Site, post) -> dict:
    """Regenerate a HostedPost in place via ArticleGenerator.update_article.

    Returns the same dict shape as `_generate_article` so `run_one` can
    package it into a `RunResult` uniformly.
    """
    from .article_generator import ArticleGenerator

    generator = ArticleGenerator(
        alias=None,
        knowledge_base=site.knowledge_base or '',
        site=site,
        default_status='published' if site.autopilot_auto_publish else 'draft',
    )
    hint = (
        "Cet article perd des impressions sur Google. Update les dates, ajoute "
        "une nouvelle section avec des donnees plus recentes, renforce le E-E-A-T."
    )
    refreshed = generator.update_article(post, refresh_prompt_hint=hint)
    return {
        'post_id': refreshed.id,
        'title': refreshed.title,
        'article_type': 'refresh',
        'length': 'medium',
    }


def _should_refresh_this_run(site: Site) -> bool:
    """Balanced mode picks refresh 1 run out of 3 (~1 refresh / 2 creations).

    Uses a simple modulo on the historical run count rather than a probability
    so the cadence is deterministic and predictable. The "count" is derived
    from the existing HostedPost count for this site - good enough as a
    monotonic counter without adding a dedicated column.
    """
    from .models import HostedPost

    n = HostedPost.objects.filter(site=site).count()
    # Out of every 3 runs, do 1 refresh: pattern create, create, refresh, ...
    return (n % 3) == 2


def run_one(site: Site, *, force: bool = False, user=None) -> RunResult:
    """Generate one article for `site` via the autopilot.

    - Respects `is_due` unless `force=True`
    - Branches on `site.autopilot_mode`:
        * create_only   -> always create a new article (legacy path)
        * refresh_first -> if decay candidates exist, refresh; else create
        * balanced      -> 1 refresh / 2 creates pattern, falls back to the
                           other branch if the picked one isn't available
    - Updates `autopilot_last_run_at` on success, `autopilot_last_error` on failure
    - Does NOT consume quota (autopilot is run by cron, not on behalf of a user
      action). The site owner's quota is bypassed here - we may revisit this
      when autopilot moves out of beta.
    """
    if not site.autopilot_enabled and not force:
        return RunResult(ok=False, skipped_reason='autopilot_disabled')

    if not force and not is_due(site):
        return RunResult(ok=False, skipped_reason='not_due_yet')

    # Delivery gate: if nothing reaches the live site, don't silently accumulate
    # content in the black hole. Skip (even under force) with a clear reason.
    from .delivery import block_reason
    if block_reason(site):
        logger.info('Autopilot skip site %s: no delivery path (black hole)', site.id)
        return RunResult(ok=False, skipped_reason='delivery_blocked')

    mode = getattr(site, 'autopilot_mode', 'balanced') or 'balanced'

    # Decide whether this run should attempt a refresh.
    try_refresh = False
    if mode == 'refresh_first':
        try_refresh = True
    elif mode == 'balanced':
        try_refresh = _should_refresh_this_run(site)
    # create_only -> try_refresh stays False

    refresh_post = None
    if try_refresh:
        try:
            candidates = _check_for_decay_candidates(site)
        except Exception as e:
            logger.warning('Decay check exception on site %s: %s', site.id, e)
            candidates = []
        if candidates:
            refresh_post = candidates[0]

    if refresh_post is not None:
        try:
            result = _refresh_article(site, refresh_post)
        except Exception as e:
            logger.exception('Autopilot refresh failed for site %s post %s', site.id, refresh_post.id)
            site.autopilot_last_error = f'refresh:{type(e).__name__}: {str(e)[:480]}'
            site.save(update_fields=['autopilot_last_error'])
            return RunResult(
                ok=False,
                topic=refresh_post.title,
                post_id=refresh_post.id,
                error=str(e),
                action='refresh',
            )

        site.autopilot_last_run_at = timezone.now()
        site.autopilot_last_error = ''
        site.save(update_fields=['autopilot_last_run_at', 'autopilot_last_error'])

        if site.autopilot_auto_publish and result.get('post_id'):
            from .views import trigger_vercel_deploy
            trigger_vercel_deploy(site)

        return RunResult(
            ok=True,
            topic=result.get('title') or refresh_post.title,
            post_id=result.get('post_id'),
            post_title=result.get('title'),
            article_type=result.get('article_type'),
            length=result.get('length'),
            action='refresh',
        )

    # Create path (default + refresh-first fallback when no decay candidate)
    keyword = pick_next_topic(site)
    if not keyword:
        # In refresh_first mode we already tried to find a decay candidate; if
        # none AND no fresh keyword, there's nothing to do this run.
        skipped = 'no_keyword' if mode != 'refresh_first' else 'no_keyword_no_decay'
        site.autopilot_last_error = 'Aucun mot-cle tracke disponible pour ce site'
        site.save(update_fields=['autopilot_last_error'])
        return RunResult(ok=False, skipped_reason=skipped)

    try:
        result = _generate_article(site, keyword)
    except Exception as e:
        logger.exception('Autopilot generation failed for site %s', site.id)
        site.autopilot_last_error = f'{type(e).__name__}: {str(e)[:500]}'
        site.save(update_fields=['autopilot_last_error'])
        return RunResult(
            ok=False,
            topic=keyword.keyword,
            keyword_id=keyword.id,
            error=str(e),
            action='create',
        )

    site.autopilot_last_run_at = timezone.now()
    site.autopilot_last_error = ''
    site.save(update_fields=['autopilot_last_run_at', 'autopilot_last_error'])

    if site.autopilot_auto_publish and result.get('post_id'):
        from .views import trigger_vercel_deploy
        trigger_vercel_deploy(site)

    return RunResult(
        ok=True,
        topic=keyword.keyword,
        keyword_id=keyword.id,
        post_id=result.get('post_id'),
        post_title=result.get('title'),
        article_type=result.get('article_type'),
        length=result.get('length'),
        action='create',
    )


def _generate_article(site: Site, keyword: TrackedKeyword) -> dict:
    """Thin wrapper around ArticleGenerator that mirrors GenerateArticleView.

    The article type and length are derived from the keyword's stored intent
    (set by IA suggestions or the regex fallback), not hardcoded. See
    keyword_intent.map_intent_to_article_type and pick_length.
    """
    from .article_generator import ArticleGenerator
    from .db_utils import ensure_site_connection
    from .keyword_intent import map_intent_to_article_type, pick_length

    if site.is_hosted or site.is_wordpress or site.is_shopify or site.is_webflow:
        alias = None
    else:
        alias = ensure_site_connection(site)

    article_type = map_intent_to_article_type(keyword.intent, keyword.keyword)
    length = pick_length(keyword.intent, keyword.keyword)
    default_status = 'published' if site.autopilot_auto_publish else 'draft'

    logger.info(
        'Autopilot site=%s keyword=%r intent=%s -> type=%s length=%s status=%s',
        site.id, keyword.keyword, keyword.intent, article_type, length, default_status,
    )

    generator = ArticleGenerator(
        alias,
        knowledge_base=site.knowledge_base or '',
        wp_site=site if site.is_wordpress else None,
        shopify_site=site if site.is_shopify else None,
        webflow_site=site if site.is_webflow else None,
        site=site,
        default_status=default_status,
    )
    out = generator.generate(
        search_method='serper',
        topic=keyword.keyword,
        title=None,
        article_type=article_type,
        length=length,
        keywords=keyword.keyword,
        dry_run=False,
        language=keyword.language or 'fr',
        brief=None,
    )

    # ArticleGenerator returns {output, post_count} but not the post object.
    # Pull the freshest post we can plausibly attribute to this run so the
    # API response can link to it. Only works in hosted mode (other modes
    # write to remote CMS APIs - we don't have a stable handle).
    post_id, post_title = None, None
    if site.is_hosted and (out or {}).get('post_count', 0) >= 1:
        from .models import HostedPost
        latest = (
            HostedPost.objects.filter(site=site)
            .order_by('-id')
            .values('id', 'title')
            .first()
        )
        if latest:
            post_id = latest['id']
            post_title = latest['title']
    return {
        'post_id': post_id,
        'title': post_title,
        'article_type': article_type,
        'length': length,
    }


def due_sites(now=None):
    """Iterator over all sites that are currently due for an autopilot run."""
    now = now or timezone.now()
    qs = Site.objects.filter(autopilot_enabled=True, is_active=True)
    for site in qs:
        if is_due(site, now=now):
            yield site

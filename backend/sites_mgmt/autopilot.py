"""Autopilot mode: scheduled, hands-off article generation per site.

The user toggles `Site.autopilot_enabled` and picks a weekly cadence
(`autopilot_weekly_count`). A cron job runs `python manage.py run_autopilot`
hourly; this module decides whether each site is due for a new article and
generates one by picking a topic from the site's TrackedKeyword list.

Generated articles always land as **draft** in this slice - the user reviews
before publishing. Auto-publish is a follow-up feature.
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
    error: Optional[str] = None


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


def run_one(site: Site, *, force: bool = False, user=None) -> RunResult:
    """Generate one article for `site` via the autopilot.

    - Respects `is_due` unless `force=True`
    - Picks a tracked keyword (returns skipped if none)
    - Calls the existing ArticleGenerator
    - Updates `autopilot_last_run_at` on success, `autopilot_last_error` on failure
    - Does NOT consume quota (autopilot is run by cron, not on behalf of a user
      action). The site owner's quota is bypassed here - we may revisit this
      when autopilot moves out of beta.
    """
    if not site.autopilot_enabled and not force:
        return RunResult(ok=False, skipped_reason='autopilot_disabled')

    if not force and not is_due(site):
        return RunResult(ok=False, skipped_reason='not_due_yet')

    keyword = pick_next_topic(site)
    if not keyword:
        site.autopilot_last_error = 'Aucun mot-cle tracke disponible pour ce site'
        site.save(update_fields=['autopilot_last_error'])
        return RunResult(ok=False, skipped_reason='no_keyword')

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
        )

    site.autopilot_last_run_at = timezone.now()
    site.autopilot_last_error = ''
    site.save(update_fields=['autopilot_last_run_at', 'autopilot_last_error'])

    return RunResult(
        ok=True,
        topic=keyword.keyword,
        keyword_id=keyword.id,
        post_id=result.get('post_id'),
        post_title=result.get('title'),
    )


def _generate_article(site: Site, keyword: TrackedKeyword) -> dict:
    """Thin wrapper around ArticleGenerator that mirrors GenerateArticleView."""
    from .article_generator import ArticleGenerator
    from .db_utils import ensure_site_connection

    if site.is_hosted or site.is_wordpress or site.is_shopify or site.is_webflow:
        alias = None
    else:
        alias = ensure_site_connection(site)

    generator = ArticleGenerator(
        alias,
        knowledge_base=site.knowledge_base or '',
        wp_site=site if site.is_wordpress else None,
        shopify_site=site if site.is_shopify else None,
        webflow_site=site if site.is_webflow else None,
        site=site,
        default_status='draft',
    )
    out = generator.generate(
        search_method='serper',
        topic=keyword.keyword,
        title=None,
        article_type='guide',
        length='medium',
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
    return {'post_id': post_id, 'title': post_title}


def due_sites(now=None):
    """Iterator over all sites that are currently due for an autopilot run."""
    now = now or timezone.now()
    qs = Site.objects.filter(autopilot_enabled=True, is_active=True)
    for site in qs:
        if is_due(site, now=now):
            yield site

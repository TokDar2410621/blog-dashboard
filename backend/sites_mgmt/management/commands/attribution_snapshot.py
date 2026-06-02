"""Daily cron: snapshot HostedPost attribution at J+30 / J+60 / J+90.

For each horizon, find posts whose `published_at == today - horizon` (within
a 1-day window) and snapshot their GSC metrics. Idempotent via
ArticleAttribution.unique_together(post, days_since_publish).

Usage:
    python manage.py attribution_snapshot              # all sites, all horizons
    python manage.py attribution_snapshot --site 3     # only site id=3
    python manage.py attribution_snapshot --horizon 30 # only J+30 (debug)
    python manage.py attribution_snapshot --post 12 --horizon 60  # one post
"""
from datetime import date, timedelta

from django.core.management.base import BaseCommand

from sites_mgmt.models import HostedPost
from sites_mgmt import proof_loop


class Command(BaseCommand):
    help = (
        'Snapshot AI-generated HostedPost attribution at J+30 / J+60 / J+90. '
        'Idempotent. Designed for daily cron execution.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--site', type=int, default=None,
                            help='Limit to a single site id.')
        parser.add_argument('--horizon', type=int, choices=[30, 60, 90], default=None,
                            help='Only run this horizon (default: all 3).')
        parser.add_argument('--post', type=int, default=None,
                            help='Force a specific HostedPost id (debug). Requires --horizon.')

    def handle(self, *args, **opts):
        site_id = opts.get('site')
        horizon = opts.get('horizon')
        post_id = opts.get('post')

        if post_id:
            if not horizon:
                self.stderr.write(self.style.ERROR('--post requires --horizon'))
                return
            post = HostedPost.objects.filter(pk=post_id).first()
            if not post:
                self.stderr.write(self.style.ERROR(f'Post {post_id} not found'))
                return
            row = proof_loop.snapshot_attribution(post, horizon)
            self.stdout.write(self.style.SUCCESS(
                f'  {"created" if row else "skipped (no GSC/published_at)"} '
                f'attribution J+{horizon} for post {post_id}'
            ))
            return

        horizons = [horizon] if horizon else [30, 60, 90]
        today = date.today()
        total_created = total_skipped = total_failed = 0

        for h in horizons:
            target_date = today - timedelta(days=h)
            qs = (HostedPost.objects
                  .filter(status='published',
                          published_at__gte=target_date - timedelta(days=1),
                          published_at__lte=target_date + timedelta(days=1))
                  .select_related('site'))
            if site_id:
                qs = qs.filter(site_id=site_id)

            count = qs.count()
            self.stdout.write(f'J+{h}: {count} post(s) due (published around {target_date.isoformat()})')

            for post in qs:
                if not (post.site.gsc_property_url and post.site.gsc_refresh_token):
                    total_skipped += 1
                    continue
                try:
                    row = proof_loop.snapshot_attribution(post, h)
                except Exception as e:
                    total_failed += 1
                    self.stderr.write(self.style.WARNING(
                        f'  [err] post={post.id} J+{h}: {type(e).__name__}: {e}'
                    ))
                    continue
                if row is None:
                    total_failed += 1
                else:
                    total_created += 1
                    self.stdout.write(
                        f'  [{post.site.name}] {post.slug} J+{h}: '
                        f'+{row.delta_vs_baseline.get("impressions", 0)} impr.'
                    )

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'Done. {total_created} created, {total_skipped} skipped (no GSC), {total_failed} failed.'
        ))

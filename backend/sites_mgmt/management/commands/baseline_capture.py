"""Capture (or refresh stale) baselines for all GSC-connected sites.

Used as a daily catch-up cron in addition to the on-connect signal: a site
that connects GSC at 3am Quebec time and creates HostedPost an hour later
gets its new posts caught by this cron.

Usage:
    python manage.py baseline_capture              # all sites
    python manage.py baseline_capture --site 3     # only site id=3
    python manage.py baseline_capture --limit 50   # snapshot last 50 posts/site (default 30)
"""
from django.core.management.base import BaseCommand

from sites_mgmt.models import Site
from sites_mgmt import proof_loop


class Command(BaseCommand):
    help = (
        'Capture baseline GSC metrics for every site whose GSC is connected. '
        'Idempotent. Skips posts with a baseline younger than 30 days.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--site', type=int, default=None,
                            help='Limit to a single site id.')
        parser.add_argument('--limit', type=int,
                            default=proof_loop.BASELINE_INITIAL_LIMIT,
                            help='Max posts per site to capture (default 30).')

    def handle(self, *args, **opts):
        site_id = opts.get('site')
        limit = opts.get('limit')

        qs = Site.objects.exclude(gsc_property_url='').exclude(gsc_refresh_token='')
        if site_id:
            qs = qs.filter(id=site_id)

        if not qs.exists():
            self.stdout.write('No GSC-connected sites to process.')
            return

        grand = {'captured': 0, 'skipped': 0, 'failed': 0}
        for site in qs:
            result = proof_loop.capture_baseline(site, limit=limit)
            for k in grand:
                grand[k] += result.get(k, 0)
            self.stdout.write(
                f'  [{site.name}] captured={result.get("captured", 0)} '
                f'skipped={result.get("skipped", 0)} failed={result.get("failed", 0)}'
            )

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'Total: {grand["captured"]} captured, {grand["skipped"]} skipped, '
            f'{grand["failed"]} failed.'
        ))

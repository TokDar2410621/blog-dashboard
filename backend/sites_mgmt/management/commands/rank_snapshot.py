"""Take a SerpRank snapshot for every active TrackedKeyword across all sites.

Designed to run from a daily cron (Railway scheduled job, external cron-job.org
hitting a protected endpoint, or manually `python manage.py rank_snapshot`).

Usage:
    python manage.py rank_snapshot              # all sites
    python manage.py rank_snapshot --site 3     # only site id=3
"""
import os
import logging

from django.core.management.base import BaseCommand
import requests as http_requests

from sites_mgmt.models import Site, TrackedKeyword, SerpRank

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        'Take a SerpRank snapshot for every active tracked keyword. '
        'Stores position 1-100 or NULL when not in top 100. '
        'Designed for daily cron execution.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--site',
            type=int,
            default=None,
            help='Limit to a single site id (default: all sites).',
        )
        parser.add_argument(
            '--keyword',
            type=int,
            default=None,
            help='Limit to a single TrackedKeyword id (debug).',
        )

    def handle(self, *args, **options):
        api_key = os.environ.get('SERPER_API_KEY')
        if not api_key:
            self.stderr.write(self.style.ERROR(
                'SERPER_API_KEY non configurée — abort.'
            ))
            return

        site_filter = options.get('site')
        keyword_filter = options.get('keyword')

        qs = TrackedKeyword.objects.filter(is_active=True)
        if site_filter:
            qs = qs.filter(site_id=site_filter)
        if keyword_filter:
            qs = qs.filter(id=keyword_filter)

        total = qs.count()
        if total == 0:
            self.stdout.write('Aucun mot-clé tracké actif à snapshotter.')
            return

        self.stdout.write(f"Snapshotting {total} tracked keyword(s)...")

        snapshots_created = 0
        not_found_count = 0
        errors = 0

        for tk in qs.select_related('site'):
            site = tk.site
            hl, gl = ('en', 'us') if tk.language == 'en' else (
                ('es', 'es') if tk.language == 'es' else ('fr', 'ca')
            )
            site_domain = (site.domain or '').lower().replace('https://', '').replace('http://', '').rstrip('/')
            target_url_norm = (tk.target_url or '').lower().rstrip('/')

            try:
                resp = http_requests.post(
                    'https://google.serper.dev/search',
                    headers={
                        'X-API-KEY': api_key,
                        'Content-Type': 'application/json',
                    },
                    json={'q': tk.keyword, 'num': 100, 'hl': hl, 'gl': gl},
                    timeout=15,
                )
            except Exception as e:
                errors += 1
                self.stderr.write(self.style.WARNING(
                    f"  Serper error for [{site.name}] '{tk.keyword}': {e}"
                ))
                continue

            if resp.status_code != 200:
                errors += 1
                self.stderr.write(self.style.WARNING(
                    f"  Serper status {resp.status_code} for [{site.name}] '{tk.keyword}'"
                ))
                continue

            organic = (resp.json() or {}).get('organic') or []
            best_hit = None
            for idx, item in enumerate(organic, start=1):
                url = (item.get('link') or '').lower()
                if not url:
                    continue
                if target_url_norm and url.rstrip('/') == target_url_norm:
                    best_hit = (idx, item, True)
                    break
                if site_domain and site_domain in url:
                    best_hit = best_hit or (idx, item, False)

            if best_hit:
                pos, item, is_target = best_hit
                SerpRank.objects.create(
                    tracked=tk,
                    position=pos,
                    url=item.get('link') or '',
                    title=item.get('title') or '',
                    is_target_match=is_target,
                    source='serper',
                )
                snapshots_created += 1
                self.stdout.write(self.style.SUCCESS(
                    f"  ✓ [{site.name}] '{tk.keyword}' → #{pos}{' (target match)' if is_target else ''}"
                ))
            else:
                SerpRank.objects.create(
                    tracked=tk,
                    position=None,
                    url='',
                    title='',
                    is_target_match=False,
                    source='serper',
                )
                not_found_count += 1
                self.stdout.write(
                    f"  - [{site.name}] '{tk.keyword}' → not in top 100"
                )

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f"Done: {snapshots_created} ranked, {not_found_count} out-of-top-100, "
            f"{errors} error(s) of {total} total."
        ))

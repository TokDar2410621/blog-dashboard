"""Cron entry point for the autopilot.

Intended to be run hourly on Railway:

    python manage.py run_autopilot

For each site where autopilot is enabled and is_due, generate one article
in draft. The interval check is in `autopilot.is_due` - this command just
loops over all sites.
"""
import logging

from django.core.management.base import BaseCommand

from sites_mgmt.autopilot import due_sites, run_one

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Run one autopilot iteration per due site (cron entry point).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--site-id', type=int, default=None,
            help='Run only for this site, even if not due (testing/debug).'
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Print what would run without actually generating anything.'
        )

    def handle(self, *args, **options):
        site_id = options.get('site_id')
        dry_run = options.get('dry_run', False)

        if site_id:
            from sites_mgmt.models import Site
            try:
                site = Site.objects.get(id=site_id, is_active=True)
            except Site.DoesNotExist:
                self.stderr.write(self.style.ERROR(f'Site #{site_id} not found or inactive'))
                return
            sites = [site]
        else:
            sites = list(due_sites())

        if not sites:
            self.stdout.write('No sites are due for an autopilot run.')
            return

        self.stdout.write(f'Autopilot: {len(sites)} site(s) to process.')

        for site in sites:
            label = f'#{site.id} "{site.name}"'
            if dry_run:
                self.stdout.write(f'  [dry-run] would run {label}')
                continue

            result = run_one(site, force=bool(site_id))
            if result.ok:
                self.stdout.write(self.style.SUCCESS(
                    f'  [OK] {label}: generated "{result.post_title or result.topic}" (post #{result.post_id})'
                ))
            elif result.skipped_reason:
                self.stdout.write(self.style.WARNING(
                    f'  [skip] {label}: {result.skipped_reason}'
                ))
            else:
                self.stderr.write(self.style.ERROR(
                    f'  [err] {label}: {result.error}'
                ))

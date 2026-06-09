"""Single cron entry point that dispatches all 4 scheduled jobs.

Instead of creating 4 separate Railway cron services (one per command),
deploy ONE service with schedule `*/5 * * * *` and start command
`python manage.py cron_dispatcher`. This file decides which jobs are
due to run based on the current UTC time.

Time-based routing (UTC):

- run_autopilot         : minute == 0       (hourly)
- publish_scheduled     : minute % 15 == 0  (every 15 min)
- rank_snapshot         : hour == 6, minute == 0  (daily 6am UTC = 2am Quebec)
- attribution_snapshot  : hour == 7, minute == 0  (daily 7am UTC = 3am Quebec)
- baseline_capture      : hour == 8, minute == 0  (daily 8am UTC = 4am Quebec)
- send_lead_sequence    : weekday == 0 (Mon), hour == 14, minute == 0

Why the < 5 buffer: the cron service fires at minute 0, 5, 10, ... but
might be delayed by a couple seconds. Using `minute < 5` as the "is this
the firing for that interval?" guard catches the right tick exactly once
per interval without missing it if delayed.
"""
import logging

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Dispatch all due scheduled jobs in a single cron tick. "
        "Schedule this command on Railway with `*/5 * * * *` instead of "
        "running 4 separate cron services."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Print which jobs would run, do not actually call them.'
        )
        parser.add_argument(
            '--force', choices=['autopilot', 'publish', 'rank', 'attribution',
                                'baseline', 'leads', 'all'],
            help='Bypass time gates and run a specific job (or all). For local testing.'
        )

    def handle(self, *args, **opts):
        now = timezone.now()
        dry = opts.get('dry_run', False)
        force = opts.get('force')

        jobs = []
        if force == 'all' or force == 'autopilot' or (force is None and now.minute < 5):
            jobs.append(('run_autopilot', 'hourly'))
        if force == 'all' or force == 'publish' or (force is None and now.minute % 15 < 5):
            jobs.append(('publish_scheduled', 'every 15 min'))
        if force == 'all' or force == 'rank' or (
            force is None and now.hour == 6 and now.minute < 5
        ):
            jobs.append(('rank_snapshot', 'daily 6am UTC'))
        if force == 'all' or force == 'attribution' or (
            force is None and now.hour == 7 and now.minute < 5
        ):
            jobs.append(('attribution_snapshot', 'daily 7am UTC'))
        if force == 'all' or force == 'baseline' or (
            force is None and now.hour == 8 and now.minute < 5
        ):
            jobs.append(('baseline_capture', 'daily 8am UTC'))
        if force == 'all' or force == 'leads' or (
            force is None and now.weekday() == 0 and now.hour == 14 and now.minute < 5
        ):
            jobs.append(('send_lead_sequence', 'Mondays 2pm UTC'))

        if not jobs:
            self.stdout.write(f'[{now.isoformat()}] No jobs due. Skipping.')
            return

        self.stdout.write(
            f'[{now.isoformat()}] Dispatching {len(jobs)} job(s): '
            + ', '.join(name for name, _ in jobs)
        )

        ok_count = 0
        fail_count = 0
        for name, cadence in jobs:
            if dry:
                self.stdout.write(f'  [dry-ok] would run: {name} ({cadence})')
                ok_count += 1
                continue
            self.stdout.write(self.style.SUCCESS(f'  --> {name} ({cadence})'))
            try:
                call_command(name)
                ok_count += 1
                self.stdout.write(self.style.SUCCESS(f'  [ok] {name}'))
            except Exception as e:
                fail_count += 1
                logger.exception('cron_dispatcher: %s failed', name)
                self.stdout.write(self.style.ERROR(
                    f'  [err] {name}: {type(e).__name__}: {e}'
                ))
                self.stderr.write(self.style.ERROR(
                    f'  [err] {name}: {type(e).__name__}: {e}'
                ))

        self.stdout.write(
            f'[{timezone.now().isoformat()}] summary: '
            f'ok={ok_count} fail={fail_count} total={len(jobs)}'
            + (' (dry-run)' if dry else '')
        )

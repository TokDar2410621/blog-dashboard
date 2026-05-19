"""Daily cron: send any due lead-sequence email step.

How to schedule on Railway:
  - Add a cron service in Railway (Settings -> Cron Jobs) or use a long-
    running scheduler service that runs:

        python manage.py send_lead_sequence

  - Recommended cadence: once a day around 09:00 America/Toronto (13:00 UTC
    in winter, 12:00 UTC in summer). The command is idempotent so running
    it twice is safe; we just don't want to spam the user with multiple
    emails the same day.

How to test locally:
  python manage.py send_lead_sequence --dry-run
    Lists what WOULD be sent without actually calling Resend.

  python manage.py send_lead_sequence --lead-id=42
    Sends ALL due steps to a single specific lead, useful for debugging
    a template render or a Resend setup.

The actual send logic + sequence definitions live in
backend/sites_mgmt/email_service.py - this command is just a thin wrapper
around send_due_steps() so the work is testable in isolation.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = (
        "Envoie les emails de la sequence lead (J+1, J+3, J+7, J+14) aux leads "
        "qui sont dus. Idempotent via LeadEmailSent unique constraint."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Liste les sends prevus sans appeler Resend.',
        )
        parser.add_argument(
            '--lead-id', type=int, default=None,
            help='Cible un seul lead (debug). Envoie tous les steps dus pour ce lead.',
        )

    def handle(self, *args, **options):
        from sites_mgmt.email_service import (
            SEQUENCE_STEPS, send_due_steps, send_lead_step,
        )
        from sites_mgmt.models import Lead

        dry_run = options.get('dry_run', False)
        lead_id = options.get('lead_id')

        if lead_id:
            try:
                lead = Lead.objects.get(pk=lead_id)
            except Lead.DoesNotExist:
                self.stderr.write(self.style.ERROR(f'Lead #{lead_id} introuvable.'))
                return

            self.stdout.write(self.style.HTTP_INFO(
                f'Lead #{lead.id} ({lead.email}, domain={lead.domain_audited})'
            ))
            for step in SEQUENCE_STEPS:
                if dry_run:
                    self.stdout.write(f'  [DRY] would send step={step.code} (delay J+{step.delay_days})')
                    continue
                result = send_lead_step(lead, step)
                if result['sent']:
                    self.stdout.write(self.style.SUCCESS(
                        f'  + {step.code} -> sent (id={result["provider_message_id"]})'
                    ))
                else:
                    self.stdout.write(f'  ~ {step.code} -> skipped ({result["reason"]})')
            return

        if dry_run:
            # We can't really dry-run send_due_steps without a side effect
            # (LeadEmailSent insert) since that's what makes it idempotent.
            # Fake it: count what WOULD be considered due.
            from datetime import timedelta
            now = timezone.now()
            for step in SEQUENCE_STEPS:
                if step.delay_days == 0:
                    continue
                threshold = now - timedelta(days=step.delay_days)
                count = Lead.objects.filter(
                    created_at__lte=threshold,
                ).exclude(emails_sent__step=step.code).count()
                # Filter out non-consenting leads for marketing steps.
                if step.code != 'j0_audit_report':
                    count = Lead.objects.filter(
                        created_at__lte=threshold, consented_marketing=True,
                    ).exclude(emails_sent__step=step.code).count()
                self.stdout.write(f'  step={step.code} (J+{step.delay_days}): {count} leads dus')
            self.stdout.write(self.style.HTTP_INFO(
                'Dry-run termine. Relance sans --dry-run pour envoyer.'
            ))
            return

        summary = send_due_steps()
        self.stdout.write(self.style.SUCCESS(
            f'Done. Checked={summary["checked"]}, '
            f'sent={summary["sent"]}, skipped={summary["skipped"]}, '
            f'errors={summary["errors"]}'
        ))
        for step_code, stats in summary['per_step'].items():
            self.stdout.write(f'  {step_code}: {stats}')

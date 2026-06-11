"""Resend wrapper + lead-sequence email definitions.

Single entry point `send_lead_step(lead, step)` :
  - skips if (lead, step) already exists in LeadEmailSent (idempotent)
  - renders subject + html + text from the step definition
  - calls Resend API
  - records the result in LeadEmailSent (success or error)

Provider: Resend (https://resend.com). Free tier = 3000 emails/month,
$20 = 50k. Far cheaper than SendGrid/Mailgun for our volume and the API is
the simplest of the lot (1 POST, JSON in / JSON out).

Env vars required (set on Railway):
  - RESEND_API_KEY  : the API key from Resend dashboard
  - RESEND_FROM     : "Gridar <darius@gridar.app>" (must be on a verified domain)

If RESEND_API_KEY is missing, send_lead_step() logs a warning and short-
circuits. We don't fail loudly because the management command shouldn't
crash a cron tick - the lead just doesn't get the email until the env var
is filled.

Steps are declared inline in SEQUENCE_STEPS below. To add an email, append
a new entry. Each entry has `delay_days` (when after Lead.created_at the
email should fire) and a `render(lead) -> {subject, html, text}` callable.
"""
from __future__ import annotations

import logging
import os
from datetime import timedelta
from typing import Callable, NamedTuple
from urllib.parse import quote

from django.core import signing
from django.template.loader import render_to_string
from django.utils import timezone

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Unsubscribe tokens
# ---------------------------------------------------------------------------
# Signed with the project SECRET_KEY (django.core.signing) so nobody can
# forge an opt-out for an address they don't control from the URL alone.
# No expiry: an unsubscribe link in a 2-year-old email must still work
# (Loi 25 / RGPD - opting out cannot be time-boxed).
#
# Legacy note: emails sent before 2026-06-11 carry a plain ?email= link.
# The unsubscribe endpoint accepts that too - an unverified opt-out is the
# compliant failure mode (worst case someone is unsubscribed by a third
# party; the inverse, a person who CANNOT opt out, is the legal risk).

_UNSUB_SALT = 'sites_mgmt.lead-unsubscribe'


def make_unsubscribe_token(email: str) -> str:
    return signing.dumps((email or '').strip().lower(), salt=_UNSUB_SALT)


def read_unsubscribe_token(token: str) -> str | None:
    """Return the email the token was signed for, or None if invalid."""
    try:
        value = signing.loads(token, salt=_UNSUB_SALT)
    except signing.BadSignature:
        return None
    return value if isinstance(value, str) and '@' in value else None


def apply_unsubscribe(email: str) -> int:
    """Opt the address out of ALL marketing. Updates every Lead row sharing
    the email (one row exists per audit, not per address) so any future
    queryset filtered on unsubscribed_at catches them all. Idempotent.
    Returns the number of rows updated (0 = unknown address or already out -
    callers should NOT leak which, to avoid email enumeration)."""
    from .models import Lead
    return Lead.objects.filter(
        email__iexact=(email or '').strip(),
        unsubscribed_at__isnull=True,
    ).update(unsubscribed_at=timezone.now(), consented_marketing=False)


def unsubscribe_url_for(email: str) -> str:
    """Public landing URL for the footer link. Carries both the signed
    token (authoritative) and the plain email (display + legacy parity)."""
    token = make_unsubscribe_token(email)
    return (
        'https://gridar.app/unsubscribe'
        f'?email={quote(email)}&t={quote(token)}'
    )


class StepDef(NamedTuple):
    code: str
    delay_days: int
    template: str  # base name under sites_mgmt/templates/emails/
    subject: str   # Resend's subject; can include {placeholders} from lead

    def render(self, lead) -> dict:
        ctx = {
            'lead': lead,
            'first_name': (lead.email.split('@')[0].split('.')[0] or 'toi').capitalize(),
            'domain': lead.domain_audited or 'ton site',
            'score': lead.score_at_capture,
            'audit_url': f'https://gridar.app/audit?domain={lead.domain_audited}',
            'signup_url': 'https://gridar.app/login',
            'unsubscribe_url': unsubscribe_url_for(lead.email),
        }
        html = render_to_string(f'emails/{self.template}.html', ctx)
        text = render_to_string(f'emails/{self.template}.txt', ctx)
        subject = self.subject.format(domain=ctx['domain'], first_name=ctx['first_name'])
        return {'subject': subject, 'html': html, 'text': text}


# The funnel. Each step fires once per Lead, delay_days after Lead.created_at.
# - j0 fires immediately (delay 0) - sent inline by PublicLeadCaptureView.
# - all others are picked up by the daily management command `send_lead_sequence`.
SEQUENCE_STEPS: list[StepDef] = [
    StepDef(
        code='j0_audit_report',
        delay_days=0,
        template='lead_j0_audit_report',
        subject='Ton rapport SEO complet de {domain}',
    ),
    StepDef(
        code='j1_competitors',
        delay_days=1,
        template='lead_j1_competitors',
        subject='3 concurrents qui rankent au-dessus de toi',
    ),
    StepDef(
        code='j3_articles_to_write',
        delay_days=3,
        template='lead_j3_articles',
        subject='5 articles a publier ce mois pour reprendre du terrain',
    ),
    StepDef(
        code='j7_case_study',
        delay_days=7,
        template='lead_j7_case_study',
        subject='Comment passer de 47/100 a 78/100 en 90 jours',
    ),
    StepDef(
        code='j14_offer',
        delay_days=14,
        template='lead_j14_offer',
        subject='Premier mois gratuit sur Gridar - sans carte',
    ),
]


def _get_resend_client():
    """Lazy import so the resend package isn't required at module load (e.g.
    during migrations or local dev without the key)."""
    api_key = os.environ.get('RESEND_API_KEY')
    if not api_key:
        return None
    try:
        import resend  # type: ignore[import-not-found]
    except ImportError:
        logger.warning('resend package not installed - skipping email sends')
        return None
    resend.api_key = api_key
    return resend


def send_lead_step(lead, step: StepDef) -> dict:
    """Send one step to one lead. Idempotent via LeadEmailSent unique
    constraint. Returns a dict {sent: bool, reason: str|None,
    provider_message_id: str|None}."""
    from .models import LeadEmailSent  # local import to avoid app-load cycle

    # Idempotency check.
    if LeadEmailSent.objects.filter(lead=lead, step=step.code).exists():
        return {'sent': False, 'reason': 'already_sent', 'provider_message_id': None}

    # Consent gate: marketing-only steps require explicit opt-in. j0 is the
    # transactional report so it doesn't require consent.
    is_marketing = step.code != 'j0_audit_report'
    if is_marketing and not lead.consented_marketing:
        return {'sent': False, 'reason': 'no_marketing_consent', 'provider_message_id': None}

    # Opt-out gate: an unsubscribed address never receives marketing again,
    # regardless of the consent flag captured at the time. j0 stays allowed -
    # it is the report the person just explicitly requested.
    if is_marketing and lead.unsubscribed_at is not None:
        return {'sent': False, 'reason': 'unsubscribed', 'provider_message_id': None}

    resend = _get_resend_client()
    if resend is None:
        # Record a failure row so the cron knows to retry later.
        return {'sent': False, 'reason': 'no_provider_key', 'provider_message_id': None}

    from_addr = os.environ.get('RESEND_FROM', 'Gridar <noreply@gridar.app>')

    try:
        rendered = step.render(lead)
    except Exception as e:
        logger.exception('Render failed for lead %s step %s', lead.id, step.code)
        LeadEmailSent.objects.create(
            lead=lead, step=step.code, subject='',
            error=f'render: {str(e)[:200]}',
        )
        return {'sent': False, 'reason': f'render_failed:{e}', 'provider_message_id': None}

    # RFC 8058 one-click unsubscribe headers. Gmail/Yahoo bulk-sender rules
    # require them for marketing mail; mailbox providers POST to the URL
    # with body "List-Unsubscribe=One-Click" and no cookies, which the
    # public one-click endpoint accepts. Only attached to marketing steps.
    headers = {}
    if is_marketing:
        token = make_unsubscribe_token(lead.email)
        one_click = (
            'https://api.gridar.app/api/public/unsubscribe/one-click/'
            f'?t={quote(token)}'
        )
        headers = {
            'List-Unsubscribe': f'<{one_click}>',
            'List-Unsubscribe-Post': 'List-Unsubscribe=One-Click',
        }

    try:
        payload = {
            'from': from_addr,
            'to': [lead.email],
            'subject': rendered['subject'],
            'html': rendered['html'],
            'text': rendered['text'],
        }
        if headers:
            payload['headers'] = headers
        resp = resend.Emails.send(payload)
        msg_id = resp.get('id', '') if isinstance(resp, dict) else ''
        LeadEmailSent.objects.create(
            lead=lead, step=step.code,
            subject=rendered['subject'][:200],
            provider_message_id=msg_id[:120],
        )
        return {'sent': True, 'reason': None, 'provider_message_id': msg_id}
    except Exception as e:
        logger.warning('Resend send failed for %s step %s: %s', lead.email, step.code, e)
        # Record the attempt so we don't loop forever on the same broken lead.
        # The error field lets us spot it in admin and inspect.
        LeadEmailSent.objects.create(
            lead=lead, step=step.code,
            subject=rendered['subject'][:200] if 'rendered' in locals() else '',
            error=str(e)[:300],
        )
        return {'sent': False, 'reason': f'provider_error:{e}', 'provider_message_id': None}


def send_due_steps(now=None) -> dict:
    """Iterate all leads and send any step that's due based on Lead.created_at.
    Returns a summary dict for the cron command's log output.

    `now` injectable for tests.
    """
    from .models import Lead

    now = now or timezone.now()
    summary = {'checked': 0, 'sent': 0, 'skipped': 0, 'errors': 0, 'per_step': {}}

    for step in SEQUENCE_STEPS:
        if step.delay_days == 0:
            # j0 is sent inline at lead capture, not via cron.
            continue
        threshold = now - timedelta(days=step.delay_days)
        # All cron-driven steps are marketing: don't even iterate leads that
        # opted out (send_lead_step re-checks as a belt-and-suspenders gate).
        due = Lead.objects.filter(
            created_at__lte=threshold,
            unsubscribed_at__isnull=True,
        ).exclude(emails_sent__step=step.code)

        per_step = {'sent': 0, 'skipped': 0, 'errors': 0}
        for lead in due.iterator():
            summary['checked'] += 1
            result = send_lead_step(lead, step)
            if result['sent']:
                per_step['sent'] += 1
                summary['sent'] += 1
            elif result['reason'] in ('already_sent', 'no_marketing_consent', 'unsubscribed'):
                per_step['skipped'] += 1
                summary['skipped'] += 1
            else:
                per_step['errors'] += 1
                summary['errors'] += 1
        summary['per_step'][step.code] = per_step

    return summary

"""Resynchronise local Subscription rows from Stripe.

Needed once after the webhook fix of 2026-09-14: until then every
subscription/invoice webhook crashed silently, so local plans and statuses
may have drifted from Stripe. Reuses the webhook's own handler, so the
mapping (price id -> plan, deleted -> free) stays in one place.

Dry-run by default: prints what would change and rolls back. Pass --apply to
write. Customer ids are masked in the output; no email is printed.
"""
import os

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from sites_mgmt.models import Subscription
from sites_mgmt.views import BillingWebhookView


def _snapshot(sub):
    return {
        'plan': sub.plan,
        'status': sub.status,
        'cancel_at_period_end': sub.cancel_at_period_end,
        'current_period_end': sub.current_period_end,
        'stripe_subscription_id': sub.stripe_subscription_id,
    }


def _mask(customer_id):
    return f'cus_...{customer_id[-4:]}' if customer_id else '(vide)'


# Stripe lists newest first. A failed plan change leaves a newer
# incomplete_expired subscription on top of the live one: taking "newest"
# would downgrade a paying client. Live subscriptions win; newest otherwise.
LIVE_STATUSES = ('active', 'trialing', 'past_due', 'unpaid')


def _pick_subscription(subscriptions):
    live = [s for s in subscriptions if s.get('status') in LIVE_STATUSES]
    if live:
        return live[0]
    return subscriptions[0] if subscriptions else None


class Command(BaseCommand):
    help = 'Resynchronise les abonnements locaux depuis Stripe (dry-run par defaut).'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Ecrire les changements.')

    def handle(self, *args, **options):
        import stripe

        key = os.environ.get('STRIPE_SECRET_KEY')
        if not key:
            raise CommandError('STRIPE_SECRET_KEY absente : resync impossible.')
        stripe.api_key = key

        apply = options['apply']
        view = BillingWebhookView()
        changed = 0

        for sub in Subscription.objects.exclude(stripe_customer_id='').order_by('pk'):
            listing = view._as_plain_dict(
                stripe.Subscription.list(customer=sub.stripe_customer_id, status='all', limit=10)
            )
            remote = _pick_subscription(listing.get('data') or [])
            label = _mask(sub.stripe_customer_id)
            if not remote:
                self.stdout.write(f'{label} : aucun abonnement Stripe, rien a faire')
                continue

            before = _snapshot(sub)
            event_type = (
                'customer.subscription.deleted'
                if remote.get('status') == 'canceled'
                else 'customer.subscription.updated'
            )
            with transaction.atomic():
                view._handle_subscription_event(event_type, remote)
                after = _snapshot(Subscription.objects.get(pk=sub.pk))
                if not apply:
                    transaction.set_rollback(True)

            diff = {k: (before[k], after[k]) for k in before if before[k] != after[k]}
            if diff:
                changed += 1
                details = ', '.join(f'{k}: {a} -> {b}' for k, (a, b) in diff.items())
                verb = 'MIS A JOUR' if apply else 'CHANGERAIT'
                self.stdout.write(f'{label} : {verb} ({details})')
            else:
                self.stdout.write(f'{label} : deja synchronise')

        mode = 'appliques' if apply else 'a appliquer (dry-run, rien ecrit)'
        self.stdout.write(f'Termine : {changed} abonnement(s) {mode}.')

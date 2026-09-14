"""Resynchronise local Subscription rows from Stripe.

Needed after the webhook fix of 2026-09-14: until then every subscription and
invoice webhook crashed silently, so local plans may have drifted from Stripe.
Reuses the webhook's own handler, so the mapping (authoritative subscription,
price id -> plan, no live subscription -> free) stays in one place.

Dry-run by default: prints what would change and rolls back. Pass --apply to
write. A downgrade of a row that already has a Stripe subscription id is only
applied with --include-downgrades; a paid plan with no Stripe subscription id
was granted by hand and is never downgraded here. Customer ids are masked in
the output; no email is printed.
"""
import os
from collections import Counter

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Count

from sites_mgmt.models import Subscription
from sites_mgmt.views import (
    LIVE_SUBSCRIPTION_STATUSES,
    BillingWebhookView,
    pick_authoritative_subscription,
)


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


class Command(BaseCommand):
    help = 'Resynchronise les abonnements locaux depuis Stripe (dry-run par defaut).'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Ecrire les changements.')
        parser.add_argument(
            '--include-downgrades',
            action='store_true',
            help="Appliquer aussi les retrogradations des lignes ayant deja un abonnement Stripe enregistre.",
        )

    def handle(self, *args, **options):
        import stripe

        key = os.environ.get('STRIPE_SECRET_KEY')
        if not key:
            raise CommandError('STRIPE_SECRET_KEY absente : resync impossible.')
        stripe.api_key = key

        apply = options['apply']
        include_downgrades = options['include_downgrades']
        rows = Subscription.objects.exclude(stripe_customer_id='')

        # The webhook syncs only the first row of a customer: with duplicates the
        # others would silently never sync and the report would say "ok".
        doublons = rows.values('stripe_customer_id').annotate(n=Count('id')).filter(n__gt=1)
        if doublons.exists():
            masques = ', '.join(_mask(d['stripe_customer_id']) for d in doublons)
            raise CommandError(
                f"Client(s) Stripe partage(s) par plusieurs lignes ({masques}) : "
                "corriger dans l'admin avant toute resync."
            )

        view = BillingWebhookView()
        compteurs = Counter()

        for sub in rows.order_by('pk'):
            label = _mask(sub.stripe_customer_id)
            try:
                listing = view._as_plain_dict(
                    stripe.Subscription.list(customer=sub.stripe_customer_id, status='all', limit=10)
                )
            except stripe.StripeError as exc:
                compteurs['erreur'] += 1
                self.stdout.write(f'{label} : ERREUR Stripe ({type(exc).__name__}), client ignore')
                continue

            subscriptions = listing.get('data') or []
            if not subscriptions:
                self.stdout.write(f'{label} : aucun abonnement Stripe, rien a faire')
                continue

            choisi = pick_authoritative_subscription(subscriptions)
            if sub.plan != 'free' and choisi.get('status') not in LIVE_SUBSCRIPTION_STATUSES:
                if not sub.stripe_subscription_id:
                    compteurs['hors_stripe'] += 1
                    self.stdout.write(
                        f'{label} : PLAN HORS STRIPE conserve ({sub.plan}, aucun abonnement Stripe vivant) : '
                        'verifier a la main'
                    )
                    continue
                if not include_downgrades:
                    compteurs['attente'] += 1
                    self.stdout.write(
                        f'{label} : RETROGRADATION EN ATTENTE ({sub.plan} -> free) : '
                        'relancer avec --include-downgrades'
                    )
                    continue

            avant = _snapshot(sub)
            with transaction.atomic():
                view._handle_subscription_event(
                    'customer.subscription.updated',
                    {'customer': sub.stripe_customer_id},
                    remote_subscriptions=subscriptions,
                )
                apres = _snapshot(Subscription.objects.get(pk=sub.pk))
                if not apply:
                    transaction.set_rollback(True)

            diff = {k: (avant[k], apres[k]) for k in avant if avant[k] != apres[k]}
            if diff:
                compteurs['change'] += 1
                details = ', '.join(f'{k}: {a} -> {b}' for k, (a, b) in diff.items())
                verbe = 'MIS A JOUR' if apply else 'CHANGERAIT'
                self.stdout.write(f'{label} : {verbe} ({details})')
            else:
                self.stdout.write(f'{label} : deja synchronise')

        mode = 'appliques' if apply else 'a appliquer (dry-run, rien ecrit)'
        self.stdout.write(
            f"Termine : {compteurs['change']} abonnement(s) {mode} ; "
            f"{compteurs['hors_stripe']} plan(s) hors Stripe conserve(s) ; "
            f"{compteurs['attente']} retrogradation(s) en attente ; "
            f"{compteurs['erreur']} erreur(s) Stripe."
        )

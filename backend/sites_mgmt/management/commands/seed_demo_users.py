"""Seed deterministic demo users for E2E tests.

Creates a fixed set of accounts with various plan + quota + credit states so
Cypress (or manual QA) can log in and exercise every UX path. Refuses to run
unless DEBUG=True or ENV in {test, local} - production safety.

Usage:
    python manage.py seed_demo_users
    python manage.py seed_demo_users --reset   # wipe their state first

Idempotent: rerunning leaves users in the same configured state.
"""
from __future__ import annotations

import os

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from sites_mgmt.models import (
    CreditBalance, CreditTransaction, MonthlyArticleQuota,
    Site, Subscription, TrackedKeyword,
)
from sites_mgmt.quota import current_month_key

User = get_user_model()

PASSWORD = 'DemoPass123!'

# Each entry produces one user + one Subscription + optional state overrides.
# `articles_used` and `credits` are the targeted state at the END of seeding;
# the command reaches that state by setting the counter row directly.
DEMO_USERS = [
    {
        'username': 'alice_free',
        'email': 'alice.free@example.test',
        'plan': 'free',
        'articles_used': 0,
        'credits': 0,
        'sites': 0,
        'description': 'Free user, never generated. Quota: 0/1.',
    },
    {
        'username': 'bob_free_exhausted',
        'email': 'bob.free.exhausted@example.test',
        'plan': 'free',
        'articles_used': 1,
        'credits': 0,
        'sites': 1,
        'description': 'Free user with quota exhausted, no credits. Should hit hard block.',
    },
    {
        'username': 'finn_free_with_credits',
        'email': 'finn.free.with.credits@example.test',
        'plan': 'free',
        'articles_used': 1,
        'credits': 5,
        'sites': 1,
        'description': 'Free user, quota done but 5 credits. Should see amber notice.',
    },
    {
        'username': 'carla_solo_warning',
        'email': 'carla.solo.warning@example.test',
        'plan': 'solo',
        'articles_used': 7,
        'credits': 0,
        'sites': 1,
        'description': 'Solo user at 7/8 (87.5%). Should see yellow soft warning.',
    },
    {
        'username': 'david_pro',
        'email': 'david.pro@example.test',
        'plan': 'pro',
        'articles_used': 20,
        'credits': 0,
        'sites': 1,
        'description': 'Pro user at 20/60. Banner hidden. API access enabled.',
    },
    {
        'username': 'eve_agency',
        'email': 'eve.agency@example.test',
        'plan': 'agency',
        'articles_used': 100,
        'credits': 50,
        'sites': 3,
        'description': 'Agency user, 100/200 articles, 50 credits, 3 sites. Power user.',
    },
]


class Command(BaseCommand):
    help = 'Seed deterministic demo users + state for Cypress / manual QA.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset', action='store_true',
            help='Wipe each demo user\'s quota/credits/sites/keywords before reseeding.',
        )

    def handle(self, *args, **options):
        if not self._is_safe_environment():
            raise CommandError(
                'Refusing to run: DEBUG must be True or ENV in {test, local}. '
                'This command MUST NEVER touch production data.'
            )

        reset = options['reset']
        month = current_month_key()

        with transaction.atomic():
            for spec in DEMO_USERS:
                user, created = User.objects.get_or_create(
                    username=spec['username'],
                    defaults={'email': spec['email']},
                )
                user.email = spec['email']
                user.set_password(PASSWORD)
                user.save()

                if reset:
                    MonthlyArticleQuota.objects.filter(user=user).delete()
                    CreditBalance.objects.filter(user=user).delete()
                    CreditTransaction.objects.filter(user=user).delete()
                    # Cascade-delete sites; this also wipes their keywords.
                    Site.objects.filter(owner=user).delete()

                # Subscription
                sub, _ = Subscription.objects.get_or_create(user=user)
                sub.plan = spec['plan']
                sub.status = 'active'
                sub.save()

                # Force monthly quota counter for current month
                if spec['articles_used'] > 0:
                    MonthlyArticleQuota.objects.update_or_create(
                        user=user, month_key=month,
                        defaults={'count': spec['articles_used']},
                    )
                else:
                    MonthlyArticleQuota.objects.filter(
                        user=user, month_key=month
                    ).delete()

                # Credit balance
                if spec['credits'] > 0:
                    bal, _ = CreditBalance.objects.get_or_create(user=user)
                    bal.balance = spec['credits']
                    bal.save()
                    # Drop a single 'gift' txn so the audit log isn't empty
                    if not CreditTransaction.objects.filter(
                        user=user, kind='gift'
                    ).exists():
                        CreditTransaction.objects.create(
                            user=user, amount=spec['credits'], kind='gift',
                            description='Seed for E2E tests',
                        )
                else:
                    CreditBalance.objects.filter(user=user).delete()

                # Sites (placeholder hosted sites)
                existing_sites = Site.objects.filter(
                    owner=user, name__startswith='Demo Site'
                ).count()
                while existing_sites < spec['sites']:
                    n = existing_sites + 1
                    Site.objects.create(
                        owner=user,
                        name=f'Demo Site {n}',
                        domain=f'demo-{user.username}-{n}.example.test',
                        is_active=True,
                    )
                    existing_sites += 1

                tag = 'created' if created else 'updated'
                self.stdout.write(self.style.SUCCESS(
                    f'  {tag} {user.username:30s} ({spec["plan"]:7s}) '
                    f'quota={spec["articles_used"]} credits={spec["credits"]} sites={spec["sites"]}'
                ))
                self.stdout.write(f'    {spec["description"]}')

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'Done. {len(DEMO_USERS)} demo users ready.'
        ))
        self.stdout.write(f'  Password for all: {PASSWORD}')

    @staticmethod
    def _is_safe_environment() -> bool:
        if getattr(settings, 'DEBUG', False):
            return True
        env = (os.environ.get('ENV') or '').lower()
        return env in ('test', 'local', 'development')

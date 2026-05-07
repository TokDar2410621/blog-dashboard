"""Tests for the quota + credits system.

Coverage:
- Per-plan article limits enforced
- Monthly quota auto-resets via month_key change
- Credits fall back when quota exhausted (consume_article)
- add_credits is idempotent on stripe_session_id
- Site + keyword limits enforced + reactivation skips the gate
"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.exceptions import PermissionDenied

from .models import (
    CreditTransaction,
    Site, Subscription, TrackedKeyword,
)
from .quota import (
    add_credits, check_article_quota, check_keyword_quota, check_site_quota,
    consume_article, consume_credit, get_articles_used,
    get_credit_balance, get_keywords_used, get_sites_used,
    increment_article_quota,
)

User = get_user_model()


class QuotaTestBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='alice', password='pwd', email='alice@example.com'
        )
        self.sub, _ = Subscription.objects.get_or_create(user=self.user)


class ArticleQuotaTests(QuotaTestBase):
    def test_free_plan_allows_one_article_then_blocks(self):
        self.sub.plan = 'free'
        self.sub.save()
        # First gen succeeds
        check_article_quota(self.user)  # no raise
        src = consume_article(self.user)
        self.assertEqual(src, 'quota')
        self.assertEqual(get_articles_used(self.user), 1)
        # Second gen blocked: 1/1 used and no credits
        with self.assertRaises(PermissionDenied) as ctx:
            check_article_quota(self.user)
        self.assertIn('1/1', str(ctx.exception))

    def test_solo_plan_allows_eight_articles(self):
        self.sub.plan = 'solo'
        self.sub.save()
        for _ in range(8):
            check_article_quota(self.user)
            consume_article(self.user)
        self.assertEqual(get_articles_used(self.user), 8)
        with self.assertRaises(PermissionDenied):
            check_article_quota(self.user)

    def test_quota_resets_with_new_month(self):
        self.sub.plan = 'free'
        self.sub.save()
        increment_article_quota(self.user)
        self.assertEqual(get_articles_used(self.user), 1)
        # Simulate next month by patching current_month_key
        with patch('sites_mgmt.quota.current_month_key', return_value='2099-01'):
            self.assertEqual(get_articles_used(self.user), 0)
            check_article_quota(self.user)  # no raise
            consume_article(self.user)
            self.assertEqual(get_articles_used(self.user), 1)
        # Original month key still has its 1
        self.assertEqual(get_articles_used(self.user), 1)

    def test_increment_is_atomic_under_repeats(self):
        self.sub.plan = 'pro'
        self.sub.save()
        for _ in range(5):
            increment_article_quota(self.user)
        self.assertEqual(get_articles_used(self.user), 5)


class CreditFallbackTests(QuotaTestBase):
    def test_credits_used_after_monthly_quota(self):
        self.sub.plan = 'free'
        self.sub.save()
        # Burn the monthly quota
        consume_article(self.user)
        self.assertEqual(get_articles_used(self.user), 1)
        # Top up 5 credits
        add_credits(self.user, 5, kind='purchase', stripe_session_id='cs_a')
        self.assertEqual(get_credit_balance(self.user), 5)
        # Generation should succeed via credits now
        check_article_quota(self.user)
        src = consume_article(self.user)
        self.assertEqual(src, 'credit')
        self.assertEqual(get_credit_balance(self.user), 4)
        # Monthly counter unchanged
        self.assertEqual(get_articles_used(self.user), 1)

    def test_check_passes_when_quota_full_but_credits_present(self):
        self.sub.plan = 'free'
        self.sub.save()
        consume_article(self.user)
        with self.assertRaises(PermissionDenied):
            check_article_quota(self.user)
        add_credits(self.user, 1, kind='purchase', stripe_session_id='cs_b')
        check_article_quota(self.user)  # no raise

    def test_quota_bucket_preferred_over_credits(self):
        # User has both quota AND credits → should consume quota first
        self.sub.plan = 'pro'
        self.sub.save()
        add_credits(self.user, 100, kind='purchase', stripe_session_id='cs_c')
        src = consume_article(self.user)
        self.assertEqual(src, 'quota')
        self.assertEqual(get_credit_balance(self.user), 100)


class CreditPurchaseIdempotencyTests(QuotaTestBase):
    def test_replay_same_session_does_not_double_credit(self):
        sid = 'cs_test_replay'
        new_balance = add_credits(
            self.user, 10, kind='purchase',
            stripe_session_id=sid, description='Pack small',
        )
        self.assertEqual(new_balance, 10)
        # Stripe redelivers the same webhook
        replay = add_credits(
            self.user, 10, kind='purchase',
            stripe_session_id=sid, description='Pack small (replay)',
        )
        self.assertEqual(replay, 10)
        # And only one transaction was logged
        self.assertEqual(
            CreditTransaction.objects.filter(
                user=self.user, kind='purchase', stripe_session_id=sid,
            ).count(),
            1,
        )

    def test_distinct_sessions_stack(self):
        add_credits(self.user, 10, kind='purchase', stripe_session_id='cs_1')
        add_credits(self.user, 50, kind='purchase', stripe_session_id='cs_2')
        self.assertEqual(get_credit_balance(self.user), 60)

    def test_consume_credit_fails_when_insufficient(self):
        self.assertEqual(get_credit_balance(self.user), 0)
        self.assertFalse(consume_credit(self.user, 1))
        # No spend transaction was logged on a failed deduction
        self.assertFalse(
            CreditTransaction.objects.filter(user=self.user, kind='spend').exists()
        )

    def test_add_credits_rejects_non_positive_amount(self):
        with self.assertRaises(ValueError):
            add_credits(self.user, 0, kind='purchase')
        with self.assertRaises(ValueError):
            add_credits(self.user, -5, kind='purchase')


class SiteQuotaTests(QuotaTestBase):
    def test_free_plan_blocks_after_one_site(self):
        self.sub.plan = 'free'
        self.sub.save()
        check_site_quota(self.user)  # 0/1 - allowed
        Site.objects.create(owner=self.user, name='s1', is_active=True)
        with self.assertRaises(PermissionDenied) as ctx:
            check_site_quota(self.user)
        self.assertIn('1/1', str(ctx.exception))

    def test_inactive_sites_dont_count(self):
        self.sub.plan = 'free'
        self.sub.save()
        Site.objects.create(owner=self.user, name='s1', is_active=False)
        self.assertEqual(get_sites_used(self.user), 0)
        check_site_quota(self.user)  # passes despite the inactive site

    def test_agency_has_room_up_to_five(self):
        self.sub.plan = 'agency'
        self.sub.save()
        for i in range(4):
            Site.objects.create(owner=self.user, name=f's{i}', is_active=True)
        check_site_quota(self.user)  # 4/5 OK
        Site.objects.create(owner=self.user, name='s5', is_active=True)
        with self.assertRaises(PermissionDenied):
            check_site_quota(self.user)


class KeywordQuotaTests(QuotaTestBase):
    def setUp(self):
        super().setUp()
        self.site = Site.objects.create(
            owner=self.user, name='s1', is_active=True
        )

    def test_free_plan_blocks_zero_keywords(self):
        self.sub.plan = 'free'
        self.sub.save()
        with self.assertRaises(PermissionDenied):
            check_keyword_quota(self.user)

    def test_pro_plan_blocks_at_thirty(self):
        self.sub.plan = 'pro'
        self.sub.save()
        for i in range(30):
            TrackedKeyword.objects.create(
                site=self.site, keyword=f'kw{i}', language='fr',
            )
        with self.assertRaises(PermissionDenied) as ctx:
            check_keyword_quota(self.user)
        self.assertIn('30/30', str(ctx.exception))

    def test_inactive_keywords_dont_count(self):
        self.sub.plan = 'free'
        self.sub.save()
        TrackedKeyword.objects.create(
            site=self.site, keyword='deactivated', language='fr', is_active=False,
        )
        self.assertEqual(get_keywords_used(self.user), 0)
        # Free still has 0 limit, so still raises
        with self.assertRaises(PermissionDenied):
            check_keyword_quota(self.user)

    def test_keywords_aggregate_across_sites(self):
        # User has 2 sites; keywords are summed
        self.sub.plan = 'solo'
        self.sub.save()
        site2 = Site.objects.create(owner=self.user, name='s2', is_active=True)
        for i in range(5):
            TrackedKeyword.objects.create(site=self.site, keyword=f'a{i}', language='fr')
        for i in range(5):
            TrackedKeyword.objects.create(site=site2, keyword=f'b{i}', language='fr')
        self.assertEqual(get_keywords_used(self.user), 10)
        with self.assertRaises(PermissionDenied):
            check_keyword_quota(self.user)


class SubscriptionLimitsTests(QuotaTestBase):
    def test_get_limits_per_plan(self):
        for plan, expected in [
            ('free',   {'sites_max': 1, 'articles_per_month': 1,   'keywords_max': 0}),
            ('solo',   {'sites_max': 1, 'articles_per_month': 8,   'keywords_max': 10}),
            ('pro',    {'sites_max': 2, 'articles_per_month': 60,  'keywords_max': 30}),
            ('agency', {'sites_max': 5, 'articles_per_month': 200, 'keywords_max': 100}),
        ]:
            self.sub.plan = plan
            self.sub.save()
            self.assertEqual(self.sub.get_limits(), expected, msg=f'plan={plan}')

    def test_is_paid_includes_solo(self):
        for plan in ('solo', 'pro', 'agency'):
            self.sub.plan = plan
            self.sub.status = 'active'
            self.sub.save()
            self.assertTrue(self.sub.is_paid, msg=f'plan={plan} should be paid')
        self.sub.plan = 'free'
        self.sub.save()
        self.assertFalse(self.sub.is_paid)

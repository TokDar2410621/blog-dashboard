"""Tests for the proof loop (baseline + attribution).

GSC client is mocked at the `_build_gsc_service` boundary so no network call
runs. All test data is in-memory SQLite (no pgvector / Postgres required).

Run all:
    python manage.py test sites_mgmt.tests_proof_loop
"""
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from .models import (
    ArticleAttribution, ArticleBaseline, HostedPost, ProofShareToken, Site,
)
from . import proof_loop

User = get_user_model()


def _fake_gsc_service(agg_rows=None, query_rows=None):
    """Return a MagicMock that mimics the GSC searchconsole service.

    Two calls per page: first an aggregated query (rowLimit=1), then a top
    queries query (dimensions=['query']). We intercept on the dimensions key
    to route between the two responses.
    """
    svc = MagicMock()

    def execute_side_effect():
        return execute_side_effect.payload

    def query(siteUrl, body):
        resp = MagicMock()
        if 'dimensions' in body and body['dimensions'] == ['query']:
            resp.execute.return_value = {'rows': query_rows or []}
        else:
            resp.execute.return_value = {'rows': agg_rows or []}
        return resp

    svc.searchanalytics.return_value.query.side_effect = query
    return svc


def _make_site(user, gsc=True, name=None):
    import uuid as _uuid
    suffix = (name or _uuid.uuid4().hex[:8])
    site = Site.objects.create(
        owner=user,
        name=f'Test Site {suffix}',
        domain=f'{suffix}.example.com',
        public_blog_domain=f'{suffix}.example.com',
    )
    if gsc:
        site.gsc_property_url = f'sc-domain:{suffix}.example.com'
        site.gsc_refresh_token = 'fake-refresh-token'
        site.save()
    return site


def _make_post(site, slug='hello', published_at=None):
    return HostedPost.objects.create(
        site=site,
        title='Hello World',
        slug=slug,
        excerpt='ex',
        content='body',
        status='published',
        published_at=published_at or date.today(),
    )


class BaselineCaptureTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='u', password='p')
        self.site = _make_site(self.user)
        self.post = _make_post(self.site, slug='post-a',
                               published_at=date.today() - timedelta(days=200))

    @patch.object(proof_loop, '_build_gsc_service')
    def test_baseline_with_data(self, mock_build):
        mock_build.return_value = _fake_gsc_service(
            agg_rows=[{'impressions': 420, 'clicks': 18, 'position': 12.4}],
            query_rows=[
                {'keys': ['seo quebec'], 'impressions': 200, 'clicks': 10, 'position': 8.2},
                {'keys': ['blog ia'], 'impressions': 100, 'clicks': 4, 'position': 14.0},
            ],
        )
        row = proof_loop.capture_baseline_for_post(self.site, self.post, is_pre_gridar=True)
        self.assertIsNotNone(row)
        self.assertEqual(row.impressions, 420)
        self.assertEqual(row.clicks, 18)
        self.assertAlmostEqual(row.avg_position, 12.4)
        self.assertEqual(len(row.top_queries), 2)
        self.assertEqual(row.top_queries[0]['query'], 'seo quebec')
        self.assertTrue(row.is_pre_gridar)

    @patch.object(proof_loop, '_build_gsc_service')
    def test_baseline_unindexed_page(self, mock_build):
        mock_build.return_value = _fake_gsc_service(agg_rows=[], query_rows=[])
        row = proof_loop.capture_baseline_for_post(self.site, self.post)
        self.assertIsNotNone(row)
        self.assertEqual(row.impressions, 0)
        self.assertEqual(row.clicks, 0)
        self.assertIsNone(row.avg_position)
        self.assertEqual(row.top_queries, [])

    @patch.object(proof_loop, '_build_gsc_service')
    def test_baseline_idempotent_within_refresh_window(self, mock_build):
        mock_build.return_value = _fake_gsc_service(
            agg_rows=[{'impressions': 10, 'clicks': 0, 'position': 50}],
        )
        first = proof_loop.capture_baseline_for_post(self.site, self.post)
        second = proof_loop.capture_baseline_for_post(self.site, self.post)
        self.assertEqual(first.id, second.id)
        self.assertEqual(ArticleBaseline.objects.filter(post=self.post).count(), 1)

    @patch.object(proof_loop, '_build_gsc_service')
    def test_baseline_recapture_after_stale(self, mock_build):
        mock_build.return_value = _fake_gsc_service(
            agg_rows=[{'impressions': 50, 'clicks': 2, 'position': 20}],
        )
        first = proof_loop.capture_baseline_for_post(self.site, self.post)
        ArticleBaseline.objects.filter(pk=first.pk).update(
            captured_at=timezone.now() - timedelta(days=40),
        )
        mock_build.return_value = _fake_gsc_service(
            agg_rows=[{'impressions': 200, 'clicks': 8, 'position': 12}],
        )
        second = proof_loop.capture_baseline_for_post(self.site, self.post)
        self.assertNotEqual(first.pk, second.pk)
        self.assertEqual(second.impressions, 200)
        self.assertEqual(ArticleBaseline.objects.filter(post=self.post).count(), 1)

    def test_baseline_skips_when_gsc_not_configured(self):
        site = _make_site(self.user, gsc=False)
        result = proof_loop.capture_baseline(site)
        self.assertEqual(result['reason'], 'gsc_not_configured')

    @patch.object(proof_loop, '_build_gsc_service')
    def test_capture_baseline_bulk(self, mock_build):
        mock_build.return_value = _fake_gsc_service(
            agg_rows=[{'impressions': 100, 'clicks': 5, 'position': 15}],
        )
        for i in range(5):
            _make_post(self.site, slug=f'post-{i}',
                       published_at=date.today() - timedelta(days=10 + i))
        result = proof_loop.capture_baseline(self.site, limit=3)
        self.assertEqual(result['captured'], 3)
        self.assertEqual(result['failed'], 0)


class AttributionSnapshotTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='u', password='p')
        self.site = _make_site(self.user)
        self.post = _make_post(self.site, slug='aip',
                               published_at=date.today() - timedelta(days=30))
        ArticleBaseline.objects.create(
            site=self.site, post=self.post,
            period_start=date.today() - timedelta(days=30),
            period_end=date.today(),
            impressions=0, clicks=0, avg_position=None,
            top_queries=[],
        )

    @patch.object(proof_loop, '_build_gsc_service')
    def test_attribution_30d_with_delta(self, mock_build):
        mock_build.return_value = _fake_gsc_service(
            agg_rows=[{'impressions': 1240, 'clicks': 42, 'position': 7.1}],
            query_rows=[{'keys': ['seo quebec gratuit'], 'impressions': 800, 'clicks': 30, 'position': 5.0}],
        )
        row = proof_loop.snapshot_attribution(self.post, 30)
        self.assertIsNotNone(row)
        self.assertEqual(row.days_since_publish, 30)
        self.assertTrue(row.indexed)
        self.assertEqual(row.impressions, 1240)
        self.assertEqual(row.delta_vs_baseline['impressions'], 1240)
        self.assertEqual(row.delta_vs_baseline['clicks'], 42)

    @patch.object(proof_loop, '_build_gsc_service')
    def test_attribution_idempotent_per_horizon(self, mock_build):
        mock_build.return_value = _fake_gsc_service(
            agg_rows=[{'impressions': 10, 'clicks': 0, 'position': 30}],
        )
        first = proof_loop.snapshot_attribution(self.post, 30)
        second = proof_loop.snapshot_attribution(self.post, 30)
        self.assertEqual(first.id, second.id)
        self.assertEqual(
            ArticleAttribution.objects.filter(post=self.post, days_since_publish=30).count(),
            1,
        )

    def test_invalid_horizon_raises(self):
        with self.assertRaises(ValueError):
            proof_loop.snapshot_attribution(self.post, 45)

    @patch.object(proof_loop, '_build_gsc_service')
    def test_attribution_unindexed(self, mock_build):
        mock_build.return_value = _fake_gsc_service(agg_rows=[], query_rows=[])
        row = proof_loop.snapshot_attribution(self.post, 60)
        self.assertIsNotNone(row)
        self.assertFalse(row.indexed)
        self.assertEqual(row.impressions, 0)

    def test_attribution_skips_without_gsc(self):
        site = _make_site(self.user, gsc=False)
        post = _make_post(site, slug='nogsc',
                          published_at=date.today() - timedelta(days=30))
        row = proof_loop.snapshot_attribution(post, 30)
        self.assertIsNone(row)


class SiteSummaryTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='u', password='p')
        self.site = _make_site(self.user)

    def test_empty_summary(self):
        summary = proof_loop.site_proof_summary(self.site)
        self.assertEqual(summary['total_impressions_gained'], 0)
        self.assertEqual(summary['posts_with_attribution'], 0)
        self.assertEqual(summary['top_gainers'], [])

    def test_summary_aggregates_latest_horizon_per_post(self):
        for i in range(3):
            post = _make_post(self.site, slug=f'p{i}',
                              published_at=date.today() - timedelta(days=90))
            ArticleBaseline.objects.create(
                site=self.site, post=post,
                period_start=date.today() - timedelta(days=90),
                period_end=date.today(),
                impressions=0, clicks=0,
            )
            ArticleAttribution.objects.create(
                post=post, days_since_publish=30,
                period_start=date.today() - timedelta(days=60),
                period_end=date.today() - timedelta(days=30),
                indexed=True, impressions=100 * (i + 1), clicks=5,
                avg_position=20.0,
                delta_vs_baseline={'impressions': 100 * (i + 1), 'clicks': 5, 'avg_position': None},
            )
            ArticleAttribution.objects.create(
                post=post, days_since_publish=60,
                period_start=date.today() - timedelta(days=60),
                period_end=date.today(),
                indexed=True, impressions=300 * (i + 1), clicks=15,
                avg_position=12.0,
                delta_vs_baseline={'impressions': 300 * (i + 1), 'clicks': 15, 'avg_position': None},
            )
        summary = proof_loop.site_proof_summary(self.site)
        self.assertEqual(summary['posts_with_attribution'], 3)
        self.assertEqual(summary['total_impressions_gained'], 300 + 600 + 900)
        self.assertEqual(summary['top_gainers'][0]['impressions_gained'], 900)
        self.assertEqual(summary['top_gainers'][0]['horizon'], 60)
        # The complete list is present and matches the attributed posts.
        self.assertEqual(len(summary['posts']), 3)

    def test_summary_excludes_pre_gridar_posts(self):
        # A page that existed before Gridar (is_pre_gridar baseline) and later
        # gets an attribution must NOT be counted as a Gridar-generated gain.
        pre = _make_post(self.site, slug='pre',
                         published_at=date.today() - timedelta(days=90))
        ArticleBaseline.objects.create(
            site=self.site, post=pre, is_pre_gridar=True,
            period_start=date.today() - timedelta(days=120),
            period_end=date.today() - timedelta(days=90),
            impressions=0, clicks=0,
        )
        ArticleAttribution.objects.create(
            post=pre, days_since_publish=30,
            period_start=date.today() - timedelta(days=60),
            period_end=date.today() - timedelta(days=30),
            indexed=True, impressions=500, clicks=20, avg_position=8.0,
            delta_vs_baseline={'impressions': 500, 'clicks': 20, 'avg_position': None},
        )
        summary = proof_loop.site_proof_summary(self.site)
        self.assertEqual(summary['total_impressions_gained'], 0)
        self.assertEqual(summary['posts_with_attribution'], 0)
        self.assertEqual(summary['posts'], [])
        self.assertEqual(summary['top_gainers'], [])


class ShareTokenTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='u', password='p')
        self.site = _make_site(self.user)

    def test_ensure_creates_then_reuses(self):
        t1 = proof_loop.ensure_proof_token(self.site)
        t2 = proof_loop.ensure_proof_token(self.site)
        self.assertEqual(t1.pk, t2.pk)
        self.assertEqual(t1.token, t2.token)
        self.assertFalse(t1.enabled)

    def test_regenerate_changes_token_keeps_enabled(self):
        t = proof_loop.ensure_proof_token(self.site)
        t.enabled = True
        t.save(update_fields=['enabled'])
        original_token = t.token
        t2 = proof_loop.regenerate_proof_token(self.site)
        self.assertEqual(t.pk, t2.pk)
        self.assertNotEqual(original_token, t2.token)
        self.assertTrue(t2.enabled)

    def test_token_is_url_safe(self):
        t = proof_loop.ensure_proof_token(self.site)
        # secrets.token_urlsafe(32) -> base64url chars only
        for ch in t.token:
            self.assertTrue(ch.isalnum() or ch in '-_')

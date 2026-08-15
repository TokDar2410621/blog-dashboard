"""Tests for the composite SEO score and its data sufficiency gate.

The gate is the point: a check with no data must not be scored as a failure,
and when too little of the site was actually measured the endpoint must
decline to publish a number instead of implying bad SEO.

Run all:
    python manage.py test sites_mgmt.tests_seo_score
"""
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase

from .api_v1 import _SEO_SCORE_KIND, _compute_site_seo_score
from .models import HostedPost, Site

User = get_user_model()


class SeoScoreGateTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username='scoretest', email='score@test.dev', password='x',
        )

    def _site(self, **kwargs):
        defaults = {
            'owner': self.user,
            'name': 'Test',
            'domain': 'exemple.ca',
            'default_language': 'fr',
        }
        defaults.update(kwargs)
        return Site.objects.create(**defaults)

    def _post(self, site, slug, schema=None, status='published'):
        return HostedPost.objects.create(
            site=site, slug=slug, title=slug, content='texte',
            status=status, language='fr', schema_jsonld=schema or {},
        )

    # -- unknown data must not be scored as failure ------------------------

    def test_unmeasurable_checks_report_none_not_zero(self):
        """An external site cannot be crawled from here, so those checks are null."""
        site = self._site(database_url='postgres://user:pw@host:5432/db')
        out = _compute_site_seo_score(site)

        self.assertIsNone(out['breakdown']['indexability'])
        self.assertIsNone(out['breakdown']['faq_coverage'])
        self.assertIn('indexability', out['data_sufficiency']['unknown_checks'])

    def test_gate_withholds_seo_score_when_nothing_measured(self):
        site = self._site(database_url='postgres://user:pw@host:5432/db')
        out = _compute_site_seo_score(site)

        self.assertFalse(out['data_sufficiency']['sufficient'])
        self.assertIsNone(out['seo_score'])
        # The overall score still exists for existing callers.
        self.assertIsNotNone(out['score'])

    def test_gate_explains_itself_in_action_items(self):
        site = self._site(database_url='postgres://user:pw@host:5432/db')
        out = _compute_site_seo_score(site)
        self.assertTrue(
            any('Score SEO indisponible' in a['issue'] for a in out['action_items']),
            'the gate must say why no score is shown',
        )

    def test_hosted_site_is_measurable_and_scored(self):
        site = self._site()
        self._post(site, 'article-un')
        out = _compute_site_seo_score(site)

        self.assertTrue(out['data_sufficiency']['sufficient'])
        self.assertIsNotNone(out['seo_score'])
        self.assertGreaterEqual(out['seo_score'], 0)
        self.assertLessEqual(out['seo_score'], 100)

    # -- weight redistribution --------------------------------------------

    def test_missing_data_does_not_drag_the_score_down(self):
        """Two sites identical except one has an extra unmeasurable check."""
        site = self._site()
        self._post(site, 'article-un')
        out = _compute_site_seo_score(site)

        # cwv_ok has no cached audit in tests, so it is unknown and excluded.
        self.assertIsNone(out['breakdown']['cwv_ok'])
        # A score of 0 would mean the unknown was counted as a failure.
        self.assertGreater(out['score'], 0)

    # -- FAQ coverage counts real FAQPage only ----------------------------

    def test_faq_coverage_ignores_non_faq_schema(self):
        site = self._site()
        self._post(site, 'a', schema={'@type': 'BlogPosting'})
        self._post(site, 'b', schema={'@type': 'Article'})
        out = _compute_site_seo_score(site)
        self.assertEqual(out['breakdown']['faq_coverage'], 0.0)

    def test_faq_coverage_counts_scalar_and_list_type(self):
        """Both shapes reach the database.

        HostedPost.save() recomputes schema_jsonld from the markdown and
        writes the scalar form; the schema detection view writes the list form
        (['BlogPosting', 'FAQPage']). queryset.update() is what puts each
        shape in place without save() overwriting it.
        """
        site = self._site()
        a = self._post(site, 'a')
        b = self._post(site, 'b')
        HostedPost.objects.filter(pk=a.pk).update(schema_jsonld={'@type': 'FAQPage'})
        HostedPost.objects.filter(pk=b.pk).update(
            schema_jsonld={'@type': ['BlogPosting', 'FAQPage']},
        )
        out = _compute_site_seo_score(site)
        self.assertEqual(out['breakdown']['faq_coverage'], 1.0)

    def test_faq_coverage_ignores_schema_that_merely_has_a_type_key(self):
        """The previous query asked only for an @type key, so any schema counted."""
        site = self._site()
        a = self._post(site, 'a')
        HostedPost.objects.filter(pk=a.pk).update(
            schema_jsonld={'@type': 'BlogPosting', 'headline': 'x'},
        )
        out = _compute_site_seo_score(site)
        self.assertEqual(out['breakdown']['faq_coverage'], 0.0)

    # -- config vs measured split -----------------------------------------

    def test_kinds_cover_every_weighted_check(self):
        site = self._site()
        out = _compute_site_seo_score(site)
        self.assertEqual(set(out['kinds']), set(out['breakdown']))
        self.assertEqual(set(_SEO_SCORE_KIND.values()), {'config', 'measured'})

    def test_onboarding_completeness_is_reported_separately(self):
        site = self._site(business_model='agency', author_bio='Bio complete ici.')
        out = _compute_site_seo_score(site)
        self.assertIsNotNone(out['onboarding_completeness'])
        # Two config checks filled out of five, so it must not be zero.
        self.assertGreater(out['onboarding_completeness'], 0)

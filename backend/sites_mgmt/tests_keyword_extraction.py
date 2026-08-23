"""Tests for candidate keyword extraction on the public audit.

The audit picks its own keywords from the page, so a bad pick becomes a false
statement about a stranger's site: "none of your keywords rank" is worthless
when the keywords are "sujet article" and "importe blog".

Run all:
    python manage.py test sites_mgmt.tests_keyword_extraction
"""
from django.test import SimpleTestCase

from .views import _extract_candidate_keywords, _keyword_confidence


class BoilerplateTests(SimpleTestCase):
    """Site furniture recurs on every page, so frequency ranks it first."""

    def test_pure_furniture_yields_nothing(self):
        """Observed on gridar.app: every slot filled with CMS vocabulary."""
        crawl = {
            'title': '', 'h1': '', 'h2_list': [], 'meta_keywords': '',
            'body_snippet': (
                'sujet article article publie sujet article publie importe blog '
                'importe blog article publie sujet article blog sujet'
            ),
        }
        self.assertEqual(_extract_candidate_keywords(crawl), [])

    def test_furniture_never_survives_any_source(self):
        crawl = {
            'title': 'Blog', 'h1': 'Articles publies', 'meta_keywords': '',
            'h2_list': ['Categories', 'Commentaires'], 'body_snippet': '',
        }
        for kw in _extract_candidate_keywords(crawl):
            self.assertNotIn(kw.lower(), {
                'articles publies', 'blog', 'categories', 'commentaires',
            })

    def test_a_real_phrase_containing_one_furniture_word_survives(self):
        """'renovation' must not die because 'projet' sits next to it."""
        crawl = {
            'title': '', 'h1': 'Renovation de toiture residentielle',
            'h2_list': [], 'meta_keywords': '', 'body_snippet': '',
        }
        self.assertTrue(_extract_candidate_keywords(crawl))


class ConfidenceTests(SimpleTestCase):
    """Weak means the keywords are our guess, not the site's own words."""

    def test_trade_named_is_strong(self):
        crawl = {
            'title': 'Line Boivin - Courtiere hypothecaire au Quebec',
            'h1': 'Courtiere hypothecaire', 'h2_list': [], 'meta_keywords': '',
            'body_snippet': '',
        }
        self.assertEqual(_keyword_confidence(crawl), 'strong')

    def test_feminine_and_derived_forms_match_the_lexicon(self):
        """The lexicon is masculine singular; Quebec sites are not."""
        for h1 in ('Courtiere hypothecaire', 'Plomberie residentielle',
                   'Couvreuse et entrepreneure en toiture'):
            crawl = {'title': '', 'h1': h1, 'h2_list': [],
                     'meta_keywords': '', 'body_snippet': ''}
            self.assertEqual(_keyword_confidence(crawl), 'strong', h1)

    def test_slogan_without_a_trade_is_weak(self):
        """Plenty of substantive words, none of them say what is sold."""
        crawl = {
            'title': 'Gridar - Le SEO en francais qui comprend le Quebec',
            'h1': 'Le SEO en francais qui comprend le Quebec',
            'h2_list': [], 'meta_keywords': '', 'body_snippet': '',
        }
        self.assertEqual(_keyword_confidence(crawl), 'weak')

    def test_empty_page_is_weak_not_a_crash(self):
        self.assertEqual(_keyword_confidence({}), 'weak')

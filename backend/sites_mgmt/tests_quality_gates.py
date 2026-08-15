"""Tests for the doorway-page thresholds and per-page quality floors.

Run all:
    python manage.py test sites_mgmt.tests_quality_gates
"""
from django.test import SimpleTestCase

from .quality_gates import (
    LOCATION_HARD_STOP_AT, LOCATION_WARNING_AT, check_location_volume,
    check_page_quality, uniqueness_ratio,
)


class LocationVolumeTests(SimpleTestCase):
    def test_below_warning_is_silent(self):
        gate = check_location_volume(existing=5, adding=1)
        self.assertEqual(gate['level'], 'ok')
        self.assertEqual(gate['message'], '')

    def test_warns_at_threshold(self):
        gate = check_location_volume(existing=LOCATION_WARNING_AT - 1, adding=1)
        self.assertEqual(gate['level'], 'warning')
        self.assertEqual(gate['total'], LOCATION_WARNING_AT)
        self.assertTrue(gate['requirements'])

    def test_hard_stop_at_threshold(self):
        gate = check_location_volume(existing=LOCATION_HARD_STOP_AT - 1, adding=1)
        self.assertEqual(gate['level'], 'hard_stop')
        self.assertIn('presence commerciale reelle', ' '.join(gate['requirements']))

    def test_hard_stop_wins_over_warning(self):
        gate = check_location_volume(existing=200, adding=1)
        self.assertEqual(gate['level'], 'hard_stop')

    def test_negative_input_does_not_crash(self):
        self.assertEqual(check_location_volume(existing=-5, adding=0)['level'], 'ok')


class UniquenessTests(SimpleTestCase):
    TEMPLATE = (
        'Notre equipe de plombiers intervient rapidement chez vous pour toute '
        'urgence. Nous couvrons le secteur de {ville} sept jours sur sept avec '
        'un devis gratuit et sans engagement pour vos travaux.'
    )

    def test_city_swap_scores_near_zero(self):
        """The doorway pattern: identical text, one word changed."""
        a = self.TEMPLATE.format(ville='Jonquiere')
        b = self.TEMPLATE.format(ville='Chicoutimi')
        ratio = uniqueness_ratio(a, [b])
        self.assertLess(ratio, 0.30, f'ratio={ratio}, should read as duplicate')

    def test_genuinely_different_text_scores_high(self):
        a = self.TEMPLATE.format(ville='Jonquiere')
        b = (
            'Le quartier Saint-Dominique concentre des maisons d avant-guerre '
            'dont la tuyauterie en fonte casse chaque hiver. Notre atelier de '
            'la rue Panet garde les pieces de rechange en stock.'
        )
        self.assertGreater(uniqueness_ratio(a, [b]), 0.8)

    def test_no_peers_means_fully_unique(self):
        self.assertEqual(uniqueness_ratio('du texte quelconque ici', []), 1.0)

    def test_empty_text_is_not_unique(self):
        self.assertEqual(uniqueness_ratio('', ['autre chose']), 0.0)


class PageQualityTests(SimpleTestCase):
    def test_flags_thin_page(self):
        findings = check_page_quality('service', text='Trois mots seulement')
        self.assertTrue(any(f['check'] == 'word_count' for f in findings))

    def test_duplicate_location_page_is_an_error_not_a_warning(self):
        """A page whose only variation is the city name.

        Length matters here: on a real page of several hundred words, one
        swapped city moves a handful of shingles out of hundreds, so the ratio
        collapses. On a one-line page it would not, which is why the floors are
        paired with a minimum word count.
        """
        template = (
            'Notre equipe de plombiers certifies intervient rapidement chez vous '
            'pour toute urgence de tuyauterie. Nous couvrons tout le secteur de '
            '{ville} sept jours sur sept, avec un devis gratuit et sans '
            'engagement pour vos travaux de plomberie residentielle et '
            'commerciale. Appelez-nous a toute heure du jour ou de la nuit.'
        )
        findings = check_page_quality(
            'location',
            text=template.format(ville='Jonquiere'),
            peers=[template.format(ville='Chicoutimi')],
        )
        uniqueness = [f for f in findings if f['check'] == 'uniqueness']
        self.assertTrue(uniqueness, 'a city-swapped page must be flagged')
        self.assertEqual(uniqueness[0]['level'], 'error')

    def test_title_and_meta_lengths(self):
        findings = check_page_quality(
            'landing', text='x ' * 700, title='Court', meta_description='Trop court.',
        )
        checks = {f['check'] for f in findings}
        self.assertIn('title_length', checks)
        self.assertIn('meta_length', checks)

    def test_clean_page_passes(self):
        findings = check_page_quality(
            'landing',
            text='mot ' * 700,
            title='Audit SEO gratuit pour les PME du Saguenay',
            meta_description=(
                'Obtiens un audit SEO complet de ton site en trente secondes, '
                'avec ton score, tes positions Google et les correctifs a '
                'appliquer en priorite. Sans inscription.'
            ),
        )
        self.assertEqual(findings, [])

    def test_unknown_page_type_falls_back_to_landing_rules(self):
        findings = check_page_quality('type_inconnu', text='court')
        self.assertTrue(any(f['check'] == 'word_count' for f in findings))

"""Tests for the unsourced-claim detector.

Everything here is offline by construction: content_verify is pure text
processing with no I/O, so there is no network call to mock. The suite is
mostly French because that is what Gridar publishes, and the English cases
guard the parity of the ported patterns.

Run all:
    python manage.py test sites_mgmt.tests_content_verify
"""
from django.test import SimpleTestCase

from .content_verify import (
    CLAIM_KINDS, extract_claims, find_unsourced_claims, verify_text,
)

NBSP = ' '
NARROW_NBSP = ' '


class ClaimAssertions(SimpleTestCase):
    """Shared helpers. Assertion messages stay ASCII so a failure on a
    Windows console never dies re-encoding the French sample."""

    def claims(self, text, lang='fr', **kwargs):
        return find_unsourced_claims(text, lang, **kwargs)

    def assertFlagged(self, text, kind=None, lang='fr', **kwargs):
        found = self.claims(text, lang, **kwargs)
        self.assertTrue(found, 'expected a claim, got none')
        if kind is not None:
            kinds = {claim['kind'] for claim in found}
            self.assertIn(kind, kinds, 'expected kind %s, got %s' % (kind, sorted(kinds)))
        return found

    def assertClean(self, text, lang='fr', **kwargs):
        found = self.claims(text, lang, **kwargs)
        self.assertEqual(
            found, [], 'expected no claim, got %s' % [c['claim'] for c in found],
        )


class FrenchStatisticTests(ClaimAssertions):
    def test_percentage_forms(self):
        for text in (
            'Environ 47 % des PME ferment avant cinq ans.',
            'Environ 47%% des PME ferment.' % (),
            'Environ 47' + NBSP + '% des PME ferment.',
            'Environ 47' + NARROW_NBSP + '% des PME ferment.',
            'Une hausse de 1,5 % a ete mesuree.',
            'Une hausse de 12.5 % a ete mesuree.',
        ):
            self.assertFlagged(text, 'statistic')

    def test_percentage_keeps_its_subject(self):
        found = self.assertFlagged('47 % des PME quebecoises ferment.', 'statistic')
        self.assertIn('des PME', found[0]['claim'])

    def test_proportion_words_without_a_digit(self):
        for text in (
            'La majorite des entreprises negligent leur fiche Google.',
            'La plupart des commerces de quartier ignorent le SEO local.',
            'Pres de la moitie des visiteurs partent en dix secondes.',
            'Les trois quarts des PME n ont pas de strategie.',
        ):
            self.assertFlagged(text, 'statistic')

    def test_ratio_out_of(self):
        self.assertFlagged('8 clients sur 10 abandonnent leur panier.', 'statistic')

    def test_plain_prose_is_left_alone(self):
        self.assertClean(
            'Nous aidons les commerces de quartier a etre trouves sur Google. '
            'Chaque mandat commence par un appel de decouverte.'
        )


class FrenchQuantityTests(ClaimAssertions):
    def test_quebec_money_forms(self):
        for text in (
            'Le marche vaut 45 000 $ par annee.',
            'Un budget de 3 M$ a ete annonce.',
            'Une subvention de 1,5 k$ est disponible.',
            'Le contrat atteint 12000 $.',
            'Un fonds de 45 000 CAD a ete cree.',
        ):
            self.assertFlagged(text, 'quantity')

    def test_english_money_form_still_matches(self):
        self.assertFlagged('The market is worth $3.2 billion today.', 'quantity', 'en')

    def test_small_price_is_not_a_claim(self):
        """A three-digit amount is almost always the site's own price."""
        self.assertClean('Le forfait de base coute 149 $ par mois.')

    def test_large_worded_numbers(self):
        for text in (
            'Nous servons 300 000 utilisateurs actifs.',
            'Une croissance de 1,5 million est prevue.',
            'Le secteur pese 2 milliards en revenus.',
        ):
            self.assertFlagged(text, 'quantity')

    def test_a_year_is_not_a_quantity(self):
        """Without the grouping guard, "2024 marquait" reads as a figure."""
        self.assertClean('2024 marquait un tournant pour le referencement.')


class FrenchAuthorityTests(ClaimAssertions):
    def test_unnamed_authority_is_flagged(self):
        for text in (
            'Selon une etude recente, le contenu long performe mieux.',
            "D'apres plusieurs rapports, le SEO local progresse.",
            'Des etudes recentes montrent que la vitesse compte.',
            "Les experts s'entendent pour dire que le contenu prime.",
            'Il est prouve que la vitesse influence le classement.',
            'Les statistiques montrent une hausse du mobile.',
            'On estime que la moitie du trafic vient du mobile.',
        ):
            self.assertFlagged(text, 'authority')

    def test_named_source_is_not_a_claim(self):
        for text in (
            'Selon Statistique Canada, le commerce en ligne progresse.',
            "D'apres l'Institut de la statistique, la tendance se confirme.",
            'Une etude de Leger montre que la confiance augmente.',
            'Les donnees de Google Search Central le confirment.',
        ):
            self.assertClean(text)

    def test_naming_an_institution_anchors_a_nearby_number(self):
        self.assertClean('Selon Statistique Canada, 47 % des PME ferment.')


class FrenchTemporalTests(ClaimAssertions):
    def test_anchored_dates_are_claims(self):
        for text in (
            'Depuis 2019, Google privilegie les fiches completes.',
            "D'ici 2030, la recherche vocale doublera.",
            'Le 12 mars 2024, Google a deploye la mise a jour.',
            'En mars 2024, le core update a frappe.',
            'Au premier trimestre 2025, le trafic a chute.',
        ):
            self.assertFlagged(text, 'temporal')

    def test_bare_year_is_not_a_claim(self):
        """Every SEO heading carries one, so flagging them buries the rest."""
        for text in (
            'Guide complet du SEO local en 2025.',
            'Les tendances du referencement en 2026 sont claires.',
        ):
            self.assertClean(text)


class FrenchComparativeTests(ClaimAssertions):
    def test_multiplier_forms(self):
        for text in (
            'Nos clients recoivent 3 fois plus d appels.',
            'Deux fois plus rapide que la concurrence.',
            'Le trafic a fait 10x plus en un an.',
            'Le cout represente le double du budget initial.',
        ):
            self.assertFlagged(text, 'comparative')


class FrenchSuperlativeTests(ClaimAssertions):
    def test_absolute_comparatives(self):
        for text in (
            'Gridar est le meilleur outil de SEO local.',
            "C'est la plus grande erreur des PME.",
            'Le seul logiciel concu pour le Quebec.',
            'Nous sommes le no 1 au Quebec.',
            'La reference du marche quebecois.',
        ):
            self.assertFlagged(text, 'superlative')

    def test_adverbial_le_plus_is_not_a_ranking(self):
        for text in (
            "C'est le plus souvent une erreur de configuration.",
            'Publie le plus tot possible apres la redaction.',
            "C'est ce qui vous apprendra le plus sur leur facon de travailler.",
        ):
            self.assertClean(text)

    def test_le_plus_with_an_adjective_is_still_a_ranking(self):
        self.assertFlagged('Nous sommes le plus grand fournisseur au Quebec.',
                           'superlative')

    def test_listicle_numbering_is_not_a_ranking(self):
        self.assertClean('Etape no 1 : verifier la fiche Google.')


class CitationMarkerTests(ClaimAssertions):
    def test_markers_suppress_a_nearby_claim(self):
        for text in (
            '[Le rapport](https://example.com/x) indique 47 % de croissance.',
            '<a href="https://example.com/x">Le rapport</a> indique 47 % de croissance.',
            '47 % des PME ferment avant cinq ans [1].',
            '47 % des PME ferment. https://statcan.gc.ca/rapport',
            '47 % des PME ferment. Source' + NBSP + ': rapport annuel 2024.',
            'Le taux atteint 47 % (Leger, 2024).',
            '47 % des PME ferment. {"@type": "Citation", "name": "x"}',
        ):
            self.assertClean(text)

    def test_citation_outside_the_window_does_not_count(self):
        filler = 'Ce paragraphe sert uniquement de remplissage narratif. ' * 6
        text = '47 % des PME ferment. ' + filler + 'Source : https://statcan.gc.ca/x'
        self.assertFlagged(text, 'statistic')

    def test_citation_in_another_paragraph_does_not_count(self):
        """One named institution must not vouch for the whole article."""
        text = ('Le marche du referencement pese 45 000 000 $ au Quebec.\n\n'
                'Selon Statistique Canada, le commerce en ligne progresse.')
        self.assertFlagged(text, 'quantity')

    def test_citation_in_the_same_paragraph_counts(self):
        text = ('Selon Statistique Canada, le commerce progresse. '
                'Le marche du referencement pese 45 000 000 $ au Quebec.')
        self.assertClean(text)

    def test_window_is_configurable(self):
        filler = 'Ce paragraphe sert uniquement de remplissage narratif. ' * 6
        text = '47 % des PME ferment. ' + filler + 'Source : https://statcan.gc.ca/x'
        self.assertClean(text, window=len(text))


class AccentToleranceTests(ClaimAssertions):
    """CMS exports and plain-text pastes routinely strip the diacritics."""

    def test_both_spellings_are_detected(self):
        pairs = (
            ('Selon une etude, le SEO paie.', 'Selon une étude, le SEO paie.'),
            ('La majorite des PME ferment.', 'La majorité des PME ferment.'),
            ('Il est prouve que la vitesse compte.',
             'Il est prouvé que la vitesse compte.'),
            ('En fevrier 2024, Google a agi.', 'En février 2024, Google a agi.'),
        )
        for bare, accented in pairs:
            self.assertFlagged(bare)
            self.assertFlagged(accented)

    def test_curly_apostrophe_is_accepted(self):
        self.assertFlagged('D’après une étude, le SEO paie.', 'authority')


class OutputShapeTests(ClaimAssertions):
    def test_keys_are_exactly_the_contract(self):
        found = self.assertFlagged('47 % des PME ferment avant cinq ans.')
        self.assertEqual(set(found[0]), {'claim', 'kind', 'position', 'context'})

    def test_kind_is_always_a_known_kind(self):
        text = ('Selon une etude, 47 % des PME ferment. Le marche vaut 45 000 $. '
                'Depuis 2019, cest 3 fois plus. Le meilleur outil du marche.')
        for claim in self.claims(text):
            self.assertIn(claim['kind'], CLAIM_KINDS)

    def test_position_indexes_the_original_text(self):
        text = 'Le rapport annuel indique que 47 % des PME ferment.'
        for claim in self.claims(text):
            self.assertTrue(
                text[claim['position']:].startswith(claim['claim']),
                'position %d does not point at the claim' % claim['position'],
            )

    def test_context_carries_the_surrounding_sentence(self):
        text = ('Un preambule assez long pour depasser le rayon de contexte et '
                'forcer une troncature au debut du passage retourne. '
                'Ensuite, 47 % des PME ferment avant cinq ans. '
                'Et le texte continue encore un long moment apres la '
                'statistique, jusqu au bout du paragraphe, bien au dela du '
                'rayon de contexte prevu par le module.')
        claim = self.claims(text)[0]
        self.assertIn('47 % des PME', claim['context'])
        self.assertTrue(claim['context'].startswith('...'))
        self.assertTrue(claim['context'].endswith('...'))
        self.assertNotIn('\n', claim['context'])

    def test_results_are_sorted_by_position(self):
        text = ('Le marche vaut 45 000 $. Selon une etude, la moitie des PME '
                'ferment. Nos clients font 3 fois plus de ventes.')
        positions = [claim['position'] for claim in self.claims(text)]
        self.assertEqual(positions, sorted(positions))
        self.assertGreaterEqual(len(positions), 3)

    def test_overlapping_patterns_report_one_claim(self):
        """"47 % des PME" is one statistic, not that plus a bare "47 %"."""
        found = self.claims('47 % des PME ferment avant cinq ans.')
        self.assertEqual(len(found), 1, [c['claim'] for c in found])


class LanguageTests(ClaimAssertions):
    def test_english_unnamed_authority_is_flagged(self):
        """Upstream marks this as sourced because its citation patterns run
        case-insensitively against [A-Z]."""
        self.assertFlagged(
            'According to a recent study, 47% of marketers agree.', 'authority', 'en',
        )

    def test_english_named_authority_is_not_flagged(self):
        self.assertClean('According to Gartner, 47% of marketers agree.', 'en')

    def test_english_kinds(self):
        self.assertFlagged('The best tool on the market.', 'superlative', 'en')
        self.assertFlagged('Revenue grew 3x faster than before.', 'comparative', 'en')
        self.assertFlagged('Since 2019, rankings have shifted.', 'temporal', 'en')
        self.assertFlagged('Two thirds of buyers research online.', 'statistic', 'en')

    def test_lang_tags_are_normalized(self):
        for lang in ('fr', 'FR', 'fr-CA', 'fr_ca', ' fr '):
            self.assertFlagged('Selon une etude, le SEO paie.', 'authority', lang)

    def test_unknown_language_keeps_neutral_claims(self):
        self.assertFlagged('El 45 % de las empresas cierran.', 'statistic', 'es')

    def test_unknown_language_keeps_every_citation_marker(self):
        """Unreadable prose should fail toward silence, not toward accusing."""
        self.assertClean('El 45 % de las empresas. Segun Statistique Canada.', 'es')
        self.assertClean('El 45 % de las empresas. According to Gartner.', 'es')

    def test_non_string_lang_falls_back(self):
        self.assertFlagged('El 45 % de las empresas.', 'statistic', None)


class GuardTests(ClaimAssertions):
    def test_empty_and_non_string_inputs(self):
        for value in ('', '   ', '\n\n', None, 42, b'47 %', ['47 %']):
            self.assertEqual(find_unsourced_claims(value), [])
            self.assertEqual(extract_claims(value), [])


class VerifyTextTests(SimpleTestCase):
    def test_counts_and_ratio(self):
        text = ('Selon Statistique Canada, 62 % des PME ferment.\n\n'
                'Un autre paragraphe affirme que la majorite des commerces '
                'ignorent le SEO local et que le marche vaut 45 000 $ par '
                'annee.')
        report = verify_text(text)

        self.assertEqual(report['claim_count'], len(report['claims']))
        self.assertGreater(report['claim_count'], report['unsourced_count'])
        self.assertGreater(report['unsourced_count'], 0)
        self.assertEqual(
            report['unsourced_count'], sum(report['unsourced_by_kind'].values()),
        )
        self.assertTrue(0 < report['unsourced_ratio'] < 1)

    def test_empty_report(self):
        report = verify_text('Aucun chiffre ici, seulement de la prose.')
        self.assertEqual(report['claim_count'], 0)
        self.assertEqual(report['unsourced_ratio'], 0.0)
        self.assertEqual(report['unsourced_by_kind'], {})

    def test_extract_claims_marks_the_sourced_ones(self):
        text = 'Selon Statistique Canada, 62 % des PME ferment.'
        claims = extract_claims(text)
        self.assertTrue(claims)
        self.assertTrue(all(claim['has_citation'] for claim in claims))
        self.assertTrue(all(claim['citation'] for claim in claims))


class GeneratedArticleTests(ClaimAssertions):
    """The case this module exists for: the generator inventing figures."""

    ARTICLE = (
        '# Pourquoi le SEO local est essentiel au Quebec\n\n'
        'La majorite des PME quebecoises n apparaissent pas dans le top 3. '
        'Selon une etude recente, 78 % des recherches locales aboutissent a '
        'une visite en magasin. Le marche du referencement local pese '
        '45 000 000 $ au Quebec.\n\n'
        'Nos clients obtiennent 3 fois plus d appels. Gridar est le meilleur '
        'outil de SEO local.\n\n'
        'D apres Statistique Canada, 62 % des entreprises de moins de 20 '
        'employes n ont pas de site web (Statistique Canada, 2023).\n'
    )

    def test_invented_figures_are_reported(self):
        found = self.claims(self.ARTICLE)
        flagged = ' | '.join(claim['claim'] for claim in found)

        self.assertIn('78', flagged)
        self.assertIn('45 000 000', flagged)
        self.assertIn('3 fois plus', flagged)
        self.assertIn('meilleur', flagged)
        self.assertIn('majorite', flagged)

    def test_the_sourced_figure_is_not_reported(self):
        found = self.claims(self.ARTICLE)
        self.assertNotIn('62', ' | '.join(claim['claim'] for claim in found))

        sourced = [claim for claim in extract_claims(self.ARTICLE)
                   if claim['has_citation']]
        self.assertTrue(any('62' in claim['claim'] for claim in sourced))

    def test_every_kind_of_finding_carries_usable_context(self):
        for claim in self.claims(self.ARTICLE):
            self.assertIn(claim['claim'], claim['context'])

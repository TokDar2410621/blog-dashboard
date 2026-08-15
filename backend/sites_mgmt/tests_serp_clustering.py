"""Tests for SERP overlap clustering.

Everything here is offline by construction: the module never opens a socket,
it only takes SERP results already fetched by the caller. The fixtures are
Quebec queries because the French labels and the accented slugs are part of
what is being tested.

Run all:
    python manage.py test sites_mgmt.tests_serp_clustering
"""
from django.test import SimpleTestCase

from .serp_clustering import (
    DEFAULT_TOP_N, PALIERS, cluster_keywords, normalize_result_url,
    serp_overlap, suggest_internal_links,
)


def _urls(prefix, count, start=1):
    return [f'https://{prefix}{n}.com/page' for n in range(start, start + count)]


class NormalizeResultUrlTests(SimpleTestCase):
    def test_same_page_written_five_ways_collapses(self):
        """The bug this exists to kill: one result counted as several."""
        forms = [
            'https://www.exemple.com/plomberie/',
            'http://exemple.com/plomberie',
            'https://exemple.com/plomberie?utm_source=google&utm_medium=cpc',
            'https://exemple.com/plomberie/index.html',
            'https://EXEMPLE.com/plomberie/amp',
            'https://exemple.com/plomberie?gclid=abc123',
            'exemple.com/plomberie',
        ]
        keys = {normalize_result_url(u) for u in forms}
        self.assertEqual(keys, {'exemple.com/plomberie'})

    def test_percent_encoded_accents_match_decoded(self):
        # Quebec slugs travel both ways through SERP APIs.
        self.assertEqual(
            normalize_result_url('https://ex.com/r%C3%A9f%C3%A9rencement'),
            normalize_result_url('https://ex.com/référencement'),
        )

    def test_keeps_meaningful_query_and_sorts_it(self):
        self.assertEqual(
            normalize_result_url('https://ex.com/blogue?p=2&utm_campaign=x'),
            'ex.com/blogue?p=2',
        )
        self.assertEqual(
            normalize_result_url('https://ex.com/a?b=2&a=1'),
            normalize_result_url('https://ex.com/a?a=1&b=2'),
        )

    def test_distinct_pages_stay_distinct(self):
        self.assertNotEqual(
            normalize_result_url('https://ex.com/plomberie'),
            normalize_result_url('https://ex.com/plomberie-urgence'),
        )
        self.assertNotEqual(
            normalize_result_url('https://ex.com/a'),
            normalize_result_url('https://autre.com/a'),
        )

    def test_accepts_serper_row(self):
        self.assertEqual(
            normalize_result_url({'title': 'T', 'link': 'https://ex.com/x'}),
            'ex.com/x',
        )

    def test_rejects_unusable_input(self):
        for junk in ('', '   ', None, 123, [], {}, {'link': ''},
                     'javascript:alert(1)', 'mailto:a@b.com',
                     'ftp://ex.com/f', '/chemin/relatif', 'localhost/admin'):
            self.assertEqual(normalize_result_url(junk), '', repr(junk))


class SerpOverlapTests(SimpleTestCase):
    def test_identical_serps_mean_one_page(self):
        serp = _urls('site', 10)
        out = serp_overlap(serp, list(serp))
        self.assertEqual(out['communs'], 10)
        self.assertEqual(out['indice'], 1.0)
        self.assertEqual(out['palier'], 'meme_page')
        self.assertEqual(out['action'], 'fusionner')

    def test_thresholds_follow_the_source_bands(self):
        base = _urls('site', 10)
        cases = {8: 'meme_page', 7: 'meme_page', 6: 'meme_page_probable',
                 4: 'meme_page_probable', 3: 'pages_distinctes_maillees',
                 2: 'pages_distinctes_maillees', 1: 'sujets_distincts',
                 0: 'sujets_distincts'}
        for shared, expected in cases.items():
            other = base[:shared] + _urls('autre', 10 - shared)
            out = serp_overlap(base, other)
            self.assertEqual(out['communs'], shared)
            self.assertEqual(out['palier'], expected, f'{shared} communs')

    def test_normalization_is_applied_before_counting(self):
        """Same ten pages, different spellings: still ten, not zero."""
        a = ['https://www.a.com/x/', 'https://b.com/y?utm_source=g',
             'https://c.com/z/index.html']
        b = ['http://a.com/x', 'https://www.b.com/y', 'https://c.com/z/amp']
        out = serp_overlap(a, b)
        self.assertEqual(out['communs'], 3)
        self.assertEqual(out['palier'], 'meme_page')

    def test_partial_serp_is_rescaled_not_penalized(self):
        # Three shared out of five compared is a 6 of 10 relationship, not a 3.
        a = _urls('site', 5)
        b = a[:3] + _urls('autre', 2)
        out = serp_overlap(a, b)
        self.assertEqual(out['communs'], 3)
        self.assertEqual(out['profondeur'], 5)
        self.assertEqual(out['communs_sur_10'], 6)
        self.assertEqual(out['palier'], 'meme_page_probable')
        self.assertTrue(out['donnees_suffisantes'])

    def test_thin_data_is_flagged(self):
        out = serp_overlap(_urls('site', 3), _urls('site', 3))
        self.assertEqual(out['palier'], 'meme_page')
        self.assertFalse(out['donnees_suffisantes'])
        self.assertIn('fragile', out['message'])

    def test_empty_serp_is_undetermined_not_distinct(self):
        out = serp_overlap([], _urls('site', 10))
        self.assertEqual(out['palier'], 'indetermine')
        self.assertEqual(out['action'], 'recolter')
        self.assertEqual(out['communs'], 0)

    def test_duplicates_inside_one_serp_count_once(self):
        a = ['https://a.com/x', 'https://www.a.com/x/', 'https://b.com/y']
        out = serp_overlap(a, ['https://a.com/x', 'https://b.com/y'])
        self.assertEqual(out['taille_a'], 2)
        self.assertEqual(out['communs'], 2)

    def test_top_n_truncates(self):
        base = _urls('site', 10)
        out = serp_overlap(base, base, top_n=3)
        self.assertEqual(out['profondeur'], 3)
        self.assertEqual(out['communs'], 3)

    def test_output_is_french(self):
        out = serp_overlap(_urls('site', 10), _urls('site', 10))
        self.assertIn('résultat', out['message'])
        for text in (out['relation'], out['consequence'], out['message']):
            self.assertNotIn('—', text)
            self.assertNotIn('–', text)


class ClusterKeywordsTests(SimpleTestCase):
    def setUp(self):
        plomberie = _urls('plomberie', 10)
        drain = _urls('drain', 10)
        self.serps = {
            'plombier montréal': plomberie,
            'plombier à montréal': plomberie[:8] + _urls('extra', 2),
            'déboucher un drain': drain,
            'comment déboucher un drain': drain[:8] + _urls('autre', 2),
            'assurance auto': _urls('assurance', 10),
        }

    def _by_pivot(self, out):
        return {c['pivot']: c for c in out['clusters']}

    def test_groups_by_measured_overlap(self):
        out = cluster_keywords(self.serps)
        self.assertEqual(len(out['clusters']), 2)
        pivots = self._by_pivot(out)
        self.assertIn('plombier montréal', pivots)
        self.assertIn('déboucher un drain', pivots)
        self.assertEqual(
            [s['mot_cle'] for s in pivots['plombier montréal']['satellites']],
            ['plombier à montréal'],
        )

    def test_isolated_keyword_becomes_orphan(self):
        out = cluster_keywords(self.serps)
        self.assertEqual([o['mot_cle'] for o in out['orphelins']], ['assurance auto'])
        self.assertEqual(out['orphelins'][0]['communs_sur_10'], 0)
        self.assertEqual(out['orphelins'][0]['palier_voisin'], 'sujets_distincts')
        self.assertIn('seuil', out['orphelins'][0]['raison'])

    def test_orphan_close_to_a_cluster_is_marked_for_interlinking(self):
        base = _urls('site', 10)
        out = cluster_keywords({
            'a': base,
            'b': base[:8] + _urls('x', 2),
            'voisin': base[:2] + _urls('y', 8),
        })
        orphan = out['orphelins'][0]
        self.assertEqual(orphan['mot_cle'], 'voisin')
        self.assertEqual(orphan['palier_voisin'], 'pages_distinctes_maillees')
        self.assertIn(orphan['meilleur_voisin'], ('a', 'b'))

    def test_ids_and_summary(self):
        out = cluster_keywords(self.serps)
        self.assertEqual([c['id'] for c in out['clusters']], ['cluster-1', 'cluster-2'])
        self.assertIn('cluster(s)', out['resume'])
        self.assertEqual(out['parametres']['min_overlap'], 4)

    def test_flags_cannibalization_inside_a_cluster(self):
        out = cluster_keywords(self.serps)
        fusions = self._by_pivot(out)['plombier montréal']['fusions_suggerees']
        self.assertEqual(len(fusions), 1)
        self.assertEqual(
            sorted(fusions[0]['mots_cles']),
            sorted(['plombier montréal', 'plombier à montréal']),
        )
        self.assertIn('cannibaliseraient', fusions[0]['message'])

    def test_no_fusion_flag_below_the_threshold(self):
        base = _urls('site', 10)
        out = cluster_keywords({
            'a': base,
            'b': base[:5] + _urls('autre', 5),
        })
        self.assertEqual(out['clusters'][0]['fusions_suggerees'], [])

    def test_pivot_is_the_most_connected_keyword(self):
        base = _urls('site', 10)
        out = cluster_keywords({
            'satellite un': base[:5] + _urls('x', 5),
            'tete de grappe': base,
            'satellite deux': base[:6] + _urls('y', 4),
        })
        self.assertEqual(len(out['clusters']), 1)
        self.assertEqual(out['clusters'][0]['pivot'], 'tete de grappe')

    def test_every_satellite_is_measured_against_its_pivot(self):
        """No chaining: A joins C's cluster only if A overlaps C itself."""
        a = _urls('a', 10)
        b = a[:5] + _urls('b', 5)
        c = b[5:] + _urls('c', 5)
        out = cluster_keywords({'a': a, 'b': b, 'c': c})
        scores = {kw: i for i, kw in enumerate(out['matrice']['mots_cles'])}
        matrix = out['matrice']['scores']
        for cluster in out['clusters']:
            pivot_i = scores[cluster['pivot']]
            for satellite in cluster['satellites']:
                self.assertGreaterEqual(
                    matrix[pivot_i][scores[satellite['mot_cle']]],
                    out['parametres']['min_overlap'],
                )

    def test_unrelated_pairs_never_merge(self):
        out = cluster_keywords({
            'a': _urls('a', 10),
            'b': _urls('a', 10)[:5] + _urls('x', 5),
            'c': _urls('c', 10),
            'd': _urls('c', 10)[:5] + _urls('y', 5),
        })
        self.assertEqual(len(out['clusters']), 2)
        for cluster in out['clusters']:
            self.assertEqual(cluster['taille'], 2)

    def test_keyword_without_serp_is_reported_separately(self):
        out = cluster_keywords({
            'a': _urls('a', 10),
            'b': _urls('a', 10),
            'sans serp': [],
        })
        self.assertEqual([r['mot_cle'] for r in out['sans_donnees']], ['sans serp'])
        self.assertNotIn('sans serp', out['matrice']['mots_cles'])
        self.assertIn('relancer', out['sans_donnees'][0]['raison'])

    def test_matrix_is_symmetric_with_full_diagonal(self):
        out = cluster_keywords(self.serps)
        scores = out['matrice']['scores']
        size = len(out['matrice']['mots_cles'])
        for i in range(size):
            self.assertEqual(scores[i][i], DEFAULT_TOP_N)
            for j in range(size):
                self.assertEqual(scores[i][j], scores[j][i])

    def test_min_overlap_is_honoured(self):
        base = _urls('site', 10)
        serps = {'a': base, 'b': base[:3] + _urls('z', 7)}
        self.assertEqual(len(cluster_keywords(serps)['clusters']), 0)
        self.assertEqual(len(cluster_keywords(serps, min_overlap=3)['clusters']), 1)

    def test_empty_input_is_safe(self):
        out = cluster_keywords({})
        self.assertEqual(out['clusters'], [])
        self.assertEqual(out['orphelins'], [])
        self.assertEqual(out['matrice']['mots_cles'], [])


class SuggestInternalLinksTests(SimpleTestCase):
    def _payload(self):
        base = _urls('site', 10)
        return cluster_keywords({
            'tete de grappe': base,
            'satellite un': base[:6] + _urls('x', 4),
            'satellite deux': base[:5] + _urls('y', 5),
            'satellite trois': base[:4] + _urls('z', 6),
        })

    def test_pivot_links_go_both_ways_and_are_mandatory(self):
        links = suggest_internal_links(self._payload())
        mandatory = {(l['de'], l['vers']) for l in links if l['obligatoire']}
        for satellite in ('satellite un', 'satellite deux', 'satellite trois'):
            self.assertIn((satellite, 'tete de grappe'), mandatory)
            self.assertIn(('tete de grappe', satellite), mandatory)
        self.assertEqual(len(mandatory), 6)

    def test_anchor_is_the_target_keyword(self):
        for link in suggest_internal_links(self._payload()):
            self.assertEqual(link['ancre'], link['vers'])

    def test_no_self_link_and_no_duplicate(self):
        links = suggest_internal_links(self._payload())
        pairs = [(l['de'], l['vers']) for l in links]
        self.assertEqual(len(pairs), len(set(pairs)))
        for source, target in pairs:
            self.assertNotEqual(source, target)

    def test_sibling_links_are_capped(self):
        links = suggest_internal_links(self._payload(), max_siblings=1)
        siblings = [l for l in links if l['type'] == 'satellite_vers_satellite']
        self.assertEqual(len(siblings), 3)
        for name in ('satellite un', 'satellite deux', 'satellite trois'):
            self.assertEqual(len([l for l in siblings if l['de'] == name]), 1)

    def test_accepts_a_bare_cluster_list(self):
        links = suggest_internal_links([{
            'id': 'cluster-1',
            'pivot': 'pivot',
            'satellites': [{'mot_cle': 's1'}, {'mot_cle': 's2'}],
        }])
        self.assertEqual(len([l for l in links if l['obligatoire']]), 4)
        self.assertEqual(
            len([l for l in links if l['type'] == 'satellite_vers_satellite']), 2,
        )

    def test_cross_cluster_links_come_from_the_2_to_3_band(self):
        pont = _urls('pont', 2)
        a = _urls('a', 10)
        c = _urls('c', 10)
        payload = cluster_keywords({
            'pivot a': a,
            'satellite a': a[:8] + pont,
            'pivot c': c,
            'satellite c': c[:8] + pont,
        })
        links = suggest_internal_links(payload)
        crossed = {(l['de'], l['vers']) for l in links if l['type'] == 'lien_croise'}
        self.assertEqual(
            crossed, {('satellite a', 'satellite c'), ('satellite c', 'satellite a')},
        )
        for link in links:
            if link['type'] == 'lien_croise':
                self.assertFalse(link['obligatoire'])
                self.assertEqual(link['cluster'], 'inter-clusters')

    def test_no_cross_cluster_link_without_a_bridge(self):
        payload = cluster_keywords({
            'pivot a': _urls('a', 10),
            'satellite a': _urls('a', 10)[:8] + _urls('x', 2),
            'pivot c': _urls('c', 10),
            'satellite c': _urls('c', 10)[:8] + _urls('y', 2),
        })
        links = suggest_internal_links(payload)
        self.assertEqual([l for l in links if l['type'] == 'lien_croise'], [])

    def test_empty_input_is_safe(self):
        self.assertEqual(suggest_internal_links(None), [])
        self.assertEqual(suggest_internal_links([]), [])
        self.assertEqual(suggest_internal_links({'clusters': []}), [])

    def test_reasons_are_french(self):
        for link in suggest_internal_links(self._payload()):
            self.assertTrue(link['raison'])
            self.assertNotIn('—', link['raison'])


class SourceHygieneTests(SimpleTestCase):
    def test_no_dash_typography_anywhere_in_the_module(self):
        """House rule: only ASCII hyphens, in code and in strings alike."""
        from . import serp_clustering

        with open(serp_clustering.__file__, encoding='utf-8') as handle:
            source = handle.read()
        self.assertNotIn('—', source)
        self.assertNotIn('–', source)

    def test_palier_table_matches_the_source_bands(self):
        self.assertEqual(
            [(p['min'], p['max']) for p in PALIERS],
            [(7, 10), (4, 6), (2, 3), (0, 1)],
        )

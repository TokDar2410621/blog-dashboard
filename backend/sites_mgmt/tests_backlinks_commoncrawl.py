"""Tests for the Common Crawl domain graph reader.

Everything runs offline. `requests.get` and `requests.head` are patched inside
the module under test and answer with in-memory gzip files built here, so the
real streaming, parsing, budget and sort code is what gets exercised, not a
stand-in. No test touches the network; a call to an unrouted URL raises.

Run all:
    python manage.py test sites_mgmt.tests_backlinks_commoncrawl
"""
import gzip
from datetime import date
from unittest.mock import patch

import requests
from django.test import SimpleTestCase

from . import backlinks_commoncrawl as cc
from .backlinks_commoncrawl import (
    CommonCrawlError, authority_signals, data_freshness, fetch_domain_graph,
    referring_domains,
)

VERSION = 'cc-main-2026-jan-feb-mar'
AUJOURDHUI = date(2026, 8, 14)

# Vertices are sorted on the reversed name, which is what the target lookup
# relies on to prove an absence without reading the whole file.
SOMMETS = (
    '0\tca.gridar\t2\n'
    '1\tca.quebec\t9\n'
    '2\tcom.example\t4\n'
    '3\tcom.zeta\t1\n'
    '4\tnet.autre\t1\n'
)

# from_id -> to_id. Vertex 0 (gridar.ca) is linked from 1, 2 and 3.
ARETES = (
    '1\t0\n'
    '2\t0\n'
    '3\t0\n'
    '4\t2\n'
)

# Ordered by harmonic rank, best first, exactly like the real file.
# com.zeta is deliberately missing: an unranked referrer must still be listed.
CLASSEMENTS = (
    '#harmonicc_pos\tharmonicc_val\tpr_pos\tpr_val\thost_rev\tn_hosts\n'
    '1\t0.94\t1\t0.51\tcom.example\t4\n'
    '5000\t0.42\t4200\t0.02\tca.quebec\t9\n'
    '9000000\t0.01\t8000000\t0.0001\tca.gridar\t2\n'
)


def _gz(texte: str) -> bytes:
    return gzip.compress(texte.encode('utf-8'))


class FakeResponse:
    """Minimal stand-in for a streamed requests.Response."""

    def __init__(self, corps=b'', status=200, content_length=True):
        self._corps = corps
        self.status_code = status
        self.headers = {}
        if content_length:
            self.headers['Content-Length'] = str(len(corps))
        self.closed = False

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f'HTTP {self.status_code}')

    def iter_content(self, chunk_size=1):
        taille = chunk_size or 1
        for debut in range(0, len(self._corps), taille):
            yield self._corps[debut:debut + taille]

    def close(self):
        self.closed = True


def _routes(sommets=SOMMETS, aretes=ARETES, classements=CLASSEMENTS, version=VERSION):
    base = f'{cc.CC_GRAPH_BASE}/{version}/domain/{version}'
    return {
        f'{base}-domain-vertices.txt.gz': _gz(sommets),
        f'{base}-domain-edges.txt.gz': _gz(aretes),
        f'{base}-domain-ranks.txt.gz': _gz(classements),
    }


class _Reseau:
    """Router for the patched requests.get, plus a log of what was fetched."""

    def __init__(self, routes, content_length=True):
        self.routes = routes
        self.content_length = content_length
        self.appels = []

    def get(self, url, **kwargs):
        self.appels.append(url)
        if url not in self.routes:
            raise requests.ConnectionError(f'route absente: {url}')
        return FakeResponse(self.routes[url], content_length=self.content_length)


def _patch(reseau):
    return patch.object(cc.requests, 'get', side_effect=reseau.get)


class NormalisationTests(SimpleTestCase):
    def test_accepte_url_et_domaine(self):
        for brut in (
            'gridar.ca', 'GRIDAR.CA', ' gridar.ca ', 'www.gridar.ca',
            'https://www.gridar.ca/blogue/article?a=1', 'gridar.ca.',
            'https://gridar.ca:8443/',
        ):
            self.assertEqual(cc._normalise_domaine(brut), 'gridar.ca', f'depuis {brut!r}')

    def test_punycode_les_domaines_accentues(self):
        # The graph stores hosts in ASCII, so a Quebec domain written with
        # accents has to be encoded before any comparison.
        self.assertTrue(cc._normalise_domaine('québec.ca').startswith('xn--'))

    def test_refuse_les_entrees_inutilisables(self):
        for brut in ('', '   ', None, 'localhost', 'user@example.com',
                     'http://[::1]/', 42, 'exemple .ca'):
            with self.assertRaises(CommonCrawlError):
                cc._normalise_domaine(brut)

    def test_inversion(self):
        self.assertEqual(cc._inverse('gridar.ca'), 'ca.gridar')
        self.assertEqual(cc._endroit('ca.gridar'), 'gridar.ca')


class VersionTests(SimpleTestCase):
    def test_refuse_une_version_qui_sort_du_chemin(self):
        """The release lands in a URL path, so it is validated before use."""
        for mauvaise in ('../../etc', 'cc-main-2026-jan-feb-mar/../..',
                         'http://evil.test/x', 'cc-main-26-jan', '', None):
            with self.assertRaises(CommonCrawlError):
                cc._valide_version(mauvaise)

    def test_candidates_derivees_du_calendrier(self):
        """August 2026: the running quarter is skipped, apr-may-jun leads."""
        candidates = cc._versions_candidates(date(2026, 8, 15))
        self.assertEqual(candidates[0], 'cc-main-2026-apr-may-jun')
        self.assertEqual(candidates[1], 'cc-main-2026-jan-feb-mar')
        self.assertEqual(candidates[2], 'cc-main-2025-oct-nov-dec')

    def test_candidates_passent_a_lannee_precedente(self):
        candidates = cc._versions_candidates(date(2026, 1, 5))
        self.assertEqual(candidates[0], 'cc-main-2025-oct-nov-dec')

    def test_periode_trimestre(self):
        debut, fin, libelle = cc._periode('cc-main-2026-jan-feb-mar')
        self.assertEqual(debut, date(2026, 1, 1))
        self.assertEqual(fin, date(2026, 3, 31))
        self.assertEqual(libelle, 'janvier à mars 2026')

    def test_periode_a_cheval_sur_deux_annees(self):
        debut, fin, libelle = cc._periode('cc-main-2025-nov-dec-jan')
        self.assertEqual(debut, date(2025, 11, 1))
        self.assertEqual(fin, date(2026, 1, 31))
        self.assertIn('2025 à', libelle)

    def test_periode_fin_decembre(self):
        _debut, fin, _libelle = cc._periode('cc-main-2025-oct-nov-dec')
        self.assertEqual(fin, date(2025, 12, 31))

    def test_periode_inconnue(self):
        self.assertIsNone(cc._periode('cc-main-2026-zzz'))
        self.assertIsNone(cc._periode(None))


class FraicheurTests(SimpleTestCase):
    def test_dit_le_crawl_et_son_age(self):
        fraicheur = data_freshness(VERSION, today=AUJOURDHUI)
        self.assertEqual(fraicheur['periode_libelle'], 'janvier à mars 2026')
        self.assertEqual(fraicheur['age_jours'], (AUJOURDHUI - date(2026, 3, 31)).days)
        self.assertFalse(fraicheur['temps_reel'])
        self.assertIn('trimestre', fraicheur['message'])

    def test_marque_une_version_trop_vieille(self):
        fraicheur = data_freshness('cc-main-2024-oct-nov-dec', today=AUJOURDHUI)
        self.assertTrue(fraicheur['est_perime'])
        self.assertIn('plus récente', fraicheur['message'])

    def test_version_inconnue_ne_ment_pas(self):
        fraicheur = data_freshness(None, today=AUJOURDHUI)
        self.assertIsNone(fraicheur['periode_libelle'])
        self.assertIn('inconnue', fraicheur['message'])

    def test_age_jamais_negatif(self):
        # A reference date before the crawl closed is a clock problem, not a
        # negative age.
        fraicheur = data_freshness(VERSION, today=date(2026, 1, 15))
        self.assertEqual(fraicheur['age_jours'], 0)


class StreamingTests(SimpleTestCase):
    def _lire(self, corps, budget_secondes=30.0, content_length=True):
        reseau = _Reseau({'https://data.commoncrawl.org/x': corps},
                         content_length=content_length)
        budget = cc._Budget(budget_secondes)
        scan = cc._Scan('test', 'https://data.commoncrawl.org/x')
        with _patch(reseau):
            lignes = list(cc._iter_lines('https://data.commoncrawl.org/x', budget, scan))
        return lignes, scan, budget

    def test_decompresse_et_decoupe(self):
        lignes, scan, _ = self._lire(_gz('a\tb\nc\td\n'))
        self.assertEqual(lignes, [b'a\tb', b'c\td'])
        self.assertTrue(scan.termine)
        self.assertEqual(scan.arret, 'fin')
        self.assertEqual(scan.fraction, 1.0)

    def test_derniere_ligne_sans_saut(self):
        lignes, _scan, _ = self._lire(_gz('a\nb'))
        self.assertEqual(lignes, [b'a', b'b'])

    def test_membres_gzip_concatenes(self):
        """Common Crawl builds some of these files by appending parts."""
        lignes, scan, _ = self._lire(_gz('a\n') + _gz('b\n'))
        self.assertEqual(lignes, [b'a', b'b'])
        self.assertTrue(scan.termine)

    def test_erreur_reseau_remonte_dans_le_scan(self):
        reseau = _Reseau({})
        budget = cc._Budget(5.0)
        scan = cc._Scan('test')
        with _patch(reseau):
            lignes = list(cc._iter_lines('https://data.commoncrawl.org/absent',
                                         budget, scan))
        self.assertEqual(lignes, [])
        self.assertEqual(scan.arret, 'erreur')
        self.assertIn('ConnectionError', scan.erreur)
        self.assertFalse(scan.termine)

    def test_budget_epuise_marque_le_scan_incomplet(self):
        lignes, scan, _ = self._lire(_gz('a\nb\n'), budget_secondes=0.0)
        self.assertFalse(scan.termine)
        self.assertEqual(scan.arret, 'budget')
        self.assertEqual(lignes, [b'a', b'b'])  # what the first chunk held

    def test_fraction_inconnue_sans_content_length(self):
        _lignes, scan, _ = self._lire(_gz('a\n'), content_length=False)
        self.assertIsNone(scan.octets_total)
        self.assertEqual(scan.fraction, 1.0)  # finished, so fully read

    def test_gzip_corrompu_ne_leve_pas(self):
        _lignes, scan, _ = self._lire(b'pas du gzip du tout')
        self.assertEqual(scan.arret, 'erreur')
        self.assertIn('gzip', scan.erreur)


class ColonnesTests(SimpleTestCase):
    def test_lit_len_tete(self):
        colonnes = cc._colonnes_classements(
            b'#harmonicc_pos\tharmonicc_val\tpr_pos\tpr_val\thost_rev\tn_hosts')
        self.assertEqual(colonnes['host_rev'], 4)
        self.assertEqual(colonnes['pr_val'], 3)

    def test_supporte_un_ordre_different(self):
        colonnes = cc._colonnes_classements(b'#host_rev\tpr_val\tharmonicc_pos')
        self.assertEqual(colonnes['host_rev'], 0)
        self.assertEqual(colonnes['harmonicc_pos'], 2)

    def test_entete_vide(self):
        self.assertIsNone(cc._colonnes_classements(b'#'))


class SommetsTests(SimpleTestCase):
    def test_layout_avec_identifiant(self):
        self.assertEqual(cc._sommet([b'7', b'ca.gridar', b'2'], 99), (7, b'ca.gridar', 2))

    def test_layout_sans_identifiant(self):
        """Numbering falls back to the line index when the id column is gone."""
        self.assertEqual(cc._sommet([b'ca.gridar', b'2'], 12), (12, b'ca.gridar', 2))

    def test_nom_seul(self):
        self.assertEqual(cc._sommet([b'ca.gridar'], 3), (3, b'ca.gridar', None))


class FetchDomainGraphTests(SimpleTestCase):
    def setUp(self):
        cc._CACHE_VERSION.update({'version': None, 'expire': 0.0})

    def test_lit_les_metriques_du_domaine(self):
        reseau = _Reseau(_routes())
        with _patch(reseau):
            payload = fetch_domain_graph(
                'https://www.gridar.ca/', release=VERSION, time_budget=30.0,
                referents=False, today=AUJOURDHUI,
            )
        self.assertEqual(payload['domaine'], 'gridar.ca')
        self.assertTrue(payload['trouve'])
        self.assertTrue(payload['conclusif'])
        self.assertEqual(payload['centralite_harmonique_rang'], 9000000)
        self.assertEqual(payload['pagerank_rang'], 8000000)
        self.assertAlmostEqual(payload['pagerank'], 0.0001)
        self.assertEqual(payload['nombre_hotes'], 2)
        self.assertEqual(payload['fraicheur']['periode_libelle'], 'janvier à mars 2026')

    def test_absence_prouvee_par_lordre_de_tri(self):
        """A name sorting past the target proves the domain is not in the graph."""
        reseau = _Reseau(_routes())
        with _patch(reseau):
            payload = fetch_domain_graph(
                'aardvark.aa', release=VERSION, time_budget=30.0,
                referents=False, today=AUJOURDHUI,
            )
        self.assertFalse(payload['trouve'])
        self.assertIs(payload['dans_le_graphe'], False)
        self.assertTrue(payload['conclusif'])
        self.assertIn('absent', payload['message'])
        sommets = [e for e in payload['etapes'] if e['nom'] == 'sommets_cible'][0]
        self.assertEqual(sommets['arret'], 'depasse')
        # Only the first line was consumed: the shortcut really fired.
        self.assertEqual(sommets['lignes'], 1)

    def test_budget_epuise_ne_conclut_pas_a_labsence(self):
        """The bug this port fixes: a timeout is not an absence."""
        reseau = _Reseau(_routes())
        with _patch(reseau):
            payload = fetch_domain_graph(
                'zzzz.zz', release=VERSION, time_budget=0.0,
                referents=False, today=AUJOURDHUI,
            )
        self.assertFalse(payload['trouve'])
        self.assertFalse(payload['conclusif'])
        self.assertIsNone(payload['dans_le_graphe'])
        self.assertIn('incomplète', payload['message'])
        self.assertNotIn('absent', payload['message'])

    def test_service_injoignable(self):
        reseau = _Reseau({})
        with _patch(reseau):
            payload = fetch_domain_graph(
                'gridar.ca', release=VERSION, time_budget=5.0,
                referents=False, today=AUJOURDHUI,
            )
        self.assertFalse(payload['trouve'])
        self.assertFalse(payload['conclusif'])
        erreurs = [e['erreur'] for e in payload['etapes'] if e['erreur']]
        self.assertTrue(erreurs)
        # Every read failing is not the same as a read that found nothing.
        self.assertEqual(payload['erreur'], 'lecture_impossible')
        self.assertIn('impossible', payload['message'])

    def test_decouverte_de_version_par_head(self):
        reseau = _Reseau(_routes(version='cc-main-2026-apr-may-jun'))

        def faux_head(url, **kwargs):
            statut = 200 if 'cc-main-2026-apr-may-jun' in url else 404
            return FakeResponse(b'', status=statut)

        with _patch(reseau), patch.object(cc.requests, 'head', side_effect=faux_head):
            payload = fetch_domain_graph(
                'gridar.ca', time_budget=30.0, referents=False,
                today=date(2026, 8, 15),
            )
        self.assertEqual(payload['version'], 'cc-main-2026-apr-may-jun')
        self.assertTrue(payload['trouve'])

    def test_version_memorisee_entre_appels(self):
        reseau = _Reseau(_routes(version='cc-main-2026-apr-may-jun'))
        appels = []

        def faux_head(url, **kwargs):
            appels.append(url)
            return FakeResponse(b'', status=200)

        with _patch(reseau), patch.object(cc.requests, 'head', side_effect=faux_head):
            fetch_domain_graph('gridar.ca', time_budget=30.0, referents=False,
                               today=date(2026, 8, 15))
            fetch_domain_graph('quebec.ca', time_budget=30.0, referents=False,
                               today=date(2026, 8, 15))
        self.assertEqual(len(appels), 1, 'la version doit etre memorisee')

    def test_aucune_version_disponible(self):
        reseau = _Reseau({})
        with _patch(reseau), patch.object(
                cc.requests, 'head', side_effect=requests.ConnectionError('nope')):
            payload = fetch_domain_graph('gridar.ca', time_budget=2.0,
                                         today=AUJOURDHUI)
        self.assertEqual(payload['erreur'], 'version_introuvable')
        self.assertFalse(payload['conclusif'])

    def test_refuse_un_budget_negatif(self):
        with self.assertRaises(ValueError):
            fetch_domain_graph('gridar.ca', time_budget=-1, release=VERSION)

    def test_refuse_une_version_invalide(self):
        with self.assertRaises(CommonCrawlError):
            fetch_domain_graph('gridar.ca', release='../../secret')

    def test_ne_lit_pas_les_aretes_quand_referents_false(self):
        reseau = _Reseau(_routes())
        with _patch(reseau):
            payload = fetch_domain_graph(
                'gridar.ca', release=VERSION, time_budget=30.0,
                referents=False, today=AUJOURDHUI,
            )
        self.assertNotIn('-domain-edges.txt.gz',
                         ' '.join(reseau.appels))
        self.assertEqual(payload['domaines_referents'], [])


class ReferringDomainsTests(SimpleTestCase):
    def setUp(self):
        cc._CACHE_VERSION.update({'version': None, 'expire': 0.0})

    def _run(self, **kwargs):
        reseau = _Reseau(kwargs.pop('routes', None) or _routes())
        options = {'release': VERSION, 'time_budget': 30.0, 'today': AUJOURDHUI}
        options.update(kwargs)
        with _patch(reseau):
            return referring_domains('gridar.ca', **options), reseau

    def test_liste_triee_par_autorite(self):
        resultat, _ = self._run()
        noms = [d['domaine'] for d in resultat['domaines_referents']]
        self.assertEqual(noms, ['example.com', 'quebec.ca', 'zeta.com'])
        self.assertEqual(resultat['nombre_total'], 3)
        self.assertEqual(resultat['liens_entrants_detectes'], 3)
        self.assertTrue(resultat['complet'])
        self.assertFalse(resultat['tronquee'])

    def test_metriques_attachees_a_chaque_referent(self):
        resultat, _ = self._run()
        premier = resultat['domaines_referents'][0]
        self.assertEqual(premier['centralite_harmonique_rang'], 1)
        self.assertEqual(premier['niveau'], 'mondiale')
        self.assertTrue(premier['autorite_lue'])

    def test_referent_non_classe_reste_dans_la_liste(self):
        """Unranked is not the same as absent: zeta.com links, it just has no rank."""
        resultat, _ = self._run()
        dernier = resultat['domaines_referents'][-1]
        self.assertEqual(dernier['domaine'], 'zeta.com')
        self.assertIsNone(dernier['centralite_harmonique_rang'])
        self.assertEqual(dernier['niveau'], 'non_classe')
        self.assertFalse(dernier['autorite_lue'])

    def test_limite_tronque_sans_mentir_sur_le_total(self):
        resultat, _ = self._run(limit=2)
        self.assertEqual(resultat['nombre'], 2)
        self.assertEqual(resultat['nombre_total'], 3)
        self.assertTrue(resultat['tronquee'])
        self.assertIn('plus forts', resultat['message'])

    def test_message_dit_lecture_complete(self):
        resultat, _ = self._run()
        self.assertIn('lecture complète', resultat['message'])
        self.assertIn('janvier à mars 2026', resultat['message'])

    def test_zero_reel_quand_la_lecture_est_complete(self):
        resultat, _ = self._run(routes=_routes(aretes='4\t2\n'))
        self.assertEqual(resultat['nombre_total'], 0)
        self.assertTrue(resultat['complet'])
        self.assertIn('le zéro est réel', resultat['message'])

    def test_budget_epuise_avant_les_liens(self):
        """Nothing was read of the edges file, so the list is not a zero."""
        resultat, _ = self._run(time_budget=0.0)
        self.assertFalse(resultat['complet'])
        self.assertEqual(resultat['domaines_referents'], [])
        self.assertIn('non établie', resultat['message'])
        self.assertNotIn('lecture complète', resultat['message'])

    def test_lecture_partielle_des_liens_donne_un_plancher(self):
        """Cut in the middle of the edges file: a floor, never a total.

        Truncation is forced on the byte ceiling rather than on the clock so
        the test stays deterministic on a slow machine. The edges fixture is
        made large on purpose, which is also the real proportion: the edges
        file dwarfs the other two.
        """
        routes = _routes(aretes=''.join(f'{i}\t0\n' for i in range(10, 3010)))
        base = f'{cc.CC_GRAPH_BASE}/{VERSION}/domain/{VERSION}'
        plafond = (len(routes[f'{base}-domain-ranks.txt.gz'])
                   + len(routes[f'{base}-domain-vertices.txt.gz'])
                   + len(routes[f'{base}-domain-edges.txt.gz']) // 2)
        with patch.object(cc, '_TAILLE_MORCEAU', 64), \
                patch.object(cc, '_MAX_OCTETS', plafond):
            resultat, _ = self._run(routes=routes)
        self.assertFalse(resultat['complet'])
        self.assertIn('plancher', resultat['message'])
        aretes = [e for e in resultat['etapes'] if e['nom'] == 'aretes'][0]
        self.assertFalse(aretes['terminee'])
        self.assertEqual(aretes['arret'], 'octets')
        self.assertLess(aretes['fraction'], 1.0)
        # Links were seen even though their names never got resolved.
        self.assertGreater(resultat['liens_entrants_detectes'], 0)

    def test_fichier_de_liens_injoignable(self):
        routes = _routes()
        del routes[f'{cc.CC_GRAPH_BASE}/{VERSION}/domain/{VERSION}-domain-edges.txt.gz']
        resultat, _ = self._run(routes=routes)
        self.assertFalse(resultat['complet'])
        self.assertIn('plancher', resultat['message'])

    def test_domaine_absent_du_graphe(self):
        reseau = _Reseau(_routes())
        with _patch(reseau):
            resultat = referring_domains('aardvark.aa', release=VERSION,
                                         time_budget=30.0, today=AUJOURDHUI)
        self.assertEqual(resultat['domaines_referents'], [])
        self.assertIs(resultat['dans_le_graphe'], False)
        self.assertIn('absent', resultat['message'])

    def test_layout_de_sommets_sans_identifiant(self):
        """Same answer when the vertices file numbers rows implicitly."""
        sommets = ('ca.gridar\t2\nca.quebec\t9\ncom.example\t4\n'
                   'com.zeta\t1\nnet.autre\t1\n')
        resultat, _ = self._run(routes=_routes(sommets=sommets))
        noms = [d['domaine'] for d in resultat['domaines_referents']]
        self.assertEqual(noms, ['example.com', 'quebec.ca', 'zeta.com'])

    def test_autorite_de_la_cible_incluse(self):
        resultat, _ = self._run()
        # gridar.ca sits at harmonic rank 9 000 000 in the fixture.
        self.assertEqual(resultat['autorite']['niveau'], 'moyenne')
        self.assertTrue(resultat['autorite']['fiable'])

    def test_refuse_une_limite_invalide(self):
        for mauvaise in (0, -3, 'dix', 2.5, True):
            with self.assertRaises(ValueError):
                referring_domains('gridar.ca', limit=mauvaise, release=VERSION)

    def test_etapes_exposent_la_couverture(self):
        resultat, _ = self._run()
        noms = {e['nom'] for e in resultat['etapes']}
        self.assertIn('aretes', noms)
        self.assertIn('classements_referents', noms)
        for etape in resultat['etapes']:
            self.assertIn('fraction', etape)
            self.assertIn('octets_lus', etape)
        self.assertIn('budget_epuise', resultat['couverture'])


class AuthoritySignalsTests(SimpleTestCase):
    def test_niveaux_par_palier(self):
        attendus = [
            (1, 'mondiale'), (10_000, 'mondiale'), (10_001, 'tres_forte'),
            (100_000, 'tres_forte'), (500_000, 'forte'), (1_000_000, 'forte'),
            (5_000_000, 'moyenne'), (10_000_000, 'moyenne'),
            (50_000_000, 'faible'),
        ]
        for rang, niveau in attendus:
            signaux = authority_signals({'centralite_harmonique_rang': rang})
            self.assertEqual(signaux['niveau'], niveau, f'rang {rang}')

    def test_centralite_prioritaire_sur_pagerank(self):
        # Common Crawl recommends harmonic centrality over PageRank at web
        # scale, so the level follows it even when PageRank flatters.
        signaux = authority_signals({
            'centralite_harmonique_rang': 50_000, 'pagerank_rang': 900,
        })
        self.assertEqual(signaux['primaire'], 'centralite_harmonique')
        self.assertEqual(signaux['niveau'], 'tres_forte')
        self.assertEqual(signaux['signaux']['pagerank']['niveau'], 'mondiale')

    def test_bascule_sur_pagerank_si_centralite_absente(self):
        signaux = authority_signals({'pagerank_rang': 900})
        self.assertEqual(signaux['primaire'], 'pagerank')
        self.assertEqual(signaux['niveau'], 'mondiale')

    def test_pas_de_percentile_sans_denominateur(self):
        """A percentile over an invented total would be a fabricated number."""
        signaux = authority_signals({'centralite_harmonique_rang': 1_000_000})
        self.assertIsNone(signaux['percentile'])
        self.assertFalse(signaux['signaux']['centralite_harmonique']
                         ['percentile_disponible'])

    def test_percentile_quand_le_total_est_fourni(self):
        signaux = authority_signals(
            {'centralite_harmonique_rang': 1_000_000}, total_domains=100_000_000)
        self.assertEqual(signaux['percentile'], 99.0)
        self.assertIn('99,0 %', signaux['resume'])

    def test_non_classe_conclusif(self):
        signaux = authority_signals({'trouve': False, 'conclusif': True})
        self.assertEqual(signaux['niveau'], 'non_classe')
        self.assertTrue(signaux['fiable'])
        self.assertIn('absent des classements', signaux['resume'])

    def test_inconnu_quand_la_lecture_na_pas_conclu(self):
        signaux = authority_signals({'trouve': False, 'conclusif': False})
        self.assertEqual(signaux['niveau'], 'inconnu')
        self.assertFalse(signaux['fiable'])
        self.assertIn('inconnue', signaux['resume'])

    def test_accepte_une_entree_de_domaine_referent(self):
        """One referring-domain entry has the same metric keys, so it just works."""
        entree = {'domaine': 'example.com', 'centralite_harmonique_rang': 1,
                  'pagerank_rang': 1}
        self.assertEqual(authority_signals(entree)['niveau'], 'mondiale')

    def test_refuse_autre_chose_quun_dict(self):
        with self.assertRaises(TypeError):
            authority_signals(['gridar.ca'])


class SortiesFrancaisesTests(SimpleTestCase):
    """User-facing strings are French and carry no em dash."""

    def _textes(self):
        reseau = _Reseau(_routes())
        with _patch(reseau):
            complet = referring_domains('gridar.ca', release=VERSION,
                                        time_budget=30.0, today=AUJOURDHUI)
            partiel = referring_domains('gridar.ca', release=VERSION,
                                        time_budget=0.0, today=AUJOURDHUI)
            absent = fetch_domain_graph('aardvark.aa', release=VERSION,
                                        time_budget=30.0, today=AUJOURDHUI)
        return [
            complet['message'], complet['fraicheur']['message'],
            complet['autorite']['resume'], partiel['message'],
            absent['message'],
            data_freshness('cc-main-2024-jan-feb-mar', today=AUJOURDHUI)['message'],
            data_freshness(None, today=AUJOURDHUI)['message'],
            authority_signals({'conclusif': False})['resume'],
        ]

    def test_aucun_tiret_cadratin(self):
        # Escaped rather than written out so the forbidden characters do not
        # appear in the source either.
        for texte in self._textes():
            self.assertNotIn('\u2014', texte)
            self.assertNotIn('\u2013', texte)

    def test_messages_non_vides(self):
        for texte in self._textes():
            self.assertTrue(texte.strip())

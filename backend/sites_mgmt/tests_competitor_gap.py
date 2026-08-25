"""Tests : Competitor Gap Finder, decouverte de concurrents et ecarts.

Contexte du 2026-08-25. L'outil ne trouvait JAMAIS un seul concurrent en
production, tout en depensant une vingtaine de credits Serper par appel.

La chaine de l'echec, verifiee en prod sur tokamdarius.ca ET notion.so, les
deux rendant `competitors_detected: []` et `total_gaps: 0` :

  1. Un appel Serper `site:{domaine}` pour amorcer la decouverte.
  2. Lecture de `relatedSearches` dans la reponse. Or Serper n'inclut PAS
     cette cle sur une requete `site:` : les seules cles rendues sont
     `credits`, `organic` et `searchParameters`. Donc `[]`, sans erreur.
  3. `if related_queries:` faux, tout le bloc de decouverte saute.
  4. `competitors` reste vide.
  5. Le code continuait quand meme : 20 appels Serper en parallele.
  6. `if host in competitors` sur une liste vide, jamais vrai. Zero ecart.

~21 credits brules pour un `total_gaps: 0` structurellement garanti, presente
au visiteur comme un resultat, donc lisible comme "ton site n'a aucun retard".

La correction derive TOUT d'une seule passe de SERP : positions du domaine,
concurrents (par frequence d'apparition) et ecarts.

LIMITE CONNUE, ASSUMEE
----------------------
La decouverte remonte parfois des hotes qui ne sont pas des concurrents
actionnables : sites d'emploi sur une requete metier, annuaires de logiciels
sur une requete produit. Une liste noire de domaines a ete essayee puis
RETIREE : une liste maintenue a la main n'est jamais complete, et chaque site
rencontre en ajoute un, ce qui revient a coder pour chaque cas particulier.
Aucun test ici ne verifie donc l'exclusion d'un domaine nomme. Le probleme
reel est en amont (l'intention de la requete), voir la docstring de
`decouvrir_concurrents`.

Run: python manage.py test sites_mgmt.tests_competitor_gap
"""
from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test import SimpleTestCase, TestCase

from .compare_mesures import (
    collecter_serps, decouvrir_concurrents, trouver_ecarts,
)


def serp(requete, hotes):
    """Un SERP verifie : hotes = liste de (hote, rang)."""
    return {
        'requete': requete,
        'verifie': True,
        'hotes': list(hotes),
        'resultats': [
            {'hote': h, 'position': r, 'url': f'https://{h}/p', 'titre': f'{h} page'}
            for h, r in hotes
        ],
    }


# ---------------------------------------------------------------------------
class DecouvrirConcurrentsTests(SimpleTestCase):

    def test_un_hote_recurrent_est_retenu(self):
        serps = [
            serp('q1', [('rival.ca', 1), ('moi.ca', 4)]),
            serp('q2', [('rival.ca', 2)]),
            serp('q3', [('rival.ca', 3), ('autre.ca', 5)]),
            serp('q4', [('autre.ca', 2)]),
        ]
        trouves = decouvrir_concurrents(serps, 'moi.ca')
        self.assertEqual(trouves[0], 'rival.ca')   # 3 apparitions
        self.assertIn('autre.ca', trouves)          # 2 apparitions

    def test_un_passant_vu_une_seule_fois_est_ecarte(self):
        """Un hote vu une fois sur dix requetes n'est pas un concurrent."""
        serps = [serp(f'q{i}', [('rival.ca', 1)]) for i in range(4)]
        serps.append(serp('q9', [('passant.ca', 8)]))
        self.assertNotIn('passant.ca', decouvrir_concurrents(serps, 'moi.ca'))

    def test_le_domaine_analyse_ne_peut_pas_etre_son_propre_concurrent(self):
        serps = [serp('q1', [('moi.ca', 1)]), serp('q2', [('moi.ca', 1)])]
        self.assertNotIn('moi.ca', decouvrir_concurrents(serps, 'moi.ca'))

    def test_une_seule_voix_par_serp_meme_avec_plusieurs_urls(self):
        serps = [
            serp('q1', [('rival.ca', 1), ('rival.ca', 2), ('rival.ca', 3)]),
            serp('q2', [('autre.ca', 1)]),
            serp('q3', [('autre.ca', 1)]),
            serp('q4', [('autre.ca', 1)]),
        ]
        # rival apparait 3 fois mais sur UN seul SERP : autre.ca doit gagner
        self.assertEqual(decouvrir_concurrents(serps, 'moi.ca')[0], 'autre.ca')

    def test_le_maximum_est_respecte(self):
        serps = [serp(f'q{i}', [(f'r{j}.ca', j + 1) for j in range(6)])
                 for i in range(4)]
        self.assertEqual(len(decouvrir_concurrents(serps, 'moi.ca', maximum=3)), 3)

    def test_aucun_serp_rend_une_liste_vide_sans_planter(self):
        self.assertEqual(decouvrir_concurrents([], 'moi.ca'), [])


# ---------------------------------------------------------------------------
class TrouverEcartsTests(SimpleTestCase):

    def test_un_ecart_est_une_requete_ou_le_rival_est_la_et_pas_nous(self):
        serps = [serp('plombier jonquiere', [('rival.ca', 2), ('tiers.com', 5)])]
        ecarts = trouver_ecarts(serps, 'moi.ca', ['rival.ca'])
        self.assertEqual(len(ecarts), 1)
        self.assertEqual(ecarts[0]['keyword'], 'plombier jonquiere')
        self.assertEqual(ecarts[0]['competitor'], 'rival.ca')
        self.assertEqual(ecarts[0]['position'], 2)
        self.assertTrue(ecarts[0]['url'])

    def test_une_requete_ou_le_domaine_se_classe_n_est_pas_un_ecart(self):
        serps = [serp('q1', [('rival.ca', 1), ('moi.ca', 7)])]
        self.assertEqual(trouver_ecarts(serps, 'moi.ca', ['rival.ca']), [])

    def test_le_rang_du_domaine_ne_change_rien_seule_sa_presence_compte(self):
        """Meme classe 9e, le domaine EST present : ce n'est pas un trou."""
        serps = [serp('q1', [('rival.ca', 1), ('moi.ca', 9)])]
        self.assertEqual(trouver_ecarts(serps, 'moi.ca', ['rival.ca']), [])

    def test_une_requete_sans_aucun_concurrent_n_est_pas_un_ecart(self):
        serps = [serp('q1', [('inconnu.ca', 1)])]
        self.assertEqual(trouver_ecarts(serps, 'moi.ca', ['rival.ca']), [])

    def test_le_mieux_classe_des_concurrents_est_retenu(self):
        serps = [serp('q1', [('rivalB.ca', 2), ('rivalA.ca', 5)])]
        ecarts = trouver_ecarts(serps, 'moi.ca', ['rivalA.ca', 'rivalB.ca'])
        self.assertEqual(ecarts[0]['competitor'], 'rivalB.ca')


# ---------------------------------------------------------------------------
class CollecterSerpsTests(SimpleTestCase):

    def _reponse(self, hotes, code=200):
        m = MagicMock()
        m.status_code = code
        m.json.return_value = {'organic': [
            {'link': f'https://{h}/x', 'position': i + 1, 'title': f'{h} titre'}
            for i, h in enumerate(hotes)]}
        return m

    def test_un_appel_par_requete_pas_un_par_domaine(self):
        import os
        with patch.dict(os.environ, {'SERPER_API_KEY': 'k'}):
            with patch('requests.post', return_value=self._reponse(['a.ca'])) as post:
                serps = collecter_serps(['q1', 'q2', 'q3'])
        self.assertEqual(post.call_count, 3)
        self.assertEqual(len(serps), 3)

    def test_les_serp_en_echec_sont_exclus_pas_comptes_comme_vides(self):
        """Un non-200 ne doit jamais se confondre avec "le site ne se classe
        pas" : sans ca, une panne de quota annonce au visiteur que son site
        n'est nulle part."""
        import os
        with patch.dict(os.environ, {'SERPER_API_KEY': 'k'}):
            with patch('requests.post') as post:
                post.side_effect = [self._reponse(['a.ca']), self._reponse([], 429)]
                serps = collecter_serps(['q1', 'q2'])
        self.assertEqual(len(serps), 1)

    def test_tout_en_echec_rend_none(self):
        import os
        with patch.dict(os.environ, {'SERPER_API_KEY': 'k'}):
            with patch('requests.post', return_value=self._reponse([], 429)):
                self.assertIsNone(collecter_serps(['q1']))

    def test_sans_cle_rend_none(self):
        import os
        with patch.dict(os.environ, {'SERPER_API_KEY': ''}):
            self.assertIsNone(collecter_serps(['q1']))


# ---------------------------------------------------------------------------
class GapViewTests(TestCase):
    """La vue de bout en bout. Aucun test ne l'exercait avant aujourd'hui,
    ce qui explique que la decouverte cassee ait survecu jusqu'en prod."""

    def setUp(self):
        cache.clear()

    def _appeler(self, serps, corps=None):
        import os
        with patch.dict(os.environ, {'SERPER_API_KEY': 'k'}):
            with patch('sites_mgmt.views_tools._analyser_page', return_value={
                'brand': 'Moi', 'sector': 'plumbing', 'sector_source': 'jina',
                'queries': ['q1', 'q2', 'q3', 'q4'], 'queries_source': 'jina',
            }):
                with patch('sites_mgmt.compare_mesures.collecter_serps',
                           return_value=serps):
                    return self.client.post(
                        '/api/public/competitor-gap/',
                        data=corps or {'domain': 'moi.ca'},
                        content_type='application/json',
                    )

    def test_des_concurrents_sont_enfin_trouves_et_les_ecarts_remontent(self):
        serps = [
            serp('q1', [('rival.ca', 1)]),
            serp('q2', [('rival.ca', 2)]),
            serp('q3', [('rival.ca', 3), ('moi.ca', 8)]),
            serp('q4', [('rival.ca', 1)]),
        ]
        corps = self._appeler(serps).json()
        self.assertEqual(corps['competitors_detected'], ['rival.ca'])
        self.assertEqual(corps['competitors_source'], 'deduits')
        self.assertEqual(corps['total_gaps'], 3)      # q3 exclue, on s'y classe
        self.assertEqual(corps['domain_ranks_for'], ['q3'])
        self.assertTrue(corps['top_opportunities'])

    def test_aucun_concurrent_le_dit_au_lieu_de_rendre_un_zero_muet(self):
        """L'ancienne version rendait total_gaps: 0 sans jamais dire que la
        decouverte avait echoue. Un zero muet se lit comme "ton site n'a
        aucun retard", l'inverse de la verite."""
        serps = [serp('q1', [('passant.ca', 9)]), serp('q2', []),
                 serp('q3', []), serp('q4', [])]
        corps = self._appeler(serps).json()
        self.assertEqual(corps['competitors_detected'], [])
        self.assertEqual(corps['total_gaps'], 0)
        self.assertIn('notice', corps)
        self.assertTrue(corps['notice'])

    def test_aucun_serp_obtenu_le_dit_franchement(self):
        corps = self._appeler(None).json()
        self.assertEqual(corps['queries_checked'], 0)
        self.assertIn('notice', corps)

    def test_les_concurrents_fournis_court_circuitent_la_decouverte(self):
        """Quand l'utilisateur nomme un concurrent, on le prend tel quel sans
        rien deduire des SERP."""
        serps = [serp('q1', [('facebook.com', 1)]), serp('q2', [('facebook.com', 2)])]
        corps = self._appeler(serps, corps={
            'domain': 'moi.ca', 'competitors': 'facebook.com'}).json()
        self.assertEqual(corps['competitors_detected'], ['facebook.com'])
        self.assertEqual(corps['competitors_source'], 'fournis')
        self.assertEqual(corps['total_gaps'], 2)

    def test_le_volume_mensuel_n_est_plus_invente(self):
        """L'ancienne version faisait `len(gaps) * 320`, un chiffre sorti de
        nulle part presente comme une estimation de trafic."""
        serps = [serp(f'q{i}', [('rival.ca', 1)]) for i in range(1, 5)]
        corps = self._appeler(serps).json()
        self.assertIsNone(corps['estimated_monthly_searches'])

    def test_les_requetes_reellement_verifiees_sont_annoncees(self):
        serps = [serp('q1', [('rival.ca', 1)]), serp('q2', [('rival.ca', 1)])]
        corps = self._appeler(serps).json()
        self.assertEqual(corps['queries_checked'], 2)
        self.assertEqual(corps['queries_tested'], ['q1', 'q2'])

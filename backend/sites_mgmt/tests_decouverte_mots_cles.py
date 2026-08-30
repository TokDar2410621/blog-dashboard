"""Tests : decouverte de mots-cles ou le site n'apparait pas encore.

Pourquoi ce pipeline existe, et ce qu'il ne pretend PAS faire.

Search Console ne montre que les requetes ou le site apparait deja. Pour
trouver ce qui manque, il faut une autre source, et le volume de recherche
n'en est pas une ici : l'endpoint `/search-volume` de Serper rend
`500 Scraping failed` (verifie en prod le 2026-08-27 sur cinq formes de
requete ; `q` est bien le parametre attendu, l'echec vient de Serper).
Google Keyword Planner rendrait des fourchettes de sept paliers geants sans
campagne publicitaire active.

Le module mesure donc trois FAITS et n'invente aucun chiffre :
  1. Google suggere la requete (elle est reellement tapee)
  2. l'intention est commerciale, jugee sur le SERP reel
  3. le site est absent du top 10, constate dans un SERP interroge

Ces tests verrouillent surtout ce qui ne doit JAMAIS arriver : qu'un volume
apparaisse, qu'un mot-cle ou le site est present soit presente comme une
occasion, ou qu'une depense de credits soit silencieuse.

Run: python manage.py test sites_mgmt.tests_decouverte_mots_cles
"""
import os
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from .decouverte_mots_cles import (
    decouvrir_mots_cles_absents, elargir_par_autocomplete,
)


def suggestions(*valeurs):
    m = MagicMock()
    m.status_code = 200
    m.json.return_value = {'suggestions': [{'value': v} for v in valeurs]}
    return m


def serp(requete, hotes):
    return {
        'requete': requete, 'verifie': True, 'hotes': list(hotes),
        'resultats': [
            {'hote': h, 'position': r, 'url': f'https://{h}/p', 'titre': f'{h} page'}
            for h, r in hotes
        ],
    }


class AutocompleteTests(SimpleTestCase):

    def test_les_suggestions_sont_dedupliquees(self):
        with patch.dict(os.environ, {'SERPER_API_KEY': 'k'}):
            with patch('requests.post', return_value=suggestions(
                    'creation site web quebec', 'Creation Site Web Quebec')):
                mots, credits = elargir_par_autocomplete(['creation site web'])
        self.assertEqual(mots, ['creation site web quebec'])
        self.assertGreater(credits, 0)

    def test_une_requete_d_un_seul_mot_est_ecartee(self):
        """Trop large pour qu'une PME locale la dispute utilement."""
        with patch.dict(os.environ, {'SERPER_API_KEY': 'k'}):
            with patch('requests.post', return_value=suggestions('seo', 'seo quebec')):
                mots, _ = elargir_par_autocomplete(['seo'])
        self.assertEqual(mots, ['seo quebec'])

    def test_le_nombre_d_appels_est_plafonne_et_rendu(self):
        with patch.dict(os.environ, {'SERPER_API_KEY': 'k'}):
            with patch('requests.post', return_value=suggestions('a b')) as post:
                _, credits = elargir_par_autocomplete(
                    ['s1', 's2', 's3', 's4', 's5'], max_appels=10)
        self.assertEqual(credits, 10)
        self.assertEqual(post.call_count, 10)

    def test_sans_cle_aucun_appel_reseau(self):
        with patch.dict(os.environ, {'SERPER_API_KEY': ''}):
            with patch('requests.post') as post:
                mots, credits = elargir_par_autocomplete(['seo quebec'])
        post.assert_not_called()
        self.assertEqual((mots, credits), ([], 0))

    def test_un_echec_reseau_ne_remonte_pas(self):
        with patch.dict(os.environ, {'SERPER_API_KEY': 'k'}):
            with patch('requests.post', side_effect=TimeoutError('boom')):
                mots, _ = elargir_par_autocomplete(['seo quebec'])
        self.assertEqual(mots, [])


class DecouverteTests(SimpleTestCase):

    def _lancer(self, serps, candidats=('mot un', 'mot deux'), ecartees=()):
        with patch('sites_mgmt.decouverte_mots_cles.elargir_par_autocomplete',
                   return_value=(list(candidats), 20)), \
             patch('sites_mgmt.compare_mesures.collecter_serps', return_value=serps), \
             patch('sites_mgmt.compare_mesures.filtrer_intention_commerciale',
                   return_value=(serps, list(ecartees))):
            return decouvrir_mots_cles_absents('moi.ca', ['seo quebec'])

    def test_un_mot_cle_ou_le_site_est_present_n_est_pas_une_occasion(self):
        """Le pipeline cherche ce qui MANQUE. Presenter une requete deja
        occupee comme une occasion serait un faux positif."""
        r = self._lancer([serp('mot un', [('moi.ca', 3), ('rival.ca', 1)])])
        self.assertEqual(r['occasions'], [])
        self.assertEqual(r['deja_present'], [{'keyword': 'mot un', 'position': 3}])

    def test_un_mot_cle_ou_le_site_est_absent_devient_une_occasion(self):
        r = self._lancer([serp('mot un', [('rival.ca', 1), ('autre.ca', 2)])])
        self.assertEqual(len(r['occasions']), 1)
        o = r['occasions'][0]
        self.assertEqual(o['keyword'], 'mot un')
        self.assertTrue(o['evidence']['site_absent_du_top_10'])
        self.assertTrue(o['occupants'])

    def test_les_occasions_disputees_par_les_concurrents_passent_devant(self):
        """Sans volume, c'est le seul classement defendable : une requete que
        ton marche occupe vaut mieux qu'une que personne ne dispute."""
        serps = [
            serp('sans rival', [('inconnu1.ca', 1)]),
            serp('avec rival', [('rival.ca', 1)]),
            serp('encore rival', [('rival.ca', 2)]),
            serp('rival aussi', [('rival.ca', 1)]),
        ]
        r = self._lancer(serps, candidats=['a b', 'c d', 'e f', 'g h'])
        self.assertIn('rival.ca', r['concurrents_identifies'])
        self.assertGreater(r['occasions'][0]['rivaux'], 0)
        self.assertEqual(r['occasions'][-1]['keyword'], 'sans rival')

    def test_aucun_volume_n_est_jamais_rendu(self):
        """Le defaut central de l'audit : afficher un chiffre non mesure."""
        r = self._lancer([serp('mot un', [('rival.ca', 1)])])
        texte = str(r).lower()
        for interdit in ('monthly_volume', 'search_volume', 'estimated_visits'):
            self.assertNotIn(interdit, texte)
        self.assertIn('aucun volume', r['note'].lower())

    def test_les_credits_depenses_sont_toujours_rendus(self):
        """Un pipeline qui depense sans le dire est un pipeline qu'on coupe."""
        r = self._lancer([serp('mot un', [('rival.ca', 1)])])
        self.assertEqual(r['credits']['autocomplete'], 20)
        self.assertEqual(r['credits']['serp'], 2)
        self.assertEqual(r['credits']['total'], 22)

    def test_les_requetes_ecartees_pour_intention_sont_nommees(self):
        r = self._lancer([serp('mot un', [('rival.ca', 1)])],
                         ecartees=['emploi developpeur'])
        self.assertEqual(r['ecartees_intention'], ['emploi developpeur'])

    def test_le_www_du_domaine_ne_fausse_pas_la_detection(self):
        with patch('sites_mgmt.decouverte_mots_cles.elargir_par_autocomplete',
                   return_value=(['mot un'], 5)), \
             patch('sites_mgmt.compare_mesures.collecter_serps',
                   return_value=[serp('mot un', [('moi.ca', 2)])]), \
             patch('sites_mgmt.compare_mesures.filtrer_intention_commerciale',
                   side_effect=lambda s: (s, [])):
            r = decouvrir_mots_cles_absents('www.moi.ca', ['seo'])
        self.assertEqual(r['occasions'], [])
        self.assertEqual(len(r['deja_present']), 1)

    def test_aucun_serp_obtenu_le_dit_au_lieu_de_rendre_une_liste_vide(self):
        with patch('sites_mgmt.decouverte_mots_cles.elargir_par_autocomplete',
                   return_value=(['mot un'], 5)), \
             patch('sites_mgmt.compare_mesures.collecter_serps', return_value=None):
            r = decouvrir_mots_cles_absents('moi.ca', ['seo'])
        self.assertEqual(r['occasions'], [])
        self.assertIn('resultats', r['note'].lower())
        self.assertEqual(r['credits']['autocomplete'], 5)

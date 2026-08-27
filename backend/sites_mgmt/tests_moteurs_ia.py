"""Tests : interrogation des moteurs d'IA dont on mesure les reponses.

Trois outils publics demandent "quand quelqu'un pose X a une IA, ce site
est-il cite ?". Ils partageaient tous le meme defaut : une panne du moteur se
lisait comme une absence de mention.

Constate en prod le 2026-08-27 : le quota Gemini etant epuise, l'AI Visibility
Checker affichait 0 % a TOUS les visiteurs, sans dire que c'etait une panne.
Quelqu'un qui testait son site concluait que l'IA ne le mentionne jamais.

Le piege des jetons de reflexion, mesure en prod le meme jour :

    gpt-5-mini  budget 200  raisonnement=200  texte=0 car   finish=length
    gpt-5-mini  budget 800  raisonnement=800  texte=0 car   finish=length
    gpt-5-mini  budget 800  effort=minimal  raisonnement=0  texte=1874 car

Augmenter le budget n'aide pas : le modele reflechit plus longtemps. Sans
`reasoning_effort: minimal`, on paye des jetons pour recevoir du vide, et ce
vide se compterait comme une non-mention.

Run: python manage.py test sites_mgmt.tests_moteurs_ia
"""
import os
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from .moteurs_ia import LIBELLES, interroger, moteurs_configures


def reponse(code=200, data=None):
    m = MagicMock()
    m.status_code = code
    m.json.return_value = data if data is not None else {}
    m.text = ''
    return m


def gemini_ok(texte='Essaie alpha.ca'):
    return reponse(200, {'candidates': [{'content': {'parts': [{'text': texte}]}}]})


def openai_ok(texte='Essaie alpha.ca', fin='stop'):
    return reponse(200, {'choices': [
        {'message': {'content': texte}, 'finish_reason': fin}]})


class MoteursConfiguresTests(SimpleTestCase):

    def test_seuls_les_moteurs_avec_cle_sont_listes(self):
        with patch.dict(os.environ, {'GEMINI_API_KEY': 'k', 'OPENAI_API_KEY': ''}):
            self.assertEqual(moteurs_configures(), ['gemini'])
        with patch.dict(os.environ, {'GEMINI_API_KEY': '', 'OPENAI_API_KEY': 'k'}):
            self.assertEqual(moteurs_configures(), ['openai'])
        with patch.dict(os.environ, {'GEMINI_API_KEY': 'k', 'OPENAI_API_KEY': 'k'}):
            self.assertEqual(moteurs_configures(), ['gemini', 'openai'])

    def test_aucune_cle_rend_une_liste_vide(self):
        with patch.dict(os.environ, {'GEMINI_API_KEY': '', 'OPENAI_API_KEY': ''}):
            self.assertEqual(moteurs_configures(), [])


class OpenAiTests(SimpleTestCase):

    def test_le_raisonnement_est_coupe(self):
        """Sans `reasoning_effort: minimal`, le modele consomme tout le budget
        en reflexion et rend une chaine vide."""
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'k'}):
            with patch('requests.post', return_value=openai_ok()) as post:
                interroger('openai', 'q')
        envoye = post.call_args.kwargs['json']
        self.assertEqual(envoye['reasoning_effort'], 'minimal')
        self.assertEqual(envoye['model'], 'gpt-5-mini')

    def test_la_cle_passe_par_un_en_tete(self):
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'secret'}):
            with patch('requests.post', return_value=openai_ok()) as post:
                interroger('openai', 'q')
        entetes = post.call_args.kwargs['headers']
        self.assertTrue(entetes['Authorization'].startswith('Bearer '))
        self.assertNotIn('secret', post.call_args.args[0])

    def test_une_reponse_vide_coupee_par_le_budget_est_indisponible(self):
        """Le cas mesure en prod : finish_reason 'length' et zero caractere.
        Ce n'est PAS une absence de mention."""
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'k'}):
            with patch('requests.post', return_value=openai_ok('', 'length')):
                r = interroger('openai', 'q')
        self.assertFalse(r['disponible'])
        self.assertIn('jetons', r['raison'].lower())
        self.assertIsNone(r['texte'])

    def test_un_quota_epuise_est_nomme(self):
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'k'}):
            with patch('requests.post', return_value=reponse(429)):
                r = interroger('openai', 'q')
        self.assertFalse(r['disponible'])
        self.assertIn('quota', r['raison'].lower())

    def test_une_reponse_nominale_est_rendue(self):
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'k'}):
            with patch('requests.post', return_value=openai_ok('Va voir alpha.ca')):
                r = interroger('openai', 'q')
        self.assertTrue(r['disponible'])
        self.assertEqual(r['texte'], 'Va voir alpha.ca')
        self.assertIsNone(r['raison'])

    def test_sans_cle_le_moteur_est_indisponible_sans_appel_reseau(self):
        with patch.dict(os.environ, {'OPENAI_API_KEY': ''}):
            with patch('requests.post') as post:
                r = interroger('openai', 'q')
        post.assert_not_called()
        self.assertFalse(r['disponible'])


class GeminiTests(SimpleTestCase):

    def test_le_thinking_est_coupe(self):
        with patch.dict(os.environ, {'GEMINI_API_KEY': 'k'}):
            with patch('requests.post', return_value=gemini_ok()) as post:
                interroger('gemini', 'q')
        envoye = post.call_args.kwargs['json']
        self.assertEqual(
            envoye['generationConfig']['thinkingConfig']['thinkingBudget'], 0)

    def test_la_cle_ne_transite_jamais_par_l_url(self):
        """Elle a fuite en clair dans les logs Railway le 2026-08-27 parce
        qu'elle etait en parametre d'URL et que `raise_for_status()` met
        l'URL complete dans le message d'exception."""
        with patch.dict(os.environ, {'GEMINI_API_KEY': 'secret'}):
            with patch('requests.post', return_value=gemini_ok()) as post:
                interroger('gemini', 'q')
        self.assertNotIn('secret', post.call_args.args[0])
        self.assertEqual(post.call_args.kwargs['headers']['x-goog-api-key'], 'secret')

    def test_un_quota_epuise_est_nomme(self):
        with patch.dict(os.environ, {'GEMINI_API_KEY': 'k'}):
            with patch('requests.post', return_value=reponse(429)):
                r = interroger('gemini', 'q')
        self.assertFalse(r['disponible'])
        self.assertIn('quota', r['raison'].lower())

    def test_une_reponse_vide_est_indisponible_pas_une_non_mention(self):
        with patch.dict(os.environ, {'GEMINI_API_KEY': 'k'}):
            with patch('requests.post', return_value=gemini_ok('')):
                r = interroger('gemini', 'q')
        self.assertFalse(r['disponible'])

    def test_une_reponse_illisible_ne_remonte_pas(self):
        with patch.dict(os.environ, {'GEMINI_API_KEY': 'k'}):
            with patch('requests.post', return_value=reponse(200, {'inattendu': 1})):
                r = interroger('gemini', 'q')
        self.assertFalse(r['disponible'])

    def test_une_panne_reseau_ne_remonte_pas(self):
        with patch.dict(os.environ, {'GEMINI_API_KEY': 'k'}):
            with patch('requests.post', side_effect=TimeoutError('boom')):
                r = interroger('gemini', 'q')
        self.assertFalse(r['disponible'])
        self.assertIn('TimeoutError', r['raison'])


class MoteurInconnuTests(SimpleTestCase):

    def test_un_moteur_inconnu_est_declare_indisponible(self):
        """L'ancien `_check_ai_mention` traversait sans un seul appel reseau
        pour tout moteur autre que 'gemini' et rendait `mentioned: False`,
        faisant passer un moteur non implemente pour un moteur qui ne cite
        jamais personne."""
        with patch('requests.post') as post:
            r = interroger('perplexity', 'q')
        post.assert_not_called()
        self.assertFalse(r['disponible'])
        self.assertIn('inconnu', r['raison'].lower())

    def test_chaque_moteur_connu_a_un_libelle_lisible(self):
        for moteur in ('gemini', 'openai'):
            self.assertIn(moteur, LIBELLES)
            self.assertTrue(LIBELLES[moteur])

"""Tests : requetes commerciales generees par DeepSeek pour les outils publics
(AI Visibility, Competitor Gap, AI Citation Checker).

Contexte du 2026-08-24. Darius s'auto-audite avec tokamdarius.ca (site de
developpeur web freelance) sur l'AI Visibility Checker et obtient des requetes
absurdes : "comparatif general 2026", "meilleur general Montreal", "general
prix abordable".

Cause : `_SECTEURS_CONNUS` ne couvre que 13 verticales locales (dentiste,
avocat, plombier, restaurant...). Un developpeur web freelance ne rentre dans
aucune, donc le secteur detecte tombe legitimement sur 'general' - la valeur
qui dit "rien ne correspond". Le probleme n'est pas la, il est en aval :
`_generate_commercial_queries` prenait ce mot et le substituait LITTERALEMENT
dans ses gabarits de repli ("meilleur {sector} Montreal" -> "meilleur general
Montreal"), montre tel quel a un visiteur.

`_requetes_commerciales_llm` genere les requetes directement depuis le
contenu reel de la page (title/H1/description), sans jamais passer par une
case de secteur : n'importe quel type d'entreprise recoit des requetes
pertinentes, meme hors des 13 verticales connues.

Run: python manage.py test sites_mgmt.tests_requetes_commerciales
"""
import os
from unittest.mock import patch

from django.test import SimpleTestCase

from .views_tools import _generate_commercial_queries, _requetes_commerciales_llm

CRAWL_DEV = {
    'title': 'Tokam Darius | Developpeur Web a Jonquiere & Chicoutimi',
    'h1': 'Developpeur web au Quebec. Du sur-mesure, pas un gabarit.',
    'meta_description': (
        'Tokam Darius, developpeur web a Jonquiere et Chicoutimi. '
        'Applications web sur mesure, React, Django, TypeScript.'
    ),
}


def reponse(texte):
    return patch('sites_mgmt.llm.call_deepseek', return_value=texte)


# ---------------------------------------------------------------------------
class LeBugReproduitTests(SimpleTestCase):
    """Le scenario exact du 2026-08-24 : un metier hors des 13 verticales."""

    def test_un_developpeur_web_recoit_des_requetes_pertinentes(self):
        """Le point entier de cette fonction : elle n'a jamais besoin de
        savoir que 'developpeur web' n'est pas dans _SECTEURS_CONNUS."""
        with reponse('["developpeur web quebec", "creation site web sur mesure",'
                     ' "application web react saguenay", "prix site web quebec"]'):
            r = _requetes_commerciales_llm(CRAWL_DEV, 'Tokam Darius', 'tokamdarius.ca')
        self.assertIsNotNone(r)
        self.assertTrue(all('general' not in q.lower() for q in r))
        self.assertIn('developpeur web quebec', r)

    def test_le_mot_general_ne_peut_structurellement_plus_apparaitre(self):
        """Cette fonction ne recoit jamais de secteur en entree : rien ici ne
        peut inserer le mot 'general' dans une requete, contrairement a
        l'ancien chemin par gabarits."""
        with reponse('["developpeur web quebec", "creation site sur mesure",'
                     ' "prix application web"]'):
            r = _requetes_commerciales_llm(CRAWL_DEV, 'Tokam Darius', 'tokamdarius.ca')
        for q in r:
            self.assertNotIn('general', q.lower())


# ---------------------------------------------------------------------------
class ReponseExploitableTests(SimpleTestCase):
    def test_trois_requetes_suffisent(self):
        with reponse('["developpeur web quebec", "creation site web sur mesure",'
                     ' "prix site web quebec"]'):
            r = _requetes_commerciales_llm(CRAWL_DEV, 'Tokam Darius', 'tokamdarius.ca')
        self.assertEqual(len(r), 3)

    def test_le_modele_peut_encadrer_sa_reponse(self):
        with reponse('Voici :\n```json\n["developpeur web quebec",'
                     ' "creation site sur mesure", "prix application web"]\n```'):
            r = _requetes_commerciales_llm(CRAWL_DEV, 'Tokam Darius', 'tokamdarius.ca')
        self.assertEqual(len(r), 3)

    def test_le_plafond_est_respecte(self):
        liste = ', '.join(f'"requete numero {i}"' for i in range(20))
        with reponse(f'[{liste}]'):
            r = _requetes_commerciales_llm(CRAWL_DEV, 'Tokam Darius', 'tokamdarius.ca', n=6)
        self.assertEqual(len(r), 6)

    def test_les_doublons_sont_ecartes(self):
        with reponse('["developpeur web", "DEVELOPPEUR WEB", "creation site web",'
                     ' "prix application web"]'):
            r = _requetes_commerciales_llm(CRAWL_DEV, 'Tokam Darius', 'tokamdarius.ca')
        self.assertEqual(len(r), 3)


# ---------------------------------------------------------------------------
class ValidationTests(SimpleTestCase):
    """Ce qui sort du modele part dans des appels Gemini/Serper factures et
    entre dans un rapport montre a un prospect."""

    def test_les_requetes_d_un_seul_mot_sont_ecartees(self):
        with reponse('["web", "developpeur web quebec", "creation site web sur mesure",'
                     ' "prix application web"]'):
            r = _requetes_commerciales_llm(CRAWL_DEV, 'Tokam Darius', 'tokamdarius.ca')
        self.assertNotIn('web', r)

    def test_une_url_n_est_pas_une_requete(self):
        with reponse('["https://tokamdarius.ca", "developpeur web quebec",'
                     ' "creation site web sur mesure", "prix application web"]'):
            r = _requetes_commerciales_llm(CRAWL_DEV, 'Tokam Darius', 'tokamdarius.ca')
        self.assertTrue(all('http' not in q for q in r))

    def test_les_balises_sont_ecartees(self):
        with reponse('["<script>alert(1)</script>", "developpeur web quebec",'
                     ' "creation site web sur mesure", "prix application web"]'):
            r = _requetes_commerciales_llm(CRAWL_DEV, 'Tokam Darius', 'tokamdarius.ca')
        self.assertTrue(all('<' not in q for q in r))

    def test_les_valeurs_non_textuelles_sont_ignorees(self):
        with reponse('[42, null, "developpeur web quebec", "creation site sur mesure",'
                     ' "prix application web"]'):
            r = _requetes_commerciales_llm(CRAWL_DEV, 'Tokam Darius', 'tokamdarius.ca')
        self.assertEqual(len(r), 3)


# ---------------------------------------------------------------------------
class RepliTests(SimpleTestCase):
    """Route publique : jamais de dependance dure a un LLM."""

    def test_reponse_vide_rend_none(self):
        with reponse(''):
            self.assertIsNone(
                _requetes_commerciales_llm(CRAWL_DEV, 'Tokam Darius', 'tokamdarius.ca'))

    def test_json_invalide_rend_none(self):
        with reponse('["developpeur web", oups'):
            self.assertIsNone(
                _requetes_commerciales_llm(CRAWL_DEV, 'Tokam Darius', 'tokamdarius.ca'))

    def test_reponse_sans_tableau_rend_none(self):
        with reponse('Je ne peux pas repondre.'):
            self.assertIsNone(
                _requetes_commerciales_llm(CRAWL_DEV, 'Tokam Darius', 'tokamdarius.ca'))

    def test_tableau_vide_rend_none(self):
        """Le gabarit demande un tableau vide quand la page ne dit pas le metier."""
        with reponse('[]'):
            self.assertIsNone(
                _requetes_commerciales_llm(CRAWL_DEV, 'Tokam Darius', 'tokamdarius.ca'))

    def test_crawl_en_erreur_n_appelle_pas_le_modele(self):
        with patch('sites_mgmt.llm.call_deepseek') as appel:
            r = _requetes_commerciales_llm({'error': 'HTTP 500'}, 'X', 'x.ca')
        self.assertIsNone(r)
        appel.assert_not_called()

    def test_crawl_vide_n_appelle_pas_le_modele(self):
        with patch('sites_mgmt.llm.call_deepseek') as appel:
            self.assertIsNone(_requetes_commerciales_llm({}, 'X', 'x.ca'))
        appel.assert_not_called()

    def test_une_panne_du_modele_ne_fait_pas_planter_l_appelant(self):
        with patch('sites_mgmt.llm.call_deepseek', side_effect=RuntimeError('boom')):
            self.assertIsNone(_requetes_commerciales_llm(CRAWL_DEV, 'X', 'x.ca'))


# ---------------------------------------------------------------------------
class FiletDeSecuriteTests(SimpleTestCase):
    """`_generate_commercial_queries` : le repli de dernier recours, quand
    `_requetes_commerciales_llm` a lui-meme echoue. Le defaut original :
    quand aucune cle Gemini n'est configuree (ou que Gemini echoue), le mot
    sentinelle 'general' etait substitue tel quel dans un gabarit.

    Gemini teste en premier a l'interieur de cette fonction : on desactive sa
    cle pour ces tests, sinon ils dependraient d'un vrai appel reseau non
    deterministe (et factureraient du quota pour un test unitaire).
    """

    def setUp(self):
        self._sans_gemini = patch.dict(os.environ, {'GEMINI_API_KEY': ''})
        self._sans_gemini.start()
        self.addCleanup(self._sans_gemini.stop)

    def test_secteur_general_ne_produit_jamais_le_mot_general(self):
        r = _generate_commercial_queries('Tokam Darius', 'general', 'tokamdarius.ca')
        self.assertTrue(all('general' not in q.lower() for q in r))

    def test_secteur_general_rend_quand_meme_une_liste_non_vide(self):
        """Le vrai defaut du 2026-08-24 : Vercel et tokamdarius.ca recevaient
        des requetes visibles, pas une liste vide - le probleme etait leur
        contenu, pas leur absence. Le repli doit rester utile."""
        r = _generate_commercial_queries('X', 'general', 'x.ca')
        self.assertGreaterEqual(len(r), 5)

    def test_secteur_connu_garde_son_comportement_par_gabarit(self):
        """Le repli sectoriel existant, pour dental etc., n'est pas touche."""
        r = _generate_commercial_queries('Cabinet Dupont', 'dental', 'dupont.ca')
        self.assertIn('meilleur dental Montreal', r)

    def test_le_plafond_n_est_jamais_depasse(self):
        r = _generate_commercial_queries('X', 'general', 'x.ca', n=3)
        self.assertEqual(len(r), 3)
        r2 = _generate_commercial_queries('X', 'dental', 'x.ca', n=3)
        self.assertEqual(len(r2), 3)

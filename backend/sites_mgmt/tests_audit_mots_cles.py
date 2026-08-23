"""Tests : mots-cles de l'audit public proposes par DeepSeek.

Contexte du 2026-08-23. L'extraction par n-grammes decoupe le H1 et le title en
tranches de deux ou trois mots. Sur un slogan, ca donne "seule interface",
"gridar quebec", "brief ecriture". Personne ne tape ca. Ces chaines partaient
pourtant chez Serper, et la part d'entre elles classees dans le top 10 devenait
la composante `rankings` du score : le site etait note sur des requetes
inventees.

DeepSeek lit la page et propose les requetes qu'un client taperait. Comme la
route est publique, il ne peut pas etre une dependance dure : tout resultat
inexploitable rend None et l'heuristique reprend la main.

La validation est severe parce que ce que rend le modele part dans des appels
Serper factures et entre dans un score montre a un prospect.

Run: python manage.py test sites_mgmt.tests_audit_mots_cles
"""
from unittest.mock import patch

from django.test import SimpleTestCase

from .views import _mots_cles_par_llm

CRAWL = {
    'title': 'Sablage de plancher a Montreal',
    'h1': 'Redonnez vie a vos planchers de bois franc',
    'meta_description': 'Sablage, vernissage et reparation de planchers.',
    'h2_list': ['Nos services', 'Zone desservie'],
    'body_snippet': 'Nous sablons et vernissons les planchers de bois franc.',
}


def reponse(texte):
    """Remplace l'appel reseau a DeepSeek par une reponse fixe."""
    return patch('sites_mgmt.llm.call_deepseek', return_value=texte)


class ReponseExploitableTests(SimpleTestCase):
    def test_un_tableau_json_propre_est_accepte(self):
        with reponse('["sablage plancher montreal", "vernir plancher bois franc"]'):
            r = _mots_cles_par_llm(CRAWL, 'exemple.ca')
        self.assertIsNone(r)  # deux requetes seulement : sous le seuil de trois

    def test_trois_requetes_suffisent(self):
        with reponse('["sablage plancher montreal", "vernir plancher bois franc",'
                     ' "reparer plancher qui craque"]'):
            r = _mots_cles_par_llm(CRAWL, 'exemple.ca')
        self.assertEqual(len(r), 3)
        self.assertIn('sablage plancher montreal', r)

    def test_le_modele_peut_encadrer_sa_reponse(self):
        """Bloc markdown et phrase d'introduction, cas courant."""
        with reponse('Voici les requetes :\n```json\n'
                     '["sablage plancher montreal", "vernis plancher bois",'
                     ' "cout sablage plancher"]\n```'):
            r = _mots_cles_par_llm(CRAWL, 'exemple.ca')
        self.assertEqual(len(r), 3)

    def test_le_plafond_est_respecte(self):
        liste = ', '.join(f'"requete numero {i}"' for i in range(20))
        with reponse(f'[{liste}]'):
            r = _mots_cles_par_llm(CRAWL, 'exemple.ca', maximum=6)
        self.assertEqual(len(r), 6)

    def test_les_doublons_sont_ecartes(self):
        with reponse('["sablage plancher", "SABLAGE PLANCHER", "vernis plancher",'
                     ' "cout sablage plancher"]'):
            r = _mots_cles_par_llm(CRAWL, 'exemple.ca')
        self.assertEqual(len(r), 3)


class ValidationTests(SimpleTestCase):
    """Ce qui sort du modele part chez Serper : rien ne passe sans controle."""

    def test_les_requetes_d_un_seul_mot_sont_ecartees(self):
        with reponse('["plancher", "sablage plancher montreal",'
                     ' "vernis plancher bois", "cout sablage plancher"]'):
            r = _mots_cles_par_llm(CRAWL, 'exemple.ca')
        self.assertNotIn('plancher', r)
        self.assertEqual(len(r), 3)

    def test_les_phrases_trop_longues_sont_ecartees(self):
        longue = 'un sablage de plancher de bois franc a montreal et en banlieue'
        with reponse(f'["{longue}", "sablage plancher montreal",'
                     ' "vernis plancher bois", "cout sablage plancher"]'):
            r = _mots_cles_par_llm(CRAWL, 'exemple.ca')
        self.assertNotIn(longue, r)

    def test_une_url_n_est_pas_une_requete(self):
        with reponse('["https://exemple.ca/sablage", "sablage plancher montreal",'
                     ' "vernis plancher bois", "cout sablage plancher"]'):
            r = _mots_cles_par_llm(CRAWL, 'exemple.ca')
        self.assertTrue(all('http' not in m for m in r))

    def test_les_balises_sont_ecartees(self):
        with reponse('["<script>alert(1)</script>", "sablage plancher montreal",'
                     ' "vernis plancher bois", "cout sablage plancher"]'):
            r = _mots_cles_par_llm(CRAWL, 'exemple.ca')
        self.assertTrue(all('<' not in m for m in r))

    def test_les_valeurs_non_textuelles_sont_ignorees(self):
        with reponse('[42, null, {"a": 1}, "sablage plancher montreal",'
                     ' "vernis plancher bois", "cout sablage plancher"]'):
            r = _mots_cles_par_llm(CRAWL, 'exemple.ca')
        self.assertEqual(len(r), 3)

    def test_la_ponctuation_et_les_espaces_sont_nettoyes(self):
        with reponse('["  sablage  plancher montreal.  ", "vernis plancher bois",'
                     ' "cout sablage plancher"]'):
            r = _mots_cles_par_llm(CRAWL, 'exemple.ca')
        self.assertIn('sablage plancher montreal', r)


class RepliTests(SimpleTestCase):
    """Route publique : jamais de dependance dure a un LLM."""

    def test_reponse_vide_rend_none(self):
        with reponse(''):
            self.assertIsNone(_mots_cles_par_llm(CRAWL, 'exemple.ca'))

    def test_json_invalide_rend_none(self):
        with reponse('["sablage plancher", oups'):
            self.assertIsNone(_mots_cles_par_llm(CRAWL, 'exemple.ca'))

    def test_reponse_sans_tableau_rend_none(self):
        with reponse('Je ne peux pas repondre a cette demande.'):
            self.assertIsNone(_mots_cles_par_llm(CRAWL, 'exemple.ca'))

    def test_tableau_vide_rend_none(self):
        """Le gabarit demande un tableau vide quand la page ne dit pas le metier."""
        with reponse('[]'):
            self.assertIsNone(_mots_cles_par_llm(CRAWL, 'exemple.ca'))

    def test_objet_json_au_lieu_d_un_tableau(self):
        with reponse('{"mots": ["sablage plancher montreal"]}'):
            # Le premier [...] trouve est bien un tableau, mais d'un seul
            # element : sous le seuil, donc repli.
            self.assertIsNone(_mots_cles_par_llm(CRAWL, 'exemple.ca'))

    def test_crawl_en_erreur_n_appelle_meme_pas_le_modele(self):
        with patch('sites_mgmt.llm.call_deepseek') as appel:
            r = _mots_cles_par_llm({'error': 'HTTP 500'}, 'exemple.ca')
        self.assertIsNone(r)
        appel.assert_not_called()

    def test_crawl_vide_n_appelle_meme_pas_le_modele(self):
        with patch('sites_mgmt.llm.call_deepseek') as appel:
            self.assertIsNone(_mots_cles_par_llm({}, 'exemple.ca'))
        appel.assert_not_called()

    def test_une_panne_du_modele_ne_fait_pas_planter_l_audit(self):
        """call_deepseek avale deja tout, mais l'audit ne doit pas dependre de
        cette promesse : une exception ici rendrait un 500 sur une route
        publique au lieu d'un audit avec des mots-cles heuristiques."""
        with patch('sites_mgmt.llm.call_deepseek', side_effect=RuntimeError('boom')):
            self.assertIsNone(_mots_cles_par_llm(CRAWL, 'exemple.ca'))

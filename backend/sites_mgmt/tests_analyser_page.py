"""Tests : lecture de page en trois etages pour les outils publics (AI
Visibility Checker, Competitor Gap, AI Citation Checker).

Contexte du 2026-08-24. Darius, en regardant le scraper maison enchainer les
correctifs specifiques a chaque site (script dans le H1, preambule CSS de
100 Ko, sous-chaine perdue dans une demo), demande de le remplacer par un
service tiers (Jina Reader) qui lit la page en texte propre au lieu d'un
parsing HTML regex maison.

Jina n'est pas magique pour autant : teste sur facebook.com, il recupere la
page de CONNEXION plutot que le vrai contenu, alors que notre crawl maison
(signature de requete differente) recoit la vraie page. D'ou l'exigence
explicite : garder le pipeline DeepSeek d'aujourd'hui comme repli quand Jina
est bloque.

`_analyser_page` enchaine trois etages :
  1. Jina Reader + DeepSeek (le contexte lu, pas devine)
  2. notre crawl maison + DeepSeek (repli, deja teste dans
     tests_ai_visibility_sector.py et tests_requetes_commerciales.py)
  3. generateur par secteur (deja teste, filet de dernier recours)

Ce fichier teste specifiquement le NOUVEAU comportement : `_contexte_page`
(le pont entre les deux formes de crawl), `_fetch_page_jina`, et
l'enchainement des etages dans `_analyser_page`.

Run: python manage.py test sites_mgmt.tests_analyser_page
"""
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from .views_tools import _analyser_page, _contexte_page, _fetch_page_jina


def deepseek(texte):
    return patch('sites_mgmt.llm.call_deepseek', return_value=texte)


# ---------------------------------------------------------------------------
class ContextePageTests(SimpleTestCase):
    """Le pont entre les deux formes de crawl : `page_text` (Jina) ou le
    trio title/H1/meta_description (crawl maison)."""

    def test_page_text_est_priorise_quand_present(self):
        crawl = {'page_text': 'Contenu Jina complet.', 'title': 'ignore'}
        self.assertEqual(_contexte_page(crawl), 'Contenu Jina complet.')

    def test_page_text_est_tronque_a_1500(self):
        crawl = {'page_text': 'x' * 3000}
        self.assertEqual(len(_contexte_page(crawl)), 1500)

    def test_repli_sur_le_trio_titre_h1_description(self):
        crawl = {'title': 'Titre', 'h1': 'Un H1', 'meta_description': 'Une description'}
        r = _contexte_page(crawl)
        self.assertIn('Titre', r)
        self.assertIn('Un H1', r)
        self.assertIn('Une description', r)

    def test_champs_absents_du_trio_restent_des_lignes_vides(self):
        """Pas de filtrage des champs vides : les appelants (verifie ci-dessous
        pour `_detecter_marque_secteur_llm` et `_requetes_commerciales_llm`)
        court-circuitent deja sur `crawl.get('error')` avant d'arriver ici,
        donc un crawl reellement vide n'atteint jamais cette fonction en
        pratique."""
        crawl = {'title': 'Seul le titre'}
        r = _contexte_page(crawl)
        self.assertIn('Titre : Seul le titre', r)
        self.assertIn('H1 : ', r)
        self.assertIn('Meta description : ', r)

    def test_crawl_totalement_vide_ne_plante_pas(self):
        r = _contexte_page({})
        self.assertIsInstance(r, str)


# ---------------------------------------------------------------------------
class FetchJinaTests(SimpleTestCase):
    """`_fetch_page_jina` : le nouveau chemin principal de lecture de page."""

    def test_reponse_propre_extrait_le_titre_et_le_texte(self):
        with patch('requests.get') as get:
            get.return_value.status_code = 200
            get.return_value.text = (
                'Title: Tokam Darius\n\nURL Source: https://tokamdarius.ca/\n\n'
                'Markdown Content:\nDeveloppeur web au Quebec.'
            )
            r = _fetch_page_jina('https://tokamdarius.ca')
        self.assertEqual(r['title'], 'Tokam Darius')
        self.assertIn('Developpeur web au Quebec.', r['page_text'])
        self.assertEqual(r['source'], 'jina')

    def test_page_text_est_tronque_a_4000(self):
        with patch('requests.get') as get:
            get.return_value.status_code = 200
            get.return_value.text = 'Title: X\n\n' + ('y' * 5000)
            r = _fetch_page_jina('https://exemple.ca')
        self.assertLessEqual(len(r['page_text']), 4000)

    def test_http_non_200_rend_none(self):
        with patch('requests.get') as get:
            get.return_value.status_code = 451
            get.return_value.text = ''
            self.assertIsNone(_fetch_page_jina('https://exemple.ca'))

    def test_reponse_vide_rend_none(self):
        with patch('requests.get') as get:
            get.return_value.status_code = 200
            get.return_value.text = '   '
            self.assertIsNone(_fetch_page_jina('https://exemple.ca'))

    def test_une_exception_reseau_ne_remonte_pas(self):
        with patch('requests.get', side_effect=TimeoutError('boom')):
            self.assertIsNone(_fetch_page_jina('https://exemple.ca'))

    def test_reponse_sans_ligne_title_laisse_le_titre_vide(self):
        """Forme degradee : pas de plantage si Jina change son format."""
        with patch('requests.get') as get:
            get.return_value.status_code = 200
            get.return_value.text = 'contenu brut sans en-tete structure'
            r = _fetch_page_jina('https://exemple.ca')
        self.assertEqual(r['title'], '')
        self.assertIn('contenu brut', r['page_text'])


# ---------------------------------------------------------------------------
class AnalyserPageTests(SimpleTestCase):
    """`_analyser_page` : l'enchainement des trois etages.

    Chaque test patche Jina et DeepSeek independamment pour forcer la
    progression a un etage precis, sans jamais toucher le reseau.
    """

    def _jina_ok(self, texte='Title: Boite\n\nMarkdown Content:\nUne vraie entreprise.'):
        m = MagicMock()
        m.status_code = 200
        m.text = texte
        return patch('requests.get', return_value=m)

    def _jina_echoue(self):
        return patch('requests.get', side_effect=TimeoutError('jina indisponible'))

    def test_etage_1_jina_plus_deepseek_reussit_directement(self):
        with self._jina_ok(), deepseek(
            '{"brand": "Boite", "sector": "general"}'
        ):
            # Le meme mock DeepSeek sert aux deux appels (secteur puis
            # requetes) : la reponse secteur est un objet, celle des
            # requetes doit etre un tableau. On differencie par effet de
            # sequence pour rester simple et lisible.
            with patch('sites_mgmt.llm.call_deepseek') as appel:
                appel.side_effect = [
                    '{"brand": "Boite", "sector": "general"}',
                    '["requete un test", "requete deux test", "requete trois test"]',
                ]
                r = _analyser_page('exemple.ca', n_queries=5)
        self.assertEqual(r['brand'], 'Boite')
        self.assertEqual(r['sector_source'], 'jina')
        self.assertEqual(r['queries_source'], 'jina')
        self.assertEqual(len(r['queries']), 3)

    def test_mur_de_connexion_bascule_a_l_etage_2(self):
        """Le scenario exact du 2026-08-24 : Jina repond 200 avec la page de
        connexion de facebook.com au lieu du vrai contenu. DeepSeek, informe
        par le gabarit, doit refuser de deviner dessus (rend brand vide),
        ce qui fait basculer sur le crawl maison."""
        contenu_connexion = (
            'Title: Facebook\n\nMarkdown Content:\n'
            'Log into Facebook\n\nEmail or mobile number\n\nForgot password?'
        )
        with self._jina_ok(texte=contenu_connexion):
            with patch('sites_mgmt.llm.call_deepseek') as appel_deepseek:
                # Etage 1 (deepseek sur le mur de connexion) : refuse.
                appel_deepseek.return_value = '{"brand": "", "sector": ""}'
                with patch('sites_mgmt.views_tools._crawl_homepage_light') as crawl_maison:
                    crawl_maison.return_value = {
                        'title': 'Facebook', 'h1': '', 'meta_description': '',
                    }
                    # Etage 2 (deepseek sur le crawl maison) : reussit.
                    appel_deepseek.side_effect = [
                        '{"brand": "", "sector": ""}',              # etage 1, secteur : refuse
                        '{"brand": "Facebook", "sector": "general"}',  # etage 2, secteur
                        '["rejoindre groupes communaute", "partager photos videos",'
                        ' "messagerie instantanee"]',                # etage 2, requetes
                    ]
                    r = _analyser_page('facebook.com', n_queries=5)
        self.assertEqual(r['brand'], 'Facebook')
        self.assertEqual(r['sector_source'], 'llm')  # etage 2, pas 'jina'
        self.assertTrue(all('general' not in q.lower() for q in r['queries']))
        crawl_maison.assert_called_once()

    def test_jina_indisponible_bascule_directement_a_l_etage_2(self):
        with self._jina_echoue():
            with patch('sites_mgmt.views_tools._crawl_homepage_light') as crawl_maison:
                crawl_maison.return_value = {
                    'title': 'Boite Quebec', 'h1': '', 'meta_description': '',
                }
                with deepseek(''):  # DeepSeek indisponible aussi : repli complet
                    r = _analyser_page('exemple.ca', n_queries=5)
        self.assertEqual(r['sector_source'], 'heuristique')
        self.assertEqual(r['queries_source'], 'sector_fallback')
        self.assertGreaterEqual(len(r['queries']), 5)
        crawl_maison.assert_called_once()

    def test_rien_ne_repond_le_dernier_filet_tient_quand_meme(self):
        """Meme quand Jina, DeepSeek et le crawl maison echouent tous, la
        fonction rend toujours un resultat exploitable (gabarits generiques),
        jamais une exception ni une liste vide."""
        with self._jina_echoue():
            with patch('sites_mgmt.views_tools._crawl_homepage_light') as crawl_maison:
                crawl_maison.return_value = {'error': 'HTTP 500'}
                r = _analyser_page('exemple.ca', n_queries=5)
        self.assertIsNotNone(r['brand'])
        self.assertTrue(all('general' not in q.lower() for q in r['queries']))
        self.assertGreaterEqual(len(r['queries']), 5)

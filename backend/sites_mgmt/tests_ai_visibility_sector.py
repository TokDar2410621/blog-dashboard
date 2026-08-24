"""Tests : detection marque/secteur des outils publics (AI Visibility Checker,
Competitor Gap, AI Citation Checker).

Contexte du 2026-08-24. Darius s'auto-audite sur l'AI Visibility Checker et
obtient 0/100 sur des requetes d'e-commerce ("meilleure plateforme e-commerce
pour PME quebecoises", "comment demarrer une boutique en ligne au Quebec?"),
sans rapport avec Gridar.

Cause : `_detect_brand_and_sector` scannait tout le HTML de la page (jusqu'a
50 Ko) a la recherche de mots-cles de secteur, sans distinguer le contenu qui
DECRIT l'entreprise du contenu decoratif. La page d'accueil de Gridar affiche
le domaine fictif d'un dashboard de demonstration, "boutique-demo.ca" : le mot
"boutique" suffisait a faire conclure a un site e-commerce.

Deux reponses :

1. le domaine fictif est renomme cote frontend (DashboardDemo.tsx) ;
2. la detection est restreinte a title/H1/meta description (jamais le corps
   de page), et DeepSeek prend le relais de l'heuristique de sous-chaine
   quand il est disponible, parce qu'il comprend le contexte : il distingue
   "cette entreprise vend X" de "cette page mentionne X en exemple".

Run: python manage.py test sites_mgmt.tests_ai_visibility_sector
"""
from unittest.mock import patch

from django.test import SimpleTestCase

from .views_tools import (
    _crawl_homepage_light,
    _detect_brand_and_sector,
    _detecter_marque_secteur_llm,
    _marque_et_secteur,
)


def reponse(texte):
    return patch('sites_mgmt.llm.call_deepseek', return_value=texte)


# ---------------------------------------------------------------------------
class LeBugReproduitTests(SimpleTestCase):
    """Le scenario exact du 2026-08-24, fige."""

    def test_le_domaine_fictif_du_dashboard_ne_pollue_plus_la_detection(self):
        """L'ancien code lisait `crawl['_html']`, qui contenait la page
        entiere. `_crawl_homepage_light` ne rend plus ce champ : meme si le
        mot 'boutique' figure quelque part sur une page, l'heuristique ne le
        voit plus tant qu'il n'est pas dans le titre, le H1 ou la description."""
        crawl = {
            'title': 'gridar - le seo fait pour toi, pour les pme du quebec',
            'h1': 'Le SEO fait pour toi. Pour les PME du Quebec',
            'meta_description': (
                'Audit SEO gratuit, generation de contenu et suivi de '
                'positions pour les PME quebecoises.'
            ),
            # Le contenu decoratif (mockup, cas d'usage, domaine de demo) ne
            # transite plus par le crawl : rien a filtrer ici, il n'existe
            # simplement plus dans ce que la fonction recoit.
        }
        r = _detect_brand_and_sector(crawl, 'gridar.app')
        self.assertNotEqual(r['sector'], 'ecommerce')
        self.assertEqual(r['sector'], 'seo')

    def test_le_crawl_leger_ne_rend_plus_le_html_complet(self):
        """`_html` etait le seul champ que l'ancienne detection lisait pour
        son scan de sous-chaine ; sa disparition rend le bug structurellement
        impossible a rejouer, meme par accident."""
        # `_crawl_homepage_light` fait `import requests as http_requests` a
        # l'interieur de la fonction : patcher `requests.get` au niveau du
        # module suffit, l'import local retrouve le meme objet.
        with patch('requests.get') as get:
            get.return_value.status_code = 200
            get.return_value.text = (
                '<html><head><title>Gridar</title></head>'
                '<body><h1>Gridar</h1>'
                '<span>boutique-demo.ca</span></body></html>'
            )
            crawl = _crawl_homepage_light('https://gridar.app')
        self.assertNotIn('_html', crawl)
        # Le mot polluant reste bien absent des trois champs retenus.
        self.assertNotIn('boutique', crawl['title'].lower())
        self.assertNotIn('boutique', crawl['h1'].lower())

    def test_un_script_injecte_dans_le_h1_est_retire(self):
        """react-wrap-balancer (et libs similaires) posent un <script> a
        l'interieur meme du <h1> pour equilibrer les lignes du titre. Vu sur
        gridar.app le 2026-08-24 : sans ce retrait, le code JS se retrouvait
        dans le H1, puis dans le prompt envoye a Gemini par l'outil Can I
        Rank."""
        with patch('requests.get') as get:
            get.return_value.status_code = 200
            get.return_value.text = (
                '<html><head><title>Gridar</title></head><body>'
                '<h1>Le SEO fait pour toi.'
                '<script>self.__wrap_n=1;document.write("x")</script>'
                ' Pour les PME du Quebec</h1></body></html>'
            )
            crawl = _crawl_homepage_light('https://gridar.app')
        self.assertNotIn('script', crawl['h1'].lower())
        self.assertNotIn('__wrap_n', crawl['h1'])
        self.assertEqual(crawl['h1'], 'Le SEO fait pour toi. Pour les PME du Quebec')


# ---------------------------------------------------------------------------
class HeuristiqueDeReplilTests(SimpleTestCase):
    """`_detect_brand_and_sector` : le repli, restreint a 3 champs."""

    def test_secteur_detecte_depuis_le_titre(self):
        r = _detect_brand_and_sector(
            {'title': 'Cabinet Dentaire Dupont', 'h1': '', 'meta_description': ''},
            'dupont.ca',
        )
        self.assertEqual(r['sector'], 'dental')

    def test_secteur_detecte_depuis_le_h1_quand_le_titre_est_generique(self):
        r = _detect_brand_and_sector(
            {'title': 'Accueil', 'h1': 'Votre plombier de confiance a Laval',
             'meta_description': ''},
            'plombierlaval.ca',
        )
        self.assertEqual(r['sector'], 'plumbing')

    def test_aucun_indice_rend_general(self):
        r = _detect_brand_and_sector(
            {'title': 'Bienvenue', 'h1': '', 'meta_description': ''}, 'exemple.ca',
        )
        self.assertEqual(r['sector'], 'general')

    def test_marque_extraite_du_titre_avec_separateur(self):
        r = _detect_brand_and_sector(
            {'title': 'Dupont Avocats | Droit des affaires a Quebec'}, 'dupont.ca',
        )
        self.assertEqual(r['brand'], 'Dupont Avocats')

    def test_titre_absent_rend_le_domaine_capitalise(self):
        r = _detect_brand_and_sector({'title': ''}, 'moncabinet.ca')
        self.assertEqual(r['brand'], 'Moncabinet')

    def test_source_annoncee_est_heuristique(self):
        r = _detect_brand_and_sector({'title': 'Test'}, 'test.ca')
        self.assertEqual(r['source'], 'heuristique')


# ---------------------------------------------------------------------------
class DetectionLlmTests(SimpleTestCase):
    """`_detecter_marque_secteur_llm` : ce que rend le modele part dans des
    requetes generees puis montrees a un prospect, la validation est stricte."""

    CRAWL = {
        'title': 'Toitures Beaulieu | Couvreur certifie Rive-Sud',
        'h1': 'Toitures Beaulieu, votre couvreur depuis 1998',
        'meta_description': 'Reparation et remplacement de toiture, Rive-Sud.',
    }

    def test_reponse_json_propre_est_acceptee(self):
        with reponse('{"brand": "Toitures Beaulieu", "sector": "general"}'):
            r = _detecter_marque_secteur_llm(self.CRAWL, 'toituresbeaulieu.ca')
        self.assertEqual(r, {'brand': 'Toitures Beaulieu', 'sector': 'general',
                            'source': 'llm'})

    def test_le_modele_peut_encadrer_sa_reponse(self):
        with reponse('Voici :\n```json\n{"brand": "Toitures Beaulieu", '
                     '"sector": "general"}\n```'):
            r = _detecter_marque_secteur_llm(self.CRAWL, 'toituresbeaulieu.ca')
        self.assertIsNotNone(r)
        self.assertEqual(r['brand'], 'Toitures Beaulieu')

    def test_un_secteur_hors_liste_est_refuse(self):
        """Un secteur invente par le modele casserait _generate_commercial_queries
        en aval, qui attend un des libelles connus."""
        with reponse('{"brand": "Toitures Beaulieu", "sector": "toiture"}'):
            r = _detecter_marque_secteur_llm(self.CRAWL, 'toituresbeaulieu.ca')
        self.assertIsNone(r)

    def test_marque_vide_est_refusee(self):
        with reponse('{"brand": "", "sector": "general"}'):
            self.assertIsNone(
                _detecter_marque_secteur_llm(self.CRAWL, 'toituresbeaulieu.ca'))

    def test_marque_trop_longue_est_refusee(self):
        with reponse('{"brand": "%s", "sector": "general"}' % ('a' * 90)):
            self.assertIsNone(
                _detecter_marque_secteur_llm(self.CRAWL, 'toituresbeaulieu.ca'))

    def test_json_invalide_rend_none(self):
        with reponse('{"brand": "Toitures Beaulieu", oups'):
            self.assertIsNone(
                _detecter_marque_secteur_llm(self.CRAWL, 'toituresbeaulieu.ca'))

    def test_reponse_sans_objet_rend_none(self):
        with reponse('Je ne sais pas.'):
            self.assertIsNone(
                _detecter_marque_secteur_llm(self.CRAWL, 'toituresbeaulieu.ca'))

    def test_reponse_vide_rend_none(self):
        with reponse(''):
            self.assertIsNone(
                _detecter_marque_secteur_llm(self.CRAWL, 'toituresbeaulieu.ca'))

    def test_un_tableau_au_lieu_d_un_objet_rend_none(self):
        with reponse('["Toitures Beaulieu", "general"]'):
            self.assertIsNone(
                _detecter_marque_secteur_llm(self.CRAWL, 'toituresbeaulieu.ca'))

    def test_crawl_en_erreur_n_appelle_pas_le_modele(self):
        with patch('sites_mgmt.llm.call_deepseek') as appel:
            r = _detecter_marque_secteur_llm({'error': 'HTTP 500'}, 'x.ca')
        self.assertIsNone(r)
        appel.assert_not_called()

    def test_crawl_vide_n_appelle_pas_le_modele(self):
        with patch('sites_mgmt.llm.call_deepseek') as appel:
            self.assertIsNone(_detecter_marque_secteur_llm({}, 'x.ca'))
        appel.assert_not_called()

    def test_une_panne_du_modele_ne_fait_pas_planter_l_appelant(self):
        with patch('sites_mgmt.llm.call_deepseek', side_effect=RuntimeError('boom')):
            self.assertIsNone(_detecter_marque_secteur_llm(self.CRAWL, 'x.ca'))


# ---------------------------------------------------------------------------
class PointDEntreeTests(SimpleTestCase):
    """`_marque_et_secteur` : LLM d'abord, repli sinon. Jamais de crash."""

    CRAWL = {'title': 'Cabinet Dentaire Dupont', 'h1': '', 'meta_description': ''}

    def test_le_llm_gagne_quand_il_repond(self):
        with reponse('{"brand": "Dupont", "sector": "general"}'):
            r = _marque_et_secteur(self.CRAWL, 'dupont.ca')
        self.assertEqual(r['source'], 'llm')

    def test_le_repli_prend_le_relais_si_le_llm_echoue(self):
        with reponse(''):
            r = _marque_et_secteur(self.CRAWL, 'dupont.ca')
        self.assertEqual(r['source'], 'heuristique')
        self.assertEqual(r['sector'], 'dental')

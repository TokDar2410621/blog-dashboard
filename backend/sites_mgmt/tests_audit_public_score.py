"""Tests : composition du score de l'audit public.

Contexte du 2026-08-23. Darius audite gridar.app avec son propre outil et
obtient 10/100. Diagnostic mesure depuis la production : PageSpeed repond bien
pour ce domaine (perf 0,77 / SEO 1,0 / a11y 0,95, moyenne 90) mais met 17 a 23
secondes contre une coupure a 25. Quand il depasse, sa composante disparait,
les poids sont renormalises, et le score reposait alors entierement sur les
positions Google. Un site correct qui ne rank pas encore ressortait a 10/100
sans que rien ne signale que la mesure etait amputee.

Deux reponses, testees ici :

1. le score DIT sur quoi il repose (`partiel`, `absentes`, `poids_effectif`) ;
2. une troisieme composante entre dans le calcul, la note on-page, qui se lit
   sur la page deja telechargee. Elle n'a ni timeout ni quota et vaut pour un
   site du premier jour, ce qui empeche le score de reposer sur les seules
   positions.

Run: python manage.py test sites_mgmt.tests_audit_public_score
"""
from django.test import SimpleTestCase

from .views import _composer_score_public, _score_onpage

TITRE_OK = 'Audit SEO gratuit de ton site en 30 secondes'          # 44 car.
DESC_OK = (
    'Entre ton domaine, decouvre ton score SEO, tes positions sur Google '
    'et les points a corriger.'
)                                                                   # 92 car.


def crawl_parfait(**surcharges):
    base = {
        'title': TITRE_OK,
        'meta_description': DESC_OK,
        'h1': 'Audit SEO gratuit',
        'h2_list': ['Comment ca marche', 'Ce que tu recois'],
    }
    base.update(surcharges)
    return base


def html_parfait(nb_h1=1, jsonld=True):
    h1 = '<h1>Audit SEO gratuit</h1>' * nb_h1
    ld = '<script type="application/ld+json">{"@type":"WebSite"}</script>' if jsonld else ''
    return f'<html><head>{ld}</head><body>{h1}<h2>Section</h2></body></html>'


def positions(*couples):
    """(position, verifie) -> la forme que rend la verification de position."""
    return [
        {'keyword': f'mot {i}', 'position': pos, 'checked': verifie}
        for i, (pos, verifie) in enumerate(couples)
    ]


def onpage(score):
    """Une note on-page deja calculee, pour tester la composition seule."""
    return {'score': score, 'controles': []}


# ---------------------------------------------------------------------------
class NoteOnPageTests(SimpleTestCase):
    """La composante qui, elle, est mesurable sur tous les sites."""

    def test_page_irreprochable_vaut_cent(self):
        r = _score_onpage(crawl_parfait(), html_parfait())
        self.assertEqual(r['score'], 100)
        self.assertTrue(all(c['reussi'] for c in r['controles']))

    def test_sans_crawl_aucune_note(self):
        """Pas de page, pas de mesure. Un zero se lirait comme un verdict."""
        self.assertIsNone(_score_onpage({}, ''))
        self.assertIsNone(_score_onpage(None, ''))

    def test_crawl_en_erreur_aucune_note(self):
        self.assertIsNone(_score_onpage({'error': 'HTTP 500'}, ''))

    def test_title_absent_coute_sa_presence_et_sa_longueur(self):
        r = _score_onpage(crawl_parfait(title=''), html_parfait())
        self.assertEqual(r['score'], 100 - 15 - 10)

    def test_title_trop_long_ne_coute_que_la_longueur(self):
        r = _score_onpage(crawl_parfait(title='a' * 90), html_parfait())
        self.assertEqual(r['score'], 90)

    def test_meta_description_absente(self):
        r = _score_onpage(crawl_parfait(meta_description=''), html_parfait())
        self.assertEqual(r['score'], 100 - 15 - 10)

    def test_meta_description_trop_courte(self):
        r = _score_onpage(crawl_parfait(meta_description='Trop court.'), html_parfait())
        self.assertEqual(r['score'], 90)

    def test_deux_h1_coutent_l_unicite(self):
        r = _score_onpage(crawl_parfait(), html_parfait(nb_h1=2))
        self.assertEqual(r['score'], 90)
        controles = {c['cle']: c['reussi'] for c in r['controles']}
        self.assertTrue(controles['h1_present'])
        self.assertFalse(controles['h1_unique'])

    def test_absence_de_donnees_structurees(self):
        r = _score_onpage(crawl_parfait(), html_parfait(jsonld=False))
        self.assertEqual(r['score'], 85)

    def test_absence_de_sous_titres(self):
        r = _score_onpage(crawl_parfait(h2_list=[]), html_parfait())
        self.assertEqual(r['score'], 90)

    def test_sans_html_le_json_ld_ne_peut_pas_etre_vu(self):
        """Le crawl a repondu mais le HTML n'a pas ete conserve."""
        r = _score_onpage(crawl_parfait(), '')
        controles = {c['cle']: c['reussi'] for c in r['controles']}
        self.assertFalse(controles['donnees_structurees'])
        # Le H1 du crawl sert de repli pour l'unicite plutot que de punir.
        self.assertTrue(controles['h1_unique'])
        self.assertEqual(r['score'], 85)

    def test_chaque_controle_est_nomme_et_pondere(self):
        r = _score_onpage(crawl_parfait(), html_parfait())
        self.assertEqual(len(r['controles']), 8)
        self.assertEqual(sum(c['poids'] for c in r['controles']), 100)
        self.assertTrue(all(c['libelle'] for c in r['controles']))


# ---------------------------------------------------------------------------
class ScoreCompletTests(SimpleTestCase):
    """Les trois composantes repondent : ponderation 40 / 35 / 25 nominale."""

    def test_ponderation_annoncee(self):
        r = _composer_score_public(
            {'avg': 90},
            positions((3, True), (7, True), (25, True), (None, True)),
            onpage(80),
        )
        # 90*0,40 + 80*0,35 + 50*0,25 = 36 + 28 + 12,5 = 76,5
        self.assertEqual(r['composite_score'], 76)
        self.assertFalse(r['partiel'])
        self.assertEqual(r['absentes'], [])
        self.assertEqual(
            [(c['cle'], c['poids_effectif']) for c in r['composantes']],
            [('pagespeed', 40), ('onpage', 35), ('rankings', 25)],
        )

    def test_le_detail_expose_la_valeur_de_chaque_composante(self):
        r = _composer_score_public({'avg': 90}, positions((1, True), (2, True)), onpage(70))
        par_cle = {c['cle']: c['valeur'] for c in r['composantes']}
        self.assertEqual(par_cle, {'pagespeed': 90, 'onpage': 70, 'rankings': 100})


# ---------------------------------------------------------------------------
class PageSpeedManquantTests(SimpleTestCase):
    """Le cas qui a produit le 10/100."""

    RANK_GRIDAR = positions(
        (3, True), (None, True), (None, True), (None, True), (None, True),
        (None, True), (None, True), (None, True), (None, True), (None, True),
    )  # 1 mot-cle sur 10 dans le top 10 -> composante rankings a 10

    def test_le_score_est_annonce_partiel(self):
        r = _composer_score_public({'error': 'PageSpeed: timeout'},
                                   self.RANK_GRIDAR, onpage(75))
        self.assertTrue(r['partiel'])
        self.assertEqual([a['cle'] for a in r['absentes']], ['pagespeed'])

    def test_l_on_page_empeche_le_score_de_s_effondrer(self):
        """La demonstration, figee. Meme site, meme timeout PageSpeed."""
        avant = _composer_score_public({'error': 'timeout'}, self.RANK_GRIDAR, None)
        apres = _composer_score_public({'error': 'timeout'}, self.RANK_GRIDAR, onpage(75))
        self.assertEqual(avant['composite_score'], 10)   # positions seules
        self.assertEqual(apres['composite_score'], 48)   # on-page + positions

    def test_avec_pagespeed_le_meme_site_monte_encore(self):
        r = _composer_score_public({'avg': 90}, self.RANK_GRIDAR, onpage(75))
        # 90*0,40 + 75*0,35 + 10*0,25 = 36 + 26,25 + 2,5 = 64,75
        self.assertEqual(r['composite_score'], 65)
        self.assertFalse(r['partiel'])

    def test_la_raison_de_l_absence_est_remontee_telle_quelle(self):
        r = _composer_score_public({'error': 'PageSpeed: timeout'},
                                   positions((5, True)), onpage(60))
        self.assertEqual(r['absentes'][0]['raison'], 'PageSpeed: timeout')

    def test_une_absence_sans_message_reste_explicite(self):
        r = _composer_score_public({}, positions((5, True)), onpage(60))
        self.assertEqual(r['absentes'][0]['raison'], 'mesure indisponible')

    def test_le_poids_effectif_montre_la_renormalisation(self):
        r = _composer_score_public({'error': 'timeout'}, positions((5, True)), onpage(60))
        par_cle = {c['cle']: c for c in r['composantes']}
        self.assertEqual(par_cle['onpage']['poids_nominal'], 35)
        # 35 annonces, 58 reellement appliques : c'est ca qu'il fallait dire.
        self.assertEqual(par_cle['onpage']['poids_effectif'], 58)
        self.assertEqual(par_cle['rankings']['poids_effectif'], 42)


# ---------------------------------------------------------------------------
class PositionsManquantesTests(SimpleTestCase):
    def test_aucun_mot_cle_verifiable(self):
        r = _composer_score_public({'avg': 82}, positions((None, False)), onpage(60))
        # (82*0,40 + 60*0,35) / 0,75 = 53,8 / 0,75 = 71,7
        self.assertEqual(r['composite_score'], 72)
        self.assertTrue(r['partiel'])
        self.assertEqual([a['cle'] for a in r['absentes']], ['rankings'])

    def test_un_mot_cle_non_verifie_ne_compte_pas_comme_un_echec(self):
        """Un quota Serper epuise ne doit pas se lire comme un site qui ne rank pas."""
        tous = _composer_score_public({'avg': 80}, positions((3, True), (4, True)), onpage(70))
        un_seul = _composer_score_public(
            {'avg': 80}, positions((3, True), (None, False)), onpage(70))
        self.assertEqual(tous['composite_score'], un_seul['composite_score'])

    def test_liste_de_positions_vide(self):
        r = _composer_score_public({'avg': 70}, [], onpage(70))
        self.assertEqual(r['composite_score'], 70)
        self.assertTrue(r['partiel'])


# ---------------------------------------------------------------------------
class RienDeMesurableTests(SimpleTestCase):
    def test_aucune_composante_ne_rend_aucun_chiffre(self):
        r = _composer_score_public({'error': 'timeout'}, positions((None, False)), None)
        self.assertIsNone(r['composite_score'])
        # Pas de chiffre, donc rien a qualifier de partiel : c'est l'absence
        # totale de mesure, que le frontend affiche deja par un tiret.
        self.assertFalse(r['partiel'])
        self.assertEqual(len(r['absentes']), 3)

    def test_entrees_nulles_ne_font_pas_planter(self):
        r = _composer_score_public({}, None, None)
        self.assertIsNone(r['composite_score'])

    def test_l_on_page_seul_suffit_a_sortir_un_chiffre(self):
        """Un site tout neuf, PageSpeed en panne : il reste quelque chose a dire."""
        r = _composer_score_public({'error': 'timeout'}, positions((None, False)), onpage(85))
        self.assertEqual(r['composite_score'], 85)
        self.assertTrue(r['partiel'])
        self.assertEqual(len(r['absentes']), 2)

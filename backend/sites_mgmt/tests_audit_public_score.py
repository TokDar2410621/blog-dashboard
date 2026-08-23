"""Tests : composition du score de l'audit public.

Contexte du 2026-08-23. Darius audite gridar.app avec son propre outil et
obtient 10/100. Diagnostic mesure depuis la production : PageSpeed repond bien
pour ce domaine (perf 0,77 / SEO 1,0 / a11y 0,95, soit une moyenne de 90) mais
met 17 a 23 secondes, contre une coupure a 25. Quand il depasse, sa composante
de 60 % disparait, les poids sont renormalises, et le score devient 100 % les
positions. Le meme site, la meme seconde, note 10 ou 54 selon qu'une API
externe repond en 24 ou en 26 secondes.

Le calcul ne peut pas empecher une mesure d'echouer. Il doit par contre DIRE
qu'elle a echoue, au lieu de rendre un chiffre qui se lit comme un verdict.
Ces tests fixent ce contrat.

Run: python manage.py test sites_mgmt.tests_audit_public_score
"""
from django.test import SimpleTestCase

from .views import _composer_score_public


def positions(*couples):
    """(position, verifie) -> la forme que rend la verification de position."""
    return [
        {'keyword': f'mot {i}', 'position': pos, 'checked': verifie}
        for i, (pos, verifie) in enumerate(couples)
    ]


class ScoreCompletTests(SimpleTestCase):
    """Les deux composantes repondent : ponderation 60/40 nominale."""

    def test_les_deux_composantes_donnent_la_ponderation_annoncee(self):
        r = _composer_score_public(
            {'avg': 90},
            positions((3, True), (7, True), (25, True), (None, True)),
        )
        # 90 * 0,6 + 50 * 0,4 = 74
        self.assertEqual(r['composite_score'], 74)
        self.assertFalse(r['partiel'])
        self.assertEqual(r['absentes'], [])
        self.assertEqual(
            [(c['cle'], c['poids_effectif']) for c in r['composantes']],
            [('pagespeed', 60), ('rankings', 40)],
        )

    def test_le_detail_expose_la_valeur_de_chaque_composante(self):
        r = _composer_score_public({'avg': 90}, positions((1, True), (2, True)))
        par_cle = {c['cle']: c for c in r['composantes']}
        self.assertEqual(par_cle['pagespeed']['valeur'], 90)
        self.assertEqual(par_cle['rankings']['valeur'], 100)


class PageSpeedManquantTests(SimpleTestCase):
    """Le cas qui a produit le 10/100."""

    def test_sans_pagespeed_le_score_est_annonce_partiel(self):
        r = _composer_score_public(
            {'error': 'PageSpeed: timeout'},
            positions((3, True), (None, True), (None, True), (None, True),
                      (None, True), (None, True), (None, True), (None, True),
                      (None, True), (None, True)),
        )
        self.assertEqual(r['composite_score'], 10)  # le fameux 10/100
        self.assertTrue(r['partiel'])
        self.assertEqual([a['cle'] for a in r['absentes']], ['pagespeed'])

    def test_la_raison_de_l_absence_est_remontee_telle_quelle(self):
        r = _composer_score_public({'error': 'PageSpeed: timeout'}, positions((5, True)))
        self.assertEqual(r['absentes'][0]['raison'], 'PageSpeed: timeout')

    def test_une_absence_sans_message_reste_explicite(self):
        r = _composer_score_public({}, positions((5, True)))
        self.assertEqual(r['absentes'][0]['raison'], 'mesure indisponible')

    def test_le_poids_effectif_montre_la_renormalisation(self):
        r = _composer_score_public({'error': 'timeout'}, positions((5, True)))
        rankings = r['composantes'][0]
        self.assertEqual(rankings['cle'], 'rankings')
        self.assertEqual(rankings['poids_nominal'], 40)
        # 40 annonces, 100 reellement appliques : c'est ca qu'il fallait dire.
        self.assertEqual(rankings['poids_effectif'], 100)

    def test_meme_site_deux_verdicts_selon_que_pagespeed_repond(self):
        """La demonstration du probleme, figee en test."""
        rank = positions((3, True), (None, True), (None, True), (None, True),
                         (None, True), (None, True), (None, True), (None, True),
                         (None, True), (None, True))
        sans = _composer_score_public({'error': 'timeout'}, rank)
        avec = _composer_score_public({'avg': 90}, rank)
        self.assertEqual(sans['composite_score'], 10)
        self.assertEqual(avec['composite_score'], 58)
        self.assertTrue(sans['partiel'])
        self.assertFalse(avec['partiel'])


class PositionsManquantesTests(SimpleTestCase):
    def test_aucun_mot_cle_verifiable_laisse_pagespeed_seul(self):
        r = _composer_score_public({'avg': 82}, positions((None, False), (None, False)))
        self.assertEqual(r['composite_score'], 82)
        self.assertTrue(r['partiel'])
        self.assertEqual([a['cle'] for a in r['absentes']], ['rankings'])

    def test_un_mot_cle_non_verifie_ne_compte_pas_comme_un_echec(self):
        """Un quota Serper epuise ne doit pas se lire comme un site qui ne rank pas."""
        tous_verifies = _composer_score_public({'avg': 80}, positions((3, True), (4, True)))
        un_seul_verifie = _composer_score_public(
            {'avg': 80}, positions((3, True), (None, False)))
        self.assertEqual(tous_verifies['composite_score'],
                         un_seul_verifie['composite_score'])

    def test_liste_de_positions_vide(self):
        r = _composer_score_public({'avg': 70}, [])
        self.assertEqual(r['composite_score'], 70)
        self.assertTrue(r['partiel'])


class RienDeMesurableTests(SimpleTestCase):
    def test_aucune_composante_ne_rend_aucun_chiffre(self):
        r = _composer_score_public({'error': 'timeout'}, positions((None, False)))
        self.assertIsNone(r['composite_score'])
        # Pas de chiffre, donc rien a qualifier de partiel : c'est l'absence
        # totale de mesure, que le frontend affiche deja par un tiret.
        self.assertFalse(r['partiel'])
        self.assertEqual(len(r['absentes']), 2)

    def test_entrees_nulles_ne_font_pas_planter(self):
        r = _composer_score_public({}, None)
        self.assertIsNone(r['composite_score'])

"""Tests : le calculateur de ROI SEO public.

Constate en production le 2026-08-25, sur une capture d'ecran de l'outil en
ligne. Pour 1000 visiteurs/mois, 1,5 % de conversion, 6500 $ par client et
100 $/mois de budget, il affichait :

    Conservateur   2 389 213 $   +199001 %   rentable des le mois 1
    Modere         3 616 019 $   +301235 %   rentable des le mois 1
    Agressif       6 620 491 $   +551608 %   rentable des le mois 1

Deux defauts se cumulaient :

1. **Le revenu deja acquis etait compte comme un gain.** Le calcul faisait
   `revenu = trafic_total x conversion x valeur`, donc 1000 x 1,5 % x 6500 =
   97 500 $ par mois de chiffre d'affaires EXISTANT credite a un budget SEO
   de 100 $. C'est ce qui produisait les ROI a six chiffres et le "rentable
   des le mois 1" systematique.
2. **La croissance composait sans plafond.** `trafic = trafic x (1 + taux)`
   douze fois de suite, jusqu'a +18 %/mois. Le scenario dit "conservateur"
   triplait le trafic en un an, l'agressif le multipliait par 12,2.

Plus une ligne de vente codee en dur dans le payload, qui promettait
d'atteindre le scenario agressif.

Ce fichier verrouille les trois corrections.

Run: python manage.py test sites_mgmt.tests_roi_calculateur
"""
from django.core.cache import cache
from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory

from .views_tools import PublicSeoRoiCalculatorView, _fraction_du_gain


class BaseRoiTests(SimpleTestCase):
    """La vue est limitee a 3 appels par minute et par IP. Les compteurs
    vivent dans le cache : sans ce vidage, le quatrieme test de la session
    recoit un 429 au lieu du resultat qu'il verifie."""

    def setUp(self):
        cache.clear()


def appeler(**entrees):
    corps = {
        'domain': 'exemple.ca',
        'monthly_traffic': 1000,
        'avg_conversion_rate': 1.5,
        'avg_deal_value': 6500,
        'monthly_seo_investment': 100,
    }
    corps.update(entrees)
    requete = APIRequestFactory().post('/x', corps, format='json')
    return PublicSeoRoiCalculatorView.as_view()(requete)


class RevenuIncrementalTests(BaseRoiTests):
    """Le defaut principal : compter le chiffre d'affaires existant."""

    def test_le_revenu_deja_acquis_est_exclu_du_gain(self):
        d = appeler().data
        # 1000 x 1,5 % x 6500 = 97 500 $/mois que le site produit deja.
        self.assertEqual(d['baseline_monthly_revenue'], 97500.0)
        premier = d['scenarios']['moderate']['monthly_projections'][0]
        # Le revenu du mois 1 doit etre celui des visiteurs GAGNES seulement,
        # tres loin des 97 500 $ de base.
        self.assertLess(premier['projected_revenue'], 10000)

    def test_le_revenu_mensuel_suit_exactement_le_trafic_gagne(self):
        d = appeler().data
        for m in d['scenarios']['moderate']['monthly_projections']:
            attendu = m['traffic_gained'] * 0.015 * 6500
            self.assertAlmostEqual(m['projected_revenue'], attendu, delta=1.0)

    def test_le_revenu_par_visiteur_est_expose(self):
        """Le ROI en pourcentage explose quand le budget est petit devant la
        valeur d'un client. Montrer ce qui le pilote evite qu'il se lise
        comme un chiffre sorti de nulle part."""
        d = appeler().data
        self.assertEqual(d['revenue_per_visitor'], 97.5)
        self.assertIn('97.50', d['insight'])

    def test_un_budget_eleve_peut_ne_jamais_etre_rentable(self):
        """L'ancienne version rendait toujours "rentable des le mois 1"."""
        d = appeler(monthly_seo_investment=500000).data
        s = d['scenarios']['conservative']
        self.assertIsNone(s['break_even_month'])
        self.assertLess(s['roi_percent'], 0)
        self.assertIn('pas rembourse', d['insight'])


class CroissanceTests(BaseRoiTests):
    """La croissance demarre lentement, accelere, puis plafonne."""

    def test_la_courbe_part_de_zero_et_atteint_le_gain_au_mois_12(self):
        self.assertAlmostEqual(_fraction_du_gain(0), 0.0, places=6)
        self.assertAlmostEqual(_fraction_du_gain(12), 1.0, places=6)

    def test_la_courbe_est_monotone(self):
        valeurs = [_fraction_du_gain(m) for m in range(13)]
        self.assertEqual(valeurs, sorted(valeurs))

    def test_le_gain_ne_tombe_pas_tout_au_premier_mois(self):
        """Le SEO ne produit pas son plein effet le mois de la signature."""
        self.assertLess(_fraction_du_gain(1), 0.10)

    def test_la_croissance_plafonne_au_lieu_de_composer(self):
        """L'ancienne version multipliait le trafic par 3,0 (conservateur) et
        12,2 (agressif) en douze mois."""
        d = appeler().data
        for cle, plafond in (('conservative', 1.35), ('moderate', 1.75),
                             ('aggressive', 2.6)):
            dernier = d['scenarios'][cle]['monthly_projections'][-1]
            facteur = dernier['projected_traffic'] / 1000
            self.assertLess(facteur, plafond, cle)

    def test_le_gain_progresse_de_moins_en_moins_vite_sur_la_fin(self):
        proj = appeler().data['scenarios']['moderate']['monthly_projections']
        gains = [m['traffic_gained'] for m in proj]
        deltas = [b - a for a, b in zip(gains, gains[1:])]
        self.assertGreater(deltas[2], deltas[-1])   # plateau en fin d'annee


class HypothesesTests(BaseRoiTests):

    def test_les_taux_sont_annonces_comme_des_hypotheses(self):
        d = appeler().data
        self.assertEqual(d['scenarios']['moderate']['assumed_growth_percent'], 70)
        self.assertIn('hypothese', d['methodologie'].lower())
        self.assertIn('supplementaire', d['methodologie'].lower())

    def test_l_utilisateur_peut_imposer_sa_propre_hypothese(self):
        d = appeler(expected_growth_percent=10).data
        self.assertEqual(list(d['scenarios']), ['moderate'])
        self.assertEqual(d['scenarios']['moderate']['assumed_growth_percent'], 10)
        self.assertEqual(d['scenarios']['moderate']['name'], 'Ton hypothese')

    def test_aucune_ligne_de_vente_dans_le_payload(self):
        """Le payload portait `gridar_advantage`, une phrase promettant
        d'atteindre le scenario agressif, dans ce qui se presente comme un
        calculateur neutre."""
        d = appeler().data
        self.assertNotIn('gridar_advantage', d)
        self.assertNotIn('gridar', str(d).lower())

    def test_la_methodologie_dit_que_le_domaine_n_est_pas_analyse(self):
        """Le domaine est valide puis sert d'etiquette : deux sites avec les
        memes entrees recoivent la meme reponse."""
        a = appeler(domain='alpha.ca').data
        b = appeler(domain='bravo.ca').data
        self.assertEqual(a['scenarios'], b['scenarios'])
        self.assertIn('hypotheses', a['methodologie'].lower())


class EntreesTests(BaseRoiTests):

    def test_un_domaine_invalide_est_refuse(self):
        self.assertEqual(appeler(domain='').status_code, 400)

    def test_des_valeurs_non_numeriques_sont_refusees(self):
        self.assertEqual(appeler(monthly_traffic='beaucoup').status_code, 400)

    def test_des_valeurs_negatives_sont_refusees(self):
        self.assertEqual(appeler(avg_deal_value=-100).status_code, 400)

    def test_un_budget_a_zero_ne_divise_pas_par_zero(self):
        d = appeler(monthly_seo_investment=0).data
        self.assertIsNone(d['scenarios']['moderate']['roi_percent'])
        self.assertIsNone(
            d['scenarios']['moderate']['monthly_projections'][0]['roi_percentage'])

    def test_un_trafic_a_zero_donne_zero_sans_planter(self):
        d = appeler(monthly_traffic=0).data
        self.assertEqual(d['baseline_monthly_revenue'], 0.0)
        self.assertEqual(d['scenarios']['moderate']['year_one_revenue'], 0)


class TauxDeConversionTests(BaseRoiTests):
    """Le taux de conversion est le chiffre que personne ne connait, et tout
    le resultat lui est proportionnel."""

    def test_le_taux_se_derive_du_nombre_de_demandes(self):
        """Un commerce sait dire "j'ai eu 15 appels", pas "je convertis a
        1,5 %". Le taux se derive de deux choses qu'il connait."""
        d = appeler(monthly_leads=15).data
        self.assertEqual(d['conversion_source'], 'derive_des_demandes')
        self.assertEqual(d['inputs']['avg_conversion_rate'], 1.5)
        self.assertEqual(d['inputs']['monthly_leads'], 15.0)
        self.assertIn('15 demandes pour 1000 visiteurs', d['insight'])

    def test_le_taux_saisi_reste_accepte(self):
        d = appeler(avg_conversion_rate=3.2).data
        self.assertEqual(d['conversion_source'], 'taux_saisi')
        self.assertEqual(d['inputs']['avg_conversion_rate'], 3.2)
        self.assertIsNone(d['inputs']['monthly_leads'])

    def test_les_demandes_ont_priorite_sur_le_taux(self):
        d = appeler(monthly_leads=50, avg_conversion_rate=99).data
        self.assertEqual(d['inputs']['avg_conversion_rate'], 5.0)

    def test_un_taux_tres_bas_est_accepte(self):
        """Le formulaire imposait un plancher de 0,1 %. Un site a fort trafic
        peut convertir a 0,05 %, valeur vraie et pourtant refusee."""
        d = appeler(avg_conversion_rate=0.05).data
        self.assertEqual(d['inputs']['avg_conversion_rate'], 0.05)
        self.assertGreater(d['scenarios']['moderate']['year_one_revenue'], 0)

    def test_la_fourchette_de_sensibilite_encadre_le_chiffre_saisi(self):
        """Le revenu est proportionnel au taux : un chiffre unique laisserait
        croire a une precision que l'entree n'a pas."""
        d = appeler(monthly_leads=15).data
        bas, milieu, haut = d['sensitivity']['points']
        self.assertEqual(milieu['label'], 'Ton chiffre')
        self.assertAlmostEqual(bas['conversion_percent'], 0.75, places=2)
        self.assertAlmostEqual(haut['conversion_percent'], 3.0, places=2)
        self.assertAlmostEqual(bas['year_one_revenue'] * 2,
                               milieu['year_one_revenue'], delta=2)
        self.assertAlmostEqual(haut['year_one_revenue'],
                               milieu['year_one_revenue'] * 2, delta=2)

    def test_des_demandes_sans_trafic_ne_divisent_pas_par_zero(self):
        d = appeler(monthly_traffic=0, monthly_leads=15).data
        self.assertEqual(d['conversion_source'], 'taux_saisi')
        self.assertEqual(d['baseline_monthly_revenue'], 0.0)

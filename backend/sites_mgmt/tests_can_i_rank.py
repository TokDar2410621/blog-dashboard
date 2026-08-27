"""Tests : Can I Rank, reconstruit sur des faits mesures.

Etat constate le 2026-08-27, dernier des outils publics a etre inspecte.

L'ancienne version envoyait a Gemini le titre, le H1 et la meta description
de la page d'accueil, et lui demandait de produire :

    overall_score, 5 notes de facteurs ("Autorite du domaine",
    "Niveau de competition"...), estimated_time_to_rank, et
    top_competitors: [{"domain": "<domaine1.com>", "authority": <0-100>}]

Ce dernier point est le pire defaut trouve pendant tout l'audit : le modele
INVENTAIT des noms de domaines concurrents et leur attribuait un score
d'autorite fabrique. L'outil pouvait donc nommer une vraie entreprise qui ne
se classe pas sur le mot-cle, lui coller une "autorite : 34", et montrer ca
a un prospect. Les autres outils inventaient des chiffres sur le site de
l'utilisateur ; celui-ci en inventait sur des tiers nommes.

Et il etait 100 % hors service : dependance dure a Gemini, dont le quota
etait epuise, donc HTTP 500 pour tout le monde sans aucun repli.

La version actuelle interroge le SERP reel du mot-cle (une requete Serper) :
les concurrents sont ceux qui occupent vraiment la page, la position du site
est lue et non devinee, et le score se calcule a partir de trois composantes
verifiables. DeepSeek n'ecrit plus que le verdict et les quick wins, et son
absence ne casse rien.

Run: python manage.py test sites_mgmt.tests_can_i_rank
"""
import json
from unittest.mock import patch

from django.core.cache import cache
from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory

from .views_tools import PublicCanIRankView

CRAWL = {
    'title': 'Plombier a Jonquiere', 'h1': 'Plombier Jonquiere',
    'meta_description': 'Service de plomberie', 'h2_list': ['Urgence'],
    'body_snippet': 'plombier jonquiere urgence 24h', '_html': '<html></html>',
}
RECIT = json.dumps({
    'verdict': 'Possible',
    'quick_wins': [{'title': 'Page service', 'description': 'Creer une page dediee.'}],
})


def serp(occupants):
    """occupants = liste de (hote, rang)."""
    return [{
        'requete': 'plombier jonquiere', 'verifie': True,
        'hotes': list(occupants),
        'resultats': [
            {'hote': h, 'position': r, 'url': f'https://{h}/p', 'titre': f'{h} page'}
            for h, r in occupants
        ],
    }]


class BaseCirTests(SimpleTestCase):
    """La vue est limitee a 3 appels/minute par IP, compteurs en cache."""

    def setUp(self):
        cache.clear()

    def appeler(self, occupants=(('rival.ca', 1), ('moi.ca', 4)),
                crawl=None, recit=RECIT, serps=None, **corps):
        donnees = {'domain': 'moi.ca', 'keyword': 'plombier jonquiere'}
        donnees.update(corps)
        with patch('sites_mgmt.compare_mesures.collecter_serps',
                   return_value=serp(occupants) if serps is None else serps), \
             patch('sites_mgmt.views._crawl_homepage',
                   return_value=dict(crawl if crawl is not None else CRAWL)), \
             patch('sites_mgmt.llm.call_deepseek', return_value=recit):
            return PublicCanIRankView.as_view()(
                APIRequestFactory().post('/x', donnees, format='json'))


class ConcurrentsReelsTests(BaseCirTests):
    """Le defaut principal : des domaines tiers inventes, avec des scores."""

    def test_les_concurrents_sont_ceux_du_serp_reel(self):
        d = self.appeler(occupants=(('alpha.ca', 1), ('bravo.ca', 2))).data
        self.assertEqual([c['domain'] for c in d['top_competitors']],
                         ['alpha.ca', 'bravo.ca'])
        self.assertEqual(d['top_competitors'][0]['position'], 1)

    def test_aucun_score_d_autorite_n_est_attribue_a_un_tiers(self):
        """Serper n'expose aucune donnee de liens. Inventer une "autorite"
        sur une entreprise nommee etait indefendable."""
        d = self.appeler().data
        for c in d['top_competitors']:
            self.assertNotIn('authority', c)

    def test_aucun_delai_n_est_estime(self):
        """`estimated_time_to_rank` ("3-6 mois") n'avait aucune base."""
        d = self.appeler().data
        self.assertNotIn('estimated_time_to_rank', d)
        self.assertIn('Aucun delai', d['methodologie'])

    def test_le_modele_ne_peut_pas_ajouter_de_concurrent(self):
        """Meme si DeepSeek en inventait, la liste vient du SERP, pas de lui."""
        d = self.appeler(recit=json.dumps({
            'verdict': 'Facile',
            'top_competitors': [{'domain': 'invente.com', 'authority': 91}],
            'quick_wins': [],
        })).data
        self.assertNotIn('invente.com', [c['domain'] for c in d['top_competitors']])


class ScoreMesureTests(BaseCirTests):

    def test_la_position_reelle_est_lue_et_exposee(self):
        d = self.appeler(occupants=(('rival.ca', 1), ('moi.ca', 4))).data
        self.assertEqual(d['current_position'], 4)
        position = [f for f in d['factors'] if f['name'] == 'Position actuelle'][0]
        self.assertIn('position 4', position['evidence'])

    def test_un_site_absent_du_serp_le_dit(self):
        d = self.appeler(occupants=(('rival.ca', 1), ('autre.ca', 2))).data
        self.assertIsNone(d['current_position'])
        position = [f for f in d['factors'] if f['name'] == 'Position actuelle'][0]
        self.assertEqual(position['score'], 0)
        self.assertIn('Absent', position['evidence'])

    def test_la_pertinence_dit_ou_le_mot_cle_apparait(self):
        d = self.appeler().data
        pert = [f for f in d['factors'] if f['name'] == 'Pertinence du contenu'][0]
        self.assertIn('le titre', pert['evidence'])
        self.assertGreater(pert['score'], 0)

    def test_un_mot_cle_absent_du_site_fait_chuter_la_pertinence(self):
        d = self.appeler(crawl={
            'title': 'Boulangerie artisanale', 'h1': 'Nos pains',
            'meta_description': '', 'h2_list': [], 'body_snippet': 'pain frais',
            '_html': '<html></html>',
        }).data
        pert = [f for f in d['factors'] if f['name'] == 'Pertinence du contenu'][0]
        self.assertEqual(pert['score'], 0)
        self.assertIn("n'apparait", pert['evidence'])

    def test_chaque_facteur_porte_sa_preuve(self):
        d = self.appeler().data
        self.assertTrue(d['factors'])
        for f in d['factors']:
            self.assertTrue(f['evidence'], f['name'])
            self.assertIsInstance(f['score'], int)

    def test_le_score_global_reste_borne(self):
        for occupants in ((('moi.ca', 1),), (('rival.ca', 1),)):
            d = self.appeler(occupants=occupants).data
            self.assertGreaterEqual(d['overall_score'], 0)
            self.assertLessEqual(d['overall_score'], 100)


class SansLlmTests(BaseCirTests):
    """La route ne depend jamais d'un LLM : c'est le defaut qui rendait
    l'outil 100 % hors service quand le quota Gemini etait epuise."""

    def test_un_modele_muet_ne_casse_pas_la_reponse(self):
        d = self.appeler(recit='').data
        self.assertIn(d['verdict'], ('Facile', 'Possible', 'Difficile', 'Tres difficile'))
        self.assertTrue(d['factors'])
        self.assertEqual(d['quick_wins'], [])

    def test_un_modele_en_panne_ne_remonte_pas(self):
        with patch('sites_mgmt.compare_mesures.collecter_serps', return_value=serp((('r.ca', 1),))), \
             patch('sites_mgmt.views._crawl_homepage', return_value=dict(CRAWL)), \
             patch('sites_mgmt.llm.call_deepseek', side_effect=RuntimeError('boom')):
            r = PublicCanIRankView.as_view()(APIRequestFactory().post(
                '/x', {'domain': 'moi.ca', 'keyword': 'plombier jonquiere'}, format='json'))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data['overall_score'] >= 0)

    def test_le_verdict_ne_peut_pas_contredire_le_score(self):
        """Vu en prod le 2026-08-27 : un site absent du top 10, note 30/100,
        s'est vu attribuer le verdict "Facile" par le modele. Le verdict
        derive desormais du score mesure, le modele ne le produit plus."""
        d = self.appeler(occupants=(('rival.ca', 1), ('autre.ca', 2)),
                         crawl={'title': 'Boulangerie', 'h1': 'Pains',
                                'meta_description': '', 'h2_list': [],
                                'body_snippet': '', '_html': '<html></html>'},
                         recit=json.dumps({'verdict': 'Facile', 'quick_wins': []})).data
        self.assertLess(d['overall_score'], 45)
        self.assertIn(d['verdict'], ('Difficile', 'Tres difficile'))

    def test_un_bon_score_donne_un_bon_verdict(self):
        d = self.appeler(occupants=(('moi.ca', 1),)).data
        self.assertGreaterEqual(d['overall_score'], 45)
        self.assertIn(d['verdict'], ('Facile', 'Possible'))

    def test_sans_serp_la_vue_le_dit_au_lieu_de_deviner(self):
        """Sans la page de resultats il n'y a rien a mesurer. Repondre quand
        meme serait exactement le defaut qu'on corrige."""
        r = self.appeler(serps=None if False else [])
        self.assertEqual(r.status_code, 503)
        self.assertIn('resultats de recherche', r.data['error'])


class EntreesTests(BaseCirTests):

    def test_un_domaine_ou_un_mot_cle_manquant_est_refuse(self):
        self.assertEqual(self.appeler(domain='').status_code, 400)
        self.assertEqual(self.appeler(keyword='   ').status_code, 400)

    def test_le_mot_cle_est_normalise_et_borne(self):
        d = self.appeler(keyword='  plombier    jonquiere  ').data
        self.assertEqual(d['keyword'], 'plombier jonquiere')


class AccentsTests(BaseCirTests):
    """Le mot-cle tape sans accents doit matcher une page qui en porte.

    Constate en prod le 2026-08-27 : tokamdarius.ca etait classe #1 sur
    "developpeur web jonquiere" et l'outil affichait "Pertinence 0/100, le
    mot-cle n'apparait ni dans le titre, ni dans le H1..." alors que le titre
    etait "Tokam Darius | Developpeur Web a Jonquiere" (avec accents). Deux
    affirmations contradictoires cote a cote, dont une fausse, montrees au
    proprietaire du site.
    """

    ACCENTUE = {
        'title': 'Tokam Darius | Developpeur Web a Jonquiere'.replace('e', 'e'),
        'h1': 'Developpeur web au Quebec', 'meta_description': '',
        'h2_list': [], 'body_snippet': '', '_html': '<html></html>',
    }

    def test_un_titre_accentue_matche_un_mot_cle_sans_accents(self):
        crawl = dict(self.ACCENTUE)
        crawl['title'] = 'Tokam Darius | D\u00e9veloppeur Web \u00e0 Jonqui\u00e8re'
        d = self.appeler(crawl=crawl, keyword='developpeur web jonquiere').data
        pert = [f for f in d['factors'] if f['name'] == 'Pertinence du contenu'][0]
        self.assertGreater(pert['score'], 0)
        self.assertIn('le titre', pert['evidence'])

    def test_un_mot_cle_accentue_matche_une_page_sans_accents(self):
        crawl = dict(self.ACCENTUE)
        crawl['title'] = 'Developpeur Web a Jonquiere'
        d = self.appeler(crawl=crawl,
                         keyword='d\u00e9veloppeur web jonqui\u00e8re').data
        pert = [f for f in d['factors'] if f['name'] == 'Pertinence du contenu'][0]
        self.assertGreater(pert['score'], 0)

    def test_un_site_classe_premier_n_est_pas_declare_hors_sujet(self):
        """Le scenario exact vu en prod, de bout en bout."""
        crawl = dict(self.ACCENTUE)
        crawl['title'] = 'Tokam Darius | D\u00e9veloppeur Web \u00e0 Jonqui\u00e8re'
        d = self.appeler(occupants=(('moi.ca', 1),), crawl=crawl,
                         keyword='developpeur web jonquiere').data
        self.assertEqual(d['current_position'], 1)
        pert = [f for f in d['factors'] if f['name'] == 'Pertinence du contenu'][0]
        self.assertGreater(pert['score'], 0, "classe #1 mais declare hors sujet")

    def test_un_mot_cle_reellement_absent_reste_a_zero(self):
        """La normalisation ne doit pas rendre tout le monde pertinent."""
        crawl = dict(self.ACCENTUE)
        crawl['title'] = 'Boulangerie artisanale'
        crawl['h1'] = 'Nos pains'
        d = self.appeler(crawl=crawl, keyword='developpeur web jonquiere').data
        pert = [f for f in d['factors'] if f['name'] == 'Pertinence du contenu'][0]
        self.assertEqual(pert['score'], 0)

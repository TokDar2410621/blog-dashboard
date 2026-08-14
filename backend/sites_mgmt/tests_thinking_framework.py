"""Tests for the falsifiability contract on SEO recommendations.

Everything here is pure data in, data out: the module makes no network call
and touches no model, so nothing needs mocking.

Run all:
    python manage.py test sites_mgmt.tests_thinking_framework
"""
from django.test import SimpleTestCase

from .thinking_framework import (
    CHAMPS_OBLIGATOIRES, INDICATEURS_PAR_TYPE, RECOMMENDATION_SYSTEM_PROMPT,
    SCALE_SANITY, TYPES_RECOMMANDATION, check_scale_sanity, deviner_type,
    enrich_recommendation, validate_recommendation,
)


# A recommendation that carries all four fields, used as the baseline the
# negative cases mutate one field at a time.
RECO_COMPLETE = {
    'action': "Retirer la balise noindex de la page /services-de-plomberie",
    'type': 'indexation',
    'observation': (
        "La page /services-de-plomberie renvoie une balise meta robots "
        "noindex dans le HTML servi, et la Search Console la classe dans "
        "« Exclue par la balise noindex » depuis le 12 mars."
    ),
    'dependances': ["Avoir l'accès au CMS pour modifier l'entête de la page"],
    'test_echec': (
        "Si l'inspection d'URL indique toujours que la page est exclue après "
        "21 jours, l'hypothèse est fausse et le blocage vient d'ailleurs."
    ),
    'indicateur_avance': (
        "le nombre d'URL indexées dans le rapport Pages de la Search Console"
    ),
}


# Written as escapes so the characters this repo bans appear nowhere in the
# file, not even inside the assertions that forbid them.
CADRATIN = '\u2014'
DEMI_CADRATIN = '\u2013'


def _codes(problemes):
    return [p['code'] for p in problemes]


class SystemPromptTests(SimpleTestCase):
    def test_imposes_the_four_fields(self):
        for champ in CHAMPS_OBLIGATOIRES:
            self.assertIn(champ, RECOMMENDATION_SYSTEM_PROMPT, f'champ {champ}')

    def test_lists_every_type_the_table_knows(self):
        """The prompt is built from the table, so the two cannot drift apart."""
        for type_ in TYPES_RECOMMANDATION:
            self.assertIn(type_, RECOMMENDATION_SYSTEM_PROMPT, f'type {type_}')

    def test_is_written_in_french_for_a_quebec_audience(self):
        for mot in ('recommandation', 'Québec', "tests d'échec",
                    'français du Québec', 'JSON'):
            self.assertIn(mot, RECOMMENDATION_SYSTEM_PROMPT, mot)

    def test_names_the_capacity_failure_upstream_warns_about(self):
        self.assertIn('pages de localité', RECOMMENDATION_SYSTEM_PROMPT)
        self.assertIn('deux personnes', RECOMMENDATION_SYSTEM_PROMPT)

    def test_no_dash_that_breaks_the_house_style(self):
        self.assertNotIn(CADRATIN, RECOMMENDATION_SYSTEM_PROMPT)
        self.assertNotIn(DEMI_CADRATIN, RECOMMENDATION_SYSTEM_PROMPT)


class TableTests(SimpleTestCase):
    def test_every_type_carries_what_enrichment_needs(self):
        for type_, fiche in INDICATEURS_PAR_TYPE.items():
            for cle in ('libelle', 'indicateur', 'verification_immediate',
                        'delai_min_jours', 'delai_max_jours', 'unite_defaut',
                        'mots_cles'):
                self.assertIn(cle, fiche, f'{type_} sans {cle}')
            self.assertLess(fiche['delai_min_jours'], fiche['delai_max_jours'],
                            f'{type_}: fenêtre inversée')
            self.assertIn(fiche['unite_defaut'], SCALE_SANITY['cout_heures'],
                          f'{type_}: unité par défaut sans coût')

    def test_crux_window_is_respected(self):
        """Field CWV data is a 28-day rolling average, so nothing before that."""
        self.assertGreaterEqual(
            INDICATEURS_PAR_TYPE['vitesse']['delai_min_jours'], 28,
        )

    def test_no_dash_anywhere_in_the_table(self):
        for type_, fiche in INDICATEURS_PAR_TYPE.items():
            for cle in ('libelle', 'indicateur', 'verification_immediate'):
                self.assertNotIn(CADRATIN, fiche[cle], f'{type_}.{cle}')
                self.assertNotIn(DEMI_CADRATIN, fiche[cle], f'{type_}.{cle}')


class DevinerTypeTests(SimpleTestCase):
    def test_maps_wording_to_the_right_family(self):
        cas = {
            "Retirer le noindex des articles de blogue": 'indexation',
            "Compresser les images pour améliorer le LCP": 'vitesse',
            "Réécrire la page de service, contenu mince": 'contenu_refonte',
            "Ajouter 12 liens internes vers la page pilier": 'maillage_interne',
            "Compléter la fiche Google Business avec les horaires": 'seo_local',
            "Ajouter le balisage JSON-LD LocalBusiness": 'donnees_structurees',
            "Fusionner les trois pages qui se cannibalisent": 'consolidation',
            "Faire parler de la marque sur Reddit et YouTube": 'notoriete',
            "Réécrire la meta description de la page d'accueil": 'balises_titres',
        }
        for texte, attendu in cas.items():
            self.assertEqual(deviner_type(texte), attendu, texte)

    def test_local_reading_wins_over_the_creation_verb(self):
        """"Créer 30 pages de localité" is a local job, not a generic content job."""
        self.assertEqual(
            deviner_type("Créer 30 pages de localité pour les villes desservies"),
            'seo_local',
        )

    def test_unknown_wording_falls_back(self):
        self.assertEqual(deviner_type("Faire quelque chose de bien"), 'autre')
        self.assertEqual(deviner_type(''), 'autre')

    def test_accents_do_not_change_the_answer(self):
        self.assertEqual(
            deviner_type("pages de localite"), deviner_type("pages de localité"),
        )


class ValidateTests(SimpleTestCase):
    def test_complete_recommendation_passes(self):
        self.assertEqual(validate_recommendation(RECO_COMPLETE), [])

    def test_each_missing_field_is_an_error(self):
        attendus = {
            'observation': 'observation_manquante',
            'dependances': 'dependances_absentes',
            'test_echec': 'test_echec_manquant',
            'indicateur_avance': 'indicateur_manquant',
        }
        for champ, code in attendus.items():
            reco = dict(RECO_COMPLETE)
            reco.pop(champ)
            problemes = validate_recommendation(reco)
            self.assertIn(code, _codes(problemes), champ)
            erreur = next(p for p in problemes if p['code'] == code)
            self.assertEqual(erreur['niveau'], 'erreur')
            self.assertEqual(erreur['champ'], champ)
            self.assertTrue(erreur['correction'], 'une correction est attendue')

    def test_errors_come_before_warnings(self):
        reco = dict(RECO_COMPLETE)
        reco.pop('test_echec')
        reco.pop('type')
        niveaux = [p['niveau'] for p in validate_recommendation(reco)]
        self.assertEqual(niveaux, sorted(niveaux, key=lambda n: n != 'erreur'))

    def test_observation_that_restates_the_action_is_refused(self):
        reco = dict(RECO_COMPLETE)
        reco['observation'] = "Retirer la balise noindex de la page /services-de-plomberie."
        self.assertIn('observation_reformule_action',
                      _codes(validate_recommendation(reco)))

    def test_observation_without_any_finding_is_flagged(self):
        reco = dict(RECO_COMPLETE)
        reco['observation'] = (
            "Les bonnes pratiques recommandent de soigner ce genre de chose "
            "pour bien performer dans les moteurs de recherche modernes."
        )
        self.assertIn('observation_sans_constat',
                      _codes(validate_recommendation(reco)))

    def test_empty_dependency_list_is_accepted(self):
        """An empty list is a claim that nothing blocks; silence is not."""
        reco = dict(RECO_COMPLETE, dependances=[])
        self.assertEqual(validate_recommendation(reco), [])

    def test_dependency_field_must_be_a_list(self):
        reco = dict(RECO_COMPLETE, dependances="l'accès au CMS")
        self.assertIn('dependances_format', _codes(validate_recommendation(reco)))

    def test_dependency_repeating_the_action_is_flagged(self):
        reco = dict(RECO_COMPLETE)
        reco['dependances'] = [RECO_COMPLETE['action']]
        self.assertIn('dependance_circulaire', _codes(validate_recommendation(reco)))

    def test_failure_test_without_a_negative_outcome_is_an_error(self):
        reco = dict(RECO_COMPLETE)
        reco['test_echec'] = "On vérifiera la Search Console dans 21 jours."
        problemes = validate_recommendation(reco)
        self.assertIn('test_echec_non_falsifiable', _codes(problemes))
        erreur = next(p for p in problemes
                      if p['code'] == 'test_echec_non_falsifiable')
        self.assertEqual(erreur['niveau'], 'erreur')

    def test_failure_test_without_a_deadline_is_a_warning(self):
        reco = dict(RECO_COMPLETE)
        reco['test_echec'] = (
            "Si les impressions de l'URL n'ont pas augmenté, l'hypothèse est fausse."
        )
        problemes = validate_recommendation(reco)
        self.assertIn('test_echec_sans_echeance', _codes(problemes))
        self.assertNotIn('test_echec_non_falsifiable', _codes(problemes))

    def test_lagging_indicator_is_flagged(self):
        reco = dict(RECO_COMPLETE)
        reco['indicateur_avance'] = "le chiffre d'affaires du mois"
        self.assertIn('indicateur_retarde', _codes(validate_recommendation(reco)))

    def test_indicator_without_a_source_is_flagged(self):
        reco = dict(RECO_COMPLETE)
        reco['indicateur_avance'] = "la performance générale du site"
        self.assertIn('indicateur_sans_source',
                      _codes(validate_recommendation(reco)))

    def test_missing_action_is_an_error(self):
        reco = dict(RECO_COMPLETE)
        reco.pop('action')
        self.assertIn('action_manquante', _codes(validate_recommendation(reco)))

    def test_unknown_type_is_only_a_warning(self):
        reco = dict(RECO_COMPLETE, type='peu_importe')
        problemes = validate_recommendation(reco)
        self.assertIn('type_inconnu', _codes(problemes))
        self.assertEqual([p['niveau'] for p in problemes], ['avertissement'])

    def test_non_dict_input_does_not_explode(self):
        for entree in (None, 'une phrase', 42, []):
            problemes = validate_recommendation(entree)
            self.assertEqual(_codes(problemes), ['structure_invalide'], repr(entree))

    def test_messages_stay_in_french_without_long_dashes(self):
        reco = {'action': 'Faire quelque chose'}
        for probleme in validate_recommendation(reco):
            self.assertNotIn(CADRATIN, probleme['message'])
            self.assertNotIn(CADRATIN, probleme['correction'])
            self.assertTrue(probleme['message'].strip())


class EnrichTests(SimpleTestCase):
    def test_fills_indicator_delay_and_failure_test(self):
        sortie = enrich_recommendation(
            {'action': "Retirer la balise noindex de la page /services"},
        )
        self.assertEqual(sortie['type'], 'indexation')
        self.assertTrue(sortie['indicateur_avance'])
        self.assertTrue(sortie['test_echec'])
        self.assertEqual(sortie['delai_observation_jours'], [3, 21])
        self.assertIn('jours', sortie['delai_observation'])
        for champ in ('type', 'indicateur_avance', 'test_echec',
                      'delai_observation'):
            self.assertIn(champ, sortie['champs_completes'], champ)

    def test_never_overwrites_what_the_model_produced(self):
        sortie = enrich_recommendation(RECO_COMPLETE)
        self.assertEqual(sortie['test_echec'], RECO_COMPLETE['test_echec'])
        self.assertEqual(sortie['indicateur_avance'],
                         RECO_COMPLETE['indicateur_avance'])
        self.assertEqual(sortie['type'], 'indexation')
        self.assertNotIn('test_echec', sortie['champs_completes'])
        self.assertNotIn('indicateur_avance', sortie['champs_completes'])

    def test_does_not_mutate_its_input(self):
        avant = dict(RECO_COMPLETE)
        enrich_recommendation(RECO_COMPLETE, {'taille_equipe': 2})
        self.assertEqual(RECO_COMPLETE, avant)

    def test_speed_recommendation_gets_the_crux_window(self):
        sortie = enrich_recommendation(
            {'action': "Compresser les images pour améliorer le LCP"},
        )
        self.assertEqual(sortie['type'], 'vitesse')
        self.assertEqual(sortie['delai_observation_jours'], [28, 56])
        self.assertIn('semaines', sortie['delai_observation'])

    def test_generated_failure_test_survives_validation(self):
        """What enrichment writes has to pass the gate it is meant to satisfy."""
        sortie = enrich_recommendation({
            'action': "Ajouter le balisage LocalBusiness sur la page d'accueil",
            'observation': (
                "La page d'accueil ne contient aucun bloc JSON-LD : le HTML "
                "servi n'a pas de script application/ld+json."
            ),
            'dependances': [],
        })
        problemes = validate_recommendation(sortie)
        erreurs = [p for p in problemes if p['niveau'] == 'erreur']
        self.assertEqual(erreurs, [], _codes(erreurs))

    def test_unknown_type_is_replaced_by_a_guess(self):
        sortie = enrich_recommendation(
            {'action': "Fusionner les trois pages qui se cannibalisent",
             'type': 'inconnu'},
        )
        self.assertEqual(sortie['type'], 'consolidation')
        self.assertIn('type', sortie['champs_completes'])

    def test_flags_something_the_client_already_tried(self):
        sortie = enrich_recommendation(
            {'action': "Publier 2 articles de blogue par mois"},
            {'deja_essaye': ["Publier 2 articles de blogue par mois"]},
        )
        self.assertTrue(sortie['avertissements'])
        self.assertIn('déjà essayé', sortie['avertissements'][0])

    def test_stays_quiet_when_nothing_matches_a_past_attempt(self):
        sortie = enrich_recommendation(
            {'action': "Corriger le fichier robots.txt"},
            {'deja_essaye': ["Acheter des liens sur un annuaire"]},
        )
        self.assertEqual(sortie['avertissements'], [])

    def test_survives_a_broken_input(self):
        sortie = enrich_recommendation(None, None)
        self.assertEqual(sortie['type'], 'autre')
        self.assertTrue(sortie['indicateur_avance'])


class ScaleSanityTests(SimpleTestCase):
    def test_thirty_location_pages_for_two_people_is_blocked(self):
        """The exact failure the upstream framework names in prose."""
        resultat = check_scale_sanity(
            {'action': "Créer 30 pages de localité", 'type': 'seo_local'},
            {'taille_equipe': 2},
        )
        self.assertTrue(resultat['applicable'])
        self.assertEqual(resultat['niveau'], 'blocage')
        self.assertEqual(resultat['quantite'], 30)
        self.assertGreater(resultat['heures_requises'], resultat['heures_disponibles'])
        self.assertLess(resultat['quantite_realiste'], 30)
        self.assertIn('pages de localité', resultat['message'])

    def test_a_reasonable_ask_passes(self):
        resultat = check_scale_sanity(
            {'action': "Créer 4 pages de localité", 'type': 'seo_local'},
            {'taille_equipe': 2},
        )
        self.assertEqual(resultat['niveau'], 'ok')
        self.assertEqual(resultat['message'], '')

    def test_a_bigger_team_absorbs_the_same_volume(self):
        reco = {'action': "Créer 30 pages de localité", 'type': 'seo_local'}
        self.assertEqual(
            check_scale_sanity(reco, {'taille_equipe': 10})['niveau'], 'ok',
        )

    def test_cheap_units_are_not_treated_like_pages(self):
        resultat = check_scale_sanity(
            {'action': "Ajouter 30 liens internes vers la page pilier"},
            {'taille_equipe': 1},
        )
        self.assertEqual(resultat['cle_cout'], 'lien_interne')
        self.assertEqual(resultat['niveau'], 'ok')

    def test_explicit_quantity_fields_win_over_the_text(self):
        resultat = check_scale_sanity(
            {'action': "Produire les articles prévus", 'quantite': 40,
             'unite': 'articles'},
            {'taille_equipe': 1},
        )
        self.assertEqual(resultat['quantite'], 40)
        self.assertEqual(resultat['cle_cout'], 'article')
        self.assertEqual(resultat['niveau'], 'blocage')

    def test_quantity_without_a_unit_falls_back_on_the_type(self):
        resultat = check_scale_sanity(
            {'action': "Produire ce qui a été convenu", 'quantite': 3,
             'type': 'notoriete'},
            {'taille_equipe': 2},
        )
        self.assertEqual(resultat['cle_cout'], 'mention')
        self.assertTrue(resultat['applicable'])

    def test_not_applicable_without_a_quantity(self):
        resultat = check_scale_sanity(
            {'action': "Corriger le fichier robots.txt"}, {'taille_equipe': 2},
        )
        self.assertFalse(resultat['applicable'])
        self.assertTrue(resultat['raison'])

    def test_not_applicable_without_a_team_size(self):
        resultat = check_scale_sanity({'action': "Créer 30 pages de localité"}, {})
        self.assertFalse(resultat['applicable'])
        self.assertIn('équipe', resultat['raison'])

    def test_context_can_override_the_capacity_assumptions(self):
        reco = {'action': "Créer 30 pages de localité", 'type': 'seo_local'}
        resultat = check_scale_sanity(
            reco, {'taille_equipe': 2, 'heures_par_semaine': 20,
                   'horizon_semaines': 12},
        )
        self.assertEqual(resultat['niveau'], 'ok')
        self.assertEqual(resultat['heures_disponibles'], 480.0)

    def test_accented_and_unaccented_wording_price_the_same(self):
        contexte = {'taille_equipe': 2}
        avec = check_scale_sanity({'action': "Créer 30 pages de localité"}, contexte)
        sans = check_scale_sanity({'action': "Creer 30 pages de localite"}, contexte)
        self.assertEqual(avec['heures_requises'], sans['heures_requises'])
        self.assertEqual(avec['unite'], sans['unite'])

    def test_reported_unit_is_written_in_proper_french(self):
        """The match runs on folded text; the client must not read "localite"."""
        resultat = check_scale_sanity(
            {'action': "Créer 30 pages de localité"}, {'taille_equipe': 2},
        )
        self.assertEqual(resultat['unite'], 'pages de localité')
        self.assertEqual(resultat['unite_detectee'], 'pages de localite')

    def test_singular_label_when_a_single_unit_is_asked(self):
        resultat = check_scale_sanity(
            {'action': "Créer 1 page de localité"}, {'taille_equipe': 2},
        )
        self.assertEqual(resultat['unite'], 'page de localité')

    def test_enrichment_carries_the_capacity_verdict(self):
        sortie = enrich_recommendation(
            {'action': "Créer 30 pages de localité"}, {'taille_equipe': 2},
        )
        self.assertEqual(sortie['echelle']['niveau'], 'blocage')
        self.assertEqual(sortie['avertissements'], [sortie['echelle']['message']])

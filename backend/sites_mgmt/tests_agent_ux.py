"""Tests for the agent readability audit.

Everything here runs offline and touches no database: the module under test
is pure Python over an HTML string, with no fetch and no ORM. Each test
isolates one criterion and asserts on its `constats`, so a weight change in
another criterion cannot silently break an unrelated assertion.

Run all:
    python manage.py test sites_mgmt.tests_agent_ux
"""
import json

from django.test import SimpleTestCase

from . import agent_ux
from .agent_ux import CRITERIA, check_agent_readability

# A page built the way the audit wants it: landmarks, one h1, labelled form,
# alt text, readable price and phone, JSON-LD. Used as the baseline that
# individual tests degrade one piece at a time.
WELL_BUILT = """<!doctype html>
<html lang="fr-CA">
<head><title>Deneigement residentiel a Quebec</title>
<script type="application/ld+json">{"@context":"https://schema.org",
"@type":"Service","name":"Deneigement","offers":{"@type":"Offer",
"price":"349.00","priceCurrency":"CAD"}}</script></head>
<body>
<header><nav><a href="/">Accueil</a> <a href="/tarifs">Nos tarifs</a></nav></header>
<main>
<h1>Deneigement residentiel a Quebec</h1>
<p>Nous deneigeons les entrees residentielles de Sainte-Foy et de Sillery.
Le contrat saisonnier couvre du 15 novembre au 15 avril, avec un passage
garanti dans les six heures suivant la fin de la precipitation. Le prix
d'une entree simple est de 349 $ pour la saison, taxes en sus. Vous pouvez
nous joindre au (418) 555-1234 ou passer au 1200 rue Saint-Jean.</p>
<h2>Ce qui est inclus</h2>
<p>Le deblaiement de l'entree, le degagement du perron et l'epandage
d'abrasif font partie du forfait. Nous plantons les balises en octobre et
nous les retirons en avril, sans frais additionnels pour ce service.</p>
<img src="/camion.jpg" alt="Camion de deneigement dans une entree enneigee">
<form>
<label for="courriel">Votre courriel</label>
<input id="courriel" type="email" name="courriel">
<button type="submit">Demander une soumission</button>
</form>
</main>
<footer><p>1200 rue Saint-Jean, Quebec (QC) G1R 1S8</p></footer>
</body></html>"""


def constats(result, key):
    return result['criteres'][key]['constats']


def score_of(result, key):
    return result['criteres'][key]['score']


class WellBuiltPageTests(SimpleTestCase):
    def setUp(self):
        self.result = check_agent_readability(WELL_BUILT, url='https://exemple.ca/')

    def test_scores_high(self):
        self.assertGreaterEqual(self.result['score'], 90)
        self.assertEqual(self.result['niveau'], 'excellent')

    def test_url_is_echoed(self):
        self.assertEqual(self.result['url'], 'https://exemple.ca/')

    def test_every_criterion_is_reported(self):
        self.assertEqual(list(self.result['criteres']), [k for k, _, _ in CRITERIA])

    def test_score_is_the_applicable_criteria_rescaled(self):
        applicable = [c for c in self.result['criteres'].values() if c['applicable']]
        earned = sum(c['score'] for c in applicable)
        possible = sum(c['max'] for c in applicable)
        self.assertEqual(self.result['score'], round(100 * earned / possible))
        self.assertEqual(self.result['points_applicables'], possible)

    def test_weights_sum_to_one_hundred(self):
        self.assertEqual(sum(points for _, _, points in CRITERIA), 100)

    def test_result_is_json_serializable(self):
        """The audit is meant to travel through a DRF response as-is."""
        json.dumps(self.result)


class SemanticLandmarkTests(SimpleTestCase):
    def test_flags_missing_landmarks(self):
        html = '<html lang="fr"><body><div>Contenu de la page</div></body></html>'
        found = constats(check_agent_readability(html), 'semantique')['reperes_trouves']
        self.assertEqual(found, [])
        self.assertEqual(score_of(check_agent_readability(html), 'semantique'), 0)

    def test_aria_roles_replace_the_tags(self):
        """role="main" is as readable as <main>, the audit must accept both."""
        html = (
            '<html lang="fr"><head><title>Titre</title></head><body>'
            '<div role="banner">En-tete</div>'
            '<div role="navigation"><a href="/">Accueil</a></div>'
            '<div role="main"><h1>Titre</h1><p>Texte</p></div>'
            '<div role="contentinfo">Pied</div>'
            '</body></html>'
        )
        c = constats(check_agent_readability(html), 'semantique')
        self.assertEqual(c['reperes_trouves'], ['footer', 'header', 'main', 'nav'])
        self.assertEqual(score_of(check_agent_readability(html), 'semantique'), 20)

    def test_missing_title_is_flagged(self):
        html = '<html lang="fr"><body><main><h1>Salut</h1></main></body></html>'
        self.assertEqual(constats(check_agent_readability(html), 'semantique')['title'], '')

    def test_svg_title_is_not_the_document_title(self):
        html = (
            '<html lang="fr"><head><title>Vrai titre</title></head><body>'
            '<button><svg><title>Fermer</title></svg></button></body></html>'
        )
        result = check_agent_readability(html)
        self.assertEqual(constats(result, 'semantique')['title'], 'Vrai titre')
        # The svg title also names the button, so it is not counted unnamed.
        self.assertEqual(constats(result, 'elements_interactifs')['boutons_sans_libelle'], 0)


class LanguageTests(SimpleTestCase):
    def test_missing_lang_is_flagged(self):
        html = WELL_BUILT.replace('<html lang="fr-CA">', '<html>')
        c = constats(check_agent_readability(html), 'semantique')
        self.assertEqual(c['lang'], '')
        self.assertLess(score_of(check_agent_readability(html), 'semantique'), 20)

    def test_french_content_declared_english_is_flagged(self):
        """A Quebec site on an English template ships lang="en" by default."""
        html = WELL_BUILT.replace('<html lang="fr-CA">', '<html lang="en">')
        result = check_agent_readability(html)
        self.assertTrue(constats(result, 'semantique')['contenu_francais'])
        messages = ' '.join(p['message'] for p in result['criteres']['semantique']['problemes'])
        self.assertIn('lang="en"', messages)

    def test_french_declaration_passes(self):
        result = check_agent_readability(WELL_BUILT)
        self.assertTrue(constats(result, 'semantique')['contenu_francais'])
        self.assertEqual(score_of(result, 'semantique'), 20)


class HeadingHierarchyTests(SimpleTestCase):
    def _headings(self, body):
        html = f'<html lang="fr"><body><main>{body}</main></body></html>'
        return check_agent_readability(html)

    def test_no_heading_at_all_zeroes_the_criterion(self):
        result = self._headings('<p>Du texte sans aucun titre.</p>')
        self.assertEqual(score_of(result, 'hierarchie_titres'), 0)
        self.assertEqual(constats(result, 'hierarchie_titres')['nb_titres'], 0)

    def test_missing_h1(self):
        result = self._headings('<h2>Section</h2><p>Texte</p>')
        self.assertEqual(constats(result, 'hierarchie_titres')['nb_h1'], 0)
        self.assertLess(score_of(result, 'hierarchie_titres'), 20)

    def test_multiple_h1(self):
        result = self._headings('<h1>Un</h1><h1>Deux</h1>')
        self.assertEqual(constats(result, 'hierarchie_titres')['nb_h1'], 2)
        self.assertEqual(score_of(result, 'hierarchie_titres'), 16)

    def test_skipped_level(self):
        result = self._headings('<h1>Un</h1><h4>Quatre</h4>')
        self.assertEqual(constats(result, 'hierarchie_titres')['sauts'], ['h1->h4'])

    def test_descending_one_level_at_a_time_passes(self):
        result = self._headings('<h1>Un</h1><h2>Deux</h2><h3>Trois</h3><h2>Bis</h2>')
        self.assertEqual(constats(result, 'hierarchie_titres')['sauts'], [])
        self.assertEqual(score_of(result, 'hierarchie_titres'), 20)

    def test_empty_heading(self):
        result = self._headings('<h1>Un</h1><h2></h2>')
        self.assertEqual(constats(result, 'hierarchie_titres')['titres_vides'], 1)

    def test_heading_text_is_read_through_nested_markup(self):
        result = self._headings('<h1><span>Titre</span> <em>compose</em></h1>')
        plan = constats(result, 'hierarchie_titres')['plan']
        self.assertEqual(plan, ['h1: Titre compose'])


class InteractiveElementTests(SimpleTestCase):
    def _page(self, body):
        html = f'<html lang="fr"><body><main>{body}</main></body></html>'
        return constats(check_agent_readability(html), 'elements_interactifs')

    def test_unlabeled_input(self):
        c = self._page('<input type="text" name="q">')
        self.assertEqual(c['champs_sans_etiquette'], 1)

    def test_label_declared_after_the_input_still_counts(self):
        """The <label for> can appear anywhere, order must not matter."""
        c = self._page('<input id="q" type="text"><label for="q">Recherche</label>')
        self.assertEqual(c['champs_sans_etiquette'], 0)

    def test_aria_label_counts(self):
        c = self._page('<input type="text" aria-label="Recherche">')
        self.assertEqual(c['champs_sans_etiquette'], 0)

    def test_input_wrapped_in_a_label_counts(self):
        c = self._page('<label>Recherche <input type="text"></label>')
        self.assertEqual(c['champs_sans_etiquette'], 0)

    def test_placeholder_alone_is_a_weaker_pass(self):
        c = self._page('<input type="text" placeholder="Courriel">')
        self.assertEqual(c['champs_sans_etiquette'], 0)
        self.assertEqual(c['champs_placeholder_seul'], 1)

    def test_hidden_input_is_ignored(self):
        c = self._page('<input type="hidden" name="csrf" value="x">')
        self.assertEqual(c['nb_champs'], 0)
        self.assertEqual(c['champs_sans_etiquette'], 0)

    def test_submit_input_is_labelled_by_the_browser(self):
        c = self._page('<input type="submit">')
        self.assertEqual(c['champs_sans_etiquette'], 0)

    def test_select_and_textarea_need_a_label_too(self):
        c = self._page('<select name="v"><option>A</option></select><textarea></textarea>')
        self.assertEqual(c['champs_sans_etiquette'], 2)

    def test_div_onclick_is_invisible_to_an_agent(self):
        c = self._page('<div onclick="acheter()">Acheter</div>')
        self.assertEqual(c['widgets_div_onclick'], 1)

    def test_div_onclick_with_role_and_tabindex_passes(self):
        c = self._page('<div onclick="go()" role="button" tabindex="0">Acheter</div>')
        self.assertEqual(c['widgets_div_onclick'], 0)
        self.assertEqual(c['widgets_div_avec_aria'], 1)

    def test_onclick_on_a_real_button_is_fine(self):
        c = self._page('<button onclick="go()">Acheter</button>')
        self.assertEqual(c['widgets_div_onclick'], 0)

    def test_icon_only_link_is_unnamed(self):
        c = self._page('<a href="/panier"><svg></svg></a>')
        self.assertEqual(c['liens_sans_libelle'], 1)

    def test_link_named_by_a_nested_image_alt(self):
        c = self._page('<a href="/"><img src="l.png" alt="Accueil Gridar"></a>')
        self.assertEqual(c['liens_sans_libelle'], 0)

    def test_link_named_by_aria_label(self):
        c = self._page('<a href="/panier" aria-label="Voir le panier"><i></i></a>')
        self.assertEqual(c['liens_sans_libelle'], 0)

    def test_anchor_without_href_is_not_a_link(self):
        c = self._page('<a name="section"></a>')
        self.assertEqual(c['nb_liens'], 0)

    def test_generic_french_label_is_flagged(self):
        c = self._page('<a href="/a">Cliquez ici</a><a href="/b">En savoir plus</a>')
        self.assertEqual(c['liens_libelle_vague'], 2)

    def test_generic_label_matching_ignores_accents_and_punctuation(self):
        c = self._page('<a href="/a">Détails :</a>')
        self.assertEqual(c['liens_libelle_vague'], 1)

    def test_descriptive_label_passes(self):
        c = self._page('<a href="/tarifs">Voir les tarifs de deneigement</a>')
        self.assertEqual(c['liens_libelle_vague'], 0)

    def test_link_without_destination(self):
        c = self._page('<a href="#">Ouvrir</a><a href="javascript:void(0)">Fermer</a>')
        self.assertEqual(c['liens_sans_destination'], 2)

    def test_unnamed_button(self):
        c = self._page('<button class="close"></button>')
        self.assertEqual(c['boutons_sans_libelle'], 1)

    def test_page_with_nothing_actionable(self):
        html = '<html lang="fr"><body><main><h1>Titre</h1><p>Texte</p></main></body></html>'
        result = check_agent_readability(html)
        messages = ' '.join(
            p['message'] for p in result['criteres']['elements_interactifs']['problemes']
        )
        self.assertIn('Aucun élément actionnable', messages)


class ImageAltTests(SimpleTestCase):
    def _page(self, body):
        html = f'<html lang="fr"><body><main>{body}</main></body></html>'
        return constats(check_agent_readability(html), 'images_alt')

    def test_missing_alt(self):
        c = self._page('<img src="a.jpg"><img src="b.jpg" alt="Un chien">')
        self.assertEqual(c['nb_images'], 2)
        self.assertEqual(c['sans_alt'], 1)

    def test_empty_alt_is_a_valid_decorative_marker(self):
        c = self._page('<img src="sep.png" alt="">')
        self.assertEqual(c['sans_alt'], 0)

    def test_presentation_role_is_decorative(self):
        c = self._page('<img src="sep.png" role="presentation">')
        self.assertEqual(c['sans_alt'], 0)

    def test_filename_alt_says_nothing(self):
        c = self._page('<img src="a.jpg" alt="IMG_2043.jpg"><img src="b.jpg" alt="photo1">')
        self.assertEqual(c['alt_non_informatif'], 2)

    def test_no_image_leaves_the_criterion_out_of_the_score(self):
        """A page with no image passes nothing, it simply has nothing to fail."""
        html = '<html lang="fr"><body><main><p>Texte</p></main></body></html>'
        result = check_agent_readability(html)
        self.assertFalse(result['criteres']['images_alt']['applicable'])
        self.assertEqual(result['points_applicables'], 85)

    def test_examples_are_collected(self):
        c = self._page('<img src="/photos/toiture.jpg">')
        self.assertEqual(c['exemples']['images_no_alt'], ['/photos/toiture.jpg'])


class StaticContentTests(SimpleTestCase):
    """The check upstream could not make: is the content in the served HTML."""

    SPA = (
        '<!doctype html><html lang="fr"><head><title>App</title></head><body>'
        '<div id="root"></div>'
        '<script src="/a.js"></script><script src="/b.js"></script>'
        '<script src="/c.js"></script></body></html>'
    )

    def test_empty_react_root_is_caught(self):
        result = check_agent_readability(self.SPA)
        c = constats(result, 'contenu_sans_js')
        self.assertTrue(c['conteneur_applicatif_vide'])
        self.assertEqual(score_of(result, 'contenu_sans_js'), 0)
        self.assertEqual(result['niveau'], 'critique')

    def test_server_rendered_page_is_not_flagged(self):
        result = check_agent_readability(WELL_BUILT)
        c = constats(result, 'contenu_sans_js')
        self.assertFalse(c['conteneur_applicatif_vide'])
        self.assertEqual(score_of(result, 'contenu_sans_js'), 15)

    def test_filled_root_container_is_not_a_shell(self):
        """Next.js with SSR also ships #__next, but with the content inside."""
        html = (
            '<html lang="fr"><head><title>T</title></head><body><div id="__next">'
            '<main><h1>Plomberie Tremblay</h1><p>' + 'Texte utile. ' * 60 +
            '</p></main></div><script src="/_next/main.js"></script></body></html>'
        )
        result = check_agent_readability(html)
        self.assertFalse(constats(result, 'contenu_sans_js')['conteneur_applicatif_vide'])
        self.assertEqual(score_of(result, 'contenu_sans_js'), 15)

    def test_noscript_notice_is_an_admission(self):
        html = (
            '<html lang="fr"><head><title>T</title></head><body>'
            '<div id="app"></div>'
            '<noscript>Vous devez activer JavaScript pour continuer.</noscript>'
            '<script src="/a.js"></script></body></html>'
        )
        c = constats(check_agent_readability(html), 'contenu_sans_js')
        self.assertTrue(c['noscript_exige_js'])

    def test_script_content_is_not_counted_as_text(self):
        html = (
            '<html lang="fr"><head><title>T</title></head><body><main>'
            '<h1>Titre</h1><script>var a = "' + 'x' * 3000 + '";</script>'
            '</main></body></html>'
        )
        c = constats(check_agent_readability(html), 'contenu_sans_js')
        self.assertEqual(c['caracteres_de_texte'], len('Titre'))
        self.assertEqual(c['nb_scripts'], 1)

    def test_template_content_does_not_count_as_served_text(self):
        html = (
            '<html lang="fr"><head><title>T</title></head><body><main>'
            '<h1>Titre</h1><template><p>' + 'Contenu inerte. ' * 40 +
            '</p></template></main></body></html>'
        )
        c = constats(check_agent_readability(html), 'contenu_sans_js')
        self.assertEqual(c['caracteres_de_texte'], len('Titre'))


class KeyInformationTests(SimpleTestCase):
    def _page(self, body):
        html = (
            '<html lang="fr"><head><title>Tarifs</title></head><body><main>'
            f'{body}</main></body></html>'
        )
        return constats(check_agent_readability(html), 'infos_cles')

    def test_quebec_price_format_is_read(self):
        """Sign after the amount, comma decimal: the local way of writing it."""
        c = self._page('<h1>Tarifs</h1><p>Le forfait coute 349,99 $ par saison.</p>')
        self.assertEqual(c['prix_lisibles'], 1)

    def test_price_with_leading_sign_is_read(self):
        c = self._page('<h1>Tarifs</h1><p>Notre forfait: $49.99 monthly.</p>')
        self.assertEqual(c['prix_lisibles'], 1)

    def test_price_with_thousand_separator_is_read(self):
        c = self._page('<h1>Tarifs</h1><p>Un forfait a 1 200,50 $ par annee.</p>')
        self.assertEqual(c['prix_lisibles'], 1)

    def test_commercial_page_without_a_readable_price(self):
        c = self._page('<h1>Nos forfaits</h1><p>Demandez votre soumission.</p>')
        self.assertTrue(c['page_commerciale'])
        self.assertEqual(c['prix_lisibles'], 0)

    def test_price_in_structured_data_counts(self):
        html = (
            '<html lang="fr"><head><title>Tarifs</title>'
            '<script type="application/ld+json">{"@type":"Product",'
            '"offers":{"@type":"Offer","price":"349.00"}}</script></head>'
            '<body><main><h1>Nos forfaits</h1><p>Demandez une soumission.</p>'
            '</main></body></html>'
        )
        result = check_agent_readability(html)
        c = constats(result, 'infos_cles')
        self.assertTrue(c['prix_dans_donnees_structurees'])
        self.assertEqual(c['types_jsonld'], ['offer', 'product'])
        self.assertEqual(score_of(result, 'infos_cles'), 10)

    def test_quebec_phone_and_postal_code_are_read(self):
        c = self._page(
            '<h1>Nous joindre</h1>'
            '<p>Telephone: (418) 555-1234, 1200 rue Saint-Jean, Quebec G1R 1S8.</p>'
        )
        self.assertEqual(c['telephones_lisibles'], 1)
        self.assertTrue(c['adresse_lisible'])

    def test_contact_page_without_readable_coordinates(self):
        c = self._page('<h1>Nous joindre</h1><p>Remplissez le formulaire.</p>')
        self.assertTrue(c['intention_contact'])
        self.assertEqual(c['telephones_lisibles'], 0)

    def test_a_bare_contact_menu_entry_does_not_trigger_the_check(self):
        """Otherwise every page of every site fails on its own navigation."""
        c = self._page('<h1>Blogue</h1><p>Un article. Voir la page Contact.</p>')
        self.assertFalse(c['intention_contact'])

    def test_missing_jsonld_is_reported(self):
        c = self._page('<h1>Blogue</h1><p>Un article sans donnees structurees.</p>')
        self.assertEqual(c['blocs_jsonld'], 0)

    def test_broken_jsonld_does_not_crash(self):
        html = (
            '<html lang="fr"><head><title>T</title>'
            '<script type="application/ld+json">{ceci nest pas du json}</script>'
            '</head><body><main><h1>Titre</h1></main></body></html>'
        )
        c = constats(check_agent_readability(html), 'infos_cles')
        self.assertEqual(c['blocs_jsonld'], 1)
        self.assertEqual(c['types_jsonld'], [])


class RobustnessTests(SimpleTestCase):
    def test_empty_html(self):
        """No free points for a document that serves nothing to read."""
        result = check_agent_readability('')
        self.assertLess(result['score'], 25)
        self.assertEqual(result['niveau'], 'critique')

    def test_none_html(self):
        result = check_agent_readability(None)
        self.assertLess(result['score'], 25)

    def test_not_html_at_all(self):
        result = check_agent_readability('{"json": true}')
        self.assertIsInstance(result['score'], int)

    def test_malformed_markup_does_not_crash(self):
        html = (
            '<html lang="fr"><body><main><div><p>Texte non ferme'
            '<h1>Titre</h1></div></section></body>'
        )
        result = check_agent_readability(html)
        self.assertGreaterEqual(result['score'], 0)
        self.assertEqual(constats(result, 'hierarchie_titres')['nb_h1'], 1)

    def test_unclosed_app_root_is_still_measured(self):
        html = '<html lang="fr"><head><title>T</title></head><body><div id="root">'
        c = constats(check_agent_readability(html), 'contenu_sans_js')
        self.assertTrue(c['conteneur_applicatif_vide'])

    def test_score_stays_within_bounds(self):
        for html in ('', '<html>', WELL_BUILT, '<div onclick="x">' * 200):
            result = check_agent_readability(html)
            self.assertGreaterEqual(result['score'], 0)
            self.assertLessEqual(result['score'], 100)
            for critere in result['criteres'].values():
                self.assertGreaterEqual(critere['score'], 0)
                self.assertLessEqual(critere['score'], critere['max'])

    def test_recommendations_are_sorted_by_recoverable_points(self):
        result = check_agent_readability('<html><body><div>a</div></body></html>')
        gains = [r['gain'] for r in result['recommandations']]
        self.assertEqual(gains, sorted(gains, reverse=True))
        self.assertTrue(result['recommandations'])

    def test_recommendations_are_french_prose_without_dashes(self):
        result = check_agent_readability('<html><body><div>a</div></body></html>')
        for reco in result['recommandations']:
            self.assertIn(reco['priorite'], ('haute', 'moyenne', 'basse'))
            self.assertTrue(reco['message'].strip())
            self.assertNotIn('—', reco['message'])
            self.assertNotIn('–', reco['message'])

    def test_deep_nesting_does_not_blow_the_stack(self):
        html = '<html lang="fr"><body>' + '<div>' * 500 + 'Texte' + '</div>' * 500 + '</body></html>'
        self.assertIsInstance(check_agent_readability(html)['score'], int)


class OfflinePurityTests(SimpleTestCase):
    """The module must stay a pure function over a string.

    Rendering (Playwright) and fetching both live outside it: upstream pulled
    Chromium in, and this port must not grow a network call by accident.
    """

    def test_module_exposes_no_fetch_helper(self):
        for banned in ('requests', 'safe_get', 'urlopen', 'render_page'):
            self.assertFalse(hasattr(agent_ux, banned), f'{banned} leaked in')

    def test_public_surface(self):
        self.assertEqual(agent_ux.__all__, ['CRITERIA', 'check_agent_readability'])

    def test_url_argument_is_optional(self):
        self.assertEqual(check_agent_readability('<html></html>')['url'], '')

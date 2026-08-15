"""Tests for the retired Google Business Profile feature linter.

Everything runs offline because the module never fetches: it takes markup and
returns findings. Half the cases here are negatives, since the value of this
linter is not finding "Clavardez avec nous sur Google" but staying quiet on
the review CTA, the SEO advice page and the article about the shutdown.

Run all:
    python manage.py test sites_mgmt.tests_gbp_lint
"""
from django.test import SimpleTestCase

from . import gbp_lint
from .gbp_lint import lint_gbp_references, summarize_gbp_lint


def page(body, head=''):
    return f'<!doctype html><html><head>{head}</head><body>{body}</body></html>'


def codes(findings):
    return [finding['code'] for finding in findings]


class ChatCtaTests(SimpleTestCase):
    """The CTA Google killed on 2024-07-31, in the wordings clients use."""

    def test_quebec_french_chat_verb(self):
        found = lint_gbp_references(
            page('<p>Une question ? Clavardez avec nous sur notre fiche Google.</p>')
        )
        self.assertEqual(codes(found), ['gbp_chat_cta'])
        self.assertEqual(found[0]['severity'], 'critical')
        self.assertIn('Clavardez', found[0]['match'])

    def test_french_variants(self):
        for body in (
            '<p>Écrivez-nous sur Google Business, on répond vite.</p>',
            '<p>Laissez-nous un message sur notre fiche Google.</p>',
            '<p>Messagez-nous via notre profil Google Business</p>',
            '<p>Envoyez un message sur notre page Google</p>',
            "<p>Contactez-nous par message sur notre fiche d'établissement Google</p>",
            '<p>Messagerie de la fiche Google</p>',
        ):
            with self.subTest(body=body):
                self.assertEqual(codes(lint_gbp_references(page(body))), ['gbp_chat_cta'])

    def test_english_variants(self):
        for body in (
            '<p>Message us on Google Business Profile</p>',
            '<p>Chat with us on Google Maps</p>',
            '<p>We answer through Google Business Messages.</p>',
        ):
            with self.subTest(body=body):
                self.assertEqual(codes(lint_gbp_references(page(body))), ['gbp_chat_cta'])

    def test_html_entities_and_accents_do_not_hide_the_cta(self):
        """The page ships &Eacute;, the pattern is ASCII, the quote keeps the accent."""
        found = lint_gbp_references(
            page('<div>&Eacute;crivez-nous sur Google Business</div>')
        )
        self.assertEqual(codes(found), ['gbp_chat_cta'])
        self.assertIn('É', found[0]['match'])

    def test_icon_button_with_only_an_aria_label(self):
        found = lint_gbp_references(
            page('<a href="#" aria-label="Clavarder avec nous sur Google Business"><i></i></a>')
        )
        self.assertEqual(codes(found), ['gbp_chat_cta'])

    def test_case_and_curly_apostrophes(self):
        found = lint_gbp_references(
            page('<p>CLAVARDEZ AVEC NOUS SUR NOTRE FICHE D’ÉTABLISSEMENT GOOGLE</p>')
        )
        self.assertEqual(codes(found), ['gbp_chat_cta'])

    def test_message_cites_the_retirement_date(self):
        found = lint_gbp_references(page('<p>Clavardez avec nous sur Google Business</p>'))
        self.assertIn('31 juillet 2024', found[0]['message'])
        self.assertEqual(found[0]['retired_on'], '2024-07-31')

    def test_call_history(self):
        found = lint_gbp_references(
            page('<p>Consultez votre historique des appels Google Business.</p>')
        )
        self.assertEqual(codes(found), ['gbp_call_history'])
        self.assertIn('31 juillet 2024', found[0]['message'])


class QuietOnLivePagesTests(SimpleTestCase):
    """Where a naive port of the upstream patterns would cry wolf."""

    def test_review_cta_is_not_a_chat_cta(self):
        for body in (
            '<p>Laissez-nous un avis sur notre fiche Google !</p>',
            '<p>Écrivez-nous un avis sur Google Business</p>',
            '<p>Donnez-nous 5 étoiles sur notre fiche Google</p>',
        ):
            with self.subTest(body=body):
                self.assertEqual(lint_gbp_references(page(body)), [])

    def test_seo_advice_is_not_a_dead_button(self):
        for body in (
            '<p>Écrivez une description pour votre fiche Google Business.</p>',
            '<p>Rédigez un message clair et publiez-le sur votre fiche Google Business.</p>',
        ):
            with self.subTest(body=body):
                self.assertEqual(lint_gbp_references(page(body)), [])

    def test_article_about_the_shutdown_is_not_a_victim_of_it(self):
        for body in (
            '<p>Le clavardage Google Business a été fermé le 31 juillet 2024.</p>',
            "<p>Google Business Messages n'existe plus depuis 2024.</p>",
            '<p>Google My Business chat was shut down in 2024.</p>',
        ):
            with self.subTest(body=body):
                self.assertEqual(lint_gbp_references(page(body)), [])

    def test_two_blocks_are_two_ideas(self):
        """A Google mention and a contact CTA in separate blocks are unrelated."""
        found = lint_gbp_references(
            page('<p>Trouvez notre fiche Google</p><p>Envoyez-nous un message</p>')
        )
        self.assertEqual(found, [])

    def test_maps_link_beside_a_contact_form(self):
        found = lint_gbp_references(page(
            '<footer><a href="https://maps.google.com/?cid=1">Google Maps</a>'
            '<p>Envoyez-nous un message</p></footer>'
        ))
        self.assertEqual(found, [])

    def test_ordinary_local_page(self):
        found = lint_gbp_references(page(
            '<h1>Plombier à Laval</h1>'
            '<p>Appelez-nous au 514-555-0199 ou écrivez-nous par courriel.</p>'
            '<p>Trouvez-nous sur Google Maps. Laissez un avis sur notre fiche Google.</p>'
            '<iframe src="https://www.google.com/maps/embed?pb=1" title="Google Maps"></iframe>'
        ))
        self.assertEqual(found, [])

    def test_script_and_style_contents_are_not_visible_text(self):
        found = lint_gbp_references(page(
            '<script>var t = "message us on google business";</script>'
            '<style>.chat-google-business{display:none}</style>'
            '<p>Bonjour</p>'
        ))
        self.assertEqual(found, [])

    def test_analytics_parameter_is_not_a_chat_widget(self):
        """GA4 ships google_business_vertical on every local conversion event."""
        found = lint_gbp_references(page(
            '<script>gtag("event", {google_business_vertical: "local"});</script>'
        ))
        self.assertEqual(found, [])


class BusinessSiteTests(SimpleTestCase):
    """Google closed these sites in March 2024, redirect off on 2024-06-10."""

    def test_link_with_scheme(self):
        found = lint_gbp_references(
            page('<a href="https://resto-chezmarie.business.site/">Notre site</a>')
        )
        self.assertEqual(codes(found), ['gbp_business_site_link'])
        self.assertEqual(found[0]['severity'], 'high')
        self.assertIn('resto-chezmarie.business.site', found[0]['message'])
        self.assertIn('10 juin 2024', found[0]['message'])

    def test_bare_host_in_running_text(self):
        found = lint_gbp_references(page('<p>Visitez resto-chezmarie.business.site.</p>'))
        self.assertEqual(codes(found), ['gbp_business_site_link'])
        self.assertEqual(found[0]['match'], 'resto-chezmarie.business.site')

    def test_json_ld_same_as(self):
        found = lint_gbp_references(page(
            '<script type="application/ld+json">'
            '{"@type":"LocalBusiness","sameAs":["https://chezmarie.business.site/"]}'
            '</script>'
        ))
        self.assertEqual(codes(found), ['gbp_business_site_link'])

    def test_similar_paths_are_not_business_site(self):
        for body in (
            '<a href="https://exemple.com/business.sitemap.xml">plan</a>',
            '<a href="https://exemple.com/notre-business.html">business</a>',
            '<p>Notre business site est en ligne.</p>',
        ):
            with self.subTest(body=body):
                self.assertEqual(lint_gbp_references(page(body)), [])

    def test_page_hosted_on_business_site_is_critical(self):
        found = lint_gbp_references(
            page('<p>Bienvenue chez Marie</p>'),
            url='https://chezmarie.business.site/accueil',
        )
        self.assertEqual(codes(found), ['gbp_site_on_business_site'])
        self.assertEqual(found[0]['severity'], 'critical')
        self.assertIn('chezmarie.business.site', found[0]['message'])

    def test_self_links_do_not_repeat_the_hosting_finding(self):
        found = lint_gbp_references(
            page('<a href="https://chezmarie.business.site/contact">Contact</a>'
                 '<a href="https://autre.business.site/">Partenaire</a>'),
            url='https://chezmarie.business.site/',
        )
        self.assertEqual(
            codes(found), ['gbp_site_on_business_site', 'gbp_business_site_link'],
        )
        self.assertEqual(found[1]['match'], 'https://autre.business.site/')


class DeadSurfaceTests(SimpleTestCase):
    def test_website_builder_link(self):
        found = lint_gbp_references(
            page('<a href="https://business.google.com/u/0/website/edit">Site</a>')
        )
        self.assertEqual(codes(found), ['gbp_website_builder_link'])

    def test_google_plus_link(self):
        found = lint_gbp_references(
            page('<a rel="publisher" href="https://plus.google.com/+MonResto">G+</a>')
        )
        self.assertEqual(codes(found), ['google_plus_link'])
        self.assertIn('2 avril 2019', found[0]['message'])

    def test_google_my_business_app_links(self):
        for body in (
            '<a href="https://play.google.com/store/apps/details?'
            'id=com.google.android.apps.vega">App</a>',
            '<a href="https://apps.apple.com/ca/app/google-my-business/id853371601">iOS</a>',
        ):
            with self.subTest(body=body):
                self.assertEqual(codes(lint_gbp_references(page(body))), ['gmb_app_link'])

    def test_business_messages_widget(self):
        for body in (
            '<script src="https://businessmessages.googleapis.com/v1/widget.js"></script>',
            '<div class="google-business-messages-widget"></div>',
        ):
            with self.subTest(body=body):
                found = lint_gbp_references(page(body))
                self.assertEqual(codes(found), ['gbp_chat_widget'])
                self.assertEqual(found[0]['severity'], 'critical')


class StaleBrandingTests(SimpleTestCase):
    def test_old_product_name_is_low_severity(self):
        found = lint_gbp_references(page('<p>Suivez-nous sur Google My Business.</p>'))
        self.assertEqual(codes(found), ['gmb_branding'])
        self.assertEqual(found[0]['severity'], 'low')
        self.assertIn('novembre 2021', found[0]['message'])

    def test_branding_does_not_double_report_a_chat_cta(self):
        found = lint_gbp_references(page('<p>Utilisez le chat Google My Business.</p>'))
        self.assertEqual(codes(found), ['gbp_chat_cta'])


class FindingShapeTests(SimpleTestCase):
    def test_every_finding_carries_the_same_keys(self):
        found = lint_gbp_references(
            page('<p>Clavardez avec nous sur notre fiche Google</p>'
                 '<a href="https://chezmarie.business.site/">Site</a>'
                 '<a href="https://plus.google.com/+X">G+</a>'
                 '<p>Suivez Google My Business</p>'),
            url='https://exemple.com/contact',
        )
        self.assertEqual(len(found), 4)
        for finding in found:
            with self.subTest(code=finding['code']):
                self.assertEqual(set(finding), {
                    'code', 'severity', 'feature', 'retired_on', 'match', 'excerpt',
                    'occurrences', 'message', 'fix', 'source', 'page_url',
                })
                self.assertEqual(finding['page_url'], 'https://exemple.com/contact')
                self.assertIn(finding['severity'], gbp_lint.SEVERITY_RANK)
                self.assertTrue(finding['message'].strip())
                self.assertTrue(finding['fix'].strip())
                self.assertNotIn('{', finding['message'])

    def test_sorted_most_severe_first(self):
        found = lint_gbp_references(page(
            '<p>Suivez Google My Business</p>'
            '<a href="https://plus.google.com/+X">G+</a>'
            '<a href="https://chezmarie.business.site/">Site</a>'
            '<p>Clavardez avec nous sur notre fiche Google</p>'
        ))
        ranks = [gbp_lint.SEVERITY_RANK[f['severity']] for f in found]
        self.assertEqual(ranks, sorted(ranks))
        self.assertEqual(found[0]['code'], 'gbp_chat_cta')

    def test_repeated_link_collapses_into_occurrences(self):
        block = ('<a href="https://x.business.site/a">a</a>'
                 '<a href="https://x.business.site/b">b</a>')
        found = lint_gbp_references(page(block * 3))
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]['occurrences'], 6)

    def test_findings_per_rule_are_capped(self):
        links = ''.join(
            f'<a href="https://client{n}.business.site/">s</a>' for n in range(9)
        )
        found = lint_gbp_references(page(links))
        self.assertEqual(len(found), 5)

    def test_page_url_defaults_to_empty(self):
        found = lint_gbp_references(page('<p>Clavardez avec nous sur Google Business</p>'))
        self.assertEqual(found[0]['page_url'], '')


class RobustnessTests(SimpleTestCase):
    def test_module_never_reaches_the_network(self):
        """No fetch here. A caller wanting one goes through url_safety.safe_get."""
        self.assertFalse(hasattr(gbp_lint, 'requests'))

    def test_empty_and_wrong_types(self):
        for value in ('', '   ', None, 42, b'<p>hi</p>', []):
            with self.subTest(value=value):
                self.assertEqual(lint_gbp_references(value), [])

    def test_malformed_markup_still_scans(self):
        found = lint_gbp_references(
            '<body><p>Clavardez avec nous sur Google Business<<< </p'
        )
        self.assertEqual(codes(found), ['gbp_chat_cta'])

    def test_markup_without_any_tag(self):
        found = lint_gbp_references('Clavardez avec nous sur notre fiche Google')
        self.assertEqual(codes(found), ['gbp_chat_cta'])

    def test_bad_url_does_not_raise(self):
        found = lint_gbp_references(page('<p>Bonjour</p>'), url='http://[::1')
        self.assertEqual(found, [])

    def test_oversized_input_is_bounded(self):
        padding = '<p>Plombier a Laval</p>' * 100_000
        found = lint_gbp_references(
            page(padding + '<p>Clavardez avec nous sur notre fiche Google</p>')
        )
        self.assertGreater(len(padding), gbp_lint._MAX_HTML)
        self.assertEqual(found, [])

    def test_same_input_gives_the_same_output(self):
        markup = page('<p>Clavardez avec nous sur Google Business</p>'
                      '<a href="https://x.business.site/">site</a>')
        self.assertEqual(lint_gbp_references(markup), lint_gbp_references(markup))


class SummaryTests(SimpleTestCase):
    def test_counts_and_blocking(self):
        found = lint_gbp_references(page(
            '<p>Clavardez avec nous sur notre fiche Google</p>'
            '<a href="https://x.business.site/">site</a>'
            '<p>Suivez Google My Business</p>'
        ))
        summary = summarize_gbp_lint(found)
        self.assertFalse(summary['ok'])
        self.assertEqual(summary['total'], 3)
        self.assertEqual(summary['blocking'], 2)
        self.assertEqual(summary['counts']['critical'], 1)
        self.assertEqual(summary['counts']['low'], 1)

    def test_clean_page(self):
        self.assertEqual(
            summarize_gbp_lint([]),
            {'ok': True, 'total': 0, 'blocking': 0,
             'counts': {'critical': 0, 'high': 0, 'medium': 0, 'low': 0}},
        )

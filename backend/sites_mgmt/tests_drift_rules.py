"""Tests for the SEO drift snapshot and the 17 comparison rules.

Everything here runs offline by construction: `drift_rules` never opens a
socket, it takes HTML in and returns data out, so there is nothing to mock.
The fixtures are Quebec French pages because the word counter and the finding
messages are the parts that were rewritten for French.

Run all:
    python manage.py test sites_mgmt.tests_drift_rules
"""
import json

from django.test import SimpleTestCase

from .drift_rules import (
    RULE_NAMES, SNAPSHOT_VERSION, capture_snapshot, compare_snapshots,
    summarize_findings,
)

PAGE_URL = 'https://exemple.ca/plomberie/montreal'

PAGE_HTML = """<!doctype html>
<html lang="fr-CA">
<head>
  <title>  Plombier &agrave; Montr&eacute;al &amp; Laval  </title>
  <meta name="description" content="On r&eacute;pare vos drains aujourd'hui.">
  <meta name="robots" content="index, follow">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta property="og:title" content="Plombier a Montreal">
  <meta property="og:image" content="https://exemple.ca/og.png">
  <link rel="canonical" href="/plomberie/montreal">
  <link rel="alternate" hreflang="fr-CA" href="https://exemple.ca/plomberie/montreal">
  <link rel="alternate" hreflang="en-CA" href="https://exemple.ca/en/plumbing/montreal">
  <script type="application/ld+json">
  {"@context":"https://schema.org","@graph":[
    {"@type":"LocalBusiness","name":"Plomberie Tremblay"},
    {"@type":"BreadcrumbList"}]}
  </script>
</head>
<body>
  <nav><a href="/accueil">Accueil</a> <a href="/contact">Contact</a></nav>
  <header><h1>Plombier d'urgence a Montreal</h1></header>
  <main>
    <p>Aujourd'hui, notre equipe peut-etre chez vous en moins d'une heure.</p>
    <p><a href="https://exemple.ca/tarifs">Nos tarifs</a> et
       <a href="https://www.exemple.ca/blogue">le blogue</a>.</p>
    <p><a href="https://www.rbq.gouv.qc.ca/">Licence RBQ</a>
       <a href="mailto:info@exemple.ca">Ecrivez-nous</a>
       <a href="#haut">Haut de page</a></p>
  </main>
  <footer>Plomberie Tremblay, tous droits reserves.</footer>
</body>
</html>
"""


def snapshot(**overrides):
    """A healthy snapshot, shaped exactly like `capture_snapshot` output."""
    base = {
        'snapshot_version': SNAPSHOT_VERSION,
        'url': PAGE_URL,
        'status_code': 200,
        'title': 'Plombier a Montreal | Plomberie Tremblay',
        'meta_description': 'Urgence 24/7 a Montreal, sans frais de deplacement.',
        'meta_robots': 'index, follow',
        'meta_googlebot': '',
        'viewport': 'width=device-width, initial-scale=1',
        'canonical': 'https://exemple.ca/plomberie/montreal',
        'h1': ['Plombier d\'urgence a Montreal'],
        'open_graph': {'og:title': 'Plombier a Montreal'},
        'hreflang': {'fr-ca': 'https://exemple.ca/', 'en-ca': 'https://exemple.ca/en/'},
        'schema_types': ['BreadcrumbList', 'LocalBusiness'],
        'schema_count': 2,
        'schema_hash': 'a' * 64,
        'word_count': 800,
        'internal_links': 20,
        'external_links': 3,
    }
    base.update(overrides)
    return base


def fired(findings, rule):
    for finding in findings:
        if finding['rule'] == rule:
            return finding
    return None


def rules_of(findings):
    return [finding['rule'] for finding in findings]


class CaptureSnapshotTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.snap = capture_snapshot(PAGE_HTML, PAGE_URL)

    def test_extracts_head_fields(self):
        self.assertEqual(self.snap['title'], 'Plombier à Montréal & Laval')
        self.assertEqual(self.snap['meta_description'], "On répare vos drains aujourd'hui.")
        self.assertEqual(self.snap['meta_robots'], 'index, follow')
        self.assertEqual(self.snap['viewport'], 'width=device-width, initial-scale=1')
        self.assertEqual(self.snap['h1'], ["Plombier d'urgence a Montreal"])
        self.assertEqual(
            sorted(self.snap['open_graph']), ['og:image', 'og:title'],
        )

    def test_resolves_relative_canonical(self):
        # Stored raw, a switch from relative to absolute would look like drift.
        self.assertEqual(self.snap['canonical'], PAGE_URL)

    def test_hreflang_keys_are_lowercased(self):
        # fr-CA and fr-ca are the same declaration, they must not read as drift.
        self.assertEqual(sorted(self.snap['hreflang']), ['en-ca', 'fr-ca'])

    def test_flattens_json_ld_graph(self):
        self.assertEqual(self.snap['schema_types'], ['BreadcrumbList', 'LocalBusiness'])
        self.assertEqual(self.snap['schema_count'], 2)
        self.assertEqual(len(self.snap['schema_hash']), 64)

    def test_splits_internal_and_external_links(self):
        # www and bare host are one site; mailto and #anchor are not links.
        self.assertEqual(self.snap['internal_links'], 4)
        self.assertEqual(self.snap['external_links'], 1)

    def test_word_count_excludes_chrome_and_head(self):
        # Body copy only: nav, header, footer, JSON-LD and <title> stay out,
        # which is what keeps the count stable when only the template moves.
        self.assertEqual(self.snap['word_count'], 21)

    def test_h1_inside_header_is_still_captured(self):
        self.assertEqual(len(self.snap['h1']), 1)

    def test_status_code_is_left_to_the_caller(self):
        self.assertIsNone(self.snap['status_code'])

    def test_snapshot_survives_a_json_round_trip(self):
        # It gets stored in a JSONField between two runs, so it has to come
        # back identical or every rule compares apples to oranges.
        self.assertEqual(json.loads(json.dumps(self.snap)), self.snap)


class FrenchWordCountTests(SimpleTestCase):
    def count(self, body):
        return capture_snapshot(f'<html><body><p>{body}</p></body></html>', PAGE_URL)['word_count']

    def test_elision_and_hyphen_stay_one_word(self):
        # The upstream regex scores these as 8 and inflates every French page.
        self.assertEqual(self.count("Aujourd'hui, peut-etre, d'une grand-mere a l'hopital"), 6)

    def test_accents_are_letters(self):
        self.assertEqual(self.count('Réparation québécoise à Montréal'), 4)

    def test_prices_count_as_words(self):
        # A number is a token, a currency sign is not: a pricing page must not
        # read as an empty page.
        self.assertEqual(self.count('Forfait 199 $ par mois'), 4)
        self.assertEqual(self.count('Forfait 1499,99 $'), 2)


class CaptureEdgeCaseTests(SimpleTestCase):
    def test_empty_html_gives_an_empty_snapshot(self):
        snap = capture_snapshot('', PAGE_URL)
        self.assertEqual(snap['title'], '')
        self.assertEqual(snap['h1'], [])
        self.assertEqual(snap['schema_count'], 0)
        self.assertEqual(snap['schema_hash'], '')
        self.assertEqual(snap['word_count'], 0)

    def test_malformed_html_does_not_raise(self):
        broken = '<html><head><title>Titre<body><p>Texte <a href=">Lien</div></p>'
        snap = capture_snapshot(broken, PAGE_URL)
        self.assertIn('Titre', snap['title'])

    def test_invalid_json_ld_is_ignored(self):
        html = '<script type="application/ld+json">{ pas du json }</script>'
        self.assertEqual(capture_snapshot(html, PAGE_URL)['schema_count'], 0)

    def test_schema_hash_ignores_key_order(self):
        first = capture_snapshot(
            '<script type="application/ld+json">{"@type":"Article","name":"A"}</script>',
            PAGE_URL,
        )
        second = capture_snapshot(
            '<script type="application/ld+json">{"name":"A","@type":"Article"}</script>',
            PAGE_URL,
        )
        self.assertEqual(first['schema_hash'], second['schema_hash'])

    def test_svg_title_is_not_the_page_title(self):
        html = '<html><head><title>Vrai titre</title></head><body><svg><title>icone</title></svg></body></html>'
        self.assertEqual(capture_snapshot(html, PAGE_URL)['title'], 'Vrai titre')

    def test_missing_base_url_treats_links_as_internal(self):
        html = '<a href="/page">Page</a><a href="https://ailleurs.ca/">Ailleurs</a>'
        snap = capture_snapshot(html, '')
        self.assertEqual(snap['internal_links'], 1)
        self.assertEqual(snap['external_links'], 1)


class CompareContractTests(SimpleTestCase):
    def test_publishes_seventeen_unique_rules(self):
        self.assertEqual(len(RULE_NAMES), 17)
        self.assertEqual(len(set(RULE_NAMES)), 17)

    def test_identical_snapshots_report_nothing(self):
        self.assertEqual(compare_snapshots(snapshot(), snapshot()), [])

    def test_missing_snapshot_reports_nothing(self):
        # A first capture has nothing to drift from.
        self.assertEqual(compare_snapshots({}, snapshot()), [])
        self.assertEqual(compare_snapshots(snapshot(), {}), [])
        self.assertEqual(compare_snapshots(None, snapshot()), [])

    def test_findings_carry_the_documented_keys(self):
        findings = compare_snapshots(snapshot(), snapshot(canonical=''))
        self.assertTrue(findings)
        for finding in findings:
            self.assertEqual(
                sorted(finding),
                ['after', 'before', 'field', 'message', 'rule', 'severity'],
            )
            self.assertIn(finding['rule'], RULE_NAMES)
            self.assertIn(finding['severity'], ('critical', 'warning', 'info'))

    def test_worst_findings_come_first(self):
        after = snapshot(
            canonical='', title='', hreflang={}, viewport='', word_count=200,
        )
        severities = [finding['severity'] for finding in compare_snapshots(snapshot(), after)]
        self.assertEqual(severities, sorted(severities, key=['critical', 'warning', 'info'].index))

    def test_messages_are_french_and_free_of_dashes(self):
        # House rule: no em dash and no en dash anywhere in client facing prose.
        after = snapshot(
            canonical='', title='', meta_description='', viewport='', hreflang={},
            open_graph={}, schema_count=0, schema_types=[], h1=[], status_code=503,
            meta_robots='noindex', word_count=100, internal_links=2,
        )
        findings = compare_snapshots(snapshot(), after)
        self.assertTrue(findings)
        for finding in findings:
            self.assertNotIn('—', finding['message'])
            self.assertNotIn('–', finding['message'])
            self.assertTrue(finding['message'].endswith('.'))

    def test_summary_counts_by_severity(self):
        after = snapshot(canonical='', title='', viewport='', hreflang={})
        summary = summarize_findings(compare_snapshots(snapshot(), after))
        self.assertEqual(summary['rules_checked'], 17)
        self.assertEqual(
            summary['total'],
            summary['critical'] + summary['warning'] + summary['info'],
        )
        self.assertGreaterEqual(summary['critical'], 2)


class CriticalRuleTests(SimpleTestCase):
    def test_schema_supprime(self):
        after = snapshot(schema_count=0, schema_types=[], schema_hash='')
        finding = fired(compare_snapshots(snapshot(), after), 'schema_supprime')
        self.assertEqual(finding['severity'], 'critical')
        self.assertIn('LocalBusiness', finding['message'])

    def test_schema_supprime_is_only_a_warning_for_retired_types(self):
        before = snapshot(schema_types=['FAQPage', 'HowTo'], schema_count=2)
        after = snapshot(schema_count=0, schema_types=[], schema_hash='')
        finding = fired(compare_snapshots(before, after), 'schema_supprime')
        self.assertEqual(finding['severity'], 'warning')

    def test_canonical_modifie(self):
        after = snapshot(canonical='https://exemple.ca/plomberie/')
        finding = fired(compare_snapshots(snapshot(), after), 'canonical_modifie')
        self.assertEqual(finding['severity'], 'critical')
        self.assertIn('https://exemple.ca/plomberie/', finding['message'])

    def test_canonical_supprime_does_not_also_report_a_change(self):
        findings = compare_snapshots(snapshot(), snapshot(canonical=''))
        self.assertIn('canonical_supprime', rules_of(findings))
        self.assertNotIn('canonical_modifie', rules_of(findings))

    def test_noindex_ajoute(self):
        after = snapshot(meta_robots='noindex, nofollow')
        finding = fired(compare_snapshots(snapshot(), after), 'noindex_ajoute')
        self.assertEqual(finding['severity'], 'critical')

    def test_noindex_ajoute_catches_the_none_directive(self):
        # content="none" means noindex plus nofollow; upstream misses it.
        after = snapshot(meta_robots='none')
        self.assertIsNotNone(fired(compare_snapshots(snapshot(), after), 'noindex_ajoute'))

    def test_noindex_ajoute_catches_the_googlebot_meta(self):
        after = snapshot(meta_googlebot='noindex')
        self.assertIsNotNone(fired(compare_snapshots(snapshot(), after), 'noindex_ajoute'))

    def test_noindex_already_present_is_not_drift(self):
        before = snapshot(meta_robots='noindex')
        after = snapshot(meta_robots='noindex, nofollow')
        self.assertIsNone(fired(compare_snapshots(before, after), 'noindex_ajoute'))

    def test_h1_supprime(self):
        finding = fired(compare_snapshots(snapshot(), snapshot(h1=[])), 'h1_supprime')
        self.assertEqual(finding['severity'], 'critical')

    def test_h1_modifie(self):
        after = snapshot(h1=['Nos forfaits infonuagiques pour PME'])
        finding = fired(compare_snapshots(snapshot(), after), 'h1_modifie')
        self.assertEqual(finding['severity'], 'critical')
        self.assertIn('%', finding['message'])

    def test_h1_rewording_stays_quiet(self):
        after = snapshot(h1=["Plombier d'urgence a Montreal (24/7)"])
        self.assertIsNone(fired(compare_snapshots(snapshot(), after), 'h1_modifie'))

    def test_h1_capitalization_stays_quiet(self):
        after = snapshot(h1=["PLOMBIER D'URGENCE A MONTREAL"])
        self.assertIsNone(fired(compare_snapshots(snapshot(), after), 'h1_modifie'))

    def test_title_supprime(self):
        findings = compare_snapshots(snapshot(), snapshot(title=''))
        self.assertIn('title_supprime', rules_of(findings))
        self.assertNotIn('title_modifie', rules_of(findings))

    def test_code_http_erreur(self):
        finding = fired(compare_snapshots(snapshot(), snapshot(status_code=410)),
                        'code_http_erreur')
        self.assertEqual(finding['severity'], 'critical')
        self.assertIn('410', finding['message'])

    def test_code_http_stays_quiet_without_both_sides(self):
        after = snapshot(status_code=500)
        before = snapshot(status_code=None)
        self.assertIsNone(fired(compare_snapshots(before, after), 'code_http_erreur'))


class WarningRuleTests(SimpleTestCase):
    def test_title_modifie(self):
        after = snapshot(title='Plomberie Tremblay | Urgence 24/7 a Montreal')
        finding = fired(compare_snapshots(snapshot(), after), 'title_modifie')
        self.assertEqual(finding['severity'], 'warning')

    def test_meta_description_modifiee(self):
        after = snapshot(meta_description='Nouvelle promesse, nouveau texte.')
        finding = fired(compare_snapshots(snapshot(), after), 'meta_description_modifiee')
        self.assertEqual(finding['severity'], 'warning')
        self.assertIn('changé', finding['message'])

    def test_meta_description_supprimee_says_so(self):
        finding = fired(compare_snapshots(snapshot(), snapshot(meta_description='')),
                        'meta_description_modifiee')
        self.assertIn('disparu', finding['message'])

    def test_contenu_ampute(self):
        finding = fired(compare_snapshots(snapshot(), snapshot(word_count=500)),
                        'contenu_ampute')
        self.assertEqual(finding['severity'], 'warning')
        self.assertIn('38 %', finding['message'])

    def test_small_content_move_stays_quiet(self):
        self.assertIsNone(fired(compare_snapshots(snapshot(), snapshot(word_count=700)),
                                'contenu_ampute'))

    def test_short_page_is_exempt_from_the_content_rule(self):
        before = snapshot(word_count=60)
        self.assertIsNone(fired(compare_snapshots(before, snapshot(word_count=10)),
                                'contenu_ampute'))

    def test_growing_content_is_not_drift(self):
        self.assertIsNone(fired(compare_snapshots(snapshot(), snapshot(word_count=1600)),
                                'contenu_ampute'))

    def test_liens_internes_perdus(self):
        finding = fired(compare_snapshots(snapshot(), snapshot(internal_links=2)),
                        'liens_internes_perdus')
        self.assertEqual(finding['severity'], 'warning')
        self.assertIn('18', finding['message'])

    def test_link_rule_ignores_pages_with_few_links(self):
        before = snapshot(internal_links=3)
        self.assertIsNone(fired(compare_snapshots(before, snapshot(internal_links=0)),
                                'liens_internes_perdus'))

    def test_og_supprimes(self):
        finding = fired(compare_snapshots(snapshot(), snapshot(open_graph={})),
                        'og_supprimes')
        self.assertEqual(finding['severity'], 'warning')

    def test_schema_modifie_reports_the_type_change(self):
        after = snapshot(schema_hash='b' * 64, schema_types=['BreadcrumbList'],
                         schema_count=1)
        finding = fired(compare_snapshots(snapshot(), after), 'schema_modifie')
        self.assertEqual(finding['severity'], 'warning')
        self.assertIn('LocalBusiness', finding['message'])

    def test_schema_modifie_reports_a_content_only_change(self):
        finding = fired(compare_snapshots(snapshot(), snapshot(schema_hash='c' * 64)),
                        'schema_modifie')
        self.assertIn('contenu', finding['message'])

    def test_schema_removal_does_not_also_report_a_modification(self):
        after = snapshot(schema_count=0, schema_types=[], schema_hash='')
        self.assertNotIn('schema_modifie', rules_of(compare_snapshots(snapshot(), after)))

    def test_viewport_supprime(self):
        finding = fired(compare_snapshots(snapshot(), snapshot(viewport='')),
                        'viewport_supprime')
        self.assertEqual(finding['severity'], 'warning')

    def test_hreflang_disparu_is_a_warning(self):
        finding = fired(compare_snapshots(snapshot(), snapshot(hreflang={})),
                        'hreflang_modifie')
        self.assertEqual(finding['severity'], 'warning')
        self.assertIn('Québec', finding['message'])


class InfoRuleTests(SimpleTestCase):
    def test_schema_ajoute(self):
        before = snapshot(schema_count=0, schema_types=[], schema_hash='')
        finding = fired(compare_snapshots(before, snapshot()), 'schema_ajoute')
        self.assertEqual(finding['severity'], 'info')
        self.assertIn('LocalBusiness', finding['message'])

    def test_hreflang_modifie_is_info_when_a_language_moves(self):
        after = snapshot(hreflang={'fr-ca': 'https://exemple.ca/'})
        finding = fired(compare_snapshots(snapshot(), after), 'hreflang_modifie')
        self.assertEqual(finding['severity'], 'info')

    def test_hreflang_case_change_is_not_drift(self):
        # capture_snapshot lowercases, so this only guards a hand built snapshot.
        after = snapshot(hreflang={'en-ca': 'https://exemple.ca/en/',
                                   'fr-ca': 'https://exemple.ca/'})
        self.assertIsNone(fired(compare_snapshots(snapshot(), after), 'hreflang_modifie'))


class EndToEndTests(SimpleTestCase):
    """Two real HTML versions of the same page, captured then compared."""

    def test_developer_breaks_the_page_between_two_crawls(self):
        broken = (
            PAGE_HTML
            .replace('<meta name="robots" content="index, follow">',
                     '<meta name="robots" content="noindex">')
            .replace('<link rel="canonical" href="/plomberie/montreal">', '')
            .replace('<h1>Plombier d\'urgence a Montreal</h1>', '')
        )
        before = capture_snapshot(PAGE_HTML, PAGE_URL)
        after = capture_snapshot(broken, PAGE_URL)

        names = rules_of(compare_snapshots(before, after))
        self.assertIn('noindex_ajoute', names)
        self.assertIn('canonical_supprime', names)
        self.assertIn('h1_supprime', names)

    def test_untouched_page_reports_nothing(self):
        before = capture_snapshot(PAGE_HTML, PAGE_URL)
        after = capture_snapshot(PAGE_HTML, PAGE_URL)
        self.assertEqual(compare_snapshots(before, after), [])

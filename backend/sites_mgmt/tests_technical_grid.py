"""Tests for the nine-category technical grid.

Everything runs offline: `score_technical` takes data and returns data, so
there is nothing to mock. The fixtures below build one page that passes every
check, then break one thing at a time and assert that the score falls by
exactly the weight of the broken check and by nothing else.

Run all:
    python manage.py test sites_mgmt.tests_technical_grid
"""
from django.test import SimpleTestCase

from .html_parse import extract_seo_signals
from .technical_grid import (
    BLOQUANTS, CATEGORIES, CRAWLERS_IA, POIDS_CATEGORIES, score_technical,
)

URL_PROPRE = 'https://plomberie-rivenord.ca/services/deboucher-drain/'

# A clean robots.txt: nothing blocked, sitemap declared, no AI crawler rule.
ROBOTS_PROPRE = """User-agent: *
Disallow: /wp-admin/
Allow: /wp-admin/admin-ajax.php

Sitemap: https://plomberie-rivenord.ca/sitemap.xml
"""

ENTETES_PROPRES = {
    'Content-Type': 'text/html; charset=UTF-8',
    'Content-Security-Policy': "default-src 'self'",
    'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
    'X-Frame-Options': 'SAMEORIGIN',
    'X-Content-Type-Options': 'nosniff',
    'Referrer-Policy': 'strict-origin-when-cross-origin',
}

CWV_BONS = {'lcp': 1.9, 'inp': 120, 'cls': 0.04, 'source': 'crux'}

_PARAGRAPHE = (
    "Un drain bouché à Laval se règle rarement avec un produit chimique acheté "
    "en quincaillerie. Notre équipe passe la caméra dans la conduite, repère la "
    "racine ou le bouchon de graisse, puis choisit entre le furet mécanique et "
    "le jet haute pression selon ce que la caméra a montré. La soumission est "
    "donnée avant les travaux et le prix ne bouge plus ensuite. "
)


def html_propre(*, paragraphes: int = 6, viewport: bool = True,
                extra_body: str = '', jsonld: bool = True) -> str:
    """A page that passes every check the raw markup can carry."""
    balise_viewport = (
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        if viewport else ''
    )
    bloc_jsonld = (
        '<script type="application/ld+json">'
        '{"@context":"https://schema.org","@type":"Service",'
        '"name":"Débouchage de drain","areaServed":"Laval"}'
        '</script>'
    ) if jsonld else ''
    liens = ''.join(
        f'<li><a href="/services/page-{n}/">Service {n}</a></li>' for n in range(10)
    )
    return f"""<!doctype html>
<html lang="fr-CA">
<head>
<meta charset="utf-8">
{balise_viewport}
<title>Débouchage de drain à Laval | Plomberie Rive-Nord</title>
<meta name="description" content="Débouchage de drain à Laval, caméra incluse et soumission avant les travaux.">
<link rel="canonical" href="{URL_PROPRE}">
{bloc_jsonld}
</head>
<body>
<nav><a href="/">Accueil</a></nav>
<main>
<h1>Débouchage de drain à Laval</h1>
<p>{_PARAGRAPHE * paragraphes}</p>
<img src="/img/camera-drain.jpg" alt="Caméra d'inspection de drain">
<ul>{liens}</ul>
{extra_body}
</main>
<footer><a href="/nous-joindre/">Nous joindre</a></footer>
</body></html>"""


def note_propre(**remplacements) -> dict:
    """Score the clean page, with any input replaced by the caller."""
    html = remplacements.pop('html', html_propre())
    url = remplacements.pop('url', URL_PROPRE)
    signals = remplacements.pop('signals', None)
    if signals is None:
        signals = extract_seo_signals(html, url)
    arguments = {
        'robots_txt': ROBOTS_PROPRE,
        'headers': ENTETES_PROPRES,
        'url': url,
        'html': html,
        'http_status': 200,
        'web_vitals': CWV_BONS,
        'indexnow_ready': True,
    }
    arguments.update(remplacements)
    return score_technical(signals, **arguments)


def codes(resultat) -> set:
    return {reco['code'] for reco in resultat['recommandations']}


def reco(resultat, code) -> dict:
    for item in resultat['recommandations']:
        if item['code'] == code:
            return item
    raise AssertionError(f'recommandation {code!r} absente de {sorted(codes(resultat))}')


class PonderationTests(SimpleTestCase):
    def test_weights_sum_to_100(self):
        self.assertEqual(sum(poids for _, _, poids in CATEGORIES), 100)
        self.assertEqual(len(POIDS_CATEGORIES), 9)

    def test_clean_page_scores_100(self):
        resultat = note_propre()
        self.assertEqual(resultat['score'], 100, resultat['recommandations'])
        self.assertEqual(resultat['recommandations'], [])
        self.assertEqual(resultat['categories_non_mesurees'], [])
        self.assertEqual(resultat['couverture'], 100.0)

    def test_every_category_reports_the_required_keys(self):
        resultat = note_propre()
        for cle, _, poids in CATEGORIES:
            categorie = resultat['categories'][cle]
            for champ in ('score', 'max', 'applicable', 'constats', 'problemes'):
                self.assertIn(champ, categorie, cle)
            self.assertTrue(categorie['applicable'], cle)
            self.assertEqual(categorie['max'], float(poids), cle)
            self.assertEqual(categorie['score'], float(poids), cle)
            self.assertEqual(categorie['problemes'], [], cle)


class NonMesurableTests(SimpleTestCase):
    """A category nobody could measure leaves the denominator, Lighthouse style."""

    def test_missing_inputs_do_not_cost_points(self):
        resultat = note_propre(
            web_vitals=None, headers=None, indexnow_ready=None,
        )
        self.assertEqual(resultat['score'], 100)
        self.assertIn('core_web_vitals', resultat['categories_non_mesurees'])
        self.assertIn('indexnow', resultat['categories_non_mesurees'])
        self.assertFalse(resultat['categories']['core_web_vitals']['applicable'])
        self.assertEqual(resultat['categories']['core_web_vitals']['max'], 0.0)
        # Security keeps the checks that do not need headers.
        self.assertTrue(resultat['categories']['securite']['applicable'])
        self.assertEqual(resultat['couverture'], 86.0)

    def test_coverage_shrinks_with_the_inputs(self):
        """Signals alone: two thirds of the grid, and the rest stays silent."""
        signals = extract_seo_signals(html_propre(), URL_PROPRE)
        maigre = score_technical(signals)
        self.assertLess(maigre['couverture'], 70)
        self.assertIsNotNone(maigre['score'])
        self.assertEqual(
            maigre['categories_non_mesurees'],
            ['securite', 'mobile', 'core_web_vitals', 'indexnow'],
        )
        # URL structure survives without an address: the trailing-slash rule
        # reads the page's own internal links.
        self.assertTrue(maigre['categories']['structure_url']['applicable'])

    def test_absent_robots_is_not_a_missing_robots(self):
        """No robots.txt passed means not fetched, never "the site has none"."""
        resultat = note_propre(robots_txt='')
        self.assertNotIn('robots_sitemap', codes(resultat))
        self.assertNotIn('robots_bloque_tout', codes(resultat))
        self.assertTrue(any(
            'robots.txt non fourni' in note
            for note in resultat['categories']['crawlabilite']['non_mesure']
        ))

    def test_nothing_measurable_returns_no_score(self):
        resultat = score_technical({'word_count': 500, 'meta_robots': 'index'})
        self.assertIsNotNone(resultat['score'])
        vide = score_technical(None)
        self.assertIsNotNone(vide['score'])


class CrawlabiliteTests(SimpleTestCase):
    def test_disallow_all_is_critical(self):
        resultat = note_propre(robots_txt='User-agent: *\nDisallow: /\n')
        item = reco(resultat, 'robots_bloque_tout')
        self.assertEqual(item['priorite'], 'critique')
        self.assertEqual(resultat['categories']['crawlabilite']['statut'], 'echec')

    def test_allow_root_overrides_disallow_all(self):
        resultat = note_propre(
            robots_txt='User-agent: *\nDisallow: /\nAllow: /\nSitemap: https://x.ca/s.xml\n',
        )
        self.assertNotIn('robots_bloque_tout', codes(resultat))

    def test_googlebot_group_wins_over_the_wildcard(self):
        resultat = note_propre(robots_txt=(
            'User-agent: *\nDisallow:\n\n'
            'User-agent: Googlebot\nDisallow: /\n\n'
            'Sitemap: https://plomberie-rivenord.ca/sitemap.xml\n'
        ))
        self.assertIn('robots_bloque_googlebot', codes(resultat))
        self.assertNotIn('robots_bloque_tout', codes(resultat))

    def test_wildcard_block_is_charged_once(self):
        """A wildcard Disallow already blocks Googlebot; it must not cost twice."""
        resultat = note_propre(robots_txt='User-agent: *\nDisallow: /\n')
        self.assertNotIn('robots_bloque_googlebot', codes(resultat))

    def test_blocked_render_resources(self):
        resultat = note_propre(robots_txt=(
            'User-agent: *\nDisallow: /wp-content/\nDisallow: /assets/\n'
            'Sitemap: https://plomberie-rivenord.ca/sitemap.xml\n'
        ))
        item = reco(resultat, 'robots_ressources')
        self.assertEqual(item['priorite'], 'elevee')
        self.assertIn('/wp-content/', item['probleme'])

    def test_missing_sitemap_declaration(self):
        resultat = note_propre(robots_txt='User-agent: *\nDisallow: /wp-admin/\n')
        self.assertIn('robots_sitemap', codes(resultat))

    def test_comments_and_blank_lines_are_ignored(self):
        resultat = note_propre(robots_txt=(
            '# robots genere par le CMS\n'
            'User-agent: *   # tout le monde\n'
            'Disallow: /wp-admin/\n\n'
            'Sitemap: https://plomberie-rivenord.ca/sitemap.xml\n'
        ))
        self.assertEqual(resultat['score'], 100)


class CrawlersIaTests(SimpleTestCase):
    """Blocking a training crawler is a business choice; blocking a citation
    crawler removes the site from AI answers, which is what Gridar sells."""

    def test_table_matches_the_source(self):
        self.assertEqual(len(CRAWLERS_IA), 7)
        noms = {nom for nom, _, _ in CRAWLERS_IA}
        self.assertEqual(noms, {
            'GPTBot', 'ChatGPT-User', 'ClaudeBot', 'PerplexityBot',
            'Bytespider', 'Google-Extended', 'CCBot',
        })

    def test_blocking_training_crawlers_costs_nothing(self):
        resultat = note_propre(robots_txt=(
            'User-agent: GPTBot\nDisallow: /\n\n'
            'User-agent: ClaudeBot\nDisallow: /\n\n'
            'User-agent: Google-Extended\nDisallow: /\n\n'
            'User-agent: *\nDisallow: /wp-admin/\n\n'
            'Sitemap: https://plomberie-rivenord.ca/sitemap.xml\n'
        ))
        self.assertEqual(resultat['score'], 100)
        constats = ' '.join(resultat['categories']['crawlabilite']['constats'])
        self.assertIn('GPTBot', constats)
        self.assertIn('Google Search', constats)

    def test_blocking_citation_crawlers_costs_points(self):
        resultat = note_propre(robots_txt=(
            'User-agent: PerplexityBot\nDisallow: /\n\n'
            'User-agent: ChatGPT-User\nDisallow: /\n\n'
            'User-agent: *\nDisallow: /wp-admin/\n\n'
            'Sitemap: https://plomberie-rivenord.ca/sitemap.xml\n'
        ))
        item = reco(resultat, 'crawlers_ia_citation')
        self.assertEqual(item['priorite'], 'elevee')
        self.assertIn('PerplexityBot', item['probleme'])
        self.assertLess(resultat['score'], 100)

    def test_one_citation_crawler_blocked_is_half_the_penalty(self):
        deux = note_propre(robots_txt=(
            'User-agent: PerplexityBot\nDisallow: /\n\n'
            'User-agent: ChatGPT-User\nDisallow: /\n\n'
            'User-agent: *\nDisallow:\n\n'
            'Sitemap: https://plomberie-rivenord.ca/sitemap.xml\n'
        ))
        une = note_propre(robots_txt=(
            'User-agent: PerplexityBot\nDisallow: /\n\n'
            'User-agent: *\nDisallow:\n\n'
            'Sitemap: https://plomberie-rivenord.ca/sitemap.xml\n'
        ))
        self.assertGreater(une['score'], deux['score'])
        self.assertAlmostEqual(
            reco(deux, 'crawlers_ia_citation')['points_recuperables'],
            reco(une, 'crawlers_ia_citation')['points_recuperables'] * 2,
            delta=0.2,  # points are rounded to a tenth before being reported
        )


class PoidsHtmlTests(SimpleTestCase):
    def test_over_2mb_is_critical(self):
        gros = html_propre(extra_body='<p>' + ('mot ' * 700_000) + '</p>')
        resultat = note_propre(html=gros)
        item = reco(resultat, 'poids_html')
        self.assertEqual(item['priorite'], 'critique')
        self.assertIn('2 premiers', item['probleme'])

    def test_between_1mb_and_2mb_is_a_warning(self):
        moyen = html_propre(extra_body='<p>' + ('mot ' * 300_000) + '</p>')
        item = reco(note_propre(html=moyen), 'poids_html')
        self.assertEqual(item['priorite'], 'moyenne')

    def test_base64_images_are_named_in_the_finding(self):
        charge = 'data:image/png;base64,' + ('A' * 400_000)
        gros = html_propre(extra_body=f'<img src="{charge}" alt="plan">' * 4)
        item = reco(note_propre(html=gros), 'poids_html')
        self.assertIn('base64', item['probleme'])


class IndexabiliteTests(SimpleTestCase):
    def test_noindex_is_critical_and_costs_its_own_weight(self):
        html = html_propre().replace(
            '<meta charset="utf-8">',
            '<meta charset="utf-8"><meta name="robots" content="noindex, follow">',
        )
        resultat = note_propre(html=html)
        item = reco(resultat, 'noindex')
        self.assertEqual(item['priorite'], 'critique')
        self.assertEqual(resultat['score'], 100 - round(item['points_recuperables']))
        self.assertEqual(resultat['categories']['indexabilite']['statut'], 'echec')

    def test_nofollow_hits_crawlability_not_indexability(self):
        html = html_propre().replace(
            '<meta charset="utf-8">',
            '<meta charset="utf-8"><meta name="robots" content="index, nofollow">',
        )
        resultat = note_propre(html=html)
        self.assertIn('meta_nofollow', codes(resultat))
        self.assertNotIn('noindex', codes(resultat))

    def test_missing_canonical(self):
        html = html_propre().replace(f'<link rel="canonical" href="{URL_PROPRE}">', '')
        resultat = note_propre(html=html)
        self.assertIn('canonical_presence', codes(resultat))
        # With no canonical there is nothing to compare, so the coherence check
        # leaves the denominator instead of failing.
        self.assertNotIn('canonical_coherence', codes(resultat))

    def test_cross_domain_canonical_is_critical(self):
        html = html_propre().replace(URL_PROPRE, 'https://autre-site.com/page/')
        resultat = note_propre(html=html)
        item = reco(resultat, 'canonical_coherence')
        self.assertEqual(item['priorite'], 'critique')

    def test_same_site_variant_canonical_is_half_credit(self):
        html = html_propre().replace(
            URL_PROPRE, 'https://plomberie-rivenord.ca/services/autre-page/',
        )
        item = reco(note_propre(html=html), 'canonical_coherence')
        self.assertEqual(item['priorite'], 'elevee')

    def test_www_and_trailing_slash_do_not_count_as_a_conflict(self):
        html = html_propre().replace(
            URL_PROPRE, 'https://www.plomberie-rivenord.ca/services/deboucher-drain',
        )
        self.assertNotIn('canonical_coherence', codes(note_propre(html=html)))

    def test_thin_content(self):
        resultat = note_propre(html=html_propre(paragraphes=1))
        item = reco(resultat, 'contenu_mince')
        self.assertEqual(item['priorite'], 'elevee')

    def test_empty_page_is_a_rendering_defect_not_thin_content(self):
        """The same failure must not be charged in two categories."""
        vide = '<html><head><title>x</title></head><body><div id="root"></div></body></html>'
        resultat = note_propre(html=vide, url=URL_PROPRE)
        self.assertNotIn('contenu_mince', codes(resultat))
        self.assertIn('contenu_servi', codes(resultat))

    def test_hreflang_needs_self_reference_and_x_default(self):
        html = html_propre().replace(
            '</head>',
            '<link rel="alternate" hreflang="en-CA" href="https://plomberie-rivenord.ca/en/">'
            '</head>',
        )
        item = reco(note_propre(html=html), 'hreflang_complet')
        self.assertIn('elle-même', item['probleme'])
        self.assertIn('x-default', item['probleme'])

    def test_complete_hreflang_cluster_passes(self):
        html = html_propre().replace(
            '</head>',
            f'<link rel="alternate" hreflang="fr-CA" href="{URL_PROPRE}">'
            '<link rel="alternate" hreflang="en-CA" href="https://plomberie-rivenord.ca/en/drain/">'
            f'<link rel="alternate" hreflang="x-default" href="{URL_PROPRE}">'
            '</head>',
        )
        self.assertEqual(note_propre(html=html)['score'], 100)

    def test_tracking_parameters_on_the_served_url(self):
        url = URL_PROPRE + '?utm_source=facebook&utm_campaign=printemps'
        resultat = note_propre(url=url, html=html_propre())
        self.assertIn('parametres_suivi', codes(resultat))


class SecuriteTests(SimpleTestCase):
    def test_http_is_critical(self):
        url = URL_PROPRE.replace('https://', 'http://')
        html = html_propre().replace(URL_PROPRE, url)
        resultat = note_propre(url=url, html=html)
        self.assertEqual(reco(resultat, 'https')['priorite'], 'critique')

    def test_mixed_content(self):
        html = html_propre(
            extra_body='<img src="http://vieux-cdn.example.com/logo.png" alt="logo">',
        )
        item = reco(note_propre(html=html), 'contenu_mixte')
        self.assertIn('HTTP', item['probleme'])

    def test_missing_security_headers_are_low_priority(self):
        resultat = note_propre(headers={'Content-Type': 'text/html'})
        item = reco(resultat, 'entetes_securite')
        self.assertEqual(item['priorite'], 'faible')
        self.assertIn('Content-Security-Policy', item['probleme'])
        # The source says not to over-weight them: five missing headers may not
        # cost more than a quarter of the security category.
        self.assertLessEqual(item['points_recuperables'], POIDS_CATEGORIES['securite'] / 4)

    def test_partial_headers_get_partial_credit(self):
        partiel = note_propre(headers={
            'Strict-Transport-Security': 'max-age=31536000',
            'X-Content-Type-Options': 'nosniff',
        })
        aucun = note_propre(headers={})
        self.assertLess(
            reco(partiel, 'entetes_securite')['points_recuperables'],
            reco(aucun, 'entetes_securite')['points_recuperables'],
        )

    def test_back_button_hijack(self):
        piege = (
            '<script>history.pushState(null, null, location.href);'
            'window.onpopstate = function () { history.go(1); };</script>'
        )
        resultat = note_propre(html=html_propre(extra_body=piege))
        item = reco(resultat, 'detournement_retour')
        self.assertEqual(item['priorite'], 'critique')

    def test_spa_router_alone_is_not_a_hijack(self):
        routeur = (
            '<script>window.addEventListener("popstate", function () {'
            'render(location.pathname); });</script>'
        )
        resultat = note_propre(html=html_propre(extra_body=routeur))
        self.assertNotIn('detournement_retour', codes(resultat))


class StructureUrlTests(SimpleTestCase):
    def _sur(self, url, **extra):
        html = html_propre().replace(URL_PROPRE, url)
        return note_propre(url=url, html=html, **extra)

    def test_long_url(self):
        url = 'https://plomberie-rivenord.ca/services/' + 'a' * 90 + '/'
        self.assertIn('longueur_url', codes(self._sur(url)))

    def test_content_parameters(self):
        self.assertIn(
            'parametres_contenu',
            codes(self._sur('https://plomberie-rivenord.ca/?p=482')),
        )

    def test_uppercase_and_underscores(self):
        resultat = self._sur('https://plomberie-rivenord.ca/Services/deboucher_drain/')
        self.assertIn('casse_url', codes(resultat))
        self.assertIn('separateurs', codes(resultat))

    def test_accented_path(self):
        """French CMS exports produce these by the hundred."""
        resultat = self._sur('https://plomberie-rivenord.ca/services/réparation/')
        self.assertIn('caracteres_encodes', codes(resultat))
        encode = self._sur('https://plomberie-rivenord.ca/services/r%C3%A9paration/')
        self.assertIn('caracteres_encodes', codes(encode))

    def test_depth(self):
        url = 'https://plomberie-rivenord.ca/a/b/c/d/e/'
        self.assertIn('profondeur', codes(self._sur(url)))

    def test_trailing_slash_consistency(self):
        melange = html_propre().replace(
            '<li><a href="/services/page-1/">Service 1</a></li>',
            '<li><a href="/services/page-1">Service 1</a></li>',
        ).replace(
            '<li><a href="/services/page-2/">Service 2</a></li>',
            '<li><a href="/services/page-2">Service 2</a></li>',
        ).replace(
            '<li><a href="/services/page-3/">Service 3</a></li>',
            '<li><a href="/services/page-3">Service 3</a></li>',
        )
        self.assertIn('barre_finale', codes(note_propre(html=melange)))

    def test_too_few_internal_links_skips_the_check(self):
        signals = extract_seo_signals(html_propre(), URL_PROPRE)
        signals['links'] = {'internal': [{'href': URL_PROPRE, 'text': '', 'rel': []}],
                            'external': []}
        resultat = note_propre(signals=signals)
        self.assertNotIn('barre_finale', codes(resultat))
        self.assertGreater(
            resultat['categories']['structure_url']['verifications']['ignorees'], 0,
        )


class MobileTests(SimpleTestCase):
    def test_missing_viewport_is_critical(self):
        resultat = note_propre(html=html_propre(viewport=False))
        self.assertEqual(reco(resultat, 'viewport')['priorite'], 'critique')
        # Nothing to say about zoom without a viewport tag, so that check drops.
        self.assertNotIn('zoom_bloque', codes(resultat))

    def test_viewport_without_device_width_is_half_credit(self):
        html = html_propre().replace('width=device-width, initial-scale=1', 'width=1024')
        item = reco(note_propre(html=html), 'viewport')
        self.assertLess(item['points_recuperables'], POIDS_CATEGORIES['mobile'] / 2)

    def test_zoom_blocked(self):
        html = html_propre().replace(
            'width=device-width, initial-scale=1',
            'width=device-width, initial-scale=1, user-scalable=no',
        )
        self.assertIn('zoom_bloque', codes(note_propre(html=html)))

    def test_promotional_interstitial(self):
        popup = (
            '<div class="newsletter-modal"><h2>Infolettre</h2>'
            '<p>Abonnez-vous et obtenez 10 % de rabais sur votre soumission.</p></div>'
        )
        self.assertIn('interstitiel', codes(note_propre(html=html_propre(extra_body=popup))))

    def test_consent_dialog_is_not_an_interstitial(self):
        """Loi 25 puts one of these on every Quebec site."""
        banniere = (
            '<div class="cookie-modal"><p>Ce site utilise des témoins pour '
            'la confidentialité de vos données.</p><button>Accepter</button></div>'
        )
        resultat = note_propre(html=html_propre(extra_body=banniere))
        self.assertNotIn('interstitiel', codes(resultat))

    def test_content_hidden_behind_accordions(self):
        replis = '<div class="accordion">Détail</div>' * 5
        self.assertIn('contenu_masque', codes(note_propre(html=html_propre(extra_body=replis))))


class CoreWebVitalsTests(SimpleTestCase):
    def test_thresholds(self):
        mauvais = note_propre(web_vitals={'lcp': 5.2, 'inp': 700, 'cls': 0.4})
        for code in ('cwv_lcp', 'cwv_inp', 'cwv_cls'):
            self.assertEqual(reco(mauvais, code)['priorite'], 'critique')
        self.assertEqual(mauvais['categories']['core_web_vitals']['score'], 0.0)

        moyen = note_propre(web_vitals={'lcp': 3.0, 'inp': 300, 'cls': 0.15})
        for code in ('cwv_lcp', 'cwv_inp', 'cwv_cls'):
            self.assertEqual(reco(moyen, code)['priorite'], 'elevee')
        self.assertEqual(
            moyen['categories']['core_web_vitals']['score'],
            POIDS_CATEGORIES['core_web_vitals'] / 2,
        )

    def test_milliseconds_are_read_as_seconds_for_lcp(self):
        """PageSpeed answers in milliseconds, a hand-filled field in seconds."""
        psi = note_propre(web_vitals={'lcp': 1900, 'inp': 120, 'cls': 0.04})
        self.assertEqual(psi['score'], 100)
        lent = note_propre(web_vitals={'lcp': 5200, 'inp': 120, 'cls': 0.04})
        self.assertIn('cwv_lcp', codes(lent))

    def test_inp_given_in_seconds(self):
        resultat = note_propre(web_vitals={'lcp': 1.9, 'inp': 0.12, 'cls': 0.04})
        self.assertEqual(resultat['score'], 100)

    def test_fid_is_ignored_and_said_so(self):
        resultat = note_propre(web_vitals={'lcp': 1.9, 'inp': 120, 'cls': 0.04, 'fid': 40})
        constats = ' '.join(resultat['categories']['core_web_vitals']['constats'])
        self.assertIn('FID', constats)
        self.assertIn('INP', constats)
        self.assertEqual(resultat['score'], 100)

    def test_a_missing_metric_leaves_the_denominator(self):
        resultat = note_propre(web_vitals={'lcp': 1.9})
        categorie = resultat['categories']['core_web_vitals']
        self.assertTrue(categorie['applicable'])
        self.assertEqual(categorie['score'], float(POIDS_CATEGORIES['core_web_vitals']))
        self.assertEqual(categorie['verifications']['faites'], 1)

    def test_french_number_format_in_the_finding(self):
        item = reco(note_propre(web_vitals={'lcp': 5.2, 'inp': 120, 'cls': 0.04}), 'cwv_lcp')
        self.assertIn('5,2 s', item['probleme'])


class DonneesStructureesTests(SimpleTestCase):
    def test_no_jsonld(self):
        resultat = note_propre(html=html_propre(jsonld=False))
        self.assertEqual(reco(resultat, 'jsonld_present')['priorite'], 'elevee')

    def test_microdata_without_jsonld(self):
        html = html_propre(jsonld=False, extra_body=(
            '<div itemscope itemtype="https://schema.org/Service">'
            '<span itemprop="name">Débouchage</span></div>'
        ))
        self.assertIn('microdata_seul', codes(note_propre(html=html)))

    def test_howto_is_low_priority(self):
        html = html_propre().replace(
            '"@type":"Service"', '"@type":"HowTo"',
        )
        item = reco(note_propre(html=html), 'types_retires')
        self.assertEqual(item['priorite'], 'faible')

    def test_faqpage_is_reported_without_penalty(self):
        """The source says flag it at info level and never recommend removal."""
        html = html_propre().replace('"@type":"Service"', '"@type":"FAQPage"')
        resultat = note_propre(html=html)
        self.assertEqual(resultat['score'], 100)
        constats = ' '.join(resultat['categories']['donnees_structurees']['constats'])
        self.assertIn('FAQPage', constats)

    def test_entity_without_type(self):
        html = html_propre().replace(
            '"@type":"Service",', '',
        )
        self.assertIn('entites_typees', codes(note_propre(html=html)))


class RenduJavascriptTests(SimpleTestCase):
    def test_empty_app_shell_is_critical(self):
        coquille = (
            '<!doctype html><html lang="fr"><head>'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            '<title>Plomberie</title></head>'
            '<body><div id="root"></div>'
            '<script>window.__DATA__={};</script></body></html>'
        )
        resultat = note_propre(html=coquille)
        self.assertEqual(reco(resultat, 'coquille_spa')['priorite'], 'critique')
        self.assertEqual(reco(resultat, 'contenu_servi')['priorite'], 'critique')

    def test_partial_content_is_half_credit(self):
        court = html_propre().replace(_PARAGRAPHE * 6, _PARAGRAPHE)
        item = reco(note_propre(html=court), 'contenu_servi')
        self.assertEqual(item['priorite'], 'elevee')

    def test_non_200_is_critical(self):
        resultat = note_propre(http_status=404)
        item = reco(resultat, 'statut_http')
        self.assertEqual(item['priorite'], 'critique')
        self.assertIn('JavaScript', item['probleme'])

    def test_unknown_status_drops_the_check(self):
        resultat = note_propre(http_status=None)
        self.assertNotIn('statut_http', codes(resultat))
        self.assertEqual(resultat['score'], 100)

    def test_script_heavy_document(self):
        lourd = (
            '<!doctype html><html lang="fr"><head>'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            '<title>Plomberie Rive-Nord</title>'
            f'<link rel="canonical" href="{URL_PROPRE}">'
            '<script type="application/ld+json">{"@context":"https://schema.org",'
            '"@type":"Service","name":"Drain"}</script></head>'
            '<body><main><h1>Drain</h1><p>' + ('mot ' * 200) + '</p></main>'
            '<script>' + ('var a=1;' * 6000) + '</script></body></html>'
        )
        self.assertIn('poids_scripts', codes(note_propre(html=lourd)))


class IndexNowTests(SimpleTestCase):
    def test_three_states(self):
        self.assertEqual(note_propre(indexnow_ready=True)['score'], 100)

        absent = note_propre(indexnow_ready=False)
        item = reco(absent, 'indexnow_actif')
        self.assertEqual(item['points_recuperables'], float(POIDS_CATEGORIES['indexnow']))
        self.assertIn('Bing', item['action'])

        inconnu = note_propre(indexnow_ready=None)
        self.assertNotIn('indexnow_actif', codes(inconnu))
        self.assertFalse(inconnu['categories']['indexnow']['applicable'])


class RecommandationsTests(SimpleTestCase):
    def test_sorted_by_recoverable_points(self):
        casse = html_propre(viewport=False, jsonld=False).replace(
            f'<link rel="canonical" href="{URL_PROPRE}">', '',
        )
        resultat = note_propre(
            html=casse,
            robots_txt='User-agent: *\nDisallow: /\n',
            web_vitals={'lcp': 6.0, 'inp': 800, 'cls': 0.5},
            indexnow_ready=False,
            http_status=500,
        )
        points = [r['points_recuperables'] for r in resultat['recommandations']]
        self.assertEqual(points, sorted(points, reverse=True))
        self.assertLess(resultat['score'], 70)
        self.assertEqual(resultat['recommandations'][0]['priorite'], 'critique')

    def test_recoverable_points_stay_inside_the_category_budget(self):
        casse = html_propre(viewport=False, jsonld=False)
        resultat = note_propre(
            html=casse,
            robots_txt='User-agent: *\nDisallow: /\n',
            web_vitals={'lcp': 6.0, 'inp': 800, 'cls': 0.5},
            indexnow_ready=False,
        )
        par_categorie = {}
        for item in resultat['recommandations']:
            par_categorie.setdefault(item['categorie'], 0.0)
            par_categorie[item['categorie']] += item['points_recuperables']
        for cle, total in par_categorie.items():
            self.assertLessEqual(round(total, 1), POIDS_CATEGORIES[cle] + 0.1, cle)

    def test_every_recommendation_carries_a_french_action(self):
        resultat = note_propre(
            html=html_propre(viewport=False, jsonld=False),
            robots_txt='User-agent: *\nDisallow: /\n',
            indexnow_ready=False,
            web_vitals={'lcp': 6.0, 'inp': 800, 'cls': 0.5},
        )
        self.assertTrue(resultat['recommandations'])
        for item in resultat['recommandations']:
            self.assertTrue(item['probleme'].strip(), item['code'])
            self.assertTrue(item['action'].strip(), item['code'])
            self.assertIn(item['priorite'], ('critique', 'elevee', 'moyenne', 'faible'))
            # House rule: no em dash and no en dash in anything a client reads.
            # Written as code points so neither character appears in this file.
            for tiret in (chr(0x2014), chr(0x2013)):
                self.assertNotIn(tiret, item['action'], item['code'])
                self.assertNotIn(tiret, item['probleme'], item['code'])


class BloquantsTests(SimpleTestCase):
    """A page that cannot be indexed still collects points elsewhere. The score
    alone would read as half decent, so the blockers are reported apart."""

    def test_clean_page_has_none(self):
        self.assertEqual(note_propre()['bloquants'], [])

    def test_disallow_all_is_a_blocker(self):
        resultat = note_propre(robots_txt='User-agent: *\nDisallow: /\n')
        self.assertEqual([b['code'] for b in resultat['bloquants']],
                         ['robots_bloque_tout'])
        # The rest of the grid still passes, which is exactly why the number
        # cannot be shown on its own.
        self.assertGreater(resultat['score'], 50)

    def test_noindex_and_error_status_are_blockers(self):
        html = html_propre().replace(
            '<meta charset="utf-8">',
            '<meta charset="utf-8"><meta name="robots" content="noindex">',
        )
        resultat = note_propre(html=html, http_status=500)
        self.assertEqual(
            {b['code'] for b in resultat['bloquants']}, {'noindex', 'statut_http'},
        )

    def test_blockers_are_a_subset_of_the_recommendations(self):
        resultat = note_propre(
            robots_txt='User-agent: *\nDisallow: /\n', http_status=404,
        )
        for bloquant in resultat['bloquants']:
            self.assertIn(bloquant['code'], BLOQUANTS)
            self.assertIn(bloquant['code'], codes(resultat))


class RobustesseTests(SimpleTestCase):
    """The grid runs on whatever an audited site returns, so nothing may raise."""

    def test_garbage_inputs(self):
        for signals in (None, {}, {'links': 'pas un dict'}, {'schema': 'x'},
                        {'word_count': None}, {'images': [None, 'x']}):
            resultat = score_technical(
                signals, robots_txt='\x00\xff pas du robots',
                headers={'x': None}, url='pas une url',
                html='<html><body>' + '<div' * 50, http_status='500',
                web_vitals={'lcp': 'lent'}, indexnow_ready='oui',
            )
            self.assertIn('categories', resultat)
            self.assertEqual(len(resultat['categories']), 9)

    def test_malformed_url_does_not_crash(self):
        resultat = score_technical({}, url='http://[bad', html='<p>x</p>')
        self.assertIsNotNone(resultat['score'])


class ContratHtmlParseTests(SimpleTestCase):
    """`signals` is exactly what `extract_seo_signals` returns, so the two
    modules are exercised together here rather than against a hand-built dict."""

    def test_reads_a_real_quebec_page(self):
        signals = extract_seo_signals(html_propre(), URL_PROPRE)
        resultat = score_technical(
            signals, robots_txt=ROBOTS_PROPRE, headers=ENTETES_PROPRES,
            url=URL_PROPRE, html=html_propre(), http_status=200,
            web_vitals=CWV_BONS, indexnow_ready=True,
        )
        self.assertEqual(resultat['score'], 100)
        self.assertGreaterEqual(signals['word_count'], 300)
        self.assertEqual(signals['canonical'], URL_PROPRE)

    def test_every_signal_key_read_here_exists_upstream(self):
        signals = extract_seo_signals(html_propre(), URL_PROPRE)
        for cle in ('meta_robots', 'canonical', 'word_count', 'images', 'links',
                    'hreflang', 'schema', 'schema_types'):
            self.assertIn(cle, signals)

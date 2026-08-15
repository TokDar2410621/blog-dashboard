"""Tests for the stdlib HTML signal extractor.

Everything here runs offline by construction: `html_parse` takes a string and
returns a dict, it opens no socket, so there is nothing to mock. The fixtures
are deliberately ugly (unclosed tags, uppercase tags, unquoted attributes,
mixed og/twitter namespaces) because that is what the pages Gridar audits
actually look like.

Run all:
    python manage.py test sites_mgmt.tests_html_parse
"""
from django.test import SimpleTestCase

from .html_parse import count_words, extract_seo_signals

NBSP = ' '  # French thousands separator, and what a stat counter uses


def page(body='', head='', html_attrs=' lang="fr-CA"'):
    return f'<!DOCTYPE html><html{html_attrs}><head>{head}</head><body>{body}</body></html>'


class HeadSignalsTests(SimpleTestCase):
    def test_reads_the_usual_head_elements(self):
        result = extract_seo_signals(page(head='''
            <title>  Plombier a Laval | Gridar  </title>
            <meta name="description" content="Urgence 24h a Laval.">
            <meta name="robots" content="index, follow">
            <meta name="keywords" content="plombier, laval">
            <link rel="canonical" href="https://ex.ca/plombier">
        '''))
        self.assertEqual(result['title'], 'Plombier a Laval | Gridar')
        self.assertEqual(result['meta_description'], 'Urgence 24h a Laval.')
        self.assertEqual(result['meta_robots'], 'index, follow')
        self.assertEqual(result['meta_keywords'], 'plombier, laval')
        self.assertEqual(result['canonical'], 'https://ex.ca/plombier')
        self.assertEqual(result['lang'], 'fr-CA')

    def test_absent_and_empty_stay_distinguishable(self):
        """No tag is None, an empty tag is ''. They are different findings."""
        result = extract_seo_signals(page(head='<meta name="description" content="">'))
        self.assertEqual(result['meta_description'], '')
        self.assertIsNone(result['meta_robots'])
        self.assertIsNone(result['title'])
        self.assertIsNone(result['canonical'])

    def test_first_meta_wins_when_a_plugin_appends_a_second(self):
        result = extract_seo_signals(page(head='''
            <meta name="description" content="premiere">
            <meta name="DESCRIPTION" content="doublon du plugin">
        '''))
        self.assertEqual(result['meta_description'], 'premiere')

    def test_reads_og_and_twitter_from_either_attribute(self):
        """Real pages swap `property` and `name`; both namespaces accept both."""
        result = extract_seo_signals(page(head='''
            <meta property="og:title" content="Titre OG">
            <meta name="og:image" content="https://ex.ca/i.png">
            <meta name="twitter:card" content="summary_large_image">
            <meta property="twitter:title" content="Titre Twitter">
        '''))
        self.assertEqual(result['open_graph'], {
            'og:title': 'Titre OG', 'og:image': 'https://ex.ca/i.png',
        })
        self.assertEqual(result['twitter_card'], {
            'twitter:card': 'summary_large_image', 'twitter:title': 'Titre Twitter',
        })

    def test_collects_hreflang_alternates_only(self):
        result = extract_seo_signals(
            page(head='''
                <link rel="alternate" hreflang="fr-ca" href="/fr/">
                <link rel="alternate" hreflang="en-ca" href="/en/">
                <link rel="alternate" type="application/rss+xml" href="/feed/">
                <link rel="stylesheet" href="/app.css">
            '''),
            base_url='https://ex.ca/fr/page',
        )
        self.assertEqual(result['hreflang'], [
            {'lang': 'fr-ca', 'href': 'https://ex.ca/fr/'},
            {'lang': 'en-ca', 'href': 'https://ex.ca/en/'},
        ])


class UrlResolutionTests(SimpleTestCase):
    def test_relative_canonical_is_resolved_against_the_page_url(self):
        result = extract_seo_signals(
            page(head='<link rel="canonical" href="/services/toiture">'),
            base_url='https://ex.ca/fr/vieille-page?x=1',
        )
        self.assertEqual(result['canonical'], 'https://ex.ca/services/toiture')

    def test_base_href_overrides_the_page_url(self):
        """<base> changes resolution document-wide, even for links parsed before it."""
        html = page(
            head='<link rel="canonical" href="toiture"><base href="https://cdn.ex.ca/fr/">',
            body='<a href="couvreur">Couvreur</a>',
        )
        result = extract_seo_signals(html, base_url='https://ex.ca/')
        self.assertEqual(result['canonical'], 'https://cdn.ex.ca/fr/toiture')
        self.assertEqual(result['links']['internal'][0]['href'], 'https://cdn.ex.ca/fr/couvreur')

    def test_hrefs_survive_without_a_base_url(self):
        result = extract_seo_signals(page(head='<link rel="canonical" href="/a">'))
        self.assertEqual(result['canonical'], '/a')


class HeadingTests(SimpleTestCase):
    def test_collects_headings_in_document_order(self):
        result = extract_seo_signals(page(body='''
            <h1>Toiture a Quebec</h1><h2>Nos services</h2>
            <h2>Nos prix</h2><h3>Bardeau</h3>
        '''))
        self.assertEqual(result['h1'], ['Toiture a Quebec'])
        self.assertEqual(result['h2'], ['Nos services', 'Nos prix'])
        self.assertEqual(result['h3'], ['Bardeau'])

    def test_inline_markup_does_not_split_or_glue_words(self):
        """<br> is a word boundary, <b> is not."""
        result = extract_seo_signals(page(body=(
            '<h1>Plombier<br>Montreal</h1>'
            '<h2>Grid<b>ar</b></h2>'
            '<h3><span>Urgence</span> <em>24h</em></h3>'
        )))
        self.assertEqual(result['h1'], ['Plombier Montreal'])
        self.assertEqual(result['h2'], ['Gridar'])
        self.assertEqual(result['h3'], ['Urgence 24h'])

    def test_flags_stat_counters_but_spares_short_real_headings(self):
        result = extract_seo_signals(page(body=(
            f'<h2>500+</h2><h2>1{NBSP}500 $</h2><h2>99,9 %</h2>'
            '<h2>1er</h2><h2>SEO</h2><h2>Nos services</h2>'
        )))
        self.assertEqual(
            result['suspicious_headings']['h2'],
            ['500+', f'1{NBSP}500 $', '99,9 %', '1er'],
        )
        self.assertEqual(result['suspicious_headings']['h1'], [])

    def test_empty_headings_are_dropped(self):
        result = extract_seo_signals(page(body='<h1></h1><h1>   </h1><h1>Vrai</h1>'))
        self.assertEqual(result['h1'], ['Vrai'])


class WordCountTests(SimpleTestCase):
    def test_french_elision_and_hyphens_count_as_one_word(self):
        text = "L'entreprise de plomberie peut-etre a Trois-Rivieres"
        self.assertEqual(count_words(text), 6)

    def test_typographic_apostrophe_counts_like_the_ascii_one(self):
        self.assertEqual(count_words('l’entreprise'), 1)
        self.assertEqual(count_words("l'entreprise"), 1)

    def test_accents_do_not_split_a_word(self):
        self.assertEqual(count_words('quebecois'), count_words('québécois'))

    def test_scripts_styles_and_chrome_are_excluded(self):
        result = extract_seo_signals(page(
            head='<title>Un titre de page assez long ici</title>',
            body='''
                <nav>Accueil Services Contact Blogue</nav>
                <script>var a = "un deux trois quatre";</script>
                <style>.x { color: red; }</style>
                <p>Nous reparons les toitures.</p>
                <footer>Tous droits reserves partout</footer>
            ''',
        ))
        self.assertEqual(result['text'], 'Nous reparons les toitures.')
        self.assertEqual(result['word_count'], 4)

    def test_hero_header_counts_when_it_is_the_content(self):
        """Upstream deletes every <header>, which throws away most hero copy."""
        inside = extract_seo_signals(page(
            body='<main><header><h1>Couvreur a Laval</h1><p>Depuis 1998.</p></header></main>',
        ))
        self.assertEqual(inside['word_count'], 5)

        outside = extract_seo_signals(page(
            body='<header><p>Menu du site ici</p></header><main><p>Contenu reel.</p></main>',
        ))
        self.assertEqual(outside['text'], 'Contenu reel.')

    def test_block_boundaries_separate_words(self):
        result = extract_seo_signals(page(body='<p>alpha</p><p>beta</p>'))
        self.assertEqual(result['text'], 'alpha beta')
        self.assertEqual(result['word_count'], 2)

    def test_entities_are_decoded(self):
        result = extract_seo_signals(page(body='<p>caf&eacute; &amp; th&eacute;</p>'))
        self.assertEqual(result['text'], 'café & thé')


class ImageTests(SimpleTestCase):
    def test_missing_alt_is_flagged_and_declared_decorative_is_not(self):
        result = extract_seo_signals(page(body='''
            <img src="/a.jpg">
            <img src="/b.jpg" alt="">
            <img src="/c.jpg" alt="   ">
            <img src="/d.jpg" alt="Toiture refaite a neuf">
            <img src="/e.jpg" role="presentation">
            <img src="/f.jpg" aria-hidden="true">
        '''))
        self.assertEqual(
            [img['src'] for img in result['images_missing_alt']],
            ['/a.jpg', '/c.jpg', '/e.jpg', '/f.jpg'],
        )
        self.assertTrue(result['images'][1]['decorative'])
        self.assertFalse(result['images'][3]['decorative'])

    def test_src_is_resolved_and_dimensions_kept(self):
        result = extract_seo_signals(
            page(body='<img src="img/toit.jpg" alt="Toit" width="800" height=600>'),
            base_url='https://ex.ca/fr/services/',
        )
        image = result['images'][0]
        self.assertEqual(image['src'], 'https://ex.ca/fr/services/img/toit.jpg')
        self.assertEqual((image['width'], image['height']), ('800', '600'))

    def test_detects_each_lazy_loading_mechanism(self):
        result = extract_seo_signals(page(body='''
            <img src="/1.jpg" alt="a" loading="lazy">
            <img src="/ph.gif" alt="b" data-perfmatters-src="/2.jpg">
            <img src="/ph.gif" alt="c" class="lazyload-eio">
            <img src="/ph.gif" alt="d" data-lazy-src="/4.jpg">
            <img src="/5.jpg" alt="e">
        '''))
        self.assertEqual(
            [img['lazy_method'] for img in result['images']],
            ['native', 'perfmatters', 'ewww', 'js-generic', 'none'],
        )


class LinkTests(SimpleTestCase):
    def test_splits_internal_from_external_ignoring_the_www_prefix(self):
        result = extract_seo_signals(
            page(body='''
                <a href="/services">Services</a>
                <a href="https://www.ex.ca/blogue">Blogue</a>
                <a href="https://ex.ca/contact">Contact</a>
                <a href="https://rbq.gouv.qc.ca/" rel="NOFOLLOW noopener">RBQ</a>
            '''),
            base_url='https://www.ex.ca/',
        )
        self.assertEqual(
            [link['href'] for link in result['links']['internal']],
            ['https://www.ex.ca/services', 'https://www.ex.ca/blogue', 'https://ex.ca/contact'],
        )
        external = result['links']['external']
        self.assertEqual([link['href'] for link in external], ['https://rbq.gouv.qc.ca/'])
        self.assertEqual(external[0]['rel'], ['nofollow', 'noopener'])

    def test_drops_non_navigational_hrefs(self):
        result = extract_seo_signals(
            page(body='''
                <a href="mailto:info@ex.ca">Courriel</a>
                <a href="tel:+15145551234">Appelez</a>
                <a href="#contenu">Aller au contenu</a>
                <a href="javascript:void(0)">Menu</a>
                <a>Sans href</a>
                <a href="/vrai">Vrai lien</a>
            '''),
            base_url='https://ex.ca/',
        )
        self.assertEqual(len(result['links']['external']), 0)
        self.assertEqual([link['href'] for link in result['links']['internal']],
                         ['https://ex.ca/vrai'])

    def test_link_text_is_captured_through_nested_markup(self):
        result = extract_seo_signals(
            page(body='<a href="/toiture"><span>Refection</span> de <b>toiture</b></a>'),
            base_url='https://ex.ca/',
        )
        self.assertEqual(result['links']['internal'][0]['text'], 'Refection de toiture')

    def test_a_subdomain_is_external(self):
        result = extract_seo_signals(
            page(body='<a href="https://blog.ex.ca/article">Blogue</a>'),
            base_url='https://ex.ca/',
        )
        self.assertEqual(len(result['links']['external']), 1)
        self.assertEqual(result['links']['internal'], [])

    def test_an_unparseable_href_is_dropped_not_raised(self):
        result = extract_seo_signals(
            page(body='<a href="http://[::1/">Casse</a><a href="/bon">Bon</a>'),
            base_url='https://ex.ca/',
        )
        self.assertEqual([link['href'] for link in result['links']['internal']],
                         ['https://ex.ca/bon'])
        self.assertEqual(result['links']['external'], [])

    def test_without_a_base_url_hosts_decide(self):
        result = extract_seo_signals(page(body='''
            <a href="/interne">Interne</a>
            <a href="https://autre.ca/x">Externe</a>
            <a href="//cdn.autre.ca/y">Protocole relatif</a>
        '''))
        self.assertEqual([link['href'] for link in result['links']['internal']], ['/interne'])
        self.assertEqual(len(result['links']['external']), 2)


class JsonLdTests(SimpleTestCase):
    def test_flattens_a_graph_container(self):
        """Yoast and RankMath ship one script holding a dozen entities."""
        result = extract_seo_signals(page(head='''
            <script type="application/ld+json">
            {"@context":"https://schema.org","@graph":[
                {"@type":"LocalBusiness","name":"Toiture Tremblay"},
                {"@type":"WebSite","name":"toituretremblay.ca"}
            ]}
            </script>
        '''))
        self.assertEqual(result['schema_types'], ['LocalBusiness', 'WebSite'])
        self.assertEqual(result['schema'][0]['name'], 'Toiture Tremblay')

    def test_graph_children_inherit_the_container_context(self):
        result = extract_seo_signals(page(head='''
            <script type="application/ld+json">
            {"@context":"https://schema.org","@graph":[{"@type":"Article","headline":"Toit"}]}
            </script>
        '''))
        self.assertEqual(result['schema'][0]['@context'], 'https://schema.org')

    def test_accepts_a_top_level_list_and_a_bare_object(self):
        result = extract_seo_signals(page(head='''
            <script type="application/ld+json">
            [{"@type":"FAQPage"},{"@type":"BreadcrumbList"}]
            </script>
            <script type="application/ld+json">{"@type":"Service"}</script>
        '''))
        self.assertEqual(result['schema_types'], ['FAQPage', 'BreadcrumbList', 'Service'])

    def test_type_arrays_are_expanded(self):
        result = extract_seo_signals(page(head='''
            <script type="application/ld+json">
            {"@type":["LocalBusiness","Plumber"],"name":"X"}
            </script>
        '''))
        self.assertEqual(result['schema_types'], ['LocalBusiness', 'Plumber'])

    def test_broken_json_is_skipped_without_killing_the_parse(self):
        result = extract_seo_signals(page(
            head='<script type="application/ld+json">{ceci n\'est pas du json}</script>',
            body='<h1>Toujours la</h1>',
        ))
        self.assertEqual(result['schema'], [])
        self.assertEqual(result['h1'], ['Toujours la'])

    def test_reads_a_cdata_wrapped_and_escaped_payload(self):
        result = extract_seo_signals(page(head='''
            <script type="application/ld+json; charset=utf-8">
            //<![CDATA[
            {&quot;@type&quot;:&quot;Organization&quot;,&quot;name&quot;:&quot;Gridar&quot;}
            //]]>
            </script>
        '''))
        self.assertEqual(result['schema_types'], ['Organization'])

    def test_plain_scripts_are_not_read_as_schema(self):
        result = extract_seo_signals(page(head='<script>{"@type":"Fake"}</script>'))
        self.assertEqual(result['schema'], [])


class MalformedHtmlTests(SimpleTestCase):
    def test_unclosed_and_stray_tags_do_not_lose_signals(self):
        html = (
            '<html lang=fr><head><title>Titre sans fermeture'
            '<body><h1>Titre principal<p>Du texte</span></div>'
            '<h2>Deuxieme</h2>'
        )
        result = extract_seo_signals(html)
        self.assertEqual(result['title'], 'Titre sans fermeture')
        self.assertEqual(result['h1'], ['Titre principal Du texte'])
        self.assertEqual(result['h2'], ['Deuxieme'])
        self.assertEqual(result['lang'], 'fr')

    def test_unclosed_head_does_not_blank_the_word_count(self):
        """Head content is invisible, so a head left open would hide the body."""
        result = extract_seo_signals(
            '<html><head><meta name="robots" content="noindex">'
            '<body><p>Quatre mots visibles ici.</p></body></html>'
        )
        self.assertEqual(result['meta_robots'], 'noindex')
        self.assertEqual(result['word_count'], 4)

    def test_an_svg_title_is_not_the_page_title(self):
        result = extract_seo_signals(page(
            head='<title>Le vrai titre</title>',
            body='<svg><title>icone de menu</title></svg>',
        ))
        self.assertEqual(result['title'], 'Le vrai titre')

    def test_svg_title_alone_is_still_not_taken(self):
        result = extract_seo_signals(page(body='<svg><title>icone</title></svg>'))
        self.assertIsNone(result['title'])

    def test_a_heading_closes_the_unclosed_heading_above_it(self):
        result = extract_seo_signals(page(body='<h1>Premier<h2>Second</h2>'))
        self.assertEqual(result['h1'], ['Premier'])
        self.assertEqual(result['h2'], ['Second'])

    def test_garbage_input_still_returns_a_dict(self):
        for value in ('<<<>>>', '<a href=', '<' * 500 + 'x', '\x00\x01 binaire'):
            result = extract_seo_signals(value, base_url='https://ex.ca/')
            self.assertIsInstance(result, dict)
            self.assertIn('word_count', result)

    def test_uppercase_tags_and_attributes(self):
        result = extract_seo_signals(
            '<HTML LANG="FR-CA"><HEAD><TITLE>Majuscules</TITLE>'
            '<META NAME="Description" CONTENT="Oui"></HEAD>'
            '<BODY><H1>Un</H1><IMG SRC="/a.png"></BODY></HTML>'
        )
        self.assertEqual(result['title'], 'Majuscules')
        self.assertEqual(result['meta_description'], 'Oui')
        self.assertEqual(result['h1'], ['Un'])
        self.assertEqual(len(result['images_missing_alt']), 1)

    def test_empty_input_returns_the_full_skeleton(self):
        for value in ('', None):
            result = extract_seo_signals(value)
            self.assertIsNone(result['title'])
            self.assertEqual(result['h1'], [])
            self.assertEqual(result['word_count'], 0)
            self.assertEqual(result['links'], {'internal': [], 'external': []})
            self.assertEqual(result['schema'], [])
            self.assertEqual(result['suspicious_headings'], {'h1': [], 'h2': [], 'h3': []})

    def test_comments_and_conditional_markup_are_not_content(self):
        result = extract_seo_signals(page(body='<!-- un commentaire cache --><p>Visible.</p>'))
        self.assertEqual(result['text'], 'Visible.')


class RealisticPageTests(SimpleTestCase):
    """One WordPress-shaped page, to check the pieces hold together."""

    HTML = f'''<!DOCTYPE html>
<html lang="fr-CA"><head>
<title>Toiture Tremblay | Couvreur a Levis</title>
<meta name="description" content="Refection de toiture a Levis depuis 1998.">
<meta name="robots" content="index, follow, max-image-preview:large">
<link rel="canonical" href="https://toituretremblay.ca/">
<link rel="alternate" hreflang="fr-ca" href="https://toituretremblay.ca/">
<link rel="alternate" hreflang="en-ca" href="https://toituretremblay.ca/en/">
<meta property="og:title" content="Couvreur a Levis">
<meta name="twitter:card" content="summary">
<script type="application/ld+json">{{"@context":"https://schema.org","@graph":[
{{"@type":"RoofingContractor","name":"Toiture Tremblay","areaServed":"Levis"}},
{{"@type":"WebPage","name":"Accueil"}}]}}</script>
</head><body>
<header class="site-header"><nav><a href="/">Accueil</a><a href="/contact">Contact</a></nav></header>
<main>
  <header class="hero"><h1>Couvreur a <span>Levis</span></h1>
  <p>Nous refaisons votre toiture, l'hiver comme l'ete.</p></header>
  <h2>1{NBSP}200 $</h2>
  <h2>Nos services de couvreur</h2>
  <img src="/img/toit.jpg" alt="Toiture refaite" loading="lazy">
  <img src="data:image/gif;base64,R0lGOD" data-lazy-src="/img/equipe.jpg">
  <p>Estimation gratuite. <a href="https://rbq.gouv.qc.ca/" rel="nofollow">Licence RBQ</a>
  ou <a href="/soumission">demandez une soumission</a>.</p>
</main>
<footer><p>Tous droits reserves</p></footer>
</body></html>'''

    def setUp(self):
        self.result = extract_seo_signals(self.HTML, base_url='https://toituretremblay.ca/')

    def test_head_signals(self):
        self.assertEqual(self.result['title'], 'Toiture Tremblay | Couvreur a Levis')
        self.assertEqual(self.result['lang'], 'fr-CA')
        self.assertEqual(self.result['canonical'], 'https://toituretremblay.ca/')
        self.assertEqual(len(self.result['hreflang']), 2)
        self.assertEqual(self.result['open_graph']['og:title'], 'Couvreur a Levis')
        self.assertEqual(self.result['twitter_card']['twitter:card'], 'summary')

    def test_schema_is_flat(self):
        self.assertEqual(self.result['schema_types'], ['RoofingContractor', 'WebPage'])

    def test_hero_h1_survives_and_the_counter_is_flagged(self):
        self.assertEqual(self.result['h1'], ['Couvreur a Levis'])
        self.assertEqual(self.result['suspicious_headings']['h2'], [f'1{NBSP}200 $'])

    def test_images_and_links(self):
        self.assertEqual(
            [img['lazy_method'] for img in self.result['images']], ['native', 'js-generic'],
        )
        self.assertEqual(len(self.result['images_missing_alt']), 1)
        self.assertEqual(
            [link['href'] for link in self.result['links']['internal']],
            ['https://toituretremblay.ca/', 'https://toituretremblay.ca/contact',
             'https://toituretremblay.ca/soumission'],
        )
        self.assertEqual(len(self.result['links']['external']), 1)

    def test_word_count_covers_the_hero_but_not_the_chrome(self):
        text = self.result['text']
        self.assertIn("l'hiver comme l'ete", text)
        self.assertNotIn('Tous droits reserves', text)
        self.assertNotIn('Accueil', text)
        self.assertEqual(self.result['word_count'], count_words(text))
        self.assertGreater(self.result['word_count'], 20)

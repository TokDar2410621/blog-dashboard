"""Tests for sitemap discovery and parsing.

Everything runs offline. `parse_sitemap` is pure, and every discovery test
patches `sites_mgmt.sitemap_discovery.safe_get`, so no socket is opened and the
SSRF guard stays the only way out of the module.

Run all:
    python manage.py test sites_mgmt.tests_sitemap_discovery
"""
import gzip
from unittest.mock import patch

from django.test import SimpleTestCase

from .sitemap_discovery import (
    COMMON_PATHS, MAX_BYTES, MAX_URLS, discover_sitemaps, parse_sitemap,
)
from .url_safety import URLSafetyError

NS = 'http://www.sitemaps.org/schemas/sitemap/0.9'
XHTML = 'http://www.w3.org/1999/xhtml'


def urlset(body: str, namespace: str = NS) -> str:
    return (
        f'<?xml version="1.0" encoding="UTF-8"?>'
        f'<urlset xmlns="{namespace}" xmlns:xhtml="{XHTML}" '
        f'xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">'
        f'{body}</urlset>'
    )


def locs(*urls: str) -> str:
    return ''.join(f'<url><loc>{u}</loc></url>' for u in urls)


class FakeResponse:
    """Minimal requests.Response stand-in for the streaming read path."""

    def __init__(self, status=200, body=b'', content_type='application/xml', url=''):
        self.status_code = status
        self.headers = {'Content-Type': content_type}
        self.url = url
        self._body = body
        self.closed = False

    def iter_content(self, chunk_size=65536):
        for i in range(0, len(self._body), chunk_size):
            yield self._body[i:i + chunk_size]

    def close(self):
        self.closed = True


def routed_get(routes: dict, default_status=404):
    """Build a safe_get double serving `routes`, 404 for anything else."""
    calls = []

    def _get(url, **kwargs):
        calls.append(url)
        if url in routes:
            value = routes[url]
            if isinstance(value, Exception):
                raise value
            body, status, ctype = value
            return FakeResponse(status, body, ctype, url)
        return FakeResponse(default_status, b'', 'text/html', url)

    _get.calls = calls
    return _get


# --------------------------------------------------------------------------
# parse_sitemap
# --------------------------------------------------------------------------

class ParseUrlsetTests(SimpleTestCase):
    def test_reads_loc_and_metadata(self):
        xml = urlset(
            '<url><loc>https://gridar.app/blogue/seo-local</loc>'
            '<lastmod>2026-08-01</lastmod><changefreq>weekly</changefreq>'
            '<priority>0.8</priority></url>'
            '<url><loc>https://gridar.app/tarifs</loc>'
            '<lastmod>2026-08-12T09:30:00-04:00</lastmod></url>'
        )
        result = parse_sitemap(xml, site_host='gridar.app')
        self.assertIsNone(result['error'])
        self.assertEqual(result['kind'], 'urlset')
        self.assertEqual(result['url_count'], 2)
        self.assertEqual(result['urls'][0]['loc'], 'https://gridar.app/blogue/seo-local')
        self.assertEqual(result['urls'][0]['changefreq'], 'weekly')
        self.assertEqual(result['urls'][0]['priority'], '0.8')
        self.assertTrue(result['latest_lastmod'].startswith('2026-08-12'))

    def test_ignores_image_locs(self):
        """<image:loc> is a grandchild; counting it inflates the page total."""
        xml = urlset(
            '<url><loc>https://gridar.app/a</loc>'
            '<image:image><image:loc>https://cdn.gridar.app/a.jpg</image:loc></image:image>'
            '<image:image><image:loc>https://cdn.gridar.app/b.jpg</image:loc></image:image>'
            '</url>'
        )
        result = parse_sitemap(xml, site_host='gridar.app')
        self.assertEqual(result['url_count'], 1)
        self.assertEqual(result['urls'][0]['images'], 2)

    def test_collects_hreflang_alternates(self):
        xml = urlset(
            '<url><loc>https://exemple.qc.ca/fr/services</loc>'
            f'<xhtml:link rel="alternate" hreflang="fr-CA" href="https://exemple.qc.ca/fr/services"/>'
            f'<xhtml:link rel="alternate" hreflang="en-CA" href="https://exemple.qc.ca/en/services"/>'
            '</url>'
        )
        result = parse_sitemap(xml, site_host='exemple.qc.ca')
        self.assertEqual(result['languages'], ['en-ca', 'fr-ca'])
        self.assertEqual(len(result['urls'][0]['alternates']), 2)

    def test_flags_unreadable_lastmod(self):
        xml = urlset(
            '<url><loc>https://gridar.app/a</loc><lastmod>hier</lastmod></url>'
        )
        result = parse_sitemap(xml, site_host='gridar.app')
        self.assertIn('invalid_lastmod', [w['code'] for w in result['warnings']])
        self.assertIsNone(result['latest_lastmod'])

    def test_warns_on_foreign_namespace(self):
        result = parse_sitemap(urlset(locs('https://gridar.app/a'), namespace='http://example.com/ns'))
        self.assertIn('unexpected_namespace', [w['code'] for w in result['warnings']])

    def test_warns_on_empty_sitemap(self):
        result = parse_sitemap(urlset(''))
        self.assertEqual(result['url_count'], 0)
        self.assertIn('empty_sitemap', [w['code'] for w in result['warnings']])


class ParseIndexTests(SimpleTestCase):
    INDEX = (
        f'<?xml version="1.0"?><sitemapindex xmlns="{NS}">'
        '<sitemap><loc>https://gridar.app/sitemap-1.xml</loc>'
        '<lastmod>2026-07-01</lastmod></sitemap>'
        '<sitemap><loc>https://gridar.app/sitemap-2.xml</loc></sitemap>'
        '</sitemapindex>'
    )

    def test_reads_children(self):
        result = parse_sitemap(self.INDEX, site_host='gridar.app')
        self.assertEqual(result['kind'], 'sitemapindex')
        self.assertEqual(result['sitemap_count'], 2)
        self.assertEqual(result['url_count'], 0)
        self.assertEqual(result['sitemaps'][0]['lastmod'], '2026-07-01')

    def test_flags_cross_host_child(self):
        xml = (
            f'<sitemapindex xmlns="{NS}">'
            '<sitemap><loc>https://spam-casino.ru/sitemap.xml</loc></sitemap>'
            '</sitemapindex>'
        )
        result = parse_sitemap(xml, site_host='gridar.app')
        self.assertEqual(result['cross_host'], ['spam-casino.ru'])


class CrossHostTests(SimpleTestCase):
    def test_flags_foreign_domain(self):
        xml = urlset(locs(
            'https://gridar.app/a',
            'https://pilules-pas-cheres.xyz/spam',
        ))
        result = parse_sitemap(xml, site_host='gridar.app')
        self.assertEqual(result['cross_host'], ['pilules-pas-cheres.xyz'])
        self.assertTrue(result['urls'][1]['cross_host'])
        codes = [w['code'] for w in result['warnings']]
        self.assertIn('cross_host_entries', codes)

    def test_subdomain_is_not_cross_host(self):
        """A CDN or shop subdomain is legitimate and must not read as a hijack."""
        xml = urlset(locs('https://boutique.gridar.app/produit', 'https://gridar.app/a'))
        result = parse_sitemap(xml, site_host='www.gridar.app')
        self.assertEqual(result['cross_host'], [])

    def test_quebec_provincial_suffix_is_not_the_registrable_domain(self):
        """montreal.qc.ca and laval.qc.ca are different owners, not one domain."""
        xml = urlset(locs('https://laval.qc.ca/spam'))
        result = parse_sitemap(xml, site_host='ville.montreal.qc.ca')
        self.assertEqual(result['cross_host'], ['laval.qc.ca'])

        same_owner = urlset(locs('https://loisirs.ville.montreal.qc.ca/a'))
        self.assertEqual(parse_sitemap(same_owner, site_host='ville.montreal.qc.ca')['cross_host'], [])

    def test_no_site_host_disables_the_check(self):
        xml = urlset(locs('https://autre-domaine.com/a'))
        self.assertEqual(parse_sitemap(xml)['cross_host'], [])


class ParseLimitsTests(SimpleTestCase):
    def test_protocol_ceilings(self):
        self.assertEqual(MAX_URLS, 50000)
        self.assertEqual(MAX_BYTES, 50 * 1024 * 1024)

    def test_truncates_past_the_url_cap(self):
        xml = urlset(locs(*[f'https://gridar.app/p{n}' for n in range(5)]))
        result = parse_sitemap(xml, site_host='gridar.app', max_urls=3)
        self.assertTrue(result['truncated'])
        self.assertEqual(result['url_count'], 3)
        self.assertIn('url_cap', [w['code'] for w in result['warnings']])

    def test_refuses_oversized_document(self):
        result = parse_sitemap(urlset(locs('https://gridar.app/a')), max_bytes=32)
        self.assertEqual(result['error_code'], 'too_large')
        self.assertEqual(result['urls'], [])

    def test_refuses_gzip_bomb_over_the_cap(self):
        payload = gzip.compress(b'x' * 5000)
        result = parse_sitemap(payload, max_bytes=1000)
        self.assertEqual(result['error_code'], 'too_large')


class ParseRobustnessTests(SimpleTestCase):
    def test_refuses_doctype(self):
        xxe = (
            '<?xml version="1.0"?>'
            '<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>'
            f'<urlset xmlns="{NS}"><url><loc>&xxe;</loc></url></urlset>'
        )
        result = parse_sitemap(xxe, site_host='gridar.app')
        self.assertEqual(result['error_code'], 'doctype_refused')

    def test_invalid_xml_returns_an_error_not_an_exception(self):
        result = parse_sitemap('<urlset><url><loc>https://a.com/</loc>')
        self.assertEqual(result['error_code'], 'invalid_xml')

    def test_unsupported_root(self):
        result = parse_sitemap('<html><body>404</body></html>')
        self.assertEqual(result['error_code'], 'unsupported_root')

    def test_empty_input(self):
        self.assertEqual(parse_sitemap('')['error_code'], 'empty')

    def test_latin1_declaration_on_a_decoded_string(self):
        """A str carrying an encoding declaration breaks ElementTree outright.

        French copy is the reason this matters: re-encoding to UTF-8 while the
        declaration still says latin-1 would mangle every accent.
        """
        xml = (
            '<?xml version="1.0" encoding="ISO-8859-1"?>'
            f'<urlset xmlns="{NS}"><url>'
            '<loc>https://exemple.qc.ca/reparation-de-toiture-a-quebec</loc>'
            '<changefreq>mensuel repare</changefreq></url></urlset>'
        )
        result = parse_sitemap(xml, site_host='exemple.qc.ca')
        self.assertIsNone(result['error'])
        self.assertEqual(result['url_count'], 1)
        self.assertEqual(result['urls'][0]['changefreq'], 'mensuel repare')

    def test_gzipped_bytes(self):
        payload = gzip.compress(urlset(locs('https://gridar.app/a')).encode('utf-8'))
        result = parse_sitemap(payload, site_host='gridar.app')
        self.assertEqual(result['url_count'], 1)

    def test_text_sitemap(self):
        body = 'https://gridar.app/a\n# commentaire\nhttps://gridar.app/b\n'
        result = parse_sitemap(body, site_host='gridar.app')
        self.assertEqual(result['kind'], 'text')
        self.assertEqual(result['url_count'], 2)

    def test_text_sitemap_rejects_garbage(self):
        result = parse_sitemap('bonjour tout le monde')
        self.assertEqual(result['error_code'], 'invalid_text')

    def test_rss_feed_is_accepted(self):
        rss = (
            '<rss version="2.0"><channel><title>Blogue</title>'
            '<item><link>https://gridar.app/blogue/a</link>'
            '<pubDate>2026-08-01T00:00:00+00:00</pubDate></item>'
            '</channel></rss>'
        )
        result = parse_sitemap(rss, site_host='gridar.app')
        self.assertEqual(result['kind'], 'rss')
        self.assertEqual(result['url_count'], 1)

    def test_entry_without_loc_is_reported(self):
        xml = urlset('<url><lastmod>2026-01-01</lastmod></url>')
        result = parse_sitemap(xml)
        self.assertIn('entries_without_loc', [w['code'] for w in result['warnings']])


# --------------------------------------------------------------------------
# discover_sitemaps
# --------------------------------------------------------------------------

class DiscoveryTests(SimpleTestCase):
    def test_reads_robots_declaration(self):
        robots = b'User-agent: *\nAllow: /\nSitemap: https://gridar.app/sitemap-custom.xml  # principal\n'
        body = urlset(locs('https://gridar.app/a', 'https://gridar.app/b')).encode('utf-8')
        fake = routed_get({
            'https://gridar.app/robots.txt': (robots, 200, 'text/plain'),
            'https://gridar.app/sitemap-custom.xml': (body, 200, 'application/xml'),
        })
        with patch('sites_mgmt.sitemap_discovery.safe_get', side_effect=fake):
            result = discover_sitemaps('gridar.app')

        self.assertIsNone(result['error'])
        self.assertEqual(result['target'], 'https://gridar.app')
        self.assertEqual(
            [d['url'] for d in result['declared']],
            ['https://gridar.app/sitemap-custom.xml'],
        )
        self.assertEqual(len(result['found']), 1)
        found = result['found'][0]
        self.assertEqual(found['source'], 'robots.txt')
        self.assertEqual(found['kind'], 'urlset')
        self.assertEqual(found['url_count'], 2)
        self.assertEqual(result['total_urls'], 2)

    def test_falls_back_to_common_paths(self):
        body = urlset(locs('https://exemple.qc.ca/a')).encode('utf-8')
        fake = routed_get({
            'https://exemple.qc.ca/wp-sitemap.xml': (body, 200, 'application/xml'),
        })
        with patch('sites_mgmt.sitemap_discovery.safe_get', side_effect=fake):
            result = discover_sitemaps('https://exemple.qc.ca/blogue/article')

        self.assertEqual([f['url'] for f in result['found']],
                         ['https://exemple.qc.ca/wp-sitemap.xml'])
        self.assertEqual(result['found'][0]['source'], 'common_path')
        for path in COMMON_PATHS:
            self.assertIn(f'https://exemple.qc.ca{path}', fake.calls)

    def test_resolves_relative_robots_declaration(self):
        robots = b'Sitemap: /sitemap_fr.xml\n'
        body = urlset(locs('https://exemple.qc.ca/fr/a')).encode('utf-8')
        fake = routed_get({
            'https://exemple.qc.ca/robots.txt': (robots, 200, 'text/plain'),
            'https://exemple.qc.ca/sitemap_fr.xml': (body, 200, 'application/xml'),
        })
        with patch('sites_mgmt.sitemap_discovery.safe_get', side_effect=fake):
            result = discover_sitemaps('exemple.qc.ca')

        self.assertEqual([d['url'] for d in result['declared']],
                         ['https://exemple.qc.ca/sitemap_fr.xml'])
        self.assertEqual(len(result['found']), 1)

    def test_flags_cross_host_declaration(self):
        robots = b'Sitemap: https://cdn-spam.ru/sitemap.xml\n'
        fake = routed_get({'https://gridar.app/robots.txt': (robots, 200, 'text/plain')})
        with patch('sites_mgmt.sitemap_discovery.safe_get', side_effect=fake):
            result = discover_sitemaps('gridar.app')

        self.assertTrue(result['declared'][0]['cross_host'])
        self.assertIn('cross_host_declared', [w['code'] for w in result['warnings']])

    def test_reports_cross_host_entries_inside_a_sitemap(self):
        body = urlset(locs(
            'https://gridar.app/a', 'https://achat-viagra.top/spam',
        )).encode('utf-8')
        fake = routed_get({'https://gridar.app/sitemap.xml': (body, 200, 'application/xml')})
        with patch('sites_mgmt.sitemap_discovery.safe_get', side_effect=fake):
            result = discover_sitemaps('gridar.app')

        self.assertEqual(result['found'][0]['cross_host_entries'], ['achat-viagra.top'])
        self.assertIn('cross_host_entries', [w['code'] for w in result['warnings']])

    def test_index_children_are_listed_not_walked(self):
        index = (
            f'<sitemapindex xmlns="{NS}">'
            '<sitemap><loc>https://gridar.app/sitemap-posts.xml</loc></sitemap>'
            '</sitemapindex>'
        ).encode('utf-8')
        fake = routed_get({'https://gridar.app/sitemap.xml': (index, 200, 'application/xml')})
        with patch('sites_mgmt.sitemap_discovery.safe_get', side_effect=fake):
            result = discover_sitemaps('gridar.app')

        found = result['found'][0]
        self.assertEqual(found['kind'], 'sitemapindex')
        self.assertEqual(found['child_sitemaps'], ['https://gridar.app/sitemap-posts.xml'])
        self.assertNotIn('https://gridar.app/sitemap-posts.xml', fake.calls)

    def test_refuses_internal_target_before_any_fetch(self):
        for target in ('localhost:8000', 'http://127.0.0.1/', 'http://169.254.169.254/',
                       'http://10.0.0.5/', 'file:///etc/passwd'):
            with patch('sites_mgmt.sitemap_discovery.safe_get') as fake:
                result = discover_sitemaps(target)
            self.assertIsNotNone(result['error'], target)
            self.assertEqual(result['found'], [])
            fake.assert_not_called()

    def test_url_safety_error_is_reported_not_raised(self):
        """A redirect into private space raises from safe_get mid-walk."""
        fake = routed_get({
            'https://gridar.app/robots.txt': URLSafetyError('redirect to 10.0.0.1'),
            'https://gridar.app/sitemap.xml': URLSafetyError('redirect to 10.0.0.1'),
        })
        with patch('sites_mgmt.sitemap_discovery.safe_get', side_effect=fake):
            result = discover_sitemaps('gridar.app')

        self.assertIsNone(result['error'])
        self.assertIn('robots_unreachable', [w['code'] for w in result['warnings']])
        self.assertEqual(result['checked'][0]['error_code'], 'url_refused')

    def test_no_sitemap_anywhere(self):
        fake = routed_get({})
        with patch('sites_mgmt.sitemap_discovery.safe_get', side_effect=fake):
            result = discover_sitemaps('gridar.app')

        self.assertEqual(result['found'], [])
        self.assertIn('no_sitemap', [w['code'] for w in result['warnings']])
        self.assertTrue(all(entry['status_code'] == 404 for entry in result['checked']))

    def test_oversized_sitemap_is_a_finding(self):
        fake = routed_get({
            'https://gridar.app/sitemap.xml': (b'<' + b'x' * 4096, 200, 'application/xml'),
        })
        with patch('sites_mgmt.sitemap_discovery.safe_get', side_effect=fake):
            result = discover_sitemaps('gridar.app', max_urls=10)
        entry = result['checked'][0]
        self.assertFalse(entry['valid'])
        self.assertEqual(entry['error_code'], 'invalid_xml')

    def test_query_string_is_redacted_from_the_report(self):
        robots = b'Sitemap: https://gridar.app/sitemap.xml?token=SECRET\n'
        fake = routed_get({'https://gridar.app/robots.txt': (robots, 200, 'text/plain')})
        with patch('sites_mgmt.sitemap_discovery.safe_get', side_effect=fake):
            result = discover_sitemaps('gridar.app')

        declared = result['declared'][0]
        self.assertNotIn('SECRET', declared['url'])
        self.assertTrue(declared['query_redacted'])

    def test_time_budget_stops_the_probe(self):
        fake = routed_get({})
        with patch('sites_mgmt.sitemap_discovery.safe_get', side_effect=fake):
            result = discover_sitemaps('gridar.app', time_budget=-1.0)

        self.assertIn('time_budget', [w['code'] for w in result['warnings']])
        self.assertEqual(result['checked'], [])
        self.assertEqual(fake.calls, ['https://gridar.app/robots.txt'])

    def test_every_fetch_goes_through_safe_get(self):
        """requests must never be called directly from this module."""
        robots = b'Sitemap: https://gridar.app/sitemap.xml\n'
        fake = routed_get({
            'https://gridar.app/robots.txt': (robots, 200, 'text/plain'),
            'https://gridar.app/sitemap.xml': (
                urlset(locs('https://gridar.app/a')).encode('utf-8'), 200, 'application/xml',
            ),
        })
        with patch('sites_mgmt.sitemap_discovery.safe_get', side_effect=fake):
            with patch('sites_mgmt.sitemap_discovery.requests.request') as raw:
                discover_sitemaps('gridar.app')
        raw.assert_not_called()
        self.assertEqual(fake.calls[0], 'https://gridar.app/robots.txt')

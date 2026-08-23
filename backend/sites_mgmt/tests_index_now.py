"""Tests : soumission IndexNow (nom du fichier de cle + host apex/www).

Contexte : constate le 2026-08-23 sur gridar.app. Deux defauts empiles faisaient
echouer 100 % des soumissions, en silence, y compris les pings automatiques a la
livraison d'un article ou d'une landing :

1. le fichier de propriete etait servi sous le nom `indexnow-key.txt`, alors que
   les moteurs exigent qu'il porte le nom de la cle (`<cle>.txt`). Reponse : 403
   `UserForbiddedToAccessSite`, quoi que declare `keyLocation` ;
2. `site.domain` stocke le domaine de marque (`gridar.app`) tandis que le site
   sert ses pages sur `www.gridar.app`. Le filtre de host jetait donc les URLs
   du sitemap avant l'envoi (`skipped_wrong_host: 7`, `submitted: 0`).

Hermetique : `requests.post` est simule, le site est un objet factice avec une
cle deja posee (donc aucune ecriture DB, aucun reseau).
Run: python manage.py test sites_mgmt.tests_index_now
"""
from unittest.mock import patch

from django.test import SimpleTestCase

from .index_now import key_file_info, key_location, submit_urls

KEY = '5ef772c2bccb3182e1383c0196b419de'


class FakeSite:
    """Site minimal : cle deja posee, donc get_or_create_key ne touche pas la DB."""

    def __init__(self, domain='gridar.app', public_blog_domain=''):
        self.id = 6
        self.pk = 6
        self.domain = domain
        self.public_blog_domain = public_blog_domain
        self.indexnow_key = KEY


class FakeResponse:
    def __init__(self, status_code=200):
        self.status_code = status_code


def _submit(site, urls, status_code=200):
    """Appelle submit_urls sans reseau et rend (resultat, payload envoye)."""
    with patch('sites_mgmt.index_now.requests.post') as post:
        post.return_value = FakeResponse(status_code)
        result = submit_urls(site, urls)
        payload = post.call_args.kwargs['json'] if post.call_args else None
    return result, payload


class KeyFileNameTests(SimpleTestCase):
    """Le fichier de propriete doit porter le nom de la cle."""

    def test_key_location_is_named_after_the_key(self):
        self.assertEqual(
            key_location(FakeSite(), KEY),
            f'https://gridar.app/{KEY}.txt',
        )

    def test_key_location_accepts_a_host_override(self):
        self.assertEqual(
            key_location(FakeSite(), KEY, 'www.gridar.app'),
            f'https://www.gridar.app/{KEY}.txt',
        )

    def test_client_instructions_name_the_file_after_the_key(self):
        info = key_file_info(FakeSite())
        self.assertEqual(info['key_file_url'], f'https://gridar.app/{KEY}.txt')
        self.assertIn(f'{KEY}.txt', info['instructions'])
        self.assertNotIn('indexnow-key.txt', info['instructions'])


class HostVariantTests(SimpleTestCase):
    """apex et www sont le meme site ; le host annonce suit les URLs."""

    def test_www_urls_are_submitted_for_an_apex_domain_site(self):
        result, payload = _submit(FakeSite(), [
            'https://www.gridar.app/tools',
            'https://www.gridar.app/tools/ai-citation-checker',
        ])
        self.assertTrue(result['ok'])
        self.assertEqual(result['submitted'], 2)
        self.assertEqual(result['skipped_wrong_host'], 0)
        self.assertEqual(result['host'], 'www.gridar.app')
        self.assertEqual(payload['host'], 'www.gridar.app')
        self.assertEqual(payload['keyLocation'],
                         f'https://www.gridar.app/{KEY}.txt')

    def test_apex_urls_still_work_for_an_apex_domain_site(self):
        result, payload = _submit(FakeSite(), ['https://gridar.app/tools'])
        self.assertTrue(result['ok'])
        self.assertEqual(payload['host'], 'gridar.app')
        self.assertEqual(payload['keyLocation'], f'https://gridar.app/{KEY}.txt')

    def test_apex_urls_work_for_a_www_domain_site(self):
        """Le miroir : domaine stocke avec www, URLs sur l'apex."""
        result, payload = _submit(FakeSite(domain='www.gridar.app'),
                                  ['https://gridar.app/tools'])
        self.assertTrue(result['ok'])
        self.assertEqual(payload['host'], 'gridar.app')

    def test_a_foreign_host_is_still_rejected(self):
        result, _ = _submit(FakeSite(), [
            'https://www.gridar.app/tools',
            'https://exemple.com/tools',
            'https://notgridar.app/tools',
        ])
        self.assertEqual(result['submitted'], 1)
        self.assertEqual(result['skipped_wrong_host'], 2)

    def test_a_lookalike_suffix_is_not_the_same_site(self):
        """wwwgridar.app et evil-gridar.app ne doivent pas passer le filtre."""
        result, _ = _submit(FakeSite(), [
            'https://wwwgridar.app/tools',
            'https://evil-gridar.app/tools',
        ])
        self.assertFalse(result['ok'])
        self.assertEqual(result['submitted'], 0)
        self.assertEqual(result['skipped_wrong_host'], 2)

    def test_a_mixed_batch_lands_on_one_host(self):
        """IndexNow refuse une liste multi-host : la minorite est rebasee."""
        result, payload = _submit(FakeSite(), [
            'https://www.gridar.app/tools',
            'https://www.gridar.app/tools/competitor-gap',
            'https://gridar.app/tools/keyword-difficulty',
        ])
        self.assertEqual(payload['host'], 'www.gridar.app')
        self.assertEqual(result['normalized_to_host'], 1)
        self.assertEqual(sorted(payload['urlList']), [
            'https://www.gridar.app/tools',
            'https://www.gridar.app/tools/competitor-gap',
            'https://www.gridar.app/tools/keyword-difficulty',
        ])
        for url in payload['urlList']:
            self.assertTrue(url.startswith('https://www.gridar.app/'))

    def test_the_public_blog_domain_still_wins_over_the_brand_domain(self):
        site = FakeSite(domain='restaurant.ca',
                        public_blog_domain='blog.restaurant.ca')
        result, payload = _submit(site, ['https://blog.restaurant.ca/poutine'])
        self.assertTrue(result['ok'])
        self.assertEqual(payload['host'], 'blog.restaurant.ca')
        # Le domaine de marque n'est pas le host du blog : il reste hors lot.
        rejected, _ = _submit(site, ['https://restaurant.ca/poutine'])
        self.assertFalse(rejected['ok'])
        self.assertEqual(rejected['skipped_wrong_host'], 1)


class FailureReportingTests(SimpleTestCase):
    """Un echec doit se dire, pas se deviner."""

    def test_no_matching_url_reports_the_site_host(self):
        result, payload = _submit(FakeSite(), ['https://exemple.com/a'])
        self.assertIsNone(payload)  # rien n'est parti
        self.assertFalse(result['ok'])
        self.assertEqual(result['submitted'], 0)
        self.assertIn('gridar.app', result['error'])

    def test_a_403_is_surfaced_with_its_reason_and_key_location(self):
        result, _ = _submit(FakeSite(), ['https://www.gridar.app/tools'],
                            status_code=403)
        self.assertFalse(result['ok'])
        self.assertEqual(result['status'], 403)
        self.assertIn('<cle>.txt', result['reason'])
        self.assertEqual(result['key_location'],
                         f'https://www.gridar.app/{KEY}.txt')

    def test_duplicates_are_sent_once(self):
        result, payload = _submit(FakeSite(), [
            'https://www.gridar.app/tools',
            'https://www.gridar.app/tools',
            '  ',
        ])
        self.assertEqual(result['submitted'], 1)
        self.assertEqual(len(payload['urlList']), 1)

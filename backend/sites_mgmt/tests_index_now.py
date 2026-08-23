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
from urllib.parse import urlparse, urlunparse

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
    def __init__(self, status_code=200, url=''):
        self.status_code = status_code
        self.url = url


def _rehost(url: str, host: str) -> str:
    return urlunparse(urlparse(url)._replace(netloc=host))


def _submit(site, urls, status_code=200, key_host=None, key_status=200,
            key_raises=False):
    """Appelle submit_urls sans reseau et rend (resultat, payload envoye).

    `key_host` : host qui sert reellement le fichier de cle une fois les
    redirections suivies (None = pas de redirection). `key_status` / `key_raises`
    simulent un fichier de cle injoignable.
    """
    def _get(url, **_kwargs):
        if key_raises:
            raise OSError('connexion refusee')
        return FakeResponse(key_status,
                            url if key_host is None else _rehost(url, key_host))

    with patch('sites_mgmt.index_now.requests.post') as post, \
            patch('sites_mgmt.index_now.requests.get', side_effect=_get):
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


class KeyHostResolutionTests(SimpleTestCase):
    """Le host annonce doit etre celui qui SERT le fichier, pas celui qui redirige.

    C'est le cas du ping automatique a la livraison : l'URL est construite depuis
    site.domain, donc sur l'apex, dont le fichier de cle n'est qu'une 308.
    """

    def test_the_announced_host_follows_the_key_file_redirect(self):
        result, payload = _submit(FakeSite(), ['https://gridar.app/mon-article'],
                                  key_host='www.gridar.app')
        self.assertEqual(payload['host'], 'www.gridar.app')
        self.assertEqual(payload['keyLocation'],
                         f'https://www.gridar.app/{KEY}.txt')
        self.assertEqual(payload['urlList'],
                         ['https://www.gridar.app/mon-article'])
        self.assertEqual(result['normalized_to_host'], 1)

    def test_no_redirect_leaves_the_host_alone(self):
        result, payload = _submit(FakeSite(), ['https://www.gridar.app/tools'])
        self.assertEqual(payload['host'], 'www.gridar.app')
        self.assertNotIn('normalized_to_host', result)

    def test_a_redirect_to_another_site_is_ignored(self):
        """Un fichier de cle qui atterrit ailleurs ne doit pas detourner le lot."""
        _, payload = _submit(FakeSite(), ['https://gridar.app/tools'],
                             key_host='cdn-parking.example')
        self.assertEqual(payload['host'], 'gridar.app')

    def test_an_unreachable_key_file_keeps_the_given_host(self):
        """Echec ouvert : sans reponse, on soumet quand meme sur le host des URLs."""
        _, payload = _submit(FakeSite(), ['https://gridar.app/tools'],
                             key_raises=True)
        self.assertEqual(payload['host'], 'gridar.app')

    def test_a_404_key_file_keeps_the_given_host(self):
        _, payload = _submit(FakeSite(), ['https://gridar.app/tools'],
                             key_status=404, key_host='www.gridar.app')
        self.assertEqual(payload['host'], 'gridar.app')


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

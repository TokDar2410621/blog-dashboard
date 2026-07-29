"""Tests for index_coverage: the silent-GSC-failure bug and its fix.

Bug (vecu 2026-07-29): GSC connectee, mais une panne transitoire faisait
retomber l'audit sur `site:` en silence -> un site sain (141 pages indexees
selon GSC) rapporte comme 13% indexe, presente comme un fait. Le fix : l'echec
GSC est TOUJOURS expose (gsc_error + note ATTENTION), et le budget
d'inspection part sur les pages douteuses d'abord.

GSC is mocked at the `_build_gsc_service` boundary; serper and sitemap at
module boundary. No network. Run:
    python manage.py test sites_mgmt.tests_index_coverage
"""
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from .models import Site
from . import index_coverage as ic
from . import proof_loop

User = get_user_model()


def _make_site(user, gsc=True, suffix='cov'):
    site = Site.objects.create(
        owner=user,
        name=f'Site {suffix}',
        domain=f'{suffix}.example.com',
        public_blog_domain=f'{suffix}.example.com',
    )
    if gsc:
        site.gsc_property_url = f'https://{suffix}.example.com'  # sans slash, comme en prod
        site.gsc_refresh_token = 'fake-refresh-token'
        site.save()
    return site


def _fake_inspect_service(indexed_urls=(), fail_all=False, fail_exc=None):
    """MagicMock du service GSC : urlInspection + sites().list."""
    svc = MagicMock()
    svc.sites.return_value.list.return_value.execute.return_value = {
        'siteEntry': [{'siteUrl': 'sc-domain:cov.example.com',
                       'permissionLevel': 'siteOwner'}],
    }

    def inspect(body):
        resp = MagicMock()
        if fail_all:
            resp.execute.side_effect = fail_exc or RuntimeError(
                'HttpError 403 "You do not own this site"')
        else:
            url = body['inspectionUrl']
            verdict = 'PASS' if url in indexed_urls else 'FAIL'
            resp.execute.return_value = {
                'inspectionResult': {'indexStatusResult': {
                    'verdict': verdict,
                    'coverageState': 'Submitted and indexed' if verdict == 'PASS' else 'Discovered - currently not indexed',
                }},
            }
        return resp

    svc.urlInspection.return_value.index.return_value.inspect.side_effect = inspect
    return svc


EXPECTED = [
    'https://cov.example.com/a',
    'https://cov.example.com/b',
    'https://cov.example.com/c',
]


class IndexCoverageGscFailureTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='u', password='x')
        self.site = _make_site(self.user)

    def _run(self, service=None, serper=None, max_inspect=25):
        with patch.object(ic, '_fetch_sitemap_urls', return_value=list(EXPECTED)), \
             patch.object(ic, '_serper_site_urls', return_value=serper or set()), \
             patch.object(proof_loop, '_build_gsc_service', return_value=service):
            return ic.index_coverage(self.site, max_inspect=max_inspect)

    def test_echec_gsc_total_expose_jamais_silencieux(self):
        """GSC connectee + toutes les inspections 403 -> gsc_error rempli,
        note ATTENTION, confidence approximatif. Plus jamais un faux 13% muet."""
        svc = _fake_inspect_service(fail_all=True)
        result = self._run(service=svc)
        self.assertFalse(result['gsc_used'])
        self.assertTrue(result['gsc_connected'])
        self.assertIn('echec', result['gsc_error'])
        self.assertIn('403', result['gsc_error'])
        self.assertIn('ATTENTION', result['note'])
        self.assertIn('SOUS-ESTIMENT', result['note'])
        self.assertEqual(result['confidence'], 'approximatif')

    def test_service_indisponible_expose(self):
        """Client OAuth absent cote serveur -> raison explicite, pas un silence."""
        result = self._run(service=None)
        self.assertFalse(result['gsc_used'])
        self.assertIn('OAuth', result['gsc_error'])
        self.assertIn('ATTENTION', result['note'])

    def test_gsc_non_connectee_note_normale(self):
        """Sans GSC : approximatif assume, pas d'ATTENTION (rien n'a echoue)."""
        site2 = _make_site(self.user, gsc=False, suffix='nogsc')
        with patch.object(ic, '_fetch_sitemap_urls', return_value=list(EXPECTED)), \
             patch.object(ic, '_serper_site_urls', return_value=set()):
            result = ic.index_coverage(site2)
        self.assertFalse(result['gsc_used'])
        self.assertFalse(result['gsc_connected'])
        self.assertIn('non connectee', result['gsc_error'])
        self.assertNotIn('ATTENTION', result['note'])
        self.assertIn('APPROXIMATIF', result['note'])

    def test_chemin_nominal_gsc_autoritatif(self):
        """GSC repond : statut autoritatif, gsc_error None, confidence gsc."""
        svc = _fake_inspect_service(indexed_urls=set(EXPECTED))
        result = self._run(service=svc)
        self.assertTrue(result['gsc_used'])
        self.assertIsNone(result['gsc_error'])
        self.assertEqual(result['confidence'], 'autoritatif')
        self.assertEqual(result['indexed_count'], 3)
        self.assertEqual(result['coverage_pct'], 100)

    def test_budget_inspection_sur_les_douteuses_d_abord(self):
        """Les pages que site: n'a PAS vues sont inspectees en premier : le
        budget cap part sur les douteuses, pas sur les confirmees."""
        svc = _fake_inspect_service(indexed_urls=set(EXPECTED))
        inspected_urls = []
        original = svc.urlInspection.return_value.index.return_value.inspect.side_effect

        def recording_inspect(body):
            inspected_urls.append(body['inspectionUrl'])
            return original(body)

        svc.urlInspection.return_value.index.return_value.inspect.side_effect = recording_inspect
        # serper a vu /a -> /b et /c sont douteuses et doivent passer d'abord.
        serper_seen = {ic._norm_url('https://cov.example.com/a')}
        result = self._run(service=svc, serper=serper_seen, max_inspect=2)
        self.assertEqual(len(inspected_urls), 2)
        self.assertNotIn('https://cov.example.com/a', inspected_urls)
        self.assertIn('https://cov.example.com/b', inspected_urls)
        self.assertIn('https://cov.example.com/c', inspected_urls)
        # /a reste indexee (source serper), pas de budget gaspille dessus.
        row_a = next(r for r in result['pages'] if r['url'].endswith('/a'))
        self.assertTrue(row_a['indexed'])
        self.assertEqual(row_a['source'], 'serper')

    def test_echec_partiel_expose_confiance_partielle(self):
        """1 inspection sur N echoue : on garde ce qu'on a (gsc_used True) MAIS
        la degradation est exposee : gsc_error 'partielle', confidence 'partiel',
        inspection_failures > 0. Plus jamais 24 echecs sous etiquette autoritative."""
        svc = _fake_inspect_service(indexed_urls={'https://cov.example.com/a'})
        calls = {'n': 0}
        original = svc.urlInspection.return_value.index.return_value.inspect.side_effect

        def flaky_inspect(body):
            calls['n'] += 1
            if calls['n'] == 2:
                resp = MagicMock()
                resp.execute.side_effect = RuntimeError('boom transitoire')
                return resp
            return original(body)

        svc.urlInspection.return_value.index.return_value.inspect.side_effect = flaky_inspect
        result = self._run(service=svc)
        self.assertTrue(result['gsc_used'])
        self.assertIn('partielle', result['gsc_error'])
        self.assertEqual(result['confidence'], 'partiel')
        self.assertEqual(result['inspection_failures'], 1)
        self.assertIn('en echec', result['note'])

    def test_max_inspect_zero_pas_de_fausse_alerte(self):
        """max_inspect=0 avec GSC connectee : rien n'a echoue, donc PAS de note
        ATTENTION mensongere (avant : 'l'inspection a echoue (raison inconnue)'
        + 'Relance l'audit' qui se reproduisait a l'infini)."""
        svc = _fake_inspect_service(indexed_urls=set(EXPECTED))
        result = self._run(service=svc, max_inspect=0)
        self.assertFalse(result['gsc_used'])
        self.assertIsNone(result['gsc_error'])
        self.assertNotIn('ATTENTION', result['note'])
        self.assertNotIn('echoue', result['note'])
        self.assertIn('aucune URL', result['note'])

    def test_ensemble_vide_pas_de_fausse_alerte(self):
        """Site frais : sitemap vide et rien de publie -> aucune inspection
        tentee, note neutre, pas d'alarme."""
        svc = _fake_inspect_service()
        with patch.object(ic, '_fetch_sitemap_urls', return_value=[]), \
             patch.object(ic, '_gridar_known_urls', return_value=[]), \
             patch.object(ic, '_serper_site_urls', return_value=set()), \
             patch.object(proof_loop, '_build_gsc_service', return_value=svc):
            result = ic.index_coverage(self.site)
        self.assertFalse(result['gsc_used'])
        self.assertIsNone(result['gsc_error'])
        self.assertNotIn('ATTENTION', result['note'])


class ResolveGscPropertyRetryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='u2', password='x')
        self.site = _make_site(self.user, suffix='retry')

    def test_retry_liste_apres_echec_transitoire(self):
        """sites().list echoue une fois puis repond : la propriete se resout
        quand meme (avant le fix : repli silencieux sur l'URL stockee -> 403)."""
        svc = MagicMock()
        ok = {'siteEntry': [{'siteUrl': 'sc-domain:retry.example.com',
                             'permissionLevel': 'siteOwner'}]}
        svc.sites.return_value.list.return_value.execute.side_effect = [
            RuntimeError('reseau transitoire'), ok,
        ]
        resolved = proof_loop.resolve_gsc_property(svc, self.site)
        self.assertEqual(resolved, 'sc-domain:retry.example.com')

    def test_double_echec_normalise_et_memo_echec_separe(self):
        """Deux echecs : repli sur l'URL stockee NORMALISEE (slash final, format
        valide de propriete URL-prefix), memoize dans le sentinel d'ECHEC (pas
        le memo de succes) : les resolves suivants de la meme instance ne
        refrappent pas l'API (30 posts = 2 appels reseau, pas 60)."""
        svc = MagicMock()
        execute = svc.sites.return_value.list.return_value.execute
        execute.side_effect = RuntimeError('down')
        resolved = proof_loop.resolve_gsc_property(svc, self.site)
        self.assertEqual(resolved, 'https://retry.example.com/')
        self.assertIsNone(getattr(self.site, '_gsc_resolved_property', None))
        self.assertEqual(self.site._gsc_resolve_failed_fallback, 'https://retry.example.com/')
        self.assertEqual(execute.call_count, 2)  # 1 + retry
        # 2e resolve : sert le sentinel, zero nouvel appel reseau.
        resolved2 = proof_loop.resolve_gsc_property(svc, self.site)
        self.assertEqual(resolved2, 'https://retry.example.com/')
        self.assertEqual(execute.call_count, 2)

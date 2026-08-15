"""Tests : la propriete GSC se remplit toute seule (bug du 2026-07-29).

Bug : le callback OAuth sauvait gsc_refresh_token mais JAMAIS gsc_property_url,
et _build_gsc_service exigeait les deux. Resultat : qrstudio.agency etait
"connecte" (jeton present) mais toutes les fonctions GSC repondaient
silencieusement "non connectee" : audit d'index, proof loop, decay, positions.

Run: python manage.py test sites_mgmt.tests_gsc_property
"""
import sys
import types
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from .models import Site
from . import proof_loop
from .views import GSCQueriesView

User = get_user_model()


def _listing(*site_urls, level='siteOwner'):
    return {'siteEntry': [{'siteUrl': u, 'permissionLevel': level} for u in site_urls]}


def _svc(listing):
    svc = MagicMock()
    svc.sites.return_value.list.return_value.execute.return_value = listing
    return svc


class BuildServiceSansProprieteTests(TestCase):
    """Le client s'authentifie avec le SEUL jeton : la propriete n'est pas
    requise pour construire le client (c'est un argument par appel)."""

    def setUp(self):
        self.user = User.objects.create_user(username='u', password='x')
        self.site = Site.objects.create(owner=self.user, name='QR', domain='qrstudio.agency')
        self.site.gsc_refresh_token = 'fake-token'   # jeton OUI, propriete VIDE
        self.site.gsc_property_url = ''
        self.site.save()

    def test_jeton_seul_franchit_la_porte(self):
        """Propriete VIDE + jeton present : la fonction ne sort plus tot, elle
        va chercher les credentials (preuve que la porte ne bloque plus). On
        n'exerce pas la construction du client Google : la lib n'est pas
        installee en dev, comme dans les autres tests du repo."""
        with patch.object(proof_loop, '_gsc_client_credentials', return_value=None) as creds:
            proof_loop._build_gsc_service(self.site)
        creds.assert_called_once()

    def test_sans_jeton_sort_avant_les_credentials(self):
        self.site.gsc_refresh_token = ''
        self.site.save()
        with patch.object(proof_loop, '_gsc_client_credentials', return_value=None) as creds:
            self.assertIsNone(proof_loop._build_gsc_service(self.site))
        creds.assert_not_called()


class AutoGuerisonProprieteTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='u2', password='x')
        self.site = Site.objects.create(owner=self.user, name='QR', domain='qrstudio.agency')
        self.site.gsc_refresh_token = 'fake-token'
        self.site.gsc_property_url = ''
        self.site.save()

    def test_propriete_domaine_decouverte_et_persistee_en_forme_url(self):
        """Propriete DOMAINE possedee (sc-domain:) : on resout vers sc-domain
        pour les appels API, mais on PERSISTE la forme URL (le champ est un
        URLField : 'sc-domain:...' exploserait au prochain save)."""
        svc = _svc(_listing('sc-domain:qrstudio.agency'))
        resolved = proof_loop.resolve_gsc_property(svc, self.site)
        self.assertEqual(resolved, 'sc-domain:qrstudio.agency')
        self.site.refresh_from_db()
        self.assertEqual(self.site.gsc_property_url, 'https://qrstudio.agency/')
        # le champ persiste doit rester valide pour le validateur URLField
        self.site.full_clean(exclude=['owner'])

    def test_propriete_prefixe_url_decouverte_et_persistee(self):
        svc = _svc(_listing('https://qrstudio.agency/'))
        resolved = proof_loop.resolve_gsc_property(svc, self.site)
        self.assertEqual(resolved, 'https://qrstudio.agency/')
        self.site.refresh_from_db()
        self.assertEqual(self.site.gsc_property_url, 'https://qrstudio.agency/')

    def test_aucune_propriete_correspondante_ne_persiste_rien(self):
        """Le jeton ne possede aucune propriete de ce domaine : on ne fabrique
        pas une valeur fausse, le champ reste vide (le callback avertit)."""
        svc = _svc(_listing('sc-domain:autre-domaine.com'))
        proof_loop.resolve_gsc_property(svc, self.site)
        self.site.refresh_from_db()
        self.assertEqual(self.site.gsc_property_url, '')

    def test_propriete_deja_renseignee_jamais_ecrasee(self):
        """Une propriete stockee valide n'est pas touchee (pas d'ecrasement)."""
        self.site.gsc_property_url = 'https://qrstudio.agency/'
        self.site.save()
        svc = _svc(_listing('https://qrstudio.agency/'))
        proof_loop.resolve_gsc_property(svc, self.site)
        self.site.refresh_from_db()
        self.assertEqual(self.site.gsc_property_url, 'https://qrstudio.agency/')

    def test_echec_de_persistance_ne_casse_pas_la_resolution(self):
        """Si le save echoue, la resolution rend quand meme la bonne propriete."""
        svc = _svc(_listing('sc-domain:qrstudio.agency'))
        with patch.object(Site, 'save', side_effect=RuntimeError('db en lecture seule')):
            resolved = proof_loop.resolve_gsc_property(svc, self.site)
        self.assertEqual(resolved, 'sc-domain:qrstudio.agency')


def _fake_googleapiclient_modules(listing, query_rows=()):
    """Injecte un module `googleapiclient` factice dans sys.modules.

    La lib google-api-python-client n'est PAS installee en dev (seul
    google-auth l'est) : les imports locaux de GSCQueriesView.get()
    ('from googleapiclient.discovery import build' etc.) levent sinon un
    ImportError et la vue repond 503 avant meme d'atteindre le code teste.
    Renvoie (dict pour patch.dict(sys.modules, ...), le MagicMock service).
    """
    service = MagicMock()
    service.sites.return_value.list.return_value.execute.return_value = listing
    service.searchanalytics.return_value.query.return_value.execute.return_value = {
        'rows': list(query_rows),
    }

    discovery_mod = types.ModuleType('googleapiclient.discovery')
    discovery_mod.build = MagicMock(return_value=service)

    class _FakeHttpError(Exception):
        pass

    errors_mod = types.ModuleType('googleapiclient.errors')
    errors_mod.HttpError = _FakeHttpError

    root_mod = types.ModuleType('googleapiclient')
    root_mod.discovery = discovery_mod
    root_mod.errors = errors_mod

    modules = {
        'googleapiclient': root_mod,
        'googleapiclient.discovery': discovery_mod,
        'googleapiclient.errors': errors_mod,
    }
    return modules, service


class GSCQueriesViewProprieteVideTests(TestCase):
    """Regression : GSCQueriesView (backend/sites_mgmt/views.py) refusait avec
    un HTTP 400 'No GSC property URL configured for this site.' des qu'un
    site avait un jeton GSC valide mais gsc_property_url vide. C'est la 3e
    porte de la meme famille que _build_gsc_service (proof_loop.py, corrigee
    en PR #5) et _gsc_inspect_urls (index_coverage.py, corrigee en PR #6) : le
    callback OAuth sauve le jeton mais jamais la propriete, et
    resolve_gsc_property sait desormais la decouvrir ET la persister. Cette
    3e porte, oubliee, laissait un site pourtant connecte (qrstudio.agency,
    site 5) recevoir un 400 trompeur sur /gsc/queries/."""

    def setUp(self):
        self.user = User.objects.create_user(username='u3', password='x')
        self.site = Site.objects.create(
            owner=self.user, name='QR', domain='qrstudio.agency',
        )
        self.site.gsc_refresh_token = 'fake-token'   # jeton OUI, propriete VIDE
        self.site.gsc_property_url = ''
        self.site.save()
        self.factory = APIRequestFactory()

    def _get(self, slug='mon-article'):
        request = self.factory.get(f'/api/sites/{self.site.id}/gsc/queries/?slug={slug}')
        force_authenticate(request, user=self.user)
        return GSCQueriesView.as_view()(request, site_id=self.site.id)

    def test_jeton_seul_ne_recoit_plus_400(self):
        """Propriete VIDE + jeton present : plus de 400. resolve_gsc_property
        decouvre la propriete du domaine, la persiste, et la requete GSC part
        avec l'URL de page construite sur la propriete resolue."""
        modules, _svc = _fake_googleapiclient_modules(
            listing={'siteEntry': [{'siteUrl': 'https://qrstudio.agency/',
                                     'permissionLevel': 'siteOwner'}]},
            query_rows=[{'keys': ['seo local'], 'clicks': 3, 'impressions': 50,
                         'ctr': 0.06, 'position': 4.2}],
        )
        with patch.dict(sys.modules, modules):
            response = self._get()
        self.assertEqual(response.status_code, 200, response.data)
        self.site.refresh_from_db()
        self.assertEqual(
            self.site.gsc_property_url, 'https://qrstudio.agency/',
            "la propriete decouverte doit avoir ete persistee (auto-guerison)")
        # Attendu change avec 5f32c6c : l'URL de page est desormais construite
        # comme celle du sitemap public (_public_article_url), donc
        # /blog/<slug> sans slash final, au lieu de propriete + slug + '/'.
        # L'ancienne forme n'existait sur aucun site et ne remontait jamais la
        # moindre ligne GSC, ce qui est le bug que ce correctif ferme.
        self.assertEqual(
            response.data['page_url'], 'https://qrstudio.agency/blog/mon-article')
        self.assertEqual(response.data['queries'][0]['query'], 'seo local')

    def test_aucune_propriete_correspondante_erreur_explicite(self):
        """Ni la propriete stockee (vide) ni aucune propriete du token ne
        correspondent, et le site n'a pas de domaine pour se rabattre :
        erreur EXPLICITE, plus le message trompeur d'avant qui laissait
        croire qu'il suffisait de remplir un champ."""
        self.site.domain = ''
        self.site.save()
        modules, _svc = _fake_googleapiclient_modules(
            listing={'siteEntry': [{'siteUrl': 'sc-domain:autre-domaine.com',
                                     'permissionLevel': 'siteOwner'}]},
        )
        with patch.dict(sys.modules, modules):
            response = self._get()
        self.assertEqual(response.status_code, 400)
        self.assertIn('Aucune propriete Search Console verifiee', response.data['error'])
        self.assertNotIn('No GSC property URL configured', response.data['error'])

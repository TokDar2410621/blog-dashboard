"""Tests : la propriete GSC se remplit toute seule (bug du 2026-07-29).

Bug : le callback OAuth sauvait gsc_refresh_token mais JAMAIS gsc_property_url,
et _build_gsc_service exigeait les deux. Resultat : qrstudio.agency etait
"connecte" (jeton present) mais toutes les fonctions GSC repondaient
silencieusement "non connectee" : audit d'index, proof loop, decay, positions.

Run: python manage.py test sites_mgmt.tests_gsc_property
"""
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from .models import Site
from . import proof_loop

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

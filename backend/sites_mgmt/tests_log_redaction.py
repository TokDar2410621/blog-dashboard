"""Tests : masquage des secrets dans les logs.

Le 2026-08-27, la cle `GEMINI_API_KEY` s'est retrouvee EN CLAIR dans les logs
Railway :

    requests.exceptions.HTTPError: 429 Client Error: Too Many Requests for
    url: https://...generateContent?key=<la cle en clair>

Trois maillons, aucun suspect isolement : cle dans l'URL, `raise_for_status()`
qui met l'URL complete dans le message d'exception, `logger.exception` qui
l'ecrit. Les cles sont passees en en-tetes (correctif a la source) ; ce
module est la ceinture pour le code futur, celui qui loggera une exception
sans se demander ce qu'elle contient.

Le test central est `test_le_traceback_de_l_incident_est_masque` : il rejoue
l'incident exact, avec un vrai `logger.exception`, et verifie que la cle
n'atteint pas la sortie.

Run: python manage.py test sites_mgmt.tests_log_redaction
"""
import logging
import os
from importlib import reload
from unittest.mock import patch

from django.test import SimpleTestCase

from config import log_redaction
from config.log_redaction import MASQUE, FormateurMasque, masquer


class MotifsTests(SimpleTestCase):
    """Passe par motif : un secret annonce par son nom, meme inconnu de ce
    processus."""

    def test_une_cle_en_parametre_d_url_est_masquee(self):
        url = 'https://api.exemple.com/v1/truc?key=AIzaSyDONCECIESTUNECLE123'
        sortie = masquer(url)
        self.assertNotIn('AIzaSyDONCECIESTUNECLE123', sortie)
        self.assertIn(MASQUE, sortie)
        self.assertIn('https://api.exemple.com/v1/truc', sortie)   # reste lisible

    def test_les_variantes_de_nom_sont_couvertes(self):
        for nom in ('api_key', 'apikey', 'api-key', 'access_token',
                    'auth_token', 'token', 'secret', 'password'):
            sortie = masquer(f'truc {nom}=VALEURSECRETE12345 suite')
            self.assertNotIn('VALEURSECRETE12345', sortie, nom)

    def test_un_en_tete_bearer_est_masque(self):
        sortie = masquer("headers={'Authorization': 'Bearer sk-proj-ABCDEF123456'}")
        self.assertNotIn('sk-proj-ABCDEF123456', sortie)
        self.assertIn('Bearer', sortie)

    def test_le_deux_points_est_reconnu_comme_le_egal(self):
        """Un repr() de dict ecrit `'x-goog-api-key': 'AIza...'`."""
        sortie = masquer("{'x-goog-api-key': 'AIzaSyUNEAUTRECLE9876'}")
        self.assertNotIn('AIzaSyUNEAUTRECLE9876', sortie)

    def test_une_valeur_trop_courte_n_est_pas_masquee(self):
        """Masquer `key=1` rendrait les logs illisibles sans rien proteger."""
        self.assertIn('key=abc', masquer('truc key=abc suite'))

    def test_le_reste_de_la_ligne_survit(self):
        sortie = masquer('429 Client Error for url: https://x.com/a?key=SECRET1234567')
        self.assertIn('429 Client Error', sortie)
        self.assertIn('https://x.com/a', sortie)


class ValeursEnvTests(SimpleTestCase):
    """Passe par valeur : le secret est masque meme sans prefixe
    reconnaissable, parce que sa valeur est connue du processus."""

    def _recharger_avec(self, env):
        with patch.dict(os.environ, env, clear=False):
            return reload(log_redaction)

    def test_une_valeur_d_env_est_masquee_sans_prefixe(self):
        mod = self._recharger_avec({'GEMINI_API_KEY': 'AIzaSyVALEURDENVIRONNEMENT'})
        try:
            sortie = mod.masquer('la valeur AIzaSyVALEURDENVIRONNEMENT apparait nue')
            self.assertNotIn('AIzaSyVALEURDENVIRONNEMENT', sortie)
        finally:
            reload(log_redaction)

    def test_une_variable_publique_n_est_pas_masquee(self):
        """Masquer une cle publiable ou une URL casserait le diagnostic sans
        rien proteger."""
        mod = self._recharger_avec({
            'STRIPE_PUBLISHABLE_KEY': 'pk_live_VALEURPUBLIQUE123',
            'DATABASE_URL': 'postgres://exemple.railway.internal/base',
        })
        try:
            self.assertIn('pk_live_VALEURPUBLIQUE123',
                          mod.masquer('cle publique pk_live_VALEURPUBLIQUE123'))
            self.assertIn('railway.internal',
                          mod.masquer('postgres://exemple.railway.internal/base'))
        finally:
            reload(log_redaction)

    def test_une_valeur_courte_n_est_pas_prise_pour_un_secret(self):
        mod = self._recharger_avec({'DEBUG_TOKEN': 'court'})
        try:
            self.assertIn('court', mod.masquer('valeur court ici'))
        finally:
            reload(log_redaction)


class FormateurTests(SimpleTestCase):

    def _rendre(self, faire):
        """Fait tourner un vrai logger et rend la ligne ecrite."""
        import io
        flux = io.StringIO()
        handler = logging.StreamHandler(flux)
        handler.setFormatter(FormateurMasque('[{levelname}] {name} {message}',
                                             style='{'))
        journal = logging.getLogger('test_masquage')
        journal.handlers = [handler]
        journal.propagate = False
        journal.setLevel(logging.DEBUG)
        faire(journal)
        return flux.getvalue()

    def test_le_traceback_de_l_incident_est_masque(self):
        """L'incident exact du 2026-08-27, rejoue de bout en bout.

        C'est le traceback qui portait la cle : un filtre travaillant sur
        `record.msg` seul serait passe a cote, parce que le traceback est
        rendu par le FORMATEUR depuis `exc_info`.
        """
        import requests

        cle = 'AIzaSyLACLEQUIAFUITEDANSLESLOGS'
        url = f'https://generativelanguage.googleapis.com/v1beta/models/x:generateContent?key={cle}'

        def faire(journal):
            try:
                raise requests.exceptions.HTTPError(
                    f'429 Client Error: Too Many Requests for url: {url}')
            except Exception:
                journal.exception('CanIRank failed')

        sortie = self._rendre(faire)
        self.assertIn('CanIRank failed', sortie)
        self.assertIn('429 Client Error', sortie)     # le diagnostic survit
        self.assertNotIn(cle, sortie)                  # la cle, non

    def test_les_arguments_du_message_sont_masques(self):
        def faire(journal):
            journal.error('appel echoue sur %s', 'https://x.com/a?key=SECRETABCDEFGH')
        sortie = self._rendre(faire)
        self.assertNotIn('SECRETABCDEFGH', sortie)
        self.assertIn('appel echoue', sortie)

    def test_une_ligne_normale_traverse_intacte(self):
        def faire(journal):
            journal.info('PSI indisponible pour https://exemple.ca: ReadTimeout')
        sortie = self._rendre(faire)
        self.assertIn('PSI indisponible pour https://exemple.ca', sortie)
        self.assertNotIn(MASQUE, sortie)


class RobustesseTests(SimpleTestCase):

    def test_un_objet_non_texte_ne_fait_pas_planter(self):
        for valeur in (None, 42, {'a': 1}, [1, 2]):
            self.assertIsInstance(masquer(valeur), str)

    def test_un_echec_interne_ne_laisse_pas_passer_le_contenu(self):
        """Le logging ne doit pas tomber, mais il ne doit pas non plus laisser
        filer la ligne telle quelle en cas d'imprevu."""
        with patch('config.log_redaction._MOTIF_PARAMETRE') as motif:
            motif.sub.side_effect = RuntimeError('boom')
            sortie = masquer('une ligne avec key=SECRETABCDEFGH')
        self.assertNotIn('SECRETABCDEFGH', sortie)

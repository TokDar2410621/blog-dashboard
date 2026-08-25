"""Tests : un corps de reponse illisible ne doit pas passer pour une page vide.

Decouvert en prod le 2026-08-25. `www.berkshirehathaway.com` repond
`content-encoding: br` meme quand notre `Accept-Encoding` ne demande que gzip
et deflate (comportement de certains WAF). Le paquet `brotli` n'etait pas
installe, donc `r.text` rendait du binaire :

    r.text[:60] -> '"\\x13\\x98\\x15\\x00A\\'\\x7f\\xaa\\xdf...'
    '<title' in r.text.lower() -> False

Le crawl ne voyait donc ni titre, ni H1, ni meta description, et ne signalait
aucune erreur. Le site ressortait de l'audit comme depourvu de toute balise,
un verdict catastrophique et faux, montre tel quel a un prospect. Le meme
corps binaire partait aussi dans les prompts LLM et dans l'extraction de
mots-cles.

Deux correctifs, testes ici :
  1. `brotli` est dans requirements.txt, donc `br` se decode reellement.
  2. `_encodage_indecodable` refuse franchement ce qui reste (zstd, etc.)
     plutot que de laisser passer du binaire.

Run: python manage.py test sites_mgmt.tests_encodage_crawl
"""
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from .views import _encodage_indecodable
from .views_tools import _crawl_homepage_light


def reponse(encodage=None, status=200, text='<html><title>Ok</title></html>'):
    m = MagicMock()
    m.status_code = status
    m.ok = status == 200
    m.text = text
    m.headers = {} if encodage is None else {'content-encoding': encodage}
    return m


class EncodageIndecodableTests(SimpleTestCase):

    def test_les_encodages_decodables_passent(self):
        for encodage in (None, '', 'identity', 'gzip', 'x-gzip', 'deflate', 'br'):
            self.assertIsNone(_encodage_indecodable(reponse(encodage)),
                              f'{encodage!r} devrait etre accepte')

    def test_brotli_est_accepte_car_le_paquet_est_installe(self):
        """Le cas exact de berkshirehathaway.com. Accepte parce que `brotli`
        figure desormais dans requirements.txt, donc urllib3 le decode."""
        self.assertIsNone(_encodage_indecodable(reponse('br')))

    def test_la_casse_et_les_espaces_ne_trompent_pas_le_controle(self):
        for encodage in ('GZIP', ' br ', 'Deflate'):
            self.assertIsNone(_encodage_indecodable(reponse(encodage)))

    def test_un_encodage_inconnu_est_refuse_franchement(self):
        erreur = _encodage_indecodable(reponse('zstd'))
        self.assertIsNotNone(erreur)
        self.assertIn('zstd', erreur)

    def test_un_en_tete_d_un_type_inattendu_se_lit_comme_absent(self):
        """On n'agit que sur un encodage POSITIVEMENT identifie comme inconnu.
        Bloquer un crawl parce qu'un en-tete a un type bizarre serait pire que
        le probleme qu'on corrige, et casserait tous les mocks de test qui ne
        posent pas d'en-tetes realistes."""
        bizarre = MagicMock()
        bizarre.headers = MagicMock()   # .get() rend un MagicMock, pas une str
        self.assertIsNone(_encodage_indecodable(bizarre))

    def test_le_crawl_leger_refuse_plutot_que_de_rendre_du_binaire(self):
        """Sans ce garde-fou, la fonction rendait title/h1/meta_description
        vides sans erreur, indiscernable d'une page reellement depourvue de
        balises."""
        with patch('requests.get', return_value=reponse('zstd', text='\x13\x98\x15\x00')):
            r = _crawl_homepage_light('https://exemple.ca')
        self.assertIn('error', r)
        self.assertIn('zstd', r['error'])
        self.assertNotIn('title', r)

    def test_le_crawl_leger_lit_normalement_une_page_gzip(self):
        html = '<html><head><title>Un titre</title></head><body><h1>Un H1</h1></body></html>'
        with patch('requests.get', return_value=reponse('gzip', text=html)):
            r = _crawl_homepage_light('https://exemple.ca')
        self.assertNotIn('error', r)
        self.assertEqual(r['title'], 'Un titre')

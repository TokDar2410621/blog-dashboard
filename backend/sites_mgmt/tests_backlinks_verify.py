"""Tests for backlink verification and report validation.

Everything runs offline. Every test that reaches the network patches
`sites_mgmt.backlinks_verify.safe_get`, so no socket is opened and the SSRF
guard stays the only way out of the module; one test asserts that a URL aimed
at a private address never reaches the fetch at all. `validate_report` is pure,
so it takes data and returns data with nothing to mock.

Run all:
    python manage.py test sites_mgmt.tests_backlinks_verify
"""
import threading
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import requests
from django.test import SimpleTestCase

from . import backlinks_verify as bv
from .backlinks_verify import (
    AGE_MAX_JOURS, LIBELLES_ETAT, SEVERITES, validate_report, verify_backlink,
    verify_batch,
)
from .url_safety import URLSafetyError

CIBLE = 'gridar.app'
SOURCE = 'https://blogue-plomberie.qc.ca/palmares-outils-seo/'


def page(corps: str, tete: str = '') -> str:
    return (
        '<!doctype html><html lang="fr-CA"><head><meta charset="utf-8">'
        f'<title>Palmarès des outils</title>{tete}</head>'
        f'<body>{corps}</body></html>'
    )


# Enough visible French text that no page below is mistaken for a JS shell.
REMPLISSAGE = (
    '<p>Nous avons testé douze outils de référencement pendant six mois sur '
    'des chantiers réels à Laval et à Trois-Rivières, en mesurant chaque fois '
    'le trafic organique avant et après. Le comparatif ci-dessous reprend les '
    'observations de terrain, les prix affichés en dollars canadiens et les '
    'limites que chaque plateforme impose aux petites entreprises du Québec. '
    'Nous avons aussi vérifié le service à la clientèle en français, un point '
    'que beaucoup de comparatifs anglophones passent sous silence.</p>'
) * 3


class FakeResponse:
    """Minimal requests.Response stand-in for the streaming read path."""

    def __init__(self, status=200, body='', content_type='text/html; charset=utf-8',
                 url=SOURCE):
        self.status_code = status
        self.headers = {'Content-Type': content_type}
        self.url = url
        self._body = body.encode('utf-8') if isinstance(body, str) else body
        self.closed = False

    def iter_content(self, chunk_size=65536):
        for i in range(0, len(self._body), chunk_size):
            yield self._body[i:i + chunk_size]

    def close(self):
        self.closed = True


def verifie(corps, cible=CIBLE, source=SOURCE, **kwargs):
    reponse = FakeResponse(body=page(corps), url=kwargs.pop('url_finale', source),
                           **kwargs)
    with patch('sites_mgmt.backlinks_verify.safe_get', return_value=reponse):
        return verify_backlink(source, cible)


class TrouverLeLien(SimpleTestCase):
    """The link is found, and described the way a client needs it described."""

    def test_lien_dans_le_contenu_confirme(self):
        r = verifie(
            f'<main>{REMPLISSAGE}<p>Voir <a href="https://gridar.app/blogue/">'
            'le meilleur outil SEO au Québec</a>.</p></main>'
        )
        self.assertEqual(r['etat'], 'confirme')
        self.assertIs(r['lien_present'], True)
        self.assertEqual(r['ancre'], 'le meilleur outil SEO au Québec')
        self.assertEqual(r['zone'], 'contenu')
        self.assertEqual(r['libelle_zone'], 'Contenu principal')
        self.assertEqual(r['nb_liens'], 1)
        self.assertIs(r['suivi'], True)
        self.assertIs(r['nofollow'], False)
        self.assertEqual(r['statut_http'], 200)
        self.assertIsNone(r['redirection'])
        self.assertEqual(r['libelle_etat'], LIBELLES_ETAT['confirme'])

    def test_date_de_verification_horodatee_en_utc(self):
        r = verifie(f'<main>{REMPLISSAGE}<a href="https://gridar.app/">Gridar</a></main>')
        moment = datetime.strptime(r['verifie_le'], '%Y-%m-%dT%H:%M:%SZ')
        moment = moment.replace(tzinfo=timezone.utc)
        ecart = abs((datetime.now(timezone.utc) - moment).total_seconds())
        self.assertLess(ecart, 120)

    def test_lien_en_pied_de_page(self):
        r = verifie(
            f'<main>{REMPLISSAGE}</main>'
            '<footer><a href="https://gridar.app/">Propulsé par Gridar</a></footer>'
        )
        self.assertEqual(r['etat'], 'confirme')
        self.assertEqual(r['zone'], 'pied_de_page')

    def test_pied_de_page_sans_balise_semantique(self):
        # The theme ships a div, which is what most of them still do.
        r = verifie(
            f'<main>{REMPLISSAGE}</main>'
            '<div id="site-footer"><a href="https://gridar.app/">Gridar</a></div>'
        )
        self.assertEqual(r['zone'], 'pied_de_page')

    def test_lien_dans_un_commentaire(self):
        r = verifie(
            f'<main>{REMPLISSAGE}'
            '<div id="comments"><p>Merci, on utilise '
            '<a href="https://gridar.app/">Gridar</a> aussi.</p></div></main>'
        )
        self.assertEqual(r['zone'], 'commentaire')

    def test_lien_dans_la_navigation(self):
        r = verifie(
            '<nav><a href="https://gridar.app/">Partenaire</a></nav>'
            f'<main>{REMPLISSAGE}</main>'
        )
        self.assertEqual(r['zone'], 'navigation')

    def test_entete_dans_article_reste_du_contenu(self):
        # An entry header is not site chrome. Same rule as html_parse, so the
        # two modules never disagree about the same page.
        r = verifie(
            '<main><article><header><h1>Palmarès</h1>'
            '<a href="https://gridar.app/">Gridar</a></header>'
            f'{REMPLISSAGE}</article></main>'
        )
        self.assertEqual(r['zone'], 'contenu')

    def test_rel_nofollow_sponsored_ugc(self):
        r = verifie(
            f'<main>{REMPLISSAGE}<a rel="nofollow sponsored" '
            'href="https://gridar.app/">Commandité</a></main>'
        )
        self.assertEqual(r['rel'], ['nofollow', 'sponsored'])
        self.assertIs(r['nofollow'], True)
        self.assertIs(r['sponsorise'], True)
        self.assertIs(r['ugc'], False)
        self.assertIs(r['suivi'], False)

    def test_sous_domaine_et_www_comptent(self):
        r = verifie(
            f'<main>{REMPLISSAGE}<a href="https://www.blogue.gridar.app/x">Gridar</a></main>'
        )
        self.assertEqual(r['etat'], 'confirme')
        self.assertEqual(r['liens'][0]['correspondance'], 'sous_domaine')

    def test_cible_donnee_en_url_complete(self):
        r = verifie(
            f'<main>{REMPLISSAGE}<a href="https://gridar.app/tarifs">Gridar</a></main>',
            cible='https://www.gridar.app/blogue/article',
        )
        self.assertEqual(r['etat'], 'confirme')
        self.assertEqual(r['domaine_cible'], 'gridar.app')

    def test_plusieurs_liens_le_contenu_represente_la_page(self):
        r = verifie(
            '<nav><a href="https://gridar.app/">menu</a></nav>'
            f'<main>{REMPLISSAGE}<a rel="nofollow" href="https://gridar.app/a">'
            'dans le texte</a></main>'
            '<footer><a href="https://gridar.app/b">pied</a></footer>'
        )
        self.assertEqual(r['nb_liens'], 3)
        self.assertEqual(r['zone'], 'contenu')
        self.assertEqual(r['ancre'], 'dans le texte')

    def test_ancre_nettoyee_et_entites_decodees(self):
        r = verifie(
            f'<main>{REMPLISSAGE}<a href="https://gridar.app/">  Outil\n  SEO '
            '&amp; <b>GEO</b>  </a></main>'
        )
        self.assertEqual(r['ancre'], 'Outil SEO & GEO')

    def test_charset_latin1_declare_donne_des_accents_lisibles(self):
        corps = ('<main>' + REMPLISSAGE +
                 '<a href="https://gridar.app/">référencement à Québec</a></main>')
        reponse = FakeResponse(
            body=page(corps).replace('<meta charset="utf-8">', '')
                            .encode('latin-1'),
            content_type='text/html; charset=ISO-8859-1',
        )
        with patch('sites_mgmt.backlinks_verify.safe_get', return_value=reponse):
            r = verify_backlink(SOURCE, CIBLE)
        self.assertEqual(r['ancre'], 'référencement à Québec')

    def test_href_sans_schema_et_schema_majuscule(self):
        r = verifie(
            f'<main>{REMPLISSAGE}<a href="//gridar.app/a">sans schéma</a>'
            '<a href="HTTPS://GRIDAR.APP/b">majuscules</a></main>'
        )
        self.assertEqual(r['nb_liens'], 2)
        self.assertEqual(r['liens'][0]['href'], 'https://gridar.app/a')

    def test_ancre_jamais_fermee(self):
        r = verifie(f'<main>{REMPLISSAGE}<a href="https://gridar.app/">Gridar')
        self.assertEqual(r['etat'], 'confirme')
        self.assertEqual(r['ancre'], 'Gridar')

    def test_contenu_imbrique_dans_un_pied_de_page_reste_du_pied_de_page(self):
        r = verifie(
            f'<main>{REMPLISSAGE}</main><footer><div class="entry-content">'
            '<a href="https://gridar.app/">Gridar</a></div></footer>'
        )
        self.assertEqual(r['zone'], 'pied_de_page')

    def test_base_href_sur_la_cible_rend_un_lien_relatif_valide(self):
        reponse = FakeResponse(body=page(
            f'<main>{REMPLISSAGE}<a href="/tarifs">nos tarifs</a></main>',
            tete='<base href="https://gridar.app/">',
        ))
        with patch('sites_mgmt.backlinks_verify.safe_get', return_value=reponse):
            r = verify_backlink(SOURCE, CIBLE)
        self.assertEqual(r['etat'], 'confirme')
        self.assertEqual(r['liens'][0]['href'], 'https://gridar.app/tarifs')


class NePasTrouverLeLien(SimpleTestCase):
    """Absence is only reported when the page really was read."""

    def test_page_lisible_sans_lien_est_une_perte(self):
        r = verifie(f'<main>{REMPLISSAGE}<a href="https://autre.ca/">Autre</a></main>')
        self.assertEqual(r['etat'], 'disparu')
        self.assertIs(r['lien_present'], False)
        self.assertEqual(r['nb_liens'], 0)

    def test_liens_relatifs_et_mailto_ignores(self):
        r = verifie(
            f'<main>{REMPLISSAGE}<a href="/gridar.app">interne</a>'
            '<a href="mailto:info@gridar.app">courriel</a>'
            '<a href="javascript:void(0)">js</a></main>'
        )
        self.assertEqual(r['etat'], 'disparu')

    def test_domaine_qui_contient_la_cible_ne_compte_pas(self):
        r = verifie(
            f'<main>{REMPLISSAGE}<a href="https://gridar.app.exemple.ca/">piège</a></main>'
        )
        self.assertEqual(r['etat'], 'disparu')

    def test_lien_dans_un_template_ne_compte_pas(self):
        r = verifie(
            f'<main>{REMPLISSAGE}<template><a href="https://gridar.app/">jamais '
            'rendu</a></template></main>'
        )
        self.assertEqual(r['etat'], 'disparu')

    def test_coquille_javascript_reste_indeterminee(self):
        reponse = FakeResponse(body=(
            '<!doctype html><html><head><title>App</title></head><body>'
            '<div id="__next"></div>' + '<!-- ' + 'x' * 6000 + ' -->'
            '</body></html>'
        ))
        with patch('sites_mgmt.backlinks_verify.safe_get', return_value=reponse):
            r = verify_backlink(SOURCE, CIBLE)
        self.assertEqual(r['etat'], 'non_verifiable')
        self.assertIsNone(r['lien_present'])
        self.assertEqual(r['code_erreur'], 'rendu_js')

    def test_next_js_rendu_serveur_reste_une_perte(self):
        # Upstream flags every React marker as unverifiable, which turns every
        # server-rendered blog into "cannot tell". Here the text has to be
        # genuinely missing.
        reponse = FakeResponse(body=page(
            f'<div id="__next"><main>{REMPLISSAGE}</main></div>'
        ))
        with patch('sites_mgmt.backlinks_verify.safe_get', return_value=reponse):
            r = verify_backlink(SOURCE, CIBLE)
        self.assertEqual(r['etat'], 'disparu')

    def test_plateforme_js_jamais_annoncee_comme_perdue(self):
        source = 'https://www.instagram.com/p/Cxyz/'
        reponse = FakeResponse(body=page(f'<main>{REMPLISSAGE}</main>'), url=source)
        with patch('sites_mgmt.backlinks_verify.safe_get', return_value=reponse):
            r = verify_backlink(source, CIBLE)
        self.assertEqual(r['etat'], 'non_verifiable')


class ReponsesHttp(SimpleTestCase):
    """Each HTTP outcome maps to the state it actually justifies."""

    def _statut(self, code):
        reponse = FakeResponse(status=code, body=page('<p>rien</p>'))
        with patch('sites_mgmt.backlinks_verify.safe_get', return_value=reponse):
            return verify_backlink(SOURCE, CIBLE)

    def test_404_page_absente(self):
        r = self._statut(404)
        self.assertEqual(r['etat'], 'page_absente')
        self.assertIs(r['lien_present'], False)

    def test_403_injoignable_pas_perdu(self):
        # Cloudflare refusing us is not a client losing a link.
        r = self._statut(403)
        self.assertEqual(r['etat'], 'injoignable')
        self.assertEqual(r['code_erreur'], 'acces_refuse')
        self.assertIsNone(r['lien_present'])

    def test_429_injoignable(self):
        self.assertEqual(self._statut(429)['code_erreur'], 'acces_refuse')

    def test_500_injoignable(self):
        r = self._statut(503)
        self.assertEqual(r['etat'], 'injoignable')
        self.assertEqual(r['code_erreur'], 'serveur')

    def test_timeout(self):
        with patch('sites_mgmt.backlinks_verify.safe_get',
                   side_effect=requests.exceptions.Timeout()):
            r = verify_backlink(SOURCE, CIBLE)
        self.assertEqual(r['etat'], 'injoignable')
        self.assertEqual(r['code_erreur'], 'timeout')

    def test_erreur_reseau(self):
        with patch('sites_mgmt.backlinks_verify.safe_get',
                   side_effect=requests.exceptions.ConnectionError()):
            r = verify_backlink(SOURCE, CIBLE)
        self.assertEqual(r['code_erreur'], 'reseau')

    def test_redirection_bloquee_par_le_garde_ssrf(self):
        with patch('sites_mgmt.backlinks_verify.safe_get',
                   side_effect=URLSafetyError('boom')):
            r = verify_backlink(SOURCE, CIBLE)
        self.assertEqual(r['etat'], 'injoignable')
        self.assertEqual(r['code_erreur'], 'url_refusee')

    def test_adresse_interne_jamais_recuperee(self):
        # The point of the module's SSRF discipline: no socket is opened at all
        # for a URL the parse-time check already refuses.
        with patch('sites_mgmt.backlinks_verify.safe_get') as faux:
            r = verify_backlink('http://169.254.169.254/latest/meta-data/', CIBLE)
        faux.assert_not_called()
        self.assertEqual(r['code_erreur'], 'url_refusee')

    def test_redirection_vers_https_nest_pas_un_demenagement(self):
        corps = f'<main>{REMPLISSAGE}<a href="https://gridar.app/">Gridar</a></main>'
        reponse = FakeResponse(body=page(corps), url='https://blogue-plomberie.qc.ca/palmares-outils-seo')
        with patch('sites_mgmt.backlinks_verify.safe_get', return_value=reponse):
            r = verify_backlink('http://blogue-plomberie.qc.ca/palmares-outils-seo/', CIBLE)
        self.assertEqual(r['etat'], 'confirme')
        self.assertIsNone(r['redirection'])

    def test_redirection_reelle_sans_lien(self):
        reponse = FakeResponse(body=page(f'<main>{REMPLISSAGE}</main>'),
                               url='https://blogue-plomberie.qc.ca/nouveau-palmares/')
        with patch('sites_mgmt.backlinks_verify.safe_get', return_value=reponse):
            r = verify_backlink(SOURCE, CIBLE)
        self.assertEqual(r['etat'], 'redirigee')
        self.assertEqual(r['redirection']['url_finale'],
                         'https://blogue-plomberie.qc.ca/nouveau-palmares/')
        self.assertIs(r['redirection']['meme_domaine'], True)

    def test_redirection_reelle_avec_lien_reste_confirmee(self):
        corps = f'<main>{REMPLISSAGE}<a href="https://gridar.app/">Gridar</a></main>'
        reponse = FakeResponse(body=page(corps),
                               url='https://blogue-plomberie.qc.ca/nouveau/')
        with patch('sites_mgmt.backlinks_verify.safe_get', return_value=reponse):
            r = verify_backlink(SOURCE, CIBLE)
        self.assertEqual(r['etat'], 'confirme')
        self.assertIsNotNone(r['redirection'])

    def test_corps_tronque_au_plafond(self):
        gros = page(f'<main>{REMPLISSAGE}</main>' + '<p>a</p>' * 20000)
        reponse = FakeResponse(body=gros)
        with patch.object(bv, 'MAX_BYTES', 4096):
            with patch('sites_mgmt.backlinks_verify.safe_get', return_value=reponse):
                r = verify_backlink(SOURCE, CIBLE)
        self.assertIs(r['page_tronquee'], True)

    def test_entrees_vides(self):
        r = verify_backlink('', CIBLE)
        self.assertEqual(r['code_erreur'], 'url_invalide')
        self.assertEqual(verify_backlink(SOURCE, '')['code_erreur'], 'domaine_invalide')

    def test_auto_reference_signalee(self):
        source = 'https://gridar.app/blogue/interne/'
        reponse = FakeResponse(body=page(
            f'<main>{REMPLISSAGE}<a href="https://gridar.app/x">interne</a></main>'),
            url=source)
        with patch('sites_mgmt.backlinks_verify.safe_get', return_value=reponse):
            r = verify_backlink(source, CIBLE)
        self.assertIs(r['auto_reference'], True)


class Lot(SimpleTestCase):
    """The batch: dedupe, budget, politeness, summary."""

    def _reponses(self, table):
        def _fake(url, **_):
            corps = table.get(url, f'<main>{REMPLISSAGE}</main>')
            return FakeResponse(body=page(corps), url=url)
        return _fake

    def test_resume_complet(self):
        avec = f'<main>{REMPLISSAGE}<a href="https://gridar.app/">Gridar</a></main>'
        sans = f'<main>{REMPLISSAGE}</main>'
        table = {
            'https://a.qc.ca/1': avec,
            'https://b.qc.ca/1': avec,
            'https://c.qc.ca/1': sans,
        }
        with patch('sites_mgmt.backlinks_verify.safe_get',
                   side_effect=self._reponses(table)):
            lot = verify_batch(list(table), CIBLE, time_budget=30.0)

        resume = lot['resume']
        self.assertEqual(resume['total'], 3)
        self.assertEqual(resume['confirmes'], 2)
        self.assertEqual(resume['perdus'], 1)
        self.assertEqual(resume['injoignables'], 0)
        self.assertEqual(resume['domaines_referents'], 2)
        self.assertEqual(resume['liens_suivis'], 2)
        self.assertEqual(resume['liens_contenu'], 2)
        self.assertAlmostEqual(resume['taux_confirmation'], 66.7)
        self.assertEqual(resume['couverture'], 100.0)
        self.assertEqual(resume['par_etat']['confirme'], 2)
        self.assertIs(lot['budget_epuise'], False)
        self.assertEqual([r['url_source'] for r in lot['resultats']], list(table))

    def test_doublons_verifies_une_seule_fois(self):
        appels = []

        def _fake(url, **_):
            appels.append(url)
            return FakeResponse(body=page(f'<main>{REMPLISSAGE}</main>'), url=url)

        liens = [
            'https://a.qc.ca/page/',
            'http://www.a.qc.ca/page',   # same address, three spellings
            'https://a.qc.ca/page',
        ]
        with patch.object(bv, 'DELAI_PAR_DOMAINE', 0):
            with patch('sites_mgmt.backlinks_verify.safe_get', side_effect=_fake):
                lot = verify_batch(liens, CIBLE, time_budget=30.0)
        self.assertEqual(len(appels), 1)
        self.assertEqual(lot['resume']['total'], 1)
        self.assertEqual(lot['resume']['soumis'], 3)
        self.assertEqual(lot['resume']['doublons_ignores'], 2)

    def test_formats_dentree_acceptes(self):
        liens = [
            'https://a.qc.ca/1',
            {'source_url': 'https://b.qc.ca/1'},
            {'url_from': 'https://c.qc.ca/1'},
            {'url_source': 'https://d.qc.ca/1'},
            {'sans_url': True},
        ]
        with patch('sites_mgmt.backlinks_verify.safe_get',
                   side_effect=self._reponses({})):
            lot = verify_batch(liens, CIBLE, time_budget=30.0)
        self.assertEqual(lot['resume']['total'], 4)

    def test_budget_epuise_rend_les_lignes_non_verifiees(self):
        with patch('sites_mgmt.backlinks_verify.safe_get') as faux:
            lot = verify_batch(['https://a.qc.ca/1', 'https://b.qc.ca/1'],
                               CIBLE, time_budget=0.0)
        faux.assert_not_called()
        self.assertIs(lot['budget_epuise'], True)
        self.assertEqual(lot['resume']['non_verifies'], 2)
        self.assertEqual(lot['resume']['taux_confirmation'], None)
        self.assertEqual(lot['resultats'][0]['code_erreur'], 'budget_epuise')

    def test_un_seul_appel_a_la_fois_par_domaine(self):
        actifs, sommets = {}, {}
        verrou = threading.Lock()

        def _fake(url, **_):
            hote = url.split('/')[2]
            with verrou:
                actifs[hote] = actifs.get(hote, 0) + 1
                sommets[hote] = max(sommets.get(hote, 0), actifs[hote])
            time.sleep(0.05)
            with verrou:
                actifs[hote] -= 1
            return FakeResponse(body=page(f'<main>{REMPLISSAGE}</main>'), url=url)

        liens = [f'https://a.qc.ca/{i}' for i in range(3)]
        liens += [f'https://b.qc.ca/{i}' for i in range(3)]
        with patch.object(bv, 'DELAI_PAR_DOMAINE', 0):
            with patch('sites_mgmt.backlinks_verify.safe_get', side_effect=_fake):
                lot = verify_batch(liens, CIBLE, max_workers=4, time_budget=30.0)
        self.assertEqual(lot['resume']['total'], 6)
        self.assertEqual(set(sommets.values()), {1})

    def test_cible_illisible_ne_lance_aucun_appel(self):
        with patch('sites_mgmt.backlinks_verify.safe_get') as faux:
            lot = verify_batch(['https://a.qc.ca/1'], '', time_budget=30.0)
        faux.assert_not_called()
        self.assertEqual(lot['resultats'][0]['code_erreur'], 'domaine_invalide')

    def test_lot_vide(self):
        lot = verify_batch([], CIBLE)
        self.assertEqual(lot['resultats'], [])
        self.assertEqual(lot['resume']['couverture'], 0.0)


class ValidationDuRapport(SimpleTestCase):
    """Reading a report before showing it."""

    def _rapport(self, **extra):
        base = {
            'domaine_cible': CIBLE,
            'resultats': [{
                'url_source': 'https://a.qc.ca/1',
                'etat': 'confirme',
                'lien_present': True,
                'nb_liens': 1,
                'verifie_le': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            }],
        }
        base.update(extra)
        return base

    def _codes(self, rapport):
        return [s['code'] for s in validate_report(rapport)]

    def test_lot_propre_ne_produit_rien(self):
        avec = f'<main>{REMPLISSAGE}<a href="https://gridar.app/">Gridar</a></main>'

        def _fake(url, **_):
            return FakeResponse(body=page(avec if url.endswith('1') else
                                          f'<main>{REMPLISSAGE}</main>'), url=url)

        with patch('sites_mgmt.backlinks_verify.safe_get', side_effect=_fake):
            lot = verify_batch(['https://a.qc.ca/1', 'https://b.qc.ca/2'],
                               CIBLE, time_budget=30.0)
        self.assertEqual(validate_report(lot), [])

    def test_entree_illisible_ne_leve_pas(self):
        for entree in (None, 'texte', 42, ['a']):
            signalements = validate_report(entree)
            self.assertEqual(len(signalements), 1)
            self.assertEqual(signalements[0]['code'], 'rapport_illisible')

    def test_lien_compte_deux_fois(self):
        rapport = self._rapport(resultats=[
            {'url_source': 'https://a.qc.ca/page/', 'etat': 'confirme',
             'nb_liens': 1, 'verifie_le': '2026-08-14T10:00:00Z'},
            {'url_source': 'http://www.a.qc.ca/page', 'etat': 'confirme',
             'nb_liens': 1, 'verifie_le': '2026-08-14T10:00:00Z'},
        ])
        signalements = validate_report(rapport)
        doublon = [s for s in signalements if s['code'] == 'doublon']
        self.assertEqual(len(doublon), 1)
        self.assertIn('2 fois', doublon[0]['constat'])
        self.assertEqual(doublon[0]['donnees']['occurrences'], 2)

    def test_domaine_referent_qui_est_le_domaine_lui_meme(self):
        rapport = self._rapport(resultats=[
            {'url_source': 'https://www.gridar.app/blogue/', 'etat': 'confirme',
             'nb_liens': 1, 'verifie_le': '2026-08-14T10:00:00Z'},
        ])
        signalements = [s for s in validate_report(rapport)
                        if s['code'] == 'auto_reference']
        self.assertEqual(len(signalements), 1)
        self.assertEqual(signalements[0]['severite'], 'critique')

    def test_total_qui_ne_correspond_pas_a_la_liste(self):
        rapport = self._rapport(total=14)
        signalement = [s for s in validate_report(rapport)
                       if s['code'] == 'total_incoherent'][0]
        self.assertEqual(signalement['donnees'], {'annonce': 14, 'reel': 1})

    def test_domaines_referents_qui_ne_correspondent_pas(self):
        rapport = self._rapport(total_referring_domains=9)
        self.assertIn('domaines_incoherents', self._codes(rapport))

    def test_resume_qui_contredit_sa_liste(self):
        rapport = self._rapport(resume={'par_etat': {'confirme': 7}, 'total': 1,
                                        'confirmes': 7})
        codes = self._codes(rapport)
        self.assertIn('resume_incoherent', codes)
        self.assertIn('resume_impossible', codes)

    def test_mentions_presentees_comme_des_liens(self):
        rapport = {
            'domaine_cible': CIBLE,
            'is_link_data': False,
            'total_referring_domains': 10,
            'saturates_at': 10,
        }
        codes = self._codes(rapport)
        self.assertIn('mentions_presentees_comme_liens', codes)
        self.assertIn('mesure_plafonnee', codes)
        self.assertEqual(validate_report(rapport)[0]['severite'], 'critique')

    def test_note_publiee_sans_aucun_lien_verifie(self):
        rapport = {'domaine_cible': CIBLE, 'score': 31, 'resultats': [
            {'url_source': 'https://a.qc.ca/1', 'etat': 'injoignable'},
        ]}
        signalement = [s for s in validate_report(rapport)
                       if s['code'] == 'affirmation_sans_donnee'][0]
        self.assertEqual(signalement['severite'], 'critique')
        self.assertIn('31', signalement['constat'])

    def test_total_annonce_sans_liste(self):
        self.assertIn('total_sans_liste',
                      self._codes({'domaine_cible': CIBLE, 'total_backlinks': 42}))

    def test_liste_sans_aucune_verification(self):
        rapport = {'domaine_cible': CIBLE, 'total': 2, 'liens': [
            {'url_source': 'https://a.qc.ca/1'},
            {'url_source': 'https://b.qc.ca/1'},
        ]}
        self.assertIn('liste_sans_verification', self._codes(rapport))

    def test_confirme_sans_lien_derriere(self):
        rapport = self._rapport(resultats=[
            {'url_source': 'https://a.qc.ca/1', 'etat': 'confirme',
             'nb_liens': 0, 'verifie_le': '2026-08-14T10:00:00Z'},
        ])
        self.assertIn('confirme_sans_lien', self._codes(rapport))

    def test_confirme_qui_se_contredit(self):
        rapport = self._rapport(resultats=[
            {'url_source': 'https://a.qc.ca/1', 'etat': 'confirme',
             'lien_present': False, 'nb_liens': 1,
             'verifie_le': '2026-08-14T10:00:00Z'},
        ])
        self.assertIn('etat_incoherent', self._codes(rapport))

    def test_date_manquante_et_date_future(self):
        futur = (datetime.now(timezone.utc) + timedelta(days=2)) \
            .strftime('%Y-%m-%dT%H:%M:%SZ')
        rapport = self._rapport(resultats=[
            {'url_source': 'https://a.qc.ca/1', 'etat': 'confirme', 'nb_liens': 1},
            {'url_source': 'https://b.qc.ca/1', 'etat': 'confirme', 'nb_liens': 1,
             'verifie_le': futur},
        ])
        codes = self._codes(rapport)
        self.assertIn('date_manquante', codes)
        self.assertIn('date_future', codes)

    def test_verification_perimee(self):
        vieux = (datetime.now(timezone.utc) - timedelta(days=AGE_MAX_JOURS + 10)) \
            .strftime('%Y-%m-%dT%H:%M:%SZ')
        rapport = self._rapport(resultats=[
            {'url_source': 'https://a.qc.ca/1', 'etat': 'confirme', 'nb_liens': 1,
             'verifie_le': vieux},
        ])
        signalement = [s for s in validate_report(rapport)
                       if s['code'] == 'verification_perimee'][0]
        self.assertEqual(signalement['severite'], 'faible')

    def test_perte_annoncee_sur_une_plateforme_javascript(self):
        rapport = self._rapport(resultats=[
            {'url_source': 'https://www.instagram.com/p/Cxyz/', 'etat': 'disparu',
             'statut_http': 200, 'nb_liens': 0},
        ])
        self.assertIn('perte_sur_plateforme_js', self._codes(rapport))

    def test_url_source_interne_refusee(self):
        rapport = self._rapport(resultats=[
            {'url_source': 'http://192.168.1.10/admin', 'etat': 'confirme',
             'nb_liens': 1, 'verifie_le': '2026-08-14T10:00:00Z'},
        ])
        self.assertIn('url_source_refusee', self._codes(rapport))

    def test_rapport_sans_domaine_cible(self):
        self.assertIn('cible_absente', self._codes(
            {'resultats': [{'url_source': 'https://a.qc.ca/1', 'etat': 'disparu'}]}))

    def test_signalements_tries_du_plus_grave_au_moins_grave(self):
        rapport = {
            'is_link_data': False,
            'total_referring_domains': 3,
            'resultats': [
                {'url_source': 'https://a.qc.ca/1', 'etat': 'confirme', 'nb_liens': 1},
                {'url_source': 'https://a.qc.ca/1/', 'etat': 'confirme', 'nb_liens': 1},
            ],
        }
        rangs = [SEVERITES.index(s['severite']) for s in validate_report(rapport)]
        self.assertEqual(rangs, sorted(rangs, reverse=True))

    def test_champs_du_signalement(self):
        signalement = validate_report(self._rapport(total=14))[0]
        self.assertEqual(
            set(signalement),
            {'code', 'severite', 'champ', 'constat', 'correction', 'donnees'},
        )
        self.assertIn(signalement['severite'], SEVERITES)

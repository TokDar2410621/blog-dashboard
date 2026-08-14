"""Tests for the Core Web Vitals depth module.

Everything runs offline. The only network call in the module is the CrUX
History POST, and every test that reaches it patches
`sites_mgmt.cwv_depth.requests.post`, so no socket is opened. The LCP
decomposition and the preload audit are pure, and the preload tests feed them
real `html_parse.extract_seo_signals` output rather than a hand-built dict, so
a change in either module shows up here.

Run all:
    python manage.py test sites_mgmt.tests_cwv_depth
"""
from datetime import date, timedelta
from unittest.mock import patch

import requests
from django.test import SimpleTestCase

from .cwv_depth import (
    SEVERITE_RANG, analyze_lcp_subparts, check_preload_signals,
    fetch_crux_history,
)
from .html_parse import extract_seo_signals

CLE = 'AIzaSyTestKeyGridar0000000000000000000'
PREMIER_LUNDI = date(2026, 1, 5)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

class FakeResponse:
    """requests.Response stand-in with just what the module reads."""

    def __init__(self, status=200, payload=None, invalide=False):
        self.status_code = status
        self._payload = payload if payload is not None else {}
        self._invalide = invalide

    def json(self):
        if self._invalide:
            raise ValueError('Expecting value')
        return self._payload


def periodes(nombre: int) -> list:
    blocs = []
    for index in range(nombre):
        debut = PREMIER_LUNDI + timedelta(days=7 * index)
        fin = debut + timedelta(days=6)
        blocs.append({
            'firstDate': {'year': debut.year, 'month': debut.month, 'day': debut.day},
            'lastDate': {'year': fin.year, 'month': fin.month, 'day': fin.day},
        })
    return blocs


def serie(p75s, histogramme=None) -> dict:
    donnees = {'percentilesTimeseries': {'p75s': list(p75s)}}
    if histogramme:
        donnees['histogramTimeseries'] = [{'densities': bac} for bac in histogramme]
    return donnees


def historique(metriques: dict, semaines: int = 0) -> dict:
    if not semaines:
        semaines = max(
            (len(m['percentilesTimeseries']['p75s']) for m in metriques.values()),
            default=0,
        )
    return {'record': {
        'collectionPeriods': periodes(semaines),
        'metrics': metriques,
    }}


def poster(reponse):
    """Patch context returning `reponse` for any CrUX call."""
    return patch('sites_mgmt.cwv_depth.requests.post', return_value=reponse)


# ---------------------------------------------------------------------------
# fetch_crux_history
# ---------------------------------------------------------------------------

class CruxHistoryLectureTests(SimpleTestCase):
    def test_lit_les_series_les_verdicts_et_les_semaines(self):
        payload = historique({
            'largest_contentful_paint': serie(
                [2400] * 21 + [4500] * 4,
                histogramme=[[0.8] * 25, [0.15] * 25, [0.05] * 25],
            ),
            'cumulative_layout_shift': serie(['0.05'] * 25),
        })
        with poster(FakeResponse(200, payload)):
            resultat = fetch_crux_history('https://exemple.qc.ca/', CLE)

        self.assertIsNone(resultat['erreur'])
        self.assertEqual(resultat['nb_semaines'], 25)
        self.assertEqual(resultat['semaines'][0]['debut'], '2026-01-05')

        lcp = resultat['metriques']['lcp']
        self.assertEqual(lcp['p75_actuel'], 4500)
        self.assertEqual(lcp['verdict'], 'mauvais')
        self.assertEqual(lcp['valeur_lisible'], '4,50 s')
        self.assertEqual(len(lcp['p75']), 25)
        self.assertEqual(lcp['part_bonne_actuelle'], 80.0)

        cls = resultat['metriques']['cls']
        self.assertEqual(cls['p75_actuel'], 0.05)
        self.assertEqual(cls['verdict'], 'bon')

    def test_ignore_une_metrique_sans_aucune_valeur(self):
        payload = historique({
            'largest_contentful_paint': serie([2000] * 8),
            'interaction_to_next_paint': serie([None, 'NaN', None, None, None, None,
                                                None, None]),
        })
        with poster(FakeResponse(200, payload)):
            resultat = fetch_crux_history('https://exemple.qc.ca/', CLE)

        self.assertIn('lcp', resultat['metriques'])
        self.assertNotIn('inp', resultat['metriques'])

    def test_les_semaines_vides_ne_cassent_pas_la_serie(self):
        p75s = [2000, 'NaN', None, 2100, 2050, 2000, 2100, 2000]
        with poster(FakeResponse(200, historique({
                'largest_contentful_paint': serie(p75s)}))):
            resultat = fetch_crux_history('https://exemple.qc.ca/', CLE)

        lcp = resultat['metriques']['lcp']
        self.assertEqual(lcp['p75'][1], None)
        self.assertEqual(lcp['p75'][2], None)
        self.assertEqual(lcp['tendance']['points'], 6)


class CruxTendanceTests(SimpleTestCase):
    def _direction(self, p75s, metrique='largest_contentful_paint'):
        with poster(FakeResponse(200, historique({metrique: serie(p75s)}))):
            resultat = fetch_crux_history('https://exemple.qc.ca/', CLE)
        cle = 'cls' if metrique == 'cumulative_layout_shift' else 'lcp'
        return resultat['metriques'][cle]['tendance']

    def test_detecte_une_degradation(self):
        tendance = self._direction([2000] * 4 + [2600, 3000, 3400] + [3800] * 4)
        self.assertEqual(tendance['direction'], 'degradation')
        self.assertGreater(tendance['variation_pct'], 5)
        self.assertEqual(tendance['debut'], 2000)
        self.assertEqual(tendance['fin'], 3800)

    def test_detecte_une_amelioration(self):
        tendance = self._direction([4200] * 4 + [3400, 3000] + [2100] * 4)
        self.assertEqual(tendance['direction'], 'amelioration')
        self.assertLess(tendance['variation_pct'], -5)

    def test_le_plancher_de_bruit_neutralise_un_micro_ecart_de_cls(self):
        """Upstream calls this a 12 % degradation; on CLS it is measurement noise."""
        tendance = self._direction(['0.05'] * 4 + ['0.056'] * 4,
                                   metrique='cumulative_layout_shift')
        self.assertEqual(tendance['direction'], 'stable')
        self.assertGreater(abs(tendance['variation_pct']), 5)

    def test_le_plancher_de_bruit_neutralise_un_micro_ecart_en_ms(self):
        tendance = self._direction([900] * 4 + [940] * 4)
        self.assertEqual(tendance['direction'], 'stable')

    def test_historique_trop_court(self):
        tendance = self._direction([2000, 2200, 2400, 3800])
        self.assertEqual(tendance['direction'], 'donnees_insuffisantes')
        self.assertIsNone(tendance['variation_pct'])


class CruxFranchissementTests(SimpleTestCase):
    def test_date_la_sortie_du_vert(self):
        payload = historique({
            'largest_contentful_paint': serie([2100] * 6 + [4500] * 4),
        })
        with poster(FakeResponse(200, payload)):
            resultat = fetch_crux_history('https://exemple.qc.ca/', CLE)

        franchissement = resultat['metriques']['lcp']['franchissement']
        self.assertEqual(franchissement['de'], 'bon')
        self.assertEqual(franchissement['vers'], 'mauvais')
        self.assertTrue(franchissement['sortie_du_vert'])
        # Seventh week of the series, the first one measured out of the green.
        self.assertEqual(franchissement['semaine'], '2026-02-22')

        codes = [alerte['code'] for alerte in resultat['alertes']]
        self.assertIn('cwv_sortie_du_vert', codes)
        self.assertIn('cwv_hors_seuil', codes)
        self.assertIn('2026-02-22', resultat['resume'] + ' '.join(
            alerte['message'] for alerte in resultat['alertes']))

    def test_pas_de_franchissement_quand_la_zone_ne_change_pas(self):
        with poster(FakeResponse(200, historique({
                'largest_contentful_paint': serie([2100] * 10)}))):
            resultat = fetch_crux_history('https://exemple.qc.ca/', CLE)
        self.assertIsNone(resultat['metriques']['lcp']['franchissement'])
        self.assertEqual(resultat['alertes'], [])

    def test_les_alertes_sont_triees_par_severite(self):
        payload = historique({
            'largest_contentful_paint': serie([2100] * 6 + [4500] * 4),
            'interaction_to_next_paint': serie([210] * 10),
        })
        with poster(FakeResponse(200, payload)):
            resultat = fetch_crux_history('https://exemple.qc.ca/', CLE)

        rangs = [SEVERITE_RANG[alerte['severity']] for alerte in resultat['alertes']]
        self.assertEqual(rangs, sorted(rangs))
        self.assertEqual(resultat['alertes'][0]['severity'], 'critical')


class CruxRequeteTests(SimpleTestCase):
    def _corps(self, cible, **kwargs):
        with patch('sites_mgmt.cwv_depth.requests.post',
                   return_value=FakeResponse(200, historique({
                       'largest_contentful_paint': serie([2000] * 8)}))) as appel:
            resultat = fetch_crux_history(cible, CLE, **kwargs)
        return appel.call_args.kwargs['json'], resultat

    def test_une_racine_est_demandee_au_niveau_origine(self):
        corps, resultat = self._corps('https://exemple.qc.ca/')
        self.assertEqual(corps['origin'], 'https://exemple.qc.ca')
        self.assertNotIn('url', corps)
        self.assertEqual(resultat['granularite'], 'origine')

    def test_une_page_est_demandee_au_niveau_url(self):
        corps, resultat = self._corps('https://exemple.qc.ca/services/deneigement')
        self.assertEqual(corps['url'], 'https://exemple.qc.ca/services/deneigement')
        self.assertEqual(resultat['granularite'], 'url')

    def test_un_domaine_nu_recoit_le_schema_https(self):
        corps, resultat = self._corps('exemple.qc.ca')
        self.assertEqual(corps['origin'], 'https://exemple.qc.ca')
        self.assertEqual(resultat['cible'], 'https://exemple.qc.ca')

    def test_form_factor_par_defaut_est_le_telephone(self):
        corps, resultat = self._corps('https://exemple.qc.ca/')
        self.assertEqual(corps['formFactor'], 'PHONE')
        self.assertEqual(resultat['form_factor'], 'PHONE')

    def test_form_factor_inconnu_demande_tous_les_appareils(self):
        corps, resultat = self._corps('https://exemple.qc.ca/', form_factor='ALL')
        self.assertNotIn('formFactor', corps)
        self.assertEqual(resultat['form_factor'], 'ALL')

    def test_la_cle_voyage_dans_un_entete_pas_dans_l_url(self):
        with patch('sites_mgmt.cwv_depth.requests.post',
                   return_value=FakeResponse(200, {})) as appel:
            fetch_crux_history('https://exemple.qc.ca/', CLE)
        args, kwargs = appel.call_args
        self.assertEqual(kwargs['headers']['X-Goog-Api-Key'], CLE)
        self.assertNotIn(CLE, args[0])


class CruxErreurTests(SimpleTestCase):
    def test_sans_cle_aucun_appel_reseau(self):
        with patch('sites_mgmt.cwv_depth.requests.post') as appel:
            resultat = fetch_crux_history('https://exemple.qc.ca/', '')
        appel.assert_not_called()
        self.assertIn('PAGESPEED_API_KEY', resultat['erreur'])

    def test_url_interne_refusee_avant_l_appel(self):
        for cible in ('http://localhost:8000/', 'http://169.254.169.254/',
                      'file:///etc/passwd', ''):
            with patch('sites_mgmt.cwv_depth.requests.post') as appel:
                resultat = fetch_crux_history(cible, CLE)
            appel.assert_not_called()
            self.assertIsNotNone(resultat['erreur'], cible)

    def test_404_au_niveau_url_suggere_le_domaine(self):
        with poster(FakeResponse(404, {})):
            resultat = fetch_crux_history('https://exemple.qc.ca/page', CLE)
        self.assertIn('domaine', resultat['erreur'])
        self.assertEqual(resultat['metriques'], {})

    def test_404_au_niveau_domaine_explique_le_trafic(self):
        with poster(FakeResponse(404, {})):
            resultat = fetch_crux_history('https://exemple.qc.ca/', CLE)
        self.assertIn('Chrome', resultat['erreur'])

    def test_429_parle_de_quota(self):
        with poster(FakeResponse(429, {})):
            resultat = fetch_crux_history('https://exemple.qc.ca/', CLE)
        self.assertIn('Quota', resultat['erreur'])

    def test_erreur_http_reprend_le_message_de_google(self):
        payload = {'error': {'message': 'API key not valid'}}
        with poster(FakeResponse(403, payload)):
            resultat = fetch_crux_history('https://exemple.qc.ca/', CLE)
        self.assertIn('403', resultat['erreur'])
        self.assertIn('API key not valid', resultat['erreur'])

    def test_la_cle_est_masquee_dans_les_messages(self):
        exception = requests.exceptions.RequestException(
            'connexion refusee vers ...?key=%s' % CLE)
        with patch('sites_mgmt.cwv_depth.requests.post', side_effect=exception):
            resultat = fetch_crux_history('https://exemple.qc.ca/', CLE)
        self.assertNotIn(CLE, resultat['erreur'])
        self.assertIn('CLE_API_MASQUEE', resultat['erreur'])

    def test_timeout(self):
        with patch('sites_mgmt.cwv_depth.requests.post',
                   side_effect=requests.exceptions.Timeout()):
            resultat = fetch_crux_history('https://exemple.qc.ca/', CLE)
        self.assertIn('délai', resultat['erreur'])

    def test_json_invalide(self):
        with poster(FakeResponse(200, invalide=True)):
            resultat = fetch_crux_history('https://exemple.qc.ca/', CLE)
        self.assertIn('illisible', resultat['erreur'])

    def test_reponse_sans_metrique_connue(self):
        with poster(FakeResponse(200, historique({'time_to_first_byte': serie([100])}))):
            resultat = fetch_crux_history('https://exemple.qc.ca/', CLE)
        self.assertIn('aucune métrique', resultat['erreur'])
        self.assertEqual(resultat['metriques'], {})


# ---------------------------------------------------------------------------
# analyze_lcp_subparts
# ---------------------------------------------------------------------------

def psi_labo(phases, lcp_ms=4000, avec_element=True, avec_total=True):
    """PageSpeed payload holding the Lighthouse LCP phase table."""
    items = []
    if avec_element:
        items.append({
            'type': 'table',
            'headings': [{'key': 'node'}],
            'items': [{'node': {
                'type': 'node',
                'selector': 'main > img.heros',
                'snippet': '<img class="heros" src="/heros.jpg">',
                'nodeLabel': 'Image du haut de page',
            }}],
        })
    items.append({
        'type': 'table',
        'headings': [{'key': 'phase'}, {'key': 'percent'}, {'key': 'timing'}],
        'items': [{'phase': nom, 'percent': '', 'timing': valeur}
                  for nom, valeur in phases],
    })
    audits = {'largest-contentful-paint-element': {
        'id': 'largest-contentful-paint-element',
        'details': {'type': 'list', 'items': items},
    }}
    if avec_total:
        audits['largest-contentful-paint'] = {'numericValue': lcp_ms}
    return {
        'id': 'https://exemple.qc.ca/',
        'lighthouseResult': {
            'finalUrl': 'https://exemple.qc.ca/',
            'configSettings': {'formFactor': 'mobile'},
            'audits': audits,
        },
    }


PHASES_RENDU_LOURD = (
    ('TTFB', 1700),
    ('Load Delay', 200),
    ('Load Time', 900),
    ('Render Delay', 1200),
)


class LcpSousPartiesTests(SimpleTestCase):
    def test_decompose_les_quatre_phases(self):
        resultat = analyze_lcp_subparts(psi_labo(PHASES_RENDU_LOURD))

        self.assertIsNone(resultat['erreur'])
        self.assertEqual(resultat['source'], 'labo')
        self.assertEqual(resultat['lcp_ms'], 4000)
        self.assertEqual(resultat['lcp_lisible'], '4,00 s')
        # 4000 ms sits exactly on Google's poor threshold, so it is still amber.
        self.assertEqual(resultat['verdict'], 'a_ameliorer')
        self.assertEqual(resultat['strategie'], 'mobile')
        self.assertEqual([part['cle'] for part in resultat['sous_parties']],
                         ['ttfb', 'delai_ressource', 'chargement_ressource', 'rendu'])
        self.assertEqual(resultat['sous_parties'][0]['ms'], 1700)
        self.assertEqual(resultat['sous_parties'][0]['part'], 0.425)

    def test_la_dominante_est_la_phase_hors_budget_pas_la_plus_grosse(self):
        """TTFB is the biggest slice but stays inside its 40 % budget.

        Upstream's flat "over 40 % of LCP" rule crowns TTFB here and sends the
        client tuning a server that is not the problem.
        """
        resultat = analyze_lcp_subparts(psi_labo(PHASES_RENDU_LOURD))

        self.assertEqual(resultat['dominante'], 'rendu')
        self.assertFalse(resultat['sous_parties'][0]['hors_budget'])
        self.assertTrue(resultat['sous_parties'][3]['hors_budget'])
        self.assertIn('rendu', resultat['diagnostic'].lower())
        self.assertIn('CSS', resultat['actions'][0])

    def test_lit_les_libelles_francais_de_lighthouse(self):
        phases = (
            ('TTFB', 1700),
            ('Délai de chargement', 200),
            ('Temps de chargement', 900),
            ('Délai de rendu', 1200),
        )
        resultat = analyze_lcp_subparts(psi_labo(phases))
        self.assertEqual(
            {part['cle']: part['ms'] for part in resultat['sous_parties']},
            {'ttfb': 1700, 'delai_ressource': 200,
             'chargement_ressource': 900, 'rendu': 1200},
        )
        self.assertEqual(resultat['dominante'], 'rendu')

    def test_identifie_l_element_du_lcp(self):
        resultat = analyze_lcp_subparts(psi_labo(PHASES_RENDU_LOURD))
        self.assertEqual(resultat['element']['selecteur'], 'main > img.heros')
        self.assertIn('heros.jpg', resultat['element']['extrait'])

    def test_un_lcp_equilibre_et_vert_ne_designe_personne(self):
        phases = (('TTFB', 800), ('Load Delay', 100),
                  ('Load Time', 850), ('Render Delay', 250))
        resultat = analyze_lcp_subparts(psi_labo(phases, lcp_ms=2000))

        self.assertEqual(resultat['verdict'], 'bon')
        self.assertIsNone(resultat['dominante'])
        self.assertEqual(resultat['actions'], [])
        self.assertIn('Rien à corriger', resultat['diagnostic'])

    def test_un_lcp_lent_mais_reparti_propose_quand_meme_deux_pistes(self):
        phases = (('TTFB', 2000), ('Load Delay', 400),
                  ('Load Time', 1900), ('Render Delay', 700))
        resultat = analyze_lcp_subparts(psi_labo(phases, lcp_ms=5000))

        self.assertEqual(resultat['verdict'], 'mauvais')
        self.assertIsNone(resultat['dominante'])
        self.assertEqual(len(resultat['actions']), 2)
        self.assertIn('réparti', resultat['diagnostic'])

    def test_les_donnees_terrain_gagnent_sur_le_laboratoire(self):
        payload = psi_labo(PHASES_RENDU_LOURD)
        payload['loadingExperience'] = {'metrics': {
            'LARGEST_CONTENTFUL_PAINT_MS': {'percentile': 3000, 'category': 'AVERAGE'},
            'LARGEST_CONTENTFUL_PAINT_IMAGE_TIME_TO_FIRST_BYTE': {'percentile': 1900},
            'LARGEST_CONTENTFUL_PAINT_IMAGE_RESOURCE_LOAD_DELAY': {'percentile': 100},
            'LARGEST_CONTENTFUL_PAINT_IMAGE_RESOURCE_LOAD_DURATION': {'percentile': 700},
            'LARGEST_CONTENTFUL_PAINT_IMAGE_ELEMENT_RENDER_DELAY': {'percentile': 300},
        }}
        resultat = analyze_lcp_subparts(payload)

        self.assertEqual(resultat['source'], 'terrain')
        self.assertEqual(resultat['lcp_ms'], 3000)
        self.assertEqual(resultat['lcp_terrain_ms'], 3000)
        self.assertEqual(resultat['verdict_terrain'], 'a_ameliorer')
        self.assertEqual(resultat['sous_parties'][0]['ms'], 1900)
        self.assertEqual(resultat['dominante'], 'ttfb')
        self.assertEqual(resultat['notes'], [])

    def test_accepte_un_enregistrement_crux_brut(self):
        payload = {'record': {'metrics': {
            'largest_contentful_paint': {'percentiles': {'p75': 4000}},
            'largest_contentful_paint_image_time_to_first_byte': {'percentiles': {'p75': 1700}},
            'largest_contentful_paint_image_resource_load_delay': {'percentiles': {'p75': 200}},
            'largest_contentful_paint_image_resource_load_duration': {'percentiles': {'p75': 900}},
            'largest_contentful_paint_image_element_render_delay': {'percentiles': {'p75': 1200}},
        }}}
        resultat = analyze_lcp_subparts(payload)
        self.assertEqual(resultat['source'], 'terrain')
        self.assertEqual(resultat['dominante'], 'rendu')

    def test_reconstitue_le_total_quand_l_audit_lcp_manque(self):
        resultat = analyze_lcp_subparts(
            psi_labo(PHASES_RENDU_LOURD, avec_total=False))
        self.assertEqual(resultat['lcp_ms'], 4000)
        self.assertTrue(any('reconstitué' in note for note in resultat['notes']))

    def test_signale_les_phases_manquantes(self):
        resultat = analyze_lcp_subparts(
            psi_labo((('TTFB', 1800), ('Render Delay', 2200))))
        self.assertEqual(len(resultat['sous_parties']), 2)
        self.assertTrue(any('Phases absentes' in note for note in resultat['notes']))

    def test_note_que_le_laboratoire_n_est_pas_le_terrain(self):
        resultat = analyze_lcp_subparts(psi_labo(PHASES_RENDU_LOURD))
        self.assertTrue(any('laboratoire' in note for note in resultat['notes']))

    def test_charge_sans_audit_lcp(self):
        payload = {'lighthouseResult': {'audits': {
            'largest-contentful-paint': {'numericValue': 4000}}}}
        resultat = analyze_lcp_subparts(payload)
        self.assertEqual(resultat['source'], 'aucune')
        self.assertIn('largest-contentful-paint-element', resultat['erreur'])

    def test_charge_illisible_ne_leve_pas(self):
        for charge in (None, '', 'bonjour', [], {}, {'autre': 1}, 42):
            resultat = analyze_lcp_subparts(charge)
            self.assertIsNotNone(resultat['erreur'], repr(charge))
            self.assertEqual(resultat['sous_parties'], [])


# ---------------------------------------------------------------------------
# check_preload_signals
# ---------------------------------------------------------------------------

LIENS = (
    '<a href="/services">Services</a><a href="/tarifs">Tarifs</a>'
    '<a href="/contact">Contact</a><a href="/blogue">Blogue</a>'
    '<a href="/a-propos">A propos</a>'
)

PAGE_EXEMPLAIRE = """<!doctype html>
<html lang="fr-CA"><head>
<title>Deneigement residentiel a Levis</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter">
<link rel="preload" as="font" type="font/woff2" href="/polices/inter.woff2" crossorigin>
<script type="speculationrules">
{"prerender":[{"where":{"href_matches":"/services/*"},"eagerness":"moderate"}]}
</script>
</head><body><main>
<h1>Deneigement residentiel</h1>
<img src="/heros.jpg" alt="Camion de deneigement" width="1200" height="600"
     fetchpriority="high">
""" + LIENS + """
</main></body></html>"""

PAGE_A_PROBLEMES = """<!doctype html>
<html lang="fr-CA"><head>
<title>Deneigement</title>
<meta http-equiv="cache-control" content="no-store">
<link rel="preload" href="/styles/site.css">
<link rel="preload" as="font" href="/polices/inter.woff2">
<link rel="prerender" href="/services">
<script>window.addEventListener('unload', function () { pingServeur(); });</script>
</head><body><main>
<h1>Deneigement</h1>
<img src="/heros.jpg" alt="Camion de deneigement" loading="lazy">
""" + LIENS + """
</main></body></html>"""


def constats_pour(html, url='https://exemple.qc.ca/'):
    return check_preload_signals(extract_seo_signals(html, url), html)


def codes(constats):
    return [constat['code'] for constat in constats]


class PreloadPageExemplaireTests(SimpleTestCase):
    def test_une_page_bien_faite_ne_produit_aucun_constat(self):
        self.assertEqual(constats_pour(PAGE_EXEMPLAIRE), [])


class PreloadImageTests(SimpleTestCase):
    def test_image_du_haut_de_page_en_lazy(self):
        constats = constats_pour(PAGE_A_PROBLEMES)
        lazy = [c for c in constats if c['code'] == 'lcp_image_en_lazy']
        self.assertEqual(len(lazy), 1)
        self.assertEqual(lazy[0]['severity'], 'critical')
        self.assertEqual(lazy[0]['methode'], 'native')
        self.assertIn('/heros.jpg', lazy[0]['message'])

    def test_reconnait_le_lazy_loading_par_script(self):
        html = ('<html><body><img data-lazy-src="/heros.jpg" alt="Camion">'
                '<img src="/bas.jpg" alt="Bas"></body></html>')
        constats = constats_pour(html)
        lazy = [c for c in constats if c['code'] == 'lcp_image_en_lazy']
        self.assertEqual(lazy[0]['methode'], 'js-generic')

    def test_une_image_decorative_ne_compte_pas_comme_heros(self):
        html = ('<html><body><img src="/logo.svg" alt="" loading="lazy">'
                '<img src="/heros.jpg" alt="Camion" fetchpriority="high">'
                '</body></html>')
        self.assertNotIn('lcp_image_en_lazy', codes(constats_pour(html)))

    def test_aucune_image_prioritaire(self):
        constats = constats_pour(PAGE_A_PROBLEMES)
        priorite = [c for c in constats if c['code'] == 'lcp_sans_priorite']
        self.assertEqual(priorite[0]['severity'], 'high')

    def test_un_preload_image_suffit_a_marquer_la_priorite(self):
        html = ('<html><head><link rel="preload" as="image" href="/heros.jpg">'
                '</head><body><img src="/heros.jpg" alt="Camion"></body></html>')
        self.assertNotIn('lcp_sans_priorite', codes(constats_pour(html)))

    def test_priorite_diluee(self):
        html = ('<html><body>'
                '<img src="/a.jpg" alt="a" fetchpriority="high">'
                '<img src="/b.jpg" alt="b" fetchpriority="high">'
                '<img src="/c.jpg" alt="c" fetchpriority="high">'
                '</body></html>')
        self.assertIn('priorite_diluee', codes(constats_pour(html)))


class PreloadIndicesTests(SimpleTestCase):
    def test_preload_sans_attribut_as(self):
        constats = constats_pour(PAGE_A_PROBLEMES)
        self.assertIn('preload_sans_as', codes(constats))

    def test_police_prechargee_sans_crossorigin(self):
        constats = constats_pour(PAGE_A_PROBLEMES)
        self.assertIn('preload_police_sans_crossorigin', codes(constats))

    def test_trop_de_prechargements(self):
        head = ''.join(
            '<link rel="preload" as="image" href="/img%s.jpg">' % index
            for index in range(7)
        )
        html = '<html><head>%s</head><body><p>Bonjour</p></body></html>' % head
        self.assertIn('preload_excessif', codes(constats_pour(html)))

    def test_preconnexion_manquante_vers_un_tiers_lourd(self):
        html = ('<html><head><link rel="stylesheet" '
                'href="https://fonts.googleapis.com/css2?family=Inter">'
                '</head><body><p>Bonjour</p></body></html>')
        constats = [c for c in constats_pour(html)
                    if c['code'] == 'preconnect_manquant']
        self.assertEqual(constats[0]['hote'], 'fonts.googleapis.com')

    def test_preconnexion_de_police_sans_crossorigin(self):
        html = ('<html><head><link rel="preconnect" href="https://fonts.gstatic.com">'
                '</head><body><p>Bonjour</p></body></html>')
        self.assertIn('preconnect_sans_crossorigin', codes(constats_pour(html)))


class PreloadSpeculationTests(SimpleTestCase):
    def test_regles_absentes_sur_une_page_qui_maille(self):
        html = '<html><head></head><body><main>%s</main></body></html>' % LIENS
        self.assertIn('regles_speculation_absentes', codes(constats_pour(html)))

    def test_pas_de_reproche_a_une_page_sans_liens_internes(self):
        html = '<html><head></head><body><p>Page seule</p></body></html>'
        self.assertNotIn('regles_speculation_absentes', codes(constats_pour(html)))

    def test_regles_illisibles(self):
        html = ('<html><head><script type="speculationrules">{oups}</script>'
                '</head><body><main>%s</main></body></html>' % LIENS)
        self.assertIn('regles_speculation_invalides', codes(constats_pour(html)))

    def test_regles_sans_prerender(self):
        html = ('<html><head><script type="speculationrules">'
                '{"prefetch":[{"where":{"href_matches":"/*"}}]}</script>'
                '</head><body><main>%s</main></body></html>' % LIENS)
        self.assertIn('speculation_sans_prerender', codes(constats_pour(html)))

    def test_rel_prerender_deprecie(self):
        self.assertIn('rel_prerender_deprecie', codes(constats_pour(PAGE_A_PROBLEMES)))


class PreloadBfcacheTests(SimpleTestCase):
    def test_ecouteur_unload(self):
        constats = [c for c in constats_pour(PAGE_A_PROBLEMES)
                    if c['code'] == 'bfcache_unload']
        self.assertEqual(constats[0]['severity'], 'high')

    def test_meta_no_store(self):
        self.assertIn('bfcache_no_store', codes(constats_pour(PAGE_A_PROBLEMES)))

    def test_beforeunload_seul_reste_mineur(self):
        html = ('<html><head><script>'
                'window.addEventListener("beforeunload", garder);</script>'
                '</head><body><p>Bonjour</p></body></html>')
        constats = [c for c in constats_pour(html)
                    if c['code'] == 'bfcache_beforeunload']
        self.assertEqual(constats[0]['severity'], 'low')


class PreloadSortieTests(SimpleTestCase):
    def test_les_constats_sont_tries_par_severite(self):
        constats = constats_pour(PAGE_A_PROBLEMES)
        rangs = [SEVERITE_RANG[constat['severity']] for constat in constats]
        self.assertEqual(rangs, sorted(rangs))
        self.assertEqual(constats[0]['code'], 'lcp_image_en_lazy')

    def test_chaque_constat_porte_un_message_et_un_correctif(self):
        for html in (PAGE_A_PROBLEMES, PAGE_EXEMPLAIRE):
            for constat in constats_pour(html):
                self.assertTrue(constat['message'].strip(), constat['code'])
                self.assertTrue(constat['fix'].strip(), constat['code'])
                self.assertIn(constat['severity'], SEVERITE_RANG)

    def test_sans_html_seule_la_verification_des_images_tourne(self):
        signals = extract_seo_signals(PAGE_A_PROBLEMES, 'https://exemple.qc.ca/')
        constats = check_preload_signals(signals)
        self.assertEqual(set(codes(constats)), {'lcp_image_en_lazy', 'html_absent'})

    def test_entrees_vides_ne_levent_pas(self):
        for signals in (None, {}, {'images': 'pas une liste'}, []):
            self.assertIsInstance(check_preload_signals(signals, ''), list)
        self.assertIsInstance(check_preload_signals({}, '<html></html>'), list)

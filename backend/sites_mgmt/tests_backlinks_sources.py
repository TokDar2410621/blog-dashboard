"""Tests for the complementary backlink sources and the sufficiency gate.

Everything runs offline. `requests.post` and `requests.get` are patched on the
module itself, so what gets exercised is the real parsing, the real
deduplication and the real gate, with only the socket replaced. The two
credential leak tests are the ones that matter most: a key that reaches a log is
a key that has to be rotated.

Run all:
    python manage.py test sites_mgmt.tests_backlinks_sources
"""
import json
from unittest.mock import patch

from django.test import SimpleTestCase

from . import backlinks_sources
from .backlinks_sources import (
    CONFIANCE_SOURCES, MESSAGE_BING_VERIFICATION, data_sufficiency,
    fetch_bing_webmaster, fetch_moz, merge_sources, registrable_domain,
)

MOZ_ID = 'mozaccess123'
MOZ_SECRET = 'mozsecret456789'
BING_KEY = 'bingkey0123456789'


class FakeResponse:
    """Minimal stand-in for requests.Response."""

    def __init__(self, status=200, payload=None, text=None):
        self.status_code = status
        self._payload = payload
        self.text = text if text is not None else (
            json.dumps(payload) if payload is not None else ''
        )

    def json(self):
        if self._payload is None:
            raise ValueError('no json')
        return self._payload


def moz_metrics_payload(**champs):
    base = {
        'domain_authority': 34,
        'page_authority': 28,
        'spam_score': 2,
        'root_domains_to_root_domain': 51,
        'external_pages_to_root_domain': 402,
        'last_crawled': '2026-08-01',
    }
    base.update(champs)
    return {'results': [base]}


def moz_domains_payload(domaines):
    return {
        'results': [
            {
                'root_domain': nom,
                'domain_authority': da,
                'spam_score': spam,
                'to_target': {'pages': pages},
            }
            for nom, da, spam, pages in domaines
        ],
    }


def bing_counts_payload(cibles, total_pages=1):
    return {'d': {
        'Links': [{'Url': url, 'Count': count} for url, count in cibles],
        'TotalPages': total_pages,
    }}


def bing_details_payload(liens, total_pages=1):
    return {'d': {
        'Details': [{'Url': url, 'AnchorText': ancre} for url, ancre in liens],
        'TotalPages': total_pages,
    }}


# --------------------------------------------------------------------------
# registrable_domain
# --------------------------------------------------------------------------

class RegistrableDomainTests(SimpleTestCase):
    def test_collapses_subdomains_to_the_owner(self):
        for valeur in ('blog.exemple.com', 'www.exemple.com', 'https://a.b.exemple.com/x',
                       'EXEMPLE.COM', 'exemple.com.'):
            self.assertEqual(registrable_domain(valeur), 'exemple.com', valeur)

    def test_quebec_provincial_suffix_keeps_three_labels(self):
        self.assertEqual(registrable_domain('www.ville.saint-jerome.qc.ca'),
                         'saint-jerome.qc.ca')
        self.assertEqual(registrable_domain('clinique.qc.ca'), 'clinique.qc.ca')

    def test_two_quebec_towns_do_not_merge(self):
        # The whole dedup rests on this: collapsing to qc.ca would turn two
        # unrelated municipalities into one referring domain.
        self.assertNotEqual(registrable_domain('ville.laval.qc.ca'),
                            registrable_domain('ville.gatineau.qc.ca'))

    def test_other_multi_label_suffixes(self):
        self.assertEqual(registrable_domain('shop.example.co.uk'), 'example.co.uk')
        self.assertEqual(registrable_domain('news.example.com.au'), 'example.com.au')

    def test_ip_literal_and_garbage(self):
        self.assertEqual(registrable_domain('192.168.1.4'), '192.168.1.4')
        self.assertEqual(registrable_domain(''), '')
        self.assertEqual(registrable_domain('   '), '')
        self.assertEqual(registrable_domain(None), '')

    def test_url_with_port_and_path(self):
        self.assertEqual(registrable_domain('http://blog.exemple.com:8080/a/b?x=1'),
                         'exemple.com')


# --------------------------------------------------------------------------
# fetch_moz
# --------------------------------------------------------------------------

class FetchMozTests(SimpleTestCase):
    def test_missing_key_is_a_status_not_an_exception(self):
        resultat = fetch_moz('exemple.com', '', '')
        self.assertEqual(resultat['statut'], 'non_configure')
        self.assertEqual(resultat['erreur'], 'cle_absente')
        self.assertEqual(resultat['domaines_referents'], [])
        self.assertIn('Moz', resultat['message'])

    def test_malformed_domain_raises(self):
        with self.assertRaises(ValueError):
            fetch_moz('localhost', MOZ_ID, MOZ_SECRET)
        with self.assertRaises(ValueError):
            fetch_moz('', MOZ_ID, MOZ_SECRET)

    def test_happy_path_reads_authority_and_domains(self):
        reponses = [
            FakeResponse(200, moz_metrics_payload()),
            FakeResponse(200, moz_domains_payload([
                ('journaldequebec.com', 78, 1, 3),
                ('blogue-local.qc.ca', 21, 0, 1),
            ])),
        ]
        with patch.object(backlinks_sources.requests, 'post',
                          side_effect=reponses) as post:
            resultat = fetch_moz('https://www.exemple.com/page', MOZ_ID, MOZ_SECRET)

        self.assertEqual(resultat['statut'], 'ok')
        self.assertEqual(resultat['source'], 'moz')
        self.assertEqual(resultat['domaine'], 'exemple.com')
        self.assertEqual(resultat['confiance'], CONFIANCE_SOURCES['moz'])
        self.assertEqual(resultat['metriques']['autorite_domaine'], 34)
        self.assertEqual(resultat['metriques']['domaines_referents_total'], 51)
        self.assertEqual(len(resultat['domaines_referents']), 2)
        self.assertEqual(resultat['domaines_referents'][0]['domaine'], 'journaldequebec.com')
        self.assertEqual(resultat['domaines_referents'][0]['liens'], 3)
        # The target travels without scheme and without www.
        self.assertEqual(post.call_args_list[0].kwargs['json'], {'targets': ['exemple.com']})

    def test_basic_auth_header_is_built_from_the_two_credentials(self):
        with patch.object(backlinks_sources.requests, 'post',
                          side_effect=[FakeResponse(200, moz_metrics_payload()),
                                       FakeResponse(200, moz_domains_payload([]))]) as post:
            fetch_moz('exemple.com', MOZ_ID, MOZ_SECRET)
        entetes = post.call_args_list[0].kwargs['headers']
        self.assertTrue(entetes['Authorization'].startswith('Basic '))
        self.assertNotIn('x-moz-token', entetes)

    def test_single_token_uses_the_token_header(self):
        with patch.object(backlinks_sources.requests, 'post',
                          side_effect=[FakeResponse(200, moz_metrics_payload()),
                                       FakeResponse(200, moz_domains_payload([]))]) as post:
            fetch_moz('exemple.com', 'jeton-unique-moz', '')
        entetes = post.call_args_list[0].kwargs['headers']
        self.assertEqual(entetes['x-moz-token'], 'jeton-unique-moz')
        self.assertNotIn('Authorization', entetes)

    def test_rate_limit_is_reported_not_slept_away(self):
        with patch.object(backlinks_sources.time, 'sleep') as dodo:
            with patch.object(backlinks_sources.requests, 'post',
                              return_value=FakeResponse(429)):
                resultat = fetch_moz('exemple.com', MOZ_ID, MOZ_SECRET)
        self.assertEqual(resultat['statut'], 'limite_atteinte')
        self.assertFalse(dodo.called)
        self.assertIn('Quota Moz', resultat['message'])

    def test_no_sleep_by_default_between_the_two_calls(self):
        with patch.object(backlinks_sources.time, 'sleep') as dodo:
            with patch.object(backlinks_sources.requests, 'post',
                              side_effect=[FakeResponse(200, moz_metrics_payload()),
                                           FakeResponse(200, moz_domains_payload([]))]):
                fetch_moz('exemple.com', MOZ_ID, MOZ_SECRET)
        self.assertFalse(dodo.called)

    def test_pause_is_honoured_when_a_worker_asks_for_it(self):
        with patch.object(backlinks_sources.time, 'sleep') as dodo:
            with patch.object(backlinks_sources.requests, 'post',
                              side_effect=[FakeResponse(200, moz_metrics_payload()),
                                           FakeResponse(200, moz_domains_payload([]))]):
                fetch_moz('exemple.com', MOZ_ID, MOZ_SECRET, pause_s=10)
        dodo.assert_called_once_with(10)

    def test_second_call_failure_keeps_authority_as_partial(self):
        with patch.object(backlinks_sources.requests, 'post',
                          side_effect=[FakeResponse(200, moz_metrics_payload()),
                                       FakeResponse(403)]):
            resultat = fetch_moz('exemple.com', MOZ_ID, MOZ_SECRET)
        self.assertEqual(resultat['statut'], 'partiel')
        self.assertEqual(resultat['metriques']['autorite_domaine'], 34)
        self.assertEqual(resultat['domaines_referents'], [])

    def test_unauthorized_key(self):
        with patch.object(backlinks_sources.requests, 'post',
                          return_value=FakeResponse(401)):
            resultat = fetch_moz('exemple.com', MOZ_ID, MOZ_SECRET)
        self.assertEqual(resultat['statut'], 'non_autorise')

    def test_timeout_comes_back_as_a_status(self):
        with patch.object(backlinks_sources.requests, 'post',
                          side_effect=backlinks_sources.requests.exceptions.Timeout()):
            resultat = fetch_moz('exemple.com', MOZ_ID, MOZ_SECRET)
        self.assertEqual(resultat['statut'], 'erreur')
        self.assertIn('délai', resultat['message'])

    def test_empty_answer_is_vide_not_error(self):
        with patch.object(backlinks_sources.requests, 'post',
                          side_effect=[FakeResponse(200, {'results': []}),
                                       FakeResponse(200, {'results': []})]):
            resultat = fetch_moz('exemple-tout-neuf.com', MOZ_ID, MOZ_SECRET)
        self.assertEqual(resultat['statut'], 'vide')
        self.assertEqual(resultat['metriques'], {})

    def test_garbage_payload_does_not_crash(self):
        with patch.object(backlinks_sources.requests, 'post',
                          side_effect=[FakeResponse(200, {'results': ['pas un objet']}),
                                       FakeResponse(200, {'results': [{'root_domain': ''},
                                                                      'texte',
                                                                      {'root_domain': 'ok.com'}]})]):
            resultat = fetch_moz('exemple.com', MOZ_ID, MOZ_SECRET)
        self.assertEqual([item['domaine'] for item in resultat['domaines_referents']], ['ok.com'])

    def test_credentials_never_appear_in_a_message(self):
        # Moz echoes the query back inside its error body; the scrubber has to
        # catch it before the message reaches a log.
        corps = {'error': 'bad request for %s:%s' % (MOZ_ID, MOZ_SECRET)}
        with patch.object(backlinks_sources.requests, 'post',
                          return_value=FakeResponse(400, corps)):
            resultat = fetch_moz('exemple.com', MOZ_ID, MOZ_SECRET)
        rendu = json.dumps(resultat, ensure_ascii=False)
        self.assertNotIn(MOZ_ID, rendu)
        self.assertNotIn(MOZ_SECRET, rendu)
        self.assertIn('***', resultat['message'])

    def test_request_exception_message_carries_no_url(self):
        exception = backlinks_sources.requests.exceptions.ConnectionError(
            'failed for https://api.moz.com/v2/url_metrics?apikey=%s' % MOZ_SECRET
        )
        with patch.object(backlinks_sources.requests, 'post', side_effect=exception):
            resultat = fetch_moz('exemple.com', MOZ_ID, MOZ_SECRET)
        self.assertNotIn(MOZ_SECRET, json.dumps(resultat, ensure_ascii=False))
        self.assertIn('ConnectionError', resultat['message'])

    def test_domains_call_can_be_skipped(self):
        with patch.object(backlinks_sources.requests, 'post',
                          return_value=FakeResponse(200, moz_metrics_payload())) as post:
            resultat = fetch_moz('exemple.com', MOZ_ID, MOZ_SECRET, inclure_domaines=False)
        self.assertEqual(post.call_count, 1)
        self.assertEqual(resultat['statut'], 'ok')


# --------------------------------------------------------------------------
# fetch_bing_webmaster
# --------------------------------------------------------------------------

class FetchBingTests(SimpleTestCase):
    def test_missing_key_states_the_verification_constraint(self):
        resultat = fetch_bing_webmaster('exemple.com', '')
        self.assertEqual(resultat['statut'], 'non_configure')
        self.assertIn('vérifiés dans le compte', resultat['message'])

    def test_happy_path_builds_referring_domains(self):
        reponses = [
            bing_counts_payload([('https://exemple.com/blogue', 4),
                                 ('https://exemple.com/', 2)]),
            bing_details_payload([('https://lapresse.ca/article-1', 'plombier Laval'),
                                  ('https://blogue.lapresse.ca/autre', 'ici')]),
            bing_details_payload([('https://annuaire.qc.ca/fiche', 'Exemple inc')]),
        ]
        with patch.object(backlinks_sources.requests, 'get',
                          side_effect=[FakeResponse(200, charge) for charge in reponses]) as get:
            resultat = fetch_bing_webmaster('exemple.com', BING_KEY)

        self.assertEqual(resultat['statut'], 'ok')
        self.assertEqual(resultat['confiance'], CONFIANCE_SOURCES['bing_webmaster'])
        noms = [item['domaine'] for item in resultat['domaines_referents']]
        # lapresse.ca and blogue.lapresse.ca are one referring domain.
        self.assertEqual(noms, ['lapresse.ca', 'annuaire.qc.ca'])
        lapresse = resultat['domaines_referents'][0]
        self.assertEqual(lapresse['liens'], 2)
        self.assertIn('plombier Laval', lapresse['ancres'])
        self.assertEqual(get.call_count, 3)

    def test_internal_links_are_not_counted_as_backlinks(self):
        reponses = [
            bing_counts_payload([('https://exemple.com/blogue', 3)]),
            bing_details_payload([('https://exemple.com/accueil', 'accueil'),
                                  ('https://www.exemple.com/a-propos', 'à propos'),
                                  ('https://tiers.com/article', 'exemple')]),
        ]
        with patch.object(backlinks_sources.requests, 'get',
                          side_effect=[FakeResponse(200, charge) for charge in reponses]):
            resultat = fetch_bing_webmaster('exemple.com', BING_KEY)
        self.assertEqual([item['domaine'] for item in resultat['domaines_referents']],
                         ['tiers.com'])
        self.assertEqual(resultat['brut']['liens_internes'], 2)

    def test_forbidden_says_the_site_must_be_verified(self):
        with patch.object(backlinks_sources.requests, 'get',
                          return_value=FakeResponse(403)):
            resultat = fetch_bing_webmaster('site-client.com', BING_KEY)
        self.assertEqual(resultat['statut'], 'non_autorise')
        self.assertIn(MESSAGE_BING_VERIFICATION, resultat['message'])

    def test_no_links_at_all_is_vide(self):
        with patch.object(backlinks_sources.requests, 'get',
                          return_value=FakeResponse(200, bing_counts_payload([]))):
            resultat = fetch_bing_webmaster('exemple.com', BING_KEY)
        self.assertEqual(resultat['statut'], 'vide')
        self.assertEqual(resultat['domaines_referents'], [])

    def test_redirects_are_refused_because_the_key_is_in_the_query(self):
        with patch.object(backlinks_sources.requests, 'get',
                          return_value=FakeResponse(200, bing_counts_payload([]))) as get:
            fetch_bing_webmaster('exemple.com', BING_KEY)
        self.assertIs(get.call_args.kwargs['allow_redirects'], False)

    def test_key_never_leaks_into_a_message(self):
        exception = backlinks_sources.requests.exceptions.ConnectionError(
            'failed for https://ssl.bing.com/webmaster/api.svc/json/GetLinkCounts?apikey=%s'
            % BING_KEY
        )
        with patch.object(backlinks_sources.requests, 'get', side_effect=exception):
            resultat = fetch_bing_webmaster('exemple.com', BING_KEY)
        self.assertNotIn(BING_KEY, json.dumps(resultat, ensure_ascii=False))

    def test_http_error_message_carries_no_key(self):
        with patch.object(backlinks_sources.requests, 'get',
                          return_value=FakeResponse(500, text='apikey=%s rejected' % BING_KEY)):
            resultat = fetch_bing_webmaster('exemple.com', BING_KEY)
        self.assertEqual(resultat['statut'], 'erreur')
        self.assertNotIn(BING_KEY, json.dumps(resultat, ensure_ascii=False))

    def test_call_count_is_bounded_by_limite_cibles(self):
        cibles = [('https://exemple.com/p%d' % index, 10 - index) for index in range(8)]
        reponses = [FakeResponse(200, bing_counts_payload(cibles))]
        reponses += [FakeResponse(200, bing_details_payload([]))] * 8
        with patch.object(backlinks_sources.requests, 'get', side_effect=reponses) as get:
            fetch_bing_webmaster('exemple.com', BING_KEY, limite_cibles=3)
        self.assertEqual(get.call_count, 4)  # 1 discovery + 3 expansions

    def test_expansion_failure_on_every_target_is_an_error(self):
        reponses = [FakeResponse(200, bing_counts_payload([('https://exemple.com/a', 1)])),
                    FakeResponse(500)]
        with patch.object(backlinks_sources.requests, 'get', side_effect=reponses):
            resultat = fetch_bing_webmaster('exemple.com', BING_KEY)
        self.assertEqual(resultat['statut'], 'erreur')
        self.assertEqual(resultat['erreur'], 'expansion_impossible')

    def test_empty_body_does_not_crash(self):
        with patch.object(backlinks_sources.requests, 'get',
                          return_value=FakeResponse(200, text='   ')):
            resultat = fetch_bing_webmaster('exemple.com', BING_KEY)
        self.assertEqual(resultat['statut'], 'vide')


# --------------------------------------------------------------------------
# merge_sources
# --------------------------------------------------------------------------

def source_moz(domaines, **metriques):
    base = {'autorite_domaine': 34}
    base.update(metriques)
    return {
        'source': 'moz', 'statut': 'ok', 'confiance': 0.85, 'domaine': 'exemple.com',
        'metriques': base,
        'domaines_referents': domaines,
    }


class MergeSourcesTests(SimpleTestCase):
    def test_deduplicates_by_registrable_domain_across_sources(self):
        sources = [
            source_moz([{'domaine': 'www.lapresse.ca', 'autorite_domaine': 88, 'liens': 2}]),
            {'source': 'bing_webmaster', 'statut': 'ok', 'domaine': 'exemple.com',
             'domaines_referents': [{'domaine': 'blogue.lapresse.ca', 'liens': 1}]},
            {'source': 'commoncrawl', 'statut': 'ok', 'domaine': 'exemple.com',
             'domaines_referents': ['https://lapresse.ca/section/x']},
        ]
        fusion = merge_sources(sources)
        self.assertEqual(fusion['total_domaines_referents'], 1)
        entree = fusion['domaines_referents'][0]
        self.assertEqual(entree['domaine'], 'lapresse.ca')
        self.assertEqual(entree['sources'], ['bing_webmaster', 'commoncrawl', 'moz'])
        self.assertEqual(entree['nb_sources'], 3)

    def test_confidence_grows_with_the_number_of_sources(self):
        seule = merge_sources([
            {'source': 'commoncrawl', 'statut': 'ok', 'domaines_referents': ['a.com']},
        ])['domaines_referents'][0]
        trois = merge_sources([
            {'source': 'commoncrawl', 'statut': 'ok', 'domaines_referents': ['a.com']},
            {'source': 'moz', 'statut': 'ok', 'domaines_referents': ['a.com']},
            {'source': 'bing_webmaster', 'statut': 'ok', 'domaines_referents': ['a.com']},
        ])['domaines_referents'][0]
        self.assertEqual(seule['confiance'], 0.5)
        self.assertGreater(trois['confiance'], seule['confiance'])
        self.assertLessEqual(trois['confiance'], 1.0)
        # noisy-OR: 1 - 0.5 * 0.15 * 0.30
        self.assertAlmostEqual(trois['confiance'], 0.9775, places=4)

    def test_a_source_listing_a_domain_twice_votes_once(self):
        fusion = merge_sources([
            {'source': 'moz', 'statut': 'ok',
             'domaines_referents': ['www.a.com', 'blog.a.com', 'a.com']},
        ])
        entree = fusion['domaines_referents'][0]
        self.assertEqual(entree['nb_sources'], 1)
        self.assertEqual(entree['confiance'], 0.85)
        self.assertEqual(fusion['sources'][0]['domaines_apportes'], 1)

    def test_multi_source_domains_are_ranked_first(self):
        fusion = merge_sources([
            {'source': 'moz', 'statut': 'ok',
             'domaines_referents': [{'domaine': 'solo.com', 'autorite_domaine': 90}]},
            {'source': 'commoncrawl', 'statut': 'ok', 'domaines_referents': ['duo.com']},
            {'source': 'bing_webmaster', 'statut': 'ok', 'domaines_referents': ['duo.com']},
        ])
        self.assertEqual(fusion['domaines_referents'][0]['domaine'], 'duo.com')
        self.assertEqual(fusion['domaines_multi_sources'], 1)

    def test_self_references_are_dropped(self):
        fusion = merge_sources([
            source_moz(['exemple.com', 'www.exemple.com', 'tiers.com']),
        ])
        self.assertEqual([item['domaine'] for item in fusion['domaines_referents']],
                         ['tiers.com'])
        self.assertEqual(fusion['ignores']['auto_references'], 2)
        self.assertEqual(fusion['domaine'], 'exemple.com')

    def test_metric_takes_the_most_confident_source(self):
        fusion = merge_sources([
            {'source': 'commoncrawl', 'statut': 'ok',
             'metriques': {'domaines_referents_total': 12}},
            source_moz([], domaines_referents_total=51),
        ])
        metrique = fusion['metriques']['domaines_referents_total']
        self.assertEqual(metrique['valeur'], 51)
        self.assertEqual(metrique['source'], 'moz')
        self.assertEqual(metrique['autres'], [{'source': 'commoncrawl', 'valeur': 12}])

    def test_wide_disagreement_is_surfaced(self):
        fusion = merge_sources([
            {'source': 'commoncrawl', 'statut': 'ok',
             'metriques': {'liens_externes_total': 10}},
            {'source': 'moz', 'statut': 'ok',
             'metriques': {'liens_externes_total': 900}},
        ])
        self.assertTrue(fusion['metriques']['liens_externes_total']['desaccord'])
        self.assertEqual(len(fusion['desaccords']), 1)
        self.assertEqual(fusion['desaccords'][0]['metrique'], 'liens_externes_total')

    def test_close_readings_are_not_flagged(self):
        fusion = merge_sources([
            {'source': 'commoncrawl', 'statut': 'ok', 'metriques': {'autorite_domaine': 30}},
            {'source': 'moz', 'statut': 'ok', 'metriques': {'autorite_domaine': 34}},
        ])
        self.assertFalse(fusion['metriques']['autorite_domaine']['desaccord'])
        self.assertEqual(fusion['desaccords'], [])

    def test_reads_the_upstream_cli_envelope(self):
        moz_envelope = {
            'status': 'success',
            'data': {'target': 'exemple.com', 'referring_domains': [
                {'domain': 'lapresse.ca', 'domain_authority': 88, 'spam_score': 1,
                 'links_to_target': 4},
            ]},
            'error': None,
            'metadata': {'source': 'moz'},
        }
        cc_envelope = {
            'status': 'success',
            'data': {'domain': 'exemple.com', 'in_crawl': True, 'pagerank': 0.0000123,
                     'harmonic_centrality': 4.2},
            'error': None,
            'metadata': {'source': 'commoncrawl'},
        }
        fusion = merge_sources([moz_envelope, cc_envelope])
        self.assertEqual(fusion['total_domaines_referents'], 1)
        entree = fusion['domaines_referents'][0]
        self.assertEqual(entree['autorite_domaine'], 88)
        self.assertEqual(entree['liens'], 4)
        self.assertIn('pagerank', fusion['metriques'])
        self.assertEqual(fusion['metriques']['centralite_harmonique']['valeur'], 4.2)

    def test_reads_the_bing_envelope_links_shape(self):
        bing_envelope = {
            'status': 'partial',
            'data': {'site_url': 'https://exemple.com/', 'links': [
                {'source_url': 'https://annuaire.qc.ca/fiche', 'target_url': 'https://exemple.com/',
                 'anchor_text': 'Exemple inc'},
            ]},
            'metadata': {'source': 'bing_webmaster'},
        }
        fusion = merge_sources([bing_envelope])
        entree = fusion['domaines_referents'][0]
        self.assertEqual(entree['domaine'], 'annuaire.qc.ca')
        self.assertEqual(entree['ancres'], ['Exemple inc'])
        self.assertEqual(fusion['sources'][0]['statut'], 'partiel')

    def test_worst_spam_and_best_authority_win(self):
        fusion = merge_sources([
            {'source': 'moz', 'statut': 'ok', 'domaines_referents': [
                {'domaine': 'douteux.com', 'autorite_domaine': 12, 'score_spam': 71}]},
            {'source': 'dataforseo', 'statut': 'ok', 'domaines_referents': [
                {'domaine': 'douteux.com', 'autorite_domaine': 20, 'score_spam': 3}]},
        ])
        entree = fusion['domaines_referents'][0]
        self.assertEqual(entree['autorite_domaine'], 20)
        self.assertEqual(entree['score_spam'], 71)

    def test_garbage_in_does_not_crash(self):
        fusion = merge_sources(['pas un dict', None, 42,
                                {'source': 'moz', 'statut': 'ok',
                                 'domaines_referents': [None, 7, {'domaine': ''},
                                                        'bon.com']}])
        self.assertEqual(fusion['total_domaines_referents'], 1)
        self.assertEqual(fusion['ignores']['sources_illisibles'], 3)
        self.assertEqual(fusion['ignores']['entrees_illisibles'], 3)

    def test_empty_input(self):
        fusion = merge_sources([])
        self.assertEqual(fusion['total_domaines_referents'], 0)
        self.assertIsNone(fusion['domaine'])
        self.assertIsNone(fusion['confiance_moyenne'])
        self.assertEqual(fusion['couverture']['sources_avec_donnees'], 0)
        self.assertEqual(len(fusion['couverture']['axes_manquants']), 5)
        self.assertIsInstance(merge_sources(None)['sources'], list)

    def test_coverage_lists_the_axes_actually_read(self):
        fusion = merge_sources([
            source_moz([{'domaine': 'a.com', 'autorite_domaine': 40, 'score_spam': 2}],
                       liens_externes_total=100),
            {'source': 'bing_webmaster', 'statut': 'ok', 'domaines_referents': [
                {'domaine': 'b.com', 'ancre': 'plombier Laval'}]},
        ])
        axes = fusion['couverture']['axes_couverts']
        for attendu in ('domaines_referents', 'autorite', 'spam', 'ancres', 'volume_liens'):
            self.assertIn(attendu, axes)
        self.assertEqual(fusion['couverture']['axes_manquants'], [])

    def test_anchor_and_url_caps_are_honoured(self):
        fusion = merge_sources([
            {'source': 'moz', 'statut': 'ok', 'domaines_referents': [
                {'domaine': 'a.com', 'ancres': ['un', 'deux', 'trois', 'quatre'],
                 'urls': ['https://a.com/1', 'https://a.com/2', 'https://a.com/3']},
            ]},
        ], ancres_max=2, urls_max=1)
        entree = fusion['domaines_referents'][0]
        self.assertEqual(len(entree['ancres']), 2)
        self.assertEqual(len(entree['urls']), 1)

    def test_common_crawl_payload_drops_in_as_is(self):
        # Shape of `backlinks_commoncrawl.referring_domains`: it names itself in
        # a nested descriptor and spells its metrics flat.
        cc = {
            'domaine': 'exemple.com',
            'version': 'cc-main-2026-may',
            'jeu_de_donnees': {'source': 'Common Crawl, graphe de domaines'},
            'pagerank': 1.2e-05,
            'centralite_harmonique': 4.2,
            'domaines_referents': [
                {'domaine': 'lapresse.ca', 'centralite_harmonique_rang': 900,
                 'niveau': 'fort'},
                {'domaine': 'petit.qc.ca', 'niveau': 'inconnu'},
            ],
            'erreur': None,
        }
        fusion = merge_sources([cc])
        ligne = fusion['sources'][0]
        self.assertEqual(ligne['source'], 'commoncrawl')
        self.assertEqual(ligne['confiance'], CONFIANCE_SOURCES['commoncrawl'])
        self.assertEqual(ligne['statut'], 'ok')
        self.assertEqual(fusion['total_domaines_referents'], 2)
        self.assertEqual(fusion['metriques']['centralite_harmonique']['valeur'], 4.2)
        self.assertTrue(data_sufficiency([cc], floor=1)['score_autorise'])

    def test_a_source_carrying_an_error_never_reads_as_answered(self):
        # Without this, a Common Crawl run that failed on the network would feed
        # the empty-profile branch and publish a zero built on nothing.
        casse = {
            'domaine': 'exemple.com',
            'jeu_de_donnees': {'source': 'Common Crawl, graphe de domaines'},
            'domaines_referents': [],
            'erreur': 'telechargement interrompu',
        }
        verdict = data_sufficiency([casse, {'source': 'moz', 'statut': 'vide'}])
        self.assertEqual(verdict['details'][0]['statut'], 'erreur')
        self.assertFalse(verdict['details'][0]['a_repondu'])
        self.assertFalse(verdict['score_autorise'])
        self.assertEqual(verdict['niveau'], 'insuffisant')

    def test_referring_urls_are_stripped_of_query_strings(self):
        fusion = merge_sources([
            {'source': 'bing_webmaster', 'statut': 'ok', 'domaines_referents': [
                {'source_url': 'https://a.com/page?session=secret#x'}]},
        ])
        self.assertEqual(fusion['domaines_referents'][0]['urls'], ['https://a.com/page'])


# --------------------------------------------------------------------------
# data_sufficiency
# --------------------------------------------------------------------------

class DataSufficiencyTests(SimpleTestCase):
    def test_two_sources_with_data_unlock_the_score(self):
        verdict = data_sufficiency([
            source_moz(['a.com']),
            {'source': 'commoncrawl', 'statut': 'ok', 'metriques': {'pagerank': 0.001}},
        ])
        self.assertTrue(verdict['score_autorise'])
        self.assertEqual(verdict['niveau'], 'suffisant')
        self.assertEqual(verdict['sources_avec_donnees'], 2)
        self.assertIn('Le score peut être calculé', verdict['message'])

    def test_one_source_refuses_the_score_and_says_why(self):
        verdict = data_sufficiency([
            source_moz(['a.com']),
            {'source': 'bing_webmaster', 'statut': 'non_autorise'},
        ])
        self.assertFalse(verdict['score_autorise'])
        self.assertEqual(verdict['niveau'], 'insuffisant')
        self.assertIn('non calculé', verdict['message'])
        self.assertIn('personne n a regardé', verdict['message'])
        self.assertIn('Common Crawl', verdict['message'])

    def test_no_source_at_all(self):
        verdict = data_sufficiency([])
        self.assertFalse(verdict['score_autorise'])
        self.assertEqual(verdict['sources_totales'], 0)
        self.assertIn('aucune source', verdict['message'])
        self.assertEqual(len(verdict['suggestions']), 3)

    def test_empty_profile_is_scoreable_when_every_source_answered(self):
        # A brand new site: the sources looked and found nothing. That is a
        # measurement, not a hole, so the gate lets the zero through.
        verdict = data_sufficiency([
            {'source': 'commoncrawl', 'statut': 'vide'},
            {'source': 'moz', 'statut': 'vide'},
        ])
        self.assertTrue(verdict['score_autorise'])
        self.assertEqual(verdict['niveau'], 'profil_vide')
        self.assertIn('vide, pas inconnu', verdict['message'])

    def test_one_answer_and_one_failure_is_still_insufficient(self):
        verdict = data_sufficiency([
            {'source': 'commoncrawl', 'statut': 'vide'},
            {'source': 'moz', 'statut': 'erreur'},
        ])
        self.assertFalse(verdict['score_autorise'])
        self.assertEqual(verdict['niveau'], 'insuffisant')

    def test_failed_sources_never_count_as_data(self):
        verdict = data_sufficiency([
            {'source': 'moz', 'statut': 'erreur', 'domaines_referents': ['a.com']},
            {'source': 'bing_webmaster', 'statut': 'limite_atteinte'},
            {'source': 'commoncrawl', 'statut': 'non_configure'},
        ])
        self.assertEqual(verdict['sources_avec_donnees'], 0)
        self.assertFalse(verdict['score_autorise'])
        raisons = [detail['raison'] for detail in verdict['details']]
        self.assertIn('Appel en échec.', raisons)
        self.assertIn('Quota atteint chez le fournisseur.', raisons)

    def test_floor_is_configurable(self):
        sources = [source_moz(['a.com'])]
        self.assertTrue(data_sufficiency(sources, floor=1)['score_autorise'])
        self.assertFalse(data_sufficiency(sources, floor=3)['score_autorise'])

    def test_counts_agree_with_the_french_they_are_printed_in(self):
        une = data_sufficiency([source_moz(['a.com'])], floor=1)
        self.assertIn('1 source porte des données', une['message'])
        deux = data_sufficiency([
            source_moz(['a.com']),
            {'source': 'commoncrawl', 'statut': 'ok', 'domaines_referents': ['b.com']},
        ])
        self.assertIn('2 sources portent des données', deux['message'])
        # Two sources carrying data but a floor of three: the refusal must not
        # claim a single source.
        trois = data_sufficiency([
            source_moz(['a.com']),
            {'source': 'commoncrawl', 'statut': 'ok', 'domaines_referents': ['b.com']},
        ], floor=3)
        self.assertFalse(trois['score_autorise'])
        self.assertIn('2 sources portent des données', trois['message'])
        self.assertNotIn('une seule source', trois['message'])
        vide = data_sufficiency([{'source': 'commoncrawl', 'statut': 'vide'}], floor=1)
        self.assertIn('1 source a répondu', vide['message'])

    def test_cumulative_confidence_uses_noisy_or(self):
        verdict = data_sufficiency([
            source_moz(['a.com']),
            {'source': 'commoncrawl', 'statut': 'ok', 'domaines_referents': ['b.com']},
        ])
        self.assertAlmostEqual(verdict['confiance_cumulee'], 0.925, places=4)

    def test_suggestions_skip_what_is_already_plugged_in(self):
        verdict = data_sufficiency([
            {'source': 'commoncrawl', 'statut': 'ok', 'domaines_referents': ['a.com']},
        ])
        proposees = [item['source'] for item in verdict['suggestions']]
        self.assertNotIn('commoncrawl', proposees)
        self.assertEqual(proposees, ['moz', 'bing_webmaster'])

    def test_bing_suggestion_carries_the_verification_warning(self):
        verdict = data_sufficiency([])
        bing = [item for item in verdict['suggestions'] if item['source'] == 'bing_webmaster'][0]
        self.assertIn('vérifié', bing['contrainte'])
        self.assertIn('Gridar', bing['contrainte'])

    def test_real_fetchers_feed_the_gate_end_to_end(self):
        with patch.object(backlinks_sources.requests, 'post',
                          side_effect=[FakeResponse(200, moz_metrics_payload()),
                                       FakeResponse(200, moz_domains_payload([
                                           ('lapresse.ca', 88, 1, 2)]))]):
            moz = fetch_moz('exemple.com', MOZ_ID, MOZ_SECRET)
        with patch.object(backlinks_sources.requests, 'get',
                          side_effect=[
                              FakeResponse(200, bing_counts_payload(
                                  [('https://exemple.com/', 1)])),
                              FakeResponse(200, bing_details_payload(
                                  [('https://www.lapresse.ca/autre', 'exemple')])),
                          ]):
            bing = fetch_bing_webmaster('exemple.com', BING_KEY)

        verdict = data_sufficiency([moz, bing])
        self.assertTrue(verdict['score_autorise'])
        fusion = merge_sources([moz, bing])
        self.assertEqual(fusion['total_domaines_referents'], 1)
        self.assertEqual(fusion['domaines_referents'][0]['nb_sources'], 2)
        self.assertEqual(fusion['domaine'], 'exemple.com')

    def test_garbage_input(self):
        verdict = data_sufficiency(None)
        self.assertEqual(verdict['sources_totales'], 0)
        self.assertFalse(verdict['score_autorise'])
        verdict = data_sufficiency(['texte', 5])
        self.assertEqual(verdict['sources_totales'], 0)

    def test_no_credential_can_reach_the_gate_output(self):
        with patch.object(backlinks_sources.requests, 'post',
                          return_value=FakeResponse(400, {'error': MOZ_SECRET})):
            moz = fetch_moz('exemple.com', MOZ_ID, MOZ_SECRET)
        rendu = json.dumps(data_sufficiency([moz]), ensure_ascii=False)
        self.assertNotIn(MOZ_SECRET, rendu)
        self.assertNotIn(MOZ_ID, rendu)

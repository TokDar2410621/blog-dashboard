"""Tests for dating a traffic drop against Google's confirmed update history.

Fully offline: the module reads one bundled JSON file and does date math, so
there is nothing to mock except the file itself in the failure cases. Every
assertion that depends on "now" injects its own reference date, otherwise the
suite would start failing on its own the day the changelog goes stale.

Run all:
    python manage.py test sites_mgmt.tests_google_updates
"""
import json
import re
from datetime import date
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase

from . import google_updates as gu
from .google_updates import (
    GoogleUpdatesError, KIND_LABELS_FR, data_freshness, explain_traffic_drop,
    traffic_drop_report, updates_in_window,
)

# Anchors taken from the shipped file. Hardcoded on purpose: when a future sync
# renames or moves one of these, the suite says so instead of silently drifting.
MAY_2026_CORE = 'May 2026 Core Update'          # 2026-05-21, 11-day rollout
FEB_2026_DISCOVER = 'February 2026 Discover Update'   # 2026-02-05, 21-day rollout
JUNE_2026_SPAM = 'June 2026 Spam Update'        # 2026-06-24, 2-day rollout
FAQ_RETIRED = 'FAQ rich results retired'        # 2026-05-07, schema, no rollout


def _names(items):
    return [i['name'] for i in items]


def _by_name(items, name):
    for item in items:
        if item['name'] == name:
            return item
    raise AssertionError(f'{name!r} not in {_names(items)}')


class DataFileTests(SimpleTestCase):
    """The JSON is the whole product here, so it gets checked like code."""

    def setUp(self):
        self.data = gu._load()

    def test_envelope_present(self):
        self.assertTrue(self.data['last_verified'])
        self.assertTrue(self.data['source_of_truth'].startswith('https://'))
        self.assertGreater(len(self.data['updates']), 20)

    def test_every_entry_is_usable(self):
        for entry in self.data['updates']:
            with self.subTest(entry=entry.get('name')):
                date.fromisoformat(entry['date'])
                self.assertTrue(entry['name'])
                self.assertIn(entry['kind'], KIND_LABELS_FR)
                self.assertTrue(entry['source'].startswith('https://'))

    def test_every_source_is_google_owned(self):
        """Upstream's rule: an entry without a Google URL is a rumor."""
        for entry in self.data['updates']:
            with self.subTest(entry=entry['name']):
                self.assertRegex(
                    entry['source'],
                    r'https://[a-z0-9.\-]*\.?(google\.com|blog\.google|web\.dev|chrome\.com)/',
                )

    def test_no_foreign_dashes_in_shipped_prose(self):
        """Em and en dashes are banned across Gridar's UI copy, data included."""
        raw = (Path(gu.__file__).resolve().parent / 'data' / 'google_updates.json').read_text('utf-8')
        self.assertNotIn('—', raw)
        self.assertNotIn('–', raw)


class RolloutParsingTests(SimpleTestCase):
    """Rollout length lives in upstream's free prose, so the parser is load-bearing."""

    def test_known_prose_forms(self):
        cases = [
            ('24-day rollout.', 24, False),
            ('Tight rollout (~7 days).', 7, False),
            ('Started Mar 27, completed Apr 8 (12-day rollout).', 12, False),
            ('Completed June 2, 2026 (~11d21h rollout).', 11, False),
            ('(started Feb 5, ~21d rollout, English/US first)', 21, False),
            ('Started June 24, completed June 26 (~2d1h rollout).', 2, False),
            ('Fastest spam update on record, 19h30m rollout (completed under a day).', 0, False),
            ('No duration stated at all.', 14, True),
            ('', 14, True),
        ]
        for notes, days, estimated in cases:
            with self.subTest(notes=notes):
                self.assertEqual(
                    gu._rollout_days({'kind': 'core', 'notes': notes}), (days, estimated),
                )

    def test_hour_form_never_read_as_days(self):
        """'~11d21h rollout' must not come back as a 21-day window."""
        days, _ = gu._rollout_days({'kind': 'core', 'notes': '(~11d21h rollout)'})
        self.assertEqual(days, 11)

    def test_defaults_are_per_kind(self):
        self.assertEqual(gu._rollout_days({'kind': 'spam', 'notes': ''}), (5, True))
        self.assertEqual(gu._rollout_days({'kind': 'schema', 'notes': ''}), (0, True))

    def test_absurd_value_is_capped(self):
        days, _ = gu._rollout_days({'kind': 'core', 'notes': '900-day rollout'})
        self.assertEqual(days, gu._MAX_ROLLOUT_DAYS)

    def test_shipped_entries_still_parse(self):
        """Drift guard: a reworded note upstream shows up here, not in prod."""
        expected = {
            '2024-11-11': 24, '2024-12-12': 7, '2025-03-13': 14, '2025-06-30': 16,
            '2025-12-11': 18, '2026-02-05': 21, '2026-03-24': 0, '2026-03-27': 12,
            '2026-05-21': 11, '2026-06-24': 2,
        }
        found = {u['date']: u for u in gu._all_enriched()}
        for iso, days in expected.items():
            with self.subTest(date=iso):
                self.assertEqual(found[iso]['rollout_days'], days)
                self.assertFalse(found[iso]['rollout_days_estimated'])

    def test_unrelated_rollout_mention_stays_estimated(self):
        """'subset rollout' states no duration, so no number may be invented."""
        entry = {u['date']: u for u in gu._all_enriched()}['2026-06-03']
        self.assertTrue(entry['rollout_days_estimated'])


class UpdatesInWindowTests(SimpleTestCase):
    def test_finds_update_inside_window(self):
        found = updates_in_window(date(2026, 5, 1), date(2026, 5, 31))
        self.assertIn(MAY_2026_CORE, _names(found))

    def test_matches_on_rollout_overlap_not_just_start_date(self):
        """The May 2026 core update started in May and was still rolling in June."""
        found = updates_in_window(date(2026, 6, 1), date(2026, 6, 1))
        self.assertIn(MAY_2026_CORE, _names(found))

    def test_excludes_update_whose_rollout_closed_before_the_window(self):
        found = updates_in_window(date(2026, 6, 3), date(2026, 6, 4))
        self.assertNotIn(MAY_2026_CORE, _names(found))

    def test_empty_window_returns_empty_list(self):
        self.assertEqual(updates_in_window(date(2020, 1, 1), date(2020, 12, 31)), [])

    def test_accepts_iso_strings(self):
        self.assertEqual(
            _names(updates_in_window('2026-05-01', '2026-05-31')),
            _names(updates_in_window(date(2026, 5, 1), date(2026, 5, 31))),
        )

    def test_rejects_reversed_window(self):
        with self.assertRaises(ValueError):
            updates_in_window(date(2026, 5, 31), date(2026, 5, 1))

    def test_rejects_garbage_date(self):
        with self.assertRaises(ValueError):
            updates_in_window('pas une date', '2026-05-31')

    def test_sorted_newest_first(self):
        found = updates_in_window(date(2024, 1, 1), date(2026, 12, 31))
        self.assertEqual([u['date'] for u in found], sorted((u['date'] for u in found), reverse=True))

    def test_kind_filter(self):
        found = updates_in_window(date(2024, 1, 1), date(2026, 12, 31), kinds=['core'])
        self.assertTrue(found)
        self.assertEqual({u['kind'] for u in found}, {'core'})

    def test_entry_shape(self):
        item = _by_name(updates_in_window('2026-05-21', '2026-05-21'), MAY_2026_CORE)
        self.assertEqual(item['rollout_end'], '2026-06-01')
        self.assertEqual(item['kind_label'], 'mise à jour principale')
        self.assertTrue(item['affects_rankings'])
        self.assertEqual(item['surface'], 'web')


class ExplainTrafficDropTests(SimpleTestCase):
    def test_drop_during_core_rollout_ranks_first(self):
        found = explain_traffic_drop(date(2026, 5, 25))
        self.assertEqual(found[0]['name'], MAY_2026_CORE)
        self.assertEqual(found[0]['confidence'], 'high')
        self.assertEqual(found[0]['confidence_label'], 'élevée')
        self.assertTrue(found[0]['during_rollout'])
        self.assertEqual(found[0]['distance_days'], 0)
        self.assertEqual(found[0]['days_from_start'], 4)

    def test_quiet_period_returns_nothing(self):
        """No confirmed update near mid-January 2026, and saying so is the answer."""
        self.assertEqual(explain_traffic_drop(date(2026, 1, 15)), [])

    def test_older_update_outside_window_is_dropped(self):
        found = explain_traffic_drop(date(2026, 6, 20), window_days=14)
        self.assertNotIn(MAY_2026_CORE, _names(found))

    def test_wider_window_brings_it_back(self):
        found = explain_traffic_drop(date(2026, 6, 20), window_days=30)
        item = _by_name(found, MAY_2026_CORE)
        self.assertEqual(item['confidence'], 'medium')
        self.assertFalse(item['during_rollout'])
        self.assertEqual(item['distance_days'], 19)

    def test_discover_update_cannot_explain_a_web_drop(self):
        item = _by_name(explain_traffic_drop(date(2026, 2, 15)), FEB_2026_DISCOVER)
        self.assertEqual(item['confidence'], 'low')
        self.assertIn('Discover', item['verdict'])

    def test_discover_update_explains_a_discover_drop(self):
        item = _by_name(
            explain_traffic_drop(date(2026, 2, 15), surface='discover'), FEB_2026_DISCOVER,
        )
        self.assertEqual(item['confidence'], 'high')

    def test_non_ranking_change_is_surfaced_not_hidden(self):
        """The FAQ retirement cost clicks without moving a ranking."""
        item = _by_name(explain_traffic_drop(date(2026, 5, 8)), FAQ_RETIRED)
        self.assertEqual(item['confidence'], 'low')
        self.assertFalse(item['affects_rankings'])
        self.assertIn('CTR', item['verdict'])

    def test_update_announced_just_after_the_drop_still_counts(self):
        found = explain_traffic_drop(date(2026, 6, 27))
        late = _by_name(found, 'Generative AI optimization guide')
        self.assertEqual(late['days_from_start'], -2)
        self.assertIn('après ta date de chute', late['verdict'])

    def test_two_updates_days_apart_both_come_back(self):
        """March 2026 stacked a spam update and a core update inside four days."""
        found = explain_traffic_drop(date(2026, 3, 25))
        self.assertIn('March 2026 Spam Update', _names(found))
        self.assertIn('March 2026 Core Update', _names(found))

    def test_ranked_high_confidence_first(self):
        ranks = [gu._CONFIDENCE_RANK[u['confidence']] for u in explain_traffic_drop(date(2026, 5, 25))]
        self.assertEqual(ranks, sorted(ranks))

    def test_zero_window_only_looks_at_the_day_itself(self):
        found = explain_traffic_drop(date(2026, 5, 8), window_days=0)
        self.assertEqual(_names(found), [])

    def test_rejects_negative_window(self):
        with self.assertRaises(ValueError):
            explain_traffic_drop(date(2026, 5, 25), window_days=-1)

    def test_accepts_iso_string(self):
        self.assertEqual(
            _names(explain_traffic_drop('2026-05-25')),
            _names(explain_traffic_drop(date(2026, 5, 25))),
        )


class DataFreshnessTests(SimpleTestCase):
    def test_reports_age_against_injected_today(self):
        fresh = data_freshness(today=date(2026, 8, 14))
        self.assertEqual(fresh['last_verified'], '2026-07-02')
        self.assertEqual(fresh['age_days'], 43)
        self.assertFalse(fresh['is_stale'])
        self.assertIn('2 juillet 2026', fresh['message'])
        self.assertEqual(fresh['latest_update_date'], '2026-06-30')
        self.assertEqual(fresh['updates_count'], len(gu._load()['updates']))

    def test_goes_stale_and_says_so(self):
        fresh = data_freshness(today=date(2026, 12, 1))
        self.assertTrue(fresh['is_stale'])
        self.assertGreater(fresh['age_days'], gu.STALE_AFTER_DAYS)
        self.assertIn('confirme sur le tableau de bord Google', fresh['message'])

    def test_reference_date_before_verification_clamps_to_zero(self):
        self.assertEqual(data_freshness(today=date(2026, 1, 1))['age_days'], 0)

    def test_defaults_to_system_date(self):
        self.assertIsInstance(data_freshness()['age_days'], int)

    def test_french_date_format(self):
        self.assertEqual(gu._fmt_fr(date(2026, 6, 1)), '1er juin 2026')
        self.assertEqual(gu._fmt_fr(date(2026, 5, 21)), '21 mai 2026')
        self.assertEqual(gu._fmt_fr(date(2026, 8, 3)), '3 août 2026')


class TrafficDropReportTests(SimpleTestCase):
    def test_covered_date_with_candidates(self):
        report = traffic_drop_report(date(2026, 5, 25), today=date(2026, 8, 14))
        self.assertTrue(report['data_covers_drop_date'])
        self.assertEqual(report['candidates'][0]['name'], MAY_2026_CORE)
        self.assertIn(MAY_2026_CORE, report['verdict'])
        self.assertIn('autres changements confirmés', report['verdict'])

    def test_covered_date_without_candidates_points_elsewhere(self):
        report = traffic_drop_report(date(2026, 1, 15), today=date(2026, 8, 14))
        self.assertEqual(report['candidates'], [])
        self.assertIn('Aucune mise à jour Google confirmée', report['verdict'])

    def test_date_beyond_last_verified_refuses_to_conclude(self):
        report = traffic_drop_report(date(2026, 7, 20), today=date(2026, 8, 14))
        self.assertFalse(report['data_covers_drop_date'])
        self.assertEqual(report['candidates'], [])
        self.assertIn('Impossible de conclure', report['verdict'])
        self.assertIn(report['freshness']['source_of_truth'], report['verdict'])

    def test_uncovered_date_with_candidates_still_carries_the_caveat(self):
        report = traffic_drop_report(date(2026, 7, 3), today=date(2026, 8, 14))
        self.assertFalse(report['data_covers_drop_date'])
        self.assertIn(JUNE_2026_SPAM, _names(report['candidates']))
        self.assertIn('Liste vérifiée le 2 juillet 2026', report['verdict'])

    def test_report_echoes_its_inputs(self):
        report = traffic_drop_report('2026-05-25', window_days=7, surface='discover',
                                     today=date(2026, 8, 14))
        self.assertEqual(report['drop_date'], '2026-05-25')
        self.assertEqual(report['window_days'], 7)
        self.assertEqual(report['surface'], 'discover')


class GeneratedProseTests(SimpleTestCase):
    """Gridar's copy rules apply to strings this module builds, not just to docs."""

    def test_no_foreign_dashes_anywhere(self):
        texts = [data_freshness(today=date(2026, 12, 1))['message']]
        for day in (1, 8, 15, 22):
            for month in range(1, 13):
                report = traffic_drop_report(date(2026, month, day), today=date(2026, 8, 14))
                texts.append(report['verdict'])
                texts.extend(c['verdict'] for c in report['candidates'])
        for text in texts:
            with self.subTest(text=text[:60]):
                self.assertNotIn('—', text)
                self.assertNotIn('–', text)

    def test_every_verdict_names_the_update_and_a_date(self):
        for candidate in explain_traffic_drop(date(2026, 5, 25)):
            with self.subTest(name=candidate['name']):
                self.assertIn(candidate['name'], candidate['verdict'])
                self.assertRegex(candidate['verdict'], r'\d{4}')


class BadDataTests(SimpleTestCase):
    def test_unknown_kind_degrades_instead_of_crashing(self):
        doc = {
            'last_verified': '2026-07-02',
            'source_of_truth': 'https://status.search.google.com/x',
            'updates': [{'date': '2026-05-10', 'name': 'Quantum Update',
                         'kind': 'quantum', 'source': 'https://blog.google/x',
                         'notes': 'no duration'}],
        }
        with patch.object(gu, '_CACHE', doc):
            item = updates_in_window('2026-05-01', '2026-05-31')[0]
            self.assertEqual(item['kind_label'], 'quantum')
            self.assertFalse(item['affects_rankings'])
            self.assertEqual(item['surface'], 'web')
            self.assertEqual(explain_traffic_drop('2026-05-11')[0]['confidence'], 'low')

    def test_missing_data_file_raises_a_typed_error(self):
        with patch.object(gu, '_CACHE', None), \
                patch.object(gu, '_DATA_FILE', Path('nowhere/google_updates.json')):
            with self.assertRaises(GoogleUpdatesError):
                data_freshness()

    def test_malformed_json_raises_a_typed_error(self):
        broken = Path(gu.__file__).resolve().parent / 'data' / '_broken_for_tests.json'
        broken.write_text('{not json', encoding='utf-8')
        try:
            with patch.object(gu, '_CACHE', None), patch.object(gu, '_DATA_FILE', broken):
                with self.assertRaises(GoogleUpdatesError):
                    data_freshness()
        finally:
            broken.unlink()

    def test_missing_last_verified_is_admitted(self):
        with patch.object(gu, '_CACHE', {'updates': [], 'source_of_truth': ''}):
            fresh = data_freshness(today=date(2026, 8, 14))
            self.assertIsNone(fresh['last_verified'])
            self.assertIsNone(fresh['age_days'])
            self.assertIn('non fiable', fresh['message'])
            self.assertIn('Impossible de conclure',
                          traffic_drop_report('2026-08-01', today=date(2026, 8, 14))['verdict'])


class ModulePurityTests(SimpleTestCase):
    """This port has to stay plain data-in / data-out so it can be reused anywhere."""

    def test_no_orm_and_no_network(self):
        source = Path(gu.__file__).resolve().with_suffix('.py').read_text('utf-8')
        for forbidden in ('from .models', 'import requests', 'django.', 'objects.filter'):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)

    def test_data_file_is_valid_json_on_disk(self):
        path = Path(gu.__file__).resolve().parent / 'data' / 'google_updates.json'
        self.assertTrue(path.exists())
        json.loads(path.read_text('utf-8'))

    def test_public_api_is_declared(self):
        for name in ('updates_in_window', 'explain_traffic_drop', 'data_freshness',
                     'traffic_drop_report'):
            self.assertIn(name, gu.__all__)


class RegexSanityTests(SimpleTestCase):
    """Cheap guard on the one regex that reads numbers out of English prose."""

    def test_day_patterns_need_the_word_rollout(self):
        self.assertEqual(gu._rollout_days({'kind': 'core', 'notes': '24 days of nothing'}), (14, True))

    def test_case_insensitive(self):
        self.assertEqual(gu._rollout_days({'kind': 'core', 'notes': '9-DAY ROLLOUT'}), (9, False))

    def test_no_pattern_matches_an_empty_note(self):
        self.assertIsNone(re.search(gu._SUBDAY_PATTERN, ''))

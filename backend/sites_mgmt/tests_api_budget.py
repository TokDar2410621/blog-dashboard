"""Tests for the budget guard on the paid APIs.

Everything runs offline by construction: `api_budget` opens no socket, reads no
file and touches no model, so there is nothing to mock. The one environment
dependency is the tz database, and the tests that turn on the local rollover
skip themselves when it is missing rather than fail on a machine without it.

Run all:
    python manage.py test sites_mgmt.tests_api_budget
"""
import io
import json
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

from django.test import SimpleTestCase

from . import api_budget
from .api_budget import (
    ANTHROPIC_MODELS, BUDGET_TIMEZONE, BudgetError, SERPER_OPERATIONS,
    SERPER_PLANS, WARN_AT_RATIO, budget_day_key, check_budget, estimate_cost,
    format_ledger_entry,
)

# The intro rate on Sonnet 5 expires; pin both sides of it so the tests keep
# asserting the same thing after it does.
DURING_INTRO = date(2026, 8, 14)
AFTER_INTRO = date(2026, 9, 1)

_LOCAL_TZ_OK = str(api_budget._TZ) == BUDGET_TIMEZONE


class SerperEstimateTests(SimpleTestCase):
    def test_one_search_costs_one_credit(self):
        est = estimate_cost('serper', 'search')
        self.assertTrue(est['known'])
        self.assertEqual(est['cost_usd'], 0.001)  # starter: 50 $ / 50 000
        self.assertEqual(est['basis']['credits_total'], 1)
        self.assertEqual(est['basis']['plan'], 'starter')

    def test_cost_scales_with_call_count(self):
        # The runaway-loop case: index_coverage paginates eight times.
        est = estimate_cost('serper', 'search', calls=8)
        self.assertEqual(est['cost_usd'], 0.008)
        self.assertEqual(est['basis']['calls'], 8)

    def test_deep_results_double_the_credits(self):
        """Serper bills two credits past 10 results, whatever the endpoint."""
        shallow = estimate_cost('serper', 'search', results_per_call=10)
        deep = estimate_cost('serper', 'search', results_per_call=20)
        self.assertEqual(deep['cost_usd'], shallow['cost_usd'] * 2)
        self.assertEqual(deep['basis']['credits_per_call'], 2)
        self.assertTrue(any('10' in n for n in deep['notes']))

    def test_results_beyond_the_api_maximum_are_capped(self):
        est = estimate_cost('serper', 'search', results_per_call=5000)
        self.assertEqual(est['basis']['results_per_call'], 100)

    def test_plan_changes_the_unit_price(self):
        prices = {
            plan: estimate_cost('serper', 'search', plan=plan)['cost_usd']
            for plan in SERPER_PLANS
        }
        self.assertEqual(prices['ultimate'], 0.0003)
        self.assertLess(prices['ultimate'], prices['starter'])

    def test_unknown_plan_falls_back_to_the_dearest(self):
        est = estimate_cost('serper', 'search', plan='forfait-imaginaire')
        self.assertEqual(est['basis']['plan'], 'starter')
        self.assertEqual(est['cost_usd'], 0.001)
        self.assertTrue(any('forfait' in n.lower() for n in est['notes']))

    def test_unknown_operation_is_priced_not_ignored(self):
        """An unrecognized endpoint must never come back free."""
        est = estimate_cost('serper', 'lens')
        self.assertFalse(est['known'])
        self.assertGreater(est['cost_usd'], 0)
        self.assertTrue(any('inconnue' in n for n in est['notes']))

    def test_operations_gridar_actually_calls_are_covered(self):
        # api_v1 and article_generator hit /search, /images and /maps.
        for slug in ('search', 'images', 'maps', 'news'):
            est = estimate_cost('serper', slug)
            self.assertTrue(est['known'], slug)
            self.assertTrue(est['label'], slug)


class AnthropicEstimateTests(SimpleTestCase):
    def test_priced_on_input_and_output_separately(self):
        est = estimate_cost(
            'anthropic', 'article', model='claude-sonnet-5',
            input_tokens=10_000, output_tokens=4_000, on_date=AFTER_INTRO,
        )
        # 10k in at 3 $/Mtok + 4k out at 15 $/Mtok
        self.assertEqual(est['cost_usd'], 0.09)
        self.assertTrue(est['known'])

    def test_intro_rate_applies_inside_its_window(self):
        during = estimate_cost(
            'anthropic', 'article', model='claude-sonnet-5',
            input_tokens=10_000, output_tokens=4_000, on_date=DURING_INTRO,
        )
        after = estimate_cost(
            'anthropic', 'article', model='claude-sonnet-5',
            input_tokens=10_000, output_tokens=4_000, on_date=AFTER_INTRO,
        )
        self.assertEqual(during['cost_usd'], 0.06)
        self.assertTrue(during['basis']['intro_rate_applied'])
        self.assertFalse(after['basis']['intro_rate_applied'])
        self.assertGreater(after['cost_usd'], during['cost_usd'])
        self.assertTrue(any('lancement' in n for n in during['notes']))

    def test_intro_rate_boundary_is_inclusive(self):
        last_day = estimate_cost(
            'anthropic', 'x', model='claude-sonnet-5', output_tokens=1000,
            on_date=date(2026, 8, 31),
        )
        next_day = estimate_cost(
            'anthropic', 'x', model='claude-sonnet-5', output_tokens=1000,
            on_date=date(2026, 9, 1),
        )
        self.assertTrue(last_day['basis']['intro_rate_applied'])
        self.assertFalse(next_day['basis']['intro_rate_applied'])

    def test_iso_string_date_accepted(self):
        est = estimate_cost(
            'anthropic', 'x', model='claude-sonnet-5', output_tokens=1000,
            on_date='2026-09-01',
        )
        self.assertFalse(est['basis']['intro_rate_applied'])

    def test_unknown_model_priced_at_the_dearest(self):
        est = estimate_cost(
            'anthropic', 'article', model='claude-inconnu-9',
            input_tokens=10_000, output_tokens=4_000,
        )
        self.assertFalse(est['known'])
        # Falls back to the most expensive row (10 $ / 50 $ per Mtok).
        self.assertEqual(est['cost_usd'], 0.3)
        self.assertTrue(any('inconnu' in n.lower() for n in est['notes']))

    def test_max_tokens_used_as_worst_case_output(self):
        """Gridar knows max_tokens before a call, never the real output."""
        est = estimate_cost(
            'anthropic', 'article', model='claude-sonnet-5',
            input_tokens=0, max_tokens=10_000, on_date=AFTER_INTRO,
        )
        self.assertEqual(est['cost_usd'], 0.15)
        self.assertEqual(est['basis']['output_tokens'], 10_000)
        self.assertTrue(any('pire cas' in n for n in est['notes']))

    def test_prompt_chars_converted_to_tokens(self):
        est = estimate_cost(
            'anthropic', 'article', model='claude-sonnet-5',
            prompt_chars=3200, output_tokens=0, on_date=AFTER_INTRO,
        )
        self.assertEqual(est['basis']['input_tokens'], 1000)  # 3200 / 3.2
        self.assertEqual(est['cost_usd'], 0.003)

    def test_no_output_signal_still_costs_something(self):
        """A generation priced at zero would let a runaway loop straight through."""
        est = estimate_cost('anthropic', 'article', model='claude-sonnet-5')
        self.assertFalse(est['known'])
        self.assertGreater(est['cost_usd'], 0)
        self.assertEqual(est['basis']['output_tokens'], 4000)

    def test_cache_reads_are_a_tenth_of_input(self):
        est = estimate_cost(
            'anthropic', 'x', model='claude-sonnet-5', input_tokens=0,
            output_tokens=0, cache_read_tokens=100_000, on_date=AFTER_INTRO,
        )
        self.assertEqual(est['cost_usd'], 0.03)  # 0.1 Mtok * 3 $ * 0.10

    def test_cache_write_premium_depends_on_ttl(self):
        short = estimate_cost(
            'anthropic', 'x', model='claude-sonnet-5', input_tokens=0,
            output_tokens=0, cache_write_tokens=100_000, cache_ttl='5m',
            on_date=AFTER_INTRO,
        )
        long = estimate_cost(
            'anthropic', 'x', model='claude-sonnet-5', input_tokens=0,
            output_tokens=0, cache_write_tokens=100_000, cache_ttl='1h',
            on_date=AFTER_INTRO,
        )
        self.assertEqual(short['cost_usd'], 0.375)
        self.assertEqual(long['cost_usd'], 0.6)

    def test_unknown_ttl_falls_back_to_five_minutes(self):
        est = estimate_cost(
            'anthropic', 'x', model='claude-sonnet-5', input_tokens=0,
            output_tokens=0, cache_write_tokens=100_000, cache_ttl='42j',
            on_date=AFTER_INTRO,
        )
        self.assertEqual(est['basis']['cache_ttl'], '5m')

    def test_call_count_multiplies(self):
        one = estimate_cost(
            'anthropic', 'x', model='claude-haiku-4-5',
            input_tokens=1_000_000, output_tokens=1_000_000,
        )
        three = estimate_cost(
            'anthropic', 'x', model='claude-haiku-4-5',
            input_tokens=1_000_000, output_tokens=1_000_000, calls=3,
        )
        self.assertEqual(one['cost_usd'], 6.0)
        self.assertEqual(three['cost_usd'], 18.0)

    def test_opus_costs_more_than_haiku(self):
        args = {'input_tokens': 100_000, 'output_tokens': 20_000}
        opus = estimate_cost('anthropic', 'x', model='claude-opus-5', **args)
        haiku = estimate_cost('anthropic', 'x', model='claude-haiku-4-5', **args)
        self.assertGreater(opus['cost_usd'], haiku['cost_usd'])


class EstimateContractTests(SimpleTestCase):
    def test_unknown_provider_raises(self):
        # Failing loudly beats pricing an unknown provider at zero.
        with self.assertRaises(BudgetError):
            estimate_cost('dataforseo', 'serp_organic_live_advanced')

    def test_every_estimate_carries_its_tariff_date(self):
        for est in (estimate_cost('serper', 'search'),
                    estimate_cost('anthropic', 'x', output_tokens=10)):
            self.assertEqual(est['tariffs_checked_on'], api_budget.TARIFFS_CHECKED_ON)
            self.assertTrue(est['source'])

    def test_estimates_are_json_serializable(self):
        for est in (estimate_cost('serper', 'maps', calls=2),
                    estimate_cost('anthropic', 'landing', max_tokens=3500)):
            self.assertIsInstance(json.dumps(est), str)


class CheckBudgetTests(SimpleTestCase):
    def test_allows_when_there_is_room(self):
        v = check_budget(spent_today=1.0, estimate=0.5, daily_cap=10.0)
        self.assertEqual(v['decision'], 'allow')
        self.assertEqual(v['reason'], 'ok')
        self.assertEqual(v['projected_usd'], 1.5)
        self.assertEqual(v['remaining_usd'], 9.0)
        self.assertEqual(v['usage_pct'], 15.0)

    def test_warns_from_the_threshold_share(self):
        v = check_budget(spent_today=7.5, estimate=0.5, daily_cap=10.0)
        self.assertEqual(v['decision'], 'warn')
        self.assertEqual(v['reason'], 'approaching_cap')
        self.assertEqual(v['projected_usd'], 10.0 * WARN_AT_RATIO)

    def test_landing_exactly_on_the_cap_is_not_refused(self):
        v = check_budget(spent_today=9.5, estimate=0.5, daily_cap=10.0)
        self.assertEqual(v['decision'], 'warn')
        self.assertEqual(v['remaining_usd'], 0.5)

    def test_denies_past_the_cap(self):
        v = check_budget(spent_today=9.8, estimate=0.5, daily_cap=10.0)
        self.assertEqual(v['decision'], 'deny')
        self.assertEqual(v['reason'], 'cap_exceeded')

    def test_call_bigger_than_the_whole_cap_gets_its_own_reason(self):
        """Raising the cap by a hair will not help, so say something else."""
        v = check_budget(spent_today=0.0, estimate=12.0, daily_cap=10.0)
        self.assertEqual(v['decision'], 'deny')
        self.assertEqual(v['reason'], 'single_call_over_cap')

    def test_zero_cap_blocks_everything(self):
        v = check_budget(spent_today=0.0, estimate=0.001, daily_cap=0.0)
        self.assertEqual(v['decision'], 'deny')
        self.assertEqual(v['reason'], 'no_budget')
        self.assertIsNone(v['usage_pct'])

    def test_negative_cap_treated_as_no_budget(self):
        v = check_budget(spent_today=0.0, estimate=0.001, daily_cap=-5.0)
        self.assertEqual(v['reason'], 'no_budget')
        self.assertEqual(v['daily_cap_usd'], 0.0)

    def test_fails_closed_on_nonsense_numbers(self):
        """The loop this guard exists for is exactly what produces these."""
        for bad in (float('nan'), float('inf'), 'beaucoup', None):
            v = check_budget(spent_today=1.0, estimate=bad, daily_cap=10.0)
            self.assertEqual(v['decision'], 'deny', bad)
            self.assertEqual(v['reason'], 'invalid_input', bad)

    def test_negative_spend_clamped(self):
        v = check_budget(spent_today=-3.0, estimate=1.0, daily_cap=10.0)
        self.assertEqual(v['decision'], 'allow')
        self.assertEqual(v['spent_today_usd'], 0.0)

    def test_messages_are_french_and_quote_the_numbers(self):
        deny = check_budget(spent_today=9.8, estimate=0.5, daily_cap=10.0)
        self.assertIn('Plafond quotidien atteint', deny['message'])
        self.assertIn('$ US', deny['message'])
        self.assertIn('9,80', deny['message'])  # comma decimal, Quebec style
        warn = check_budget(spent_today=7.5, estimate=0.5, daily_cap=10.0)
        self.assertIn('Budget serré', warn['message'])
        self.assertIn('%', warn['message'])

    def test_tenth_of_a_cent_still_shows_up_in_the_message(self):
        """Two decimals would print every Serper call as 0,00 $ US."""
        v = check_budget(spent_today=0.0, estimate=0.001, daily_cap=10.0)
        self.assertIn('0,0010', v['message'])

    def test_verdicts_are_json_serializable(self):
        v = check_budget(spent_today=1.0, estimate=0.5, daily_cap=10.0)
        self.assertIsInstance(json.dumps(v), str)


class BudgetDayKeyTests(SimpleTestCase):
    def test_naive_datetime_read_as_utc(self):
        naive = datetime(2026, 8, 14, 12, 0, 0)
        aware = datetime(2026, 8, 14, 12, 0, 0, tzinfo=timezone.utc)
        self.assertEqual(budget_day_key(naive), budget_day_key(aware))

    @unittest.skipUnless(_LOCAL_TZ_OK, 'tz database unavailable, UTC fallback active')
    def test_day_rolls_over_at_local_midnight(self):
        # 02:00 UTC on the 15th is still the evening of the 14th in Quebec.
        late_evening = datetime(2026, 8, 15, 2, 0, tzinfo=timezone.utc)
        self.assertEqual(budget_day_key(late_evening), '2026-08-14')
        just_after = datetime(2026, 8, 15, 5, 0, tzinfo=timezone.utc)
        self.assertEqual(budget_day_key(just_after), '2026-08-15')

    def test_returns_an_iso_date(self):
        self.assertRegex(budget_day_key(), r'^\d{4}-\d{2}-\d{2}$')


class LedgerEntryTests(SimpleTestCase):
    def _estimate(self):
        return estimate_cost('serper', 'search', calls=3)

    def test_bills_the_estimate_when_the_real_cost_never_came_back(self):
        """Serper returns no cost field, so the estimate is all there is."""
        entry = format_ledger_entry(
            provider='serper', operation='search', estimate=self._estimate(),
        )
        self.assertEqual(entry['estimated_cost_usd'], 0.003)
        self.assertIsNone(entry['actual_cost_usd'])
        self.assertEqual(entry['billed_cost_usd'], 0.003)

    def test_measured_cost_wins_over_the_estimate(self):
        entry = format_ledger_entry(
            provider='anthropic', operation='article',
            estimate=estimate_cost('anthropic', 'article', max_tokens=4000),
            actual_cost_usd=0.0123,
        )
        self.assertEqual(entry['actual_cost_usd'], 0.0123)
        self.assertEqual(entry['billed_cost_usd'], 0.0123)

    def test_denied_call_bills_nothing(self):
        entry = format_ledger_entry(
            provider='serper', operation='search', estimate=self._estimate(),
            status='denied', decision='deny',
        )
        self.assertEqual(entry['billed_cost_usd'], 0.0)
        self.assertEqual(entry['estimated_cost_usd'], 0.003)
        self.assertEqual(entry['decision'], 'deny')

    def test_failure_that_consumed_nothing_says_so_explicitly(self):
        entry = format_ledger_entry(
            provider='serper', operation='search', estimate=self._estimate(),
            status='error', actual_cost_usd=0.0,
        )
        self.assertEqual(entry['billed_cost_usd'], 0.0)

    def test_failure_of_unknown_cost_still_moves_the_counter(self):
        # A timeout after the provider did the work is not free.
        entry = format_ledger_entry(
            provider='serper', operation='search', estimate=self._estimate(),
            status='error',
        )
        self.assertEqual(entry['billed_cost_usd'], 0.003)

    def test_missing_estimate_is_tolerated(self):
        entry = format_ledger_entry(provider='serper', operation='search')
        self.assertEqual(entry['estimated_cost_usd'], 0.0)
        self.assertFalse(entry['estimate_known'])

    def test_model_pulled_from_the_estimate(self):
        entry = format_ledger_entry(
            provider='anthropic', operation='landing',
            estimate=estimate_cost(
                'anthropic', 'landing', model='claude-sonnet-5', max_tokens=3500,
            ),
        )
        self.assertEqual(entry['model'], 'claude-sonnet-5')

    def test_unknown_status_raises(self):
        with self.assertRaises(BudgetError):
            format_ledger_entry(
                provider='serper', operation='search', status='peut-etre',
            )

    def test_day_is_local_while_the_timestamp_stays_utc(self):
        moment = datetime(2026, 8, 15, 2, 0, tzinfo=timezone.utc)
        entry = format_ledger_entry(
            provider='serper', operation='search', occurred_at=moment,
        )
        self.assertTrue(entry['occurred_at'].startswith('2026-08-15T02:00'))
        self.assertEqual(entry['day'], budget_day_key(moment))

    def test_context_is_copied_not_aliased(self):
        ctx = {'site_id': 12, 'user_id': 3}
        entry = format_ledger_entry(
            provider='serper', operation='search', context=ctx,
        )
        ctx['site_id'] = 999
        self.assertEqual(entry['context']['site_id'], 12)

    def test_entry_is_json_serializable(self):
        entry = format_ledger_entry(
            provider='anthropic', operation='article',
            estimate=estimate_cost('anthropic', 'article', max_tokens=4000),
            actual_cost_usd=0.02, decision='allow',
            context={'site_id': 7, 'source': 'autopilot'},
        )
        self.assertIsInstance(json.dumps(entry), str)


class FakeBudgetStore:
    """In-memory stand-in for the Postgres counter the report describes."""

    def __init__(self):
        self.entries = []
        self.totals = {}

    def spent_today(self, day, provider=None):
        return sum(
            e['billed_cost_usd'] for e in self.entries
            if e['day'] == day and (provider is None or e['provider'] == provider)
        )

    def record(self, entry):
        self.entries.append(entry)
        return self.spent_today(entry['day'], entry['provider'])


class RoundTripTests(SimpleTestCase):
    """estimate -> check -> record -> the next call sees the spend."""

    def test_guard_eventually_stops_a_loop(self):
        store = FakeBudgetStore()
        cap = 1.0
        day = budget_day_key()
        allowed = 0

        for _ in range(5000):  # a generation loop gone wrong
            est = estimate_cost(
                'anthropic', 'article', model='claude-sonnet-5',
                input_tokens=5_000, max_tokens=4_000, on_date=AFTER_INTRO,
            )
            verdict = check_budget(
                store.spent_today(day, 'anthropic'), est['cost_usd'], cap,
            )
            if verdict['decision'] == 'deny':
                store.record(format_ledger_entry(
                    provider='anthropic', operation='article', estimate=est,
                    status='denied', decision='deny',
                ))
                break
            allowed += 1
            store.record(format_ledger_entry(
                provider='anthropic', operation='article', estimate=est,
                actual_cost_usd=est['cost_usd'], decision=verdict['decision'],
            ))
        else:
            self.fail('le garde-fou n a jamais bloque la boucle')

        self.assertGreater(allowed, 0)
        self.assertLessEqual(store.spent_today(day, 'anthropic'), cap)
        self.assertEqual(store.entries[-1]['billed_cost_usd'], 0.0)

    def test_per_provider_and_global_totals_both_readable(self):
        store = FakeBudgetStore()
        day = budget_day_key()
        store.record(format_ledger_entry(
            provider='serper', operation='search',
            estimate=estimate_cost('serper', 'search', calls=10),
        ))
        store.record(format_ledger_entry(
            provider='anthropic', operation='article',
            estimate=estimate_cost(
                'anthropic', 'article', model='claude-sonnet-5',
                input_tokens=0, output_tokens=1000, on_date=AFTER_INTRO,
            ),
        ))
        self.assertEqual(store.spent_today(day, 'serper'), 0.01)
        self.assertEqual(store.spent_today(day, 'anthropic'), 0.015)
        self.assertAlmostEqual(store.spent_today(day), 0.025, places=6)


class TariffTableTests(SimpleTestCase):
    def test_every_serper_operation_has_a_french_label_and_a_price(self):
        for slug, entry in SERPER_OPERATIONS.items():
            self.assertTrue(entry['label'], slug)
            self.assertGreaterEqual(entry['credits'], 1, slug)

    def test_every_model_has_both_rates_and_output_costs_more(self):
        for name, entry in ANTHROPIC_MODELS.items():
            self.assertGreater(entry['input'], 0, name)
            self.assertGreater(entry['output'], entry['input'], name)

    def test_intro_rates_are_cheaper_and_dated(self):
        for name, entry in ANTHROPIC_MODELS.items():
            intro = entry.get('intro')
            if not intro:
                continue
            self.assertLess(intro['input'], entry['input'], name)
            self.assertLess(intro['output'], entry['output'], name)
            date.fromisoformat(intro['until'])  # raises if malformed

    def test_plans_priced_per_credit_and_ordered(self):
        values = list(SERPER_PLANS.values())
        self.assertEqual(values, sorted(values, reverse=True))
        self.assertEqual(max(values), SERPER_PLANS['starter'])


class HouseStyleTests(SimpleTestCase):
    def test_no_dash_typography_reaches_the_user(self):
        """Standing rule for this repo: no em dash, no en dash, anywhere.

        The two characters are built from their code points on purpose: written
        as literals they would appear in this file and the check would flag
        itself.
        """
        banned = {'cadratin': chr(0x2014), 'demi-cadratin': chr(0x2013)}
        for name in ('api_budget.py', 'tests_api_budget.py'):
            path = Path(__file__).resolve().parent / name
            source = io.open(path, encoding='utf-8').read()
            for label, char in banned.items():
                self.assertNotIn(char, source, f'{name}: {label}')

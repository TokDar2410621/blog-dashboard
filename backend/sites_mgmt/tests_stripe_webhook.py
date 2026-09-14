"""Stripe webhook handlers fed with real StripeObject payloads.

Regression for 2026-09-13: Stripe SDK 12+ removed dict.get() from
StripeObject, every handler crashed with AttributeError, and post() swallowed
it to ack Stripe. The old tests never caught it because nothing built a real
StripeObject. These do, the way stripe.Webhook.construct_event does.

The reconciliation and resync classes lock the defects a review found once the
webhook worked again: an old subscription's event overwriting a paying
client, an incomplete checkout granting the plan, a Stripe account shared with
other products, and a resync that could downgrade or crash.

Run: python manage.py test sites_mgmt.tests_stripe_webhook
"""
import os
from io import StringIO
from unittest.mock import patch

import stripe
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from .models import CreditTransaction, Subscription
from .quota import CREDIT_PACKS, get_credit_balance
from .views import BillingCreditsCheckoutView, BillingWebhookView

User = get_user_model()

PRICES = {
    'STRIPE_PRICE_SOLO': 'price_solo',
    'STRIPE_PRICE_PRO': 'price_pro',
    'STRIPE_PRICE_AGENCY': 'price_agency',
}


def stripe_obj(payload):
    """What construct_event hands the view: a StripeObject, not a dict."""
    return stripe.StripeObject.construct_from(payload, 'sk_test_fake')


def event(event_type, obj):
    return stripe_obj({'id': 'evt_test', 'type': event_type, 'data': {'object': obj}})


def listing(*payloads):
    """Stripe.Subscription.list result, newest first like the real API."""
    return stripe_obj({'object': 'list', 'data': list(payloads)})


def subscription_payload(price_id='price_agency', status='active', **extra):
    payload = {
        'id': 'sub_123',
        'customer': 'cus_abc',
        'status': status,
        'cancel_at_period_end': False,
        'items': {'data': [{'price': {'id': price_id}}]},
        'current_period_end': 1893456000,  # 2030-01-01
    }
    payload.update(extra)
    return payload


class StripeWebhookBase(TestCase):
    def setUp(self):
        # Patched here, not as a class decorator: patch.dict on a class only
        # wraps the test methods defined on that class, never a subclass's.
        env = patch.dict(os.environ, {**PRICES, 'STRIPE_SECRET_KEY': 'sk_test_fake'})
        env.start()
        self.addCleanup(env.stop)
        self.user = User.objects.create_user(username='client', password='x')
        self.sub, _ = Subscription.objects.get_or_create(user=self.user)
        self.sub.stripe_customer_id = 'cus_abc'
        self.sub.stripe_subscription_id = 'sub_123'
        self.sub.plan = 'pro'
        self.sub.save()
        self.view = BillingWebhookView()
        # No network: by default Stripe returns no subscription, so the handler
        # falls back on the event object. Tests set their own listing.
        patcher = patch('stripe.Subscription.list', return_value=listing())
        self.list_mock = patcher.start()
        self.addCleanup(patcher.stop)

    def make_client(self, username, customer_id, plan='pro', status='active', sub_id=''):
        user = User.objects.create_user(username=username, password='x')
        sub, _ = Subscription.objects.get_or_create(user=user)
        sub.stripe_customer_id = customer_id
        sub.plan = plan
        sub.status = status
        sub.stripe_subscription_id = sub_id
        sub.save()
        return sub


class SubscriptionEventTests(StripeWebhookBase):
    def test_updated_applies_plan_from_a_real_stripeobject(self):
        # The exact shape that crashed in prod on 2026-09-13.
        self.view._dispatch(event('customer.subscription.updated', subscription_payload('price_agency')))
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.plan, 'agency')
        self.assertEqual(self.sub.stripe_subscription_id, 'sub_123')
        self.assertIsNotNone(self.sub.current_period_end)

    def test_deleted_drops_to_free_and_canceled(self):
        self.view._dispatch(event('customer.subscription.deleted', subscription_payload(status='canceled')))
        self.sub.refresh_from_db()
        self.assertEqual((self.sub.plan, self.sub.status), ('free', 'canceled'))

    def test_cancel_at_period_end_is_recorded(self):
        self.view._dispatch(event(
            'customer.subscription.updated', subscription_payload(cancel_at_period_end=True),
        ))
        self.sub.refresh_from_db()
        self.assertTrue(self.sub.cancel_at_period_end)

    def test_period_end_read_from_items_on_newer_api_versions(self):
        # Stripe API 2025-03-31+ moved current_period_end onto the items.
        payload = subscription_payload()
        payload.pop('current_period_end')
        payload['items']['data'][0]['current_period_end'] = 1893456000
        self.view._dispatch(event('customer.subscription.updated', payload))
        self.sub.refresh_from_db()
        self.assertIsNotNone(self.sub.current_period_end)

    def test_unknown_price_keeps_current_plan(self):
        self.view._dispatch(event('customer.subscription.updated', subscription_payload('price_inconnu')))
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.plan, 'pro')

    def test_unknown_customer_is_ignored_without_calling_stripe(self):
        payload = subscription_payload()
        payload['customer'] = 'cus_personne'
        self.view._dispatch(event('customer.subscription.updated', payload))
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.plan, 'pro')
        self.list_mock.assert_not_called()


class ReconciliationTests(StripeWebhookBase):
    """The event is a trigger; the state is re-read from Stripe."""

    def setUp(self):
        super().setUp()
        self.sub.plan = 'agency'
        self.sub.stripe_subscription_id = 'sub_agency'
        self.sub.save()

    def test_cancelling_an_old_subscription_keeps_the_live_one(self):
        # Upgrade through /billing/checkout/ left an old pro subscription; the
        # client cancels it in the portal. It must not drop them to free.
        self.list_mock.return_value = listing(
            subscription_payload('price_agency', id='sub_agency'),
            subscription_payload('price_pro', status='canceled', id='sub_old'),
        )
        self.view._dispatch(event('customer.subscription.deleted', subscription_payload(
            'price_pro', status='canceled', id='sub_old')))
        self.sub.refresh_from_db()
        self.assertEqual((self.sub.plan, self.sub.status, self.sub.stripe_subscription_id),
                         ('agency', 'active', 'sub_agency'))

    def test_renewal_of_an_old_subscription_does_not_overwrite_the_plan(self):
        self.list_mock.return_value = listing(
            subscription_payload('price_agency', id='sub_agency'),
            subscription_payload('price_pro', id='sub_old'),
        )
        self.view._dispatch(event('customer.subscription.updated', subscription_payload('price_pro', id='sub_old')))
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.plan, 'agency')

    def test_incomplete_checkout_does_not_grant_the_plan(self):
        self.sub.plan = 'pro'
        self.sub.stripe_subscription_id = 'sub_pro'
        self.sub.save()
        self.list_mock.return_value = listing(
            subscription_payload('price_agency', status='incomplete', id='sub_try'),
            subscription_payload('price_pro', id='sub_pro'),
        )
        self.view._dispatch(event('customer.subscription.created', subscription_payload(
            'price_agency', status='incomplete', id='sub_try')))
        self.sub.refresh_from_db()
        self.assertEqual((self.sub.plan, self.sub.stripe_subscription_id), ('pro', 'sub_pro'))

    def test_first_checkout_grants_the_plan_only_once_paid(self):
        self.sub.plan = 'free'
        self.sub.stripe_subscription_id = ''
        self.sub.save()
        self.list_mock.return_value = listing(subscription_payload('price_agency', status='incomplete', id='sub_new'))
        self.view._dispatch(event('customer.subscription.created', subscription_payload(
            'price_agency', status='incomplete', id='sub_new')))
        self.sub.refresh_from_db()
        self.assertEqual((self.sub.plan, self.sub.status), ('free', 'incomplete'))

        self.list_mock.return_value = listing(subscription_payload('price_agency', id='sub_new'))
        self.view._dispatch(event('customer.subscription.updated', subscription_payload('price_agency', id='sub_new')))
        self.sub.refresh_from_db()
        self.assertEqual((self.sub.plan, self.sub.status), ('agency', 'active'))

    def test_stripe_unreachable_never_lets_another_subscription_overwrite(self):
        self.list_mock.side_effect = stripe.APIConnectionError('stripe down')
        self.view._dispatch(event('customer.subscription.updated', subscription_payload('price_pro', id='sub_old')))
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.plan, 'agency')
        # The client's own subscription still updates from the event.
        self.view._dispatch(event('customer.subscription.updated', subscription_payload(
            'price_agency', status='past_due', id='sub_agency')))
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.status, 'past_due')

    def test_plan_granted_outside_stripe_is_never_taken_away(self):
        self.sub.stripe_subscription_id = ''
        self.sub.save()
        self.list_mock.return_value = listing(subscription_payload('price_solo', status='canceled', id='sub_x'))
        self.view._dispatch(event('customer.subscription.deleted', subscription_payload(
            'price_solo', status='canceled', id='sub_x')))
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.plan, 'agency')


class InvoiceAndCheckoutEventTests(StripeWebhookBase):
    def test_payment_failed_marks_past_due(self):
        self.view._dispatch(event('invoice.payment_failed', {
            'customer': 'cus_abc', 'amount_due': 9900, 'attempt_count': 1,
        }))
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.status, 'past_due')

    def test_payment_succeeded_restores_active(self):
        self.sub.status = 'past_due'
        self.sub.save()
        self.view._dispatch(event('invoice.payment_succeeded', {
            'customer': 'cus_abc', 'billing_reason': 'subscription_cycle', 'amount_paid': 9900,
        }))
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.status, 'active')

    def test_gridar_credit_pack_checkout_credits_the_user(self):
        self.view._dispatch(event('checkout.session.completed', {
            'id': 'cs_pack_1',
            'mode': 'payment',
            'metadata': {'app': 'gridar', 'pack': 'small', 'user_id': str(self.user.id), 'credits': '10'},
        }))
        self.assertEqual(get_credit_balance(self.user), 10)
        self.assertEqual(CreditTransaction.objects.filter(stripe_session_id='cs_pack_1').count(), 1)

    def test_checkout_from_another_product_credits_nobody(self):
        # Shared Stripe account: another product's user_id means nothing here.
        self.view._dispatch(event('checkout.session.completed', {
            'id': 'cs_autre_produit',
            'mode': 'payment',
            'metadata': {'pack': 'small', 'user_id': str(self.user.id), 'credits': '10'},
        }))
        self.assertEqual(get_credit_balance(self.user), 0)
        self.assertFalse(CreditTransaction.objects.filter(stripe_session_id='cs_autre_produit').exists())

    def test_credits_checkout_session_carries_the_gridar_marker(self):
        pack = next(iter(CREDIT_PACKS))
        request = APIRequestFactory().post('/billing/credits/buy/', {'pack': pack}, format='json')
        force_authenticate(request, user=self.user)
        session = type('Session', (), {'url': 'https://checkout.stripe.test/s'})()
        with patch.dict(os.environ, {CREDIT_PACKS[pack]['env']: 'price_pack'}), \
                patch('stripe.checkout.Session.create', return_value=session) as create:
            response = BillingCreditsCheckoutView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(create.call_args.kwargs['metadata']['app'], 'gridar')


@patch.dict(os.environ, {'STRIPE_WEBHOOK_SECRET': 'whsec_fake'})
class WebhookEndpointTests(StripeWebhookBase):
    def test_endpoint_applies_event_without_swallowing_a_crash(self):
        fake = event('customer.subscription.updated', subscription_payload('price_agency'))
        request = APIRequestFactory().post('/billing/webhook/', data=b'{}', content_type='application/json')
        with patch('stripe.Webhook.construct_event', return_value=fake), \
                patch('sites_mgmt.views.logger.exception') as crash_log:
            response = BillingWebhookView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        crash_log.assert_not_called()
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.plan, 'agency')


class ResyncCommandTests(StripeWebhookBase):
    def run_resync(self, *args):
        out = StringIO()
        call_command('stripe_resync_subscriptions', *args, stdout=out)
        return out.getvalue()

    def test_dry_run_reports_but_writes_nothing(self):
        self.list_mock.return_value = listing(subscription_payload('price_agency'))
        out = self.run_resync()
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.plan, 'pro')
        self.assertIn('CHANGERAIT', out)
        self.assertNotIn('cus_abc', out)

    def test_apply_writes_the_stripe_state(self):
        self.list_mock.return_value = listing(subscription_payload('price_agency'))
        out = self.run_resync('--apply')
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.plan, 'agency')
        self.assertIn('MIS A JOUR', out)

    def test_live_subscription_wins_over_a_newer_failed_one(self):
        self.list_mock.return_value = listing(
            subscription_payload('price_solo', status='incomplete_expired', id='sub_new'),
            subscription_payload('price_agency', status='active'),
        )
        self.run_resync('--apply')
        self.sub.refresh_from_db()
        self.assertEqual((self.sub.plan, self.sub.status), ('agency', 'active'))

    def test_only_a_failed_checkout_never_upgrades_a_free_client(self):
        self.sub.plan = 'free'
        self.sub.status = 'canceled'
        self.sub.stripe_subscription_id = ''
        self.sub.save()
        self.list_mock.return_value = listing(subscription_payload('price_agency', status='incomplete_expired'))
        self.run_resync('--apply')
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.plan, 'free')

    def test_downgrade_waits_for_the_explicit_flag(self):
        self.list_mock.return_value = listing(subscription_payload('price_pro', status='canceled'))
        out = self.run_resync('--apply')
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.plan, 'pro')
        self.assertIn('RETROGRADATION EN ATTENTE', out)

        self.run_resync('--apply', '--include-downgrades')
        self.sub.refresh_from_db()
        self.assertEqual((self.sub.plan, self.sub.status), ('free', 'canceled'))

    def test_plan_granted_outside_stripe_survives_even_with_the_flag(self):
        self.sub.plan = 'agency'
        self.sub.stripe_subscription_id = ''
        self.sub.save()
        self.list_mock.return_value = listing(subscription_payload('price_solo', status='canceled'))
        out = self.run_resync('--apply', '--include-downgrades')
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.plan, 'agency')
        self.assertIn('PLAN HORS STRIPE', out)

    def test_duplicate_customer_rows_stop_before_any_write(self):
        self.make_client('doublon', 'cus_abc', plan='free', status='canceled')
        self.list_mock.return_value = listing(subscription_payload('price_agency'))
        with self.assertRaises(CommandError):
            self.run_resync('--apply')
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.plan, 'pro')

    def test_a_stripe_error_on_one_client_does_not_stop_the_others(self):
        suivant = self.make_client('suivant', 'cus_ok', plan='pro', sub_id='sub_ok')

        def fake_list(customer=None, **kwargs):
            if customer == 'cus_abc':
                raise stripe.InvalidRequestError("No such customer: 'cus_abc'", 'customer')
            return listing(subscription_payload('price_agency', id='sub_ok', customer='cus_ok'))

        self.list_mock.side_effect = fake_list
        out = self.run_resync('--apply')
        suivant.refresh_from_db()
        self.assertEqual(suivant.plan, 'agency')
        self.assertIn('ERREUR Stripe', out)

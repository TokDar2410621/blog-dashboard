"""Stripe webhook handlers fed with real StripeObject payloads.

Regression for 2026-09-13: Stripe SDK 12+ removed dict.get() from
StripeObject, every handler crashed with AttributeError, and post() swallowed
it to ack Stripe. The old tests never caught it because nothing built a real
StripeObject. These do, the way stripe.Webhook.construct_event does.

Run: python manage.py test sites_mgmt.tests_stripe_webhook
"""
import os
from io import StringIO
from unittest.mock import patch

import stripe
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIRequestFactory

from .models import CreditTransaction, Subscription
from .quota import get_credit_balance
from .views import BillingWebhookView

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
        self.user = User.objects.create_user(username='client', password='x')
        self.sub, _ = Subscription.objects.get_or_create(user=self.user)
        self.sub.stripe_customer_id = 'cus_abc'
        self.sub.plan = 'pro'
        self.sub.save()
        self.view = BillingWebhookView()


@patch.dict(os.environ, PRICES)
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

    def test_unknown_customer_is_ignored(self):
        payload = subscription_payload()
        payload['customer'] = 'cus_personne'
        self.view._dispatch(event('customer.subscription.updated', payload))
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.plan, 'pro')


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

    def test_credit_pack_checkout_credits_the_user(self):
        self.view._dispatch(event('checkout.session.completed', {
            'id': 'cs_pack_1',
            'mode': 'payment',
            'metadata': {'pack': 'small', 'user_id': str(self.user.id), 'credits': '10'},
        }))
        self.assertEqual(get_credit_balance(self.user), 10)
        self.assertEqual(CreditTransaction.objects.filter(stripe_session_id='cs_pack_1').count(), 1)


@patch.dict(os.environ, {**PRICES, 'STRIPE_SECRET_KEY': 'sk_test_fake', 'STRIPE_WEBHOOK_SECRET': 'whsec_fake'})
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


@patch.dict(os.environ, {**PRICES, 'STRIPE_SECRET_KEY': 'sk_test_fake'})
class ResyncCommandTests(StripeWebhookBase):
    def _listing(self, payload):
        return stripe_obj({'object': 'list', 'data': [payload]})

    def test_dry_run_reports_but_writes_nothing(self):
        out = StringIO()
        with patch('stripe.Subscription.list', return_value=self._listing(subscription_payload('price_agency'))):
            call_command('stripe_resync_subscriptions', stdout=out)
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.plan, 'pro')
        self.assertIn('CHANGERAIT', out.getvalue())
        self.assertNotIn('cus_abc', out.getvalue())

    def test_apply_writes_the_stripe_state(self):
        out = StringIO()
        with patch('stripe.Subscription.list', return_value=self._listing(subscription_payload('price_agency'))):
            call_command('stripe_resync_subscriptions', '--apply', stdout=out)
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.plan, 'agency')
        self.assertIn('MIS A JOUR', out.getvalue())

    def test_live_subscription_wins_over_a_newer_failed_one(self):
        # A failed plan change leaves a newer incomplete_expired subscription on
        # top of Stripe's list; picking "newest" would downgrade a paying client.
        newer_failed = subscription_payload('price_solo', status='incomplete_expired', id='sub_new')
        active = subscription_payload('price_agency', status='active')
        listing = stripe_obj({'object': 'list', 'data': [newer_failed, active]})
        with patch('stripe.Subscription.list', return_value=listing):
            call_command('stripe_resync_subscriptions', '--apply', stdout=StringIO())
        self.sub.refresh_from_db()
        self.assertEqual((self.sub.plan, self.sub.status), ('agency', 'active'))

    def test_canceled_remote_subscription_drops_to_free(self):
        with patch('stripe.Subscription.list', return_value=self._listing(subscription_payload(status='canceled'))):
            call_command('stripe_resync_subscriptions', '--apply', stdout=StringIO())
        self.sub.refresh_from_db()
        self.assertEqual((self.sub.plan, self.sub.status), ('free', 'canceled'))

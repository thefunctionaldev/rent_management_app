# Copyright (c) 2026, Shashank Dixit and Contributors
# See license.txt

import hashlib
import hmac
import json
import time
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, add_months, getdate, nowdate

from rent_management import api, razorpay, saas, subscription
from rent_management.tests.test_subscription import KEYS, PLANS


class FakeSubscriptions:
	def __init__(self):
		self.prefix = frappe.generate_hash(length=6)  # unique across tests (rollback is per class)
		self.plans, self.subscriptions, self.payments, self.invoices = {}, {}, {}, {}

	def create_plan(self, payload):
		plan_id = f"plan_{self.prefix}_{len(self.plans) + 1}"
		self.plans[plan_id] = payload
		return {"id": plan_id, **payload}

	def create_subscription(self, payload):
		sub_id = f"sub_{self.prefix}_{len(self.subscriptions) + 1}"
		self.subscriptions[sub_id] = {
			"id": sub_id,
			"status": "created",
			"created_at": int(time.time()) + len(self.subscriptions),
			**payload,
		}
		self.invoices[sub_id] = []
		return self.subscriptions[sub_id]

	def charge(self, sub_id):
		"""Razorpay charges the mandate (first payment, or a renewal)."""
		amount = self.plans[self.subscriptions[sub_id]["plan_id"]]["item"]["amount"]
		payment_id = f"pay_{sub_id}_{len(self.invoices[sub_id]) + 1}"
		self.payments[payment_id] = {
			"id": payment_id,
			"amount": amount,
			"currency": "INR",
			"status": "captured",
		}
		self.invoices[sub_id].append(
			{"status": "paid", "payment_id": payment_id, "amount_paid": amount, "currency": "INR"}
		)
		self.subscriptions[sub_id]["status"] = "active"
		return payment_id

	def get_payment(self, payment_id, auth=None):
		return self.payments[payment_id]

	def get_subscription(self, sub_id):
		return self.subscriptions[sub_id]

	def cancel_subscription(self, sub_id):
		if self.subscriptions[sub_id]["status"] in subscription.ENDED_STATES:
			frappe.throw("Payment gateway error: Subscription is not cancellable in cancelled status.")
		self.subscriptions[sub_id]["status"] = "cancelled"
		return self.subscriptions[sub_id]

	def get_subscription_invoices(self, sub_id):
		return self.invoices[sub_id]


def sign(message, secret=KEYS["razorpay_key_secret"]):
	return hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()


class TestAutopay(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.enterContext(patch.dict(frappe.conf, {**KEYS, "rent_subscription_plans": PLANS}))
		self.gateway = FakeSubscriptions()
		for name in (
			"create_plan",
			"create_subscription",
			"get_payment",
			"get_subscription",
			"cancel_subscription",
			"get_subscription_invoices",
		):
			self.enterContext(patch.object(razorpay, name, getattr(self.gateway, name)))
		self.enterContext(patch.object(subscription, "check_plan_fits"))  # limits are tested elsewhere
		frappe.cache.delete_keys("rent:razorpay-plan")
		frappe.db.delete(subscription.PAYMENT)
		subscription.update_subscription(
			plan="small", billing_cycle=None, trial_ends_on=add_days(nowdate(), 5), current_period_start=None,
			current_period_end=None, auto_renew=0, razorpay_subscription_id=None,
		)  # fmt: skip

	def subscribe(self, plan="small", cycle="Monthly"):
		options = api.create_autopay_checkout(plan, cycle)
		payment_id = self.gateway.charge(options["subscription_id"])
		state = api.verify_autopay(
			payment_id, options["subscription_id"], sign(f"{payment_id}|{options['subscription_id']}")
		)
		return options, state

	def test_first_charge_and_renewals(self):
		options, state = self.subscribe()
		self.assertTrue(state["auto_renew"])
		self.assertEqual(state["status"], "Active")
		first_end = getdate(state["current_period_end"])
		plan = self.gateway.plans[self.gateway.subscriptions[options["subscription_id"]]["plan_id"]]
		self.assertEqual((plan["period"], plan["item"]["amount"]), ("monthly", 30000))

		# Razorpay charges the next month by itself; the daily job records it once
		self.gateway.charge(options["subscription_id"])
		self.assertEqual(len(subscription.reconcile_autopay()), 1)
		self.assertEqual(subscription.reconcile_autopay(), [])
		state = subscription.get_state()
		self.assertEqual(
			getdate(state["current_period_end"]), add_days(add_months(add_days(first_end, 1), 1), -1)
		)
		self.assertEqual(
			frappe.db.count(subscription.PAYMENT, {"status": "Paid", "payment_method": subscription.AUTOPAY}),
			2,
		)

	def test_plan_is_created_once(self):
		api.create_autopay_checkout("small", "Monthly")
		api.create_autopay_checkout("small", "Monthly")
		self.assertEqual(len(self.gateway.plans), 1)
		with patch.dict(frappe.conf, {"rent_razorpay_plan_ids": {"small:Yearly": "plan_from_dashboard"}}):
			self.assertEqual(subscription.get_razorpay_plan("small", "Yearly"), "plan_from_dashboard")

	def test_bad_signature(self):
		options = api.create_autopay_checkout("small", "Monthly")
		payment_id = self.gateway.charge(options["subscription_id"])
		self.assertRaises(
			frappe.ValidationError, api.verify_autopay, payment_id, options["subscription_id"], "forged"
		)
		self.assertFalse(subscription.get_state()["auto_renew"])

	def test_cancel_and_ended_mandate(self):
		options, _state = self.subscribe()
		state = api.cancel_autopay()
		self.assertFalse(state["auto_renew"])
		self.assertEqual(state["status"], "Active")  # the month already paid for stays
		self.assertEqual(self.gateway.subscriptions[options["subscription_id"]]["status"], "cancelled")

		# cancelled from the customer's UPI app: auto-renew turns off on the next check
		options, _state = self.subscribe()
		self.gateway.subscriptions[options["subscription_id"]]["status"] = "cancelled"
		subscription.reconcile_autopay()
		self.assertFalse(subscription.get_state()["auto_renew"])

	def test_switching_plan_replaces_the_mandate(self):
		first, _state = self.subscribe("small")
		second, state = self.subscribe("big")
		self.assertEqual(state["plan"], "big")
		self.assertEqual(self.gateway.subscriptions[first["subscription_id"]]["status"], "cancelled")
		self.assertEqual(
			frappe.db.get_single_value(subscription.SUBSCRIPTION, "razorpay_subscription_id"),
			second["subscription_id"],
		)

	def test_turn_on_later_for_current_plan(self):
		subscription.record_manual_payment("small", "Monthly", 300)
		options = api.create_autopay_checkout("small", "Monthly", start_later=1)
		self.assertIn("start_at", self.gateway.subscriptions[options["subscription_id"]])
		# the mandate is authorised with a small payment that Razorpay refunds
		auth_payment = "pay_auth_only"
		self.gateway.payments[auth_payment] = {
			"id": auth_payment,
			"amount": 500,
			"currency": "INR",
			"status": "captured",
		}
		state = api.verify_autopay(
			auth_payment, options["subscription_id"], sign(f"{auth_payment}|{options['subscription_id']}")
		)
		self.assertTrue(state["auto_renew"])
		self.assertEqual(frappe.db.count(subscription.PAYMENT, {"status": "Paid"}), 1)  # nothing charged yet
		self.assertEqual(frappe.db.get_value(subscription.PAYMENT, options["payment"], "status"), "Created")
		self.assertRaises(frappe.ValidationError, api.create_autopay_checkout, "big", "Monthly", 1)

	def test_first_charge_when_checkout_never_came_back(self):
		options = api.create_autopay_checkout("small", "Monthly")
		self.gateway.charge(options["subscription_id"])  # paid, but the tab was closed
		self.assertEqual(subscription.reconcile_autopay(), [options["payment"]])
		state = subscription.get_state()
		self.assertTrue(state["auto_renew"])
		self.assertEqual(state["status"], "Active")
		self.assertEqual(subscription.reconcile_autopay(), [])

	def test_start_later_when_checkout_never_came_back(self):
		subscription.record_manual_payment("small", "Monthly", 300)
		options = api.create_autopay_checkout("small", "Monthly", start_later=1)
		self.gateway.subscriptions[options["subscription_id"]]["status"] = "authenticated"
		self.assertEqual(subscription.reconcile_autopay(), [])
		self.assertTrue(subscription.get_state()["auto_renew"])
		end = getdate(subscription.get_state()["current_period_end"])

		# the first charge is made when the paid month ends
		self.gateway.charge(options["subscription_id"])
		self.assertEqual(subscription.reconcile_autopay(), [options["payment"]])
		self.assertEqual(
			getdate(subscription.get_state()["current_period_end"]),
			add_days(add_months(add_days(end, 1), 1), -1),
		)

	def test_abandoned_checkout_is_dropped(self):
		options = api.create_autopay_checkout("small", "Monthly")
		subscription.reconcile_autopay()
		self.assertEqual(frappe.db.get_value(subscription.PAYMENT, options["payment"], "status"), "Created")
		self.gateway.subscriptions[options["subscription_id"]]["created_at"] -= 3 * 86400
		subscription.reconcile_autopay()
		self.assertEqual(frappe.db.get_value(subscription.PAYMENT, options["payment"], "status"), "Failed")
		self.assertFalse(subscription.get_state()["auto_renew"])

	def test_older_checkout_finishing_late_does_not_replace_the_mandate(self):
		older = api.create_autopay_checkout("small", "Monthly")
		newer, _state = self.subscribe("big")
		self.gateway.charge(older["subscription_id"])
		self.assertEqual(subscription.reconcile_autopay(), [older["payment"]])  # the money still counts
		self.assertEqual(self.gateway.subscriptions[older["subscription_id"]]["status"], "cancelled")
		self.assertEqual(
			frappe.db.get_single_value(subscription.SUBSCRIPTION, "razorpay_subscription_id"),
			newer["subscription_id"],
		)
		self.assertTrue(subscription.get_state()["auto_renew"])

	def test_paying_for_another_plan_stops_the_mandate(self):
		options, _state = self.subscribe("small")
		subscription.record_manual_payment("small", "Monthly", 300)  # same plan: mandate stays
		self.assertTrue(subscription.get_state()["auto_renew"])
		subscription.record_manual_payment("big", "Monthly", 600)
		self.assertFalse(subscription.get_state()["auto_renew"])
		self.assertEqual(self.gateway.subscriptions[options["subscription_id"]]["status"], "cancelled")

	def test_auto_renew_stays_on_if_the_mandate_could_not_be_cancelled(self):
		self.subscribe()

		def unreachable(sub_id):
			frappe.throw("Could not reach the payment gateway.")

		with patch.object(razorpay, "cancel_subscription", unreachable):
			self.assertRaises(frappe.ValidationError, api.cancel_autopay)
		self.assertTrue(subscription.get_state()["auto_renew"])

	def test_subscription_webhook_reconciles(self):
		options, _state = self.subscribe()
		self.gateway.charge(options["subscription_id"])
		event = {
			"event": "subscription.charged",
			"payload": {"subscription": {"entity": {"id": options["subscription_id"]}}},
		}
		body = json.dumps(event)
		frappe.set_user("Guest")
		try:
			with (
				patch.object(frappe, "request", frappe._dict(get_data=lambda: body.encode()), create=True),
				patch.object(
					frappe,
					"get_request_header",
					lambda name, default=None: sign(body, KEYS["razorpay_webhook_secret"]),
				),
			):
				self.assertEqual(subscription.razorpay_webhook()["status"], "ok")
		finally:
			frappe.set_user("Administrator")
		self.assertEqual(frappe.db.count(subscription.PAYMENT, {"status": "Paid"}), 2)

	def test_webhook_for_a_checkout_that_never_came_back(self):
		options = api.create_autopay_checkout("small", "Monthly")
		self.gateway.charge(options["subscription_id"])
		self.assertEqual(self.webhook(options["subscription_id"])["status"], "ok")
		self.assertTrue(subscription.get_state()["auto_renew"])
		self.assertEqual(self.webhook("sub_of_another_site")["status"], "ignored")

	def webhook(self, sub_id):
		body = json.dumps(
			{"event": "subscription.activated", "payload": {"subscription": {"entity": {"id": sub_id}}}}
		)
		frappe.set_user("Guest")
		try:
			with (
				patch.object(frappe, "request", frappe._dict(get_data=lambda: body.encode()), create=True),
				patch.object(
					frappe,
					"get_request_header",
					lambda name, default=None: sign(body, KEYS["razorpay_webhook_secret"]),
				),
			):
				return subscription.razorpay_webhook()
		finally:
			frappe.set_user("Administrator")

	def test_control_site_forwards_webhooks(self):
		frappe.db.delete(saas.CUSTOMER)
		saas.record_heartbeat({"site": "sharma.example.com", "status": "Active"})
		event = {
			"event": "subscription.charged",
			"payload": {"subscription": {"entity": {"id": "sub_x", "notes": {"site": "sharma.example.com"}}}},
		}
		body = json.dumps(event)
		signature = sign(body, KEYS["razorpay_webhook_secret"])

		def call(event_body):
			frappe.set_user("Guest")
			try:
				with (
					patch.object(
						frappe, "request", frappe._dict(get_data=lambda: event_body.encode()), create=True
					),
					patch.object(
						frappe,
						"get_request_header",
						lambda name, default=None: sign(event_body, KEYS["razorpay_webhook_secret"]),
					),
				):
					return saas.razorpay_webhook()
			finally:
				frappe.set_user("Administrator")

		with (
			patch.dict(frappe.conf, {"rent_control_site": 1}),
			patch.object(saas.requests, "post", return_value=MagicMock(ok=True)) as post,
		):
			self.assertEqual(call(body)["site"], "sharma.example.com")
			self.assertEqual(
				post.call_args.args[0],
				"https://sharma.example.com/api/method/rent_management.subscription.razorpay_webhook",
			)
			self.assertEqual(post.call_args.kwargs["headers"]["X-Razorpay-Signature"], signature)
			self.assertEqual(post.call_args.kwargs["data"], body.encode())
			# events of sites that aren't our customers are dropped
			stranger = json.dumps(
				{"event": "order.paid", "payload": {"order": {"entity": {"notes": {"site": "evil.example"}}}}}
			)
			self.assertEqual(call(stranger)["status"], "ignored")

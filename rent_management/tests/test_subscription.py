# Copyright (c) 2026, Shashank Dixit and Contributors
# See license.txt

import hashlib
import hmac
import json
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, add_months, getdate, nowdate

from rent_management import api, razorpay, subscription
from rent_management.rent_management_system.doctype.tenant_space_allotment.test_tenant_space_allotment import (
	make_room,
	make_tenant,
)
from rent_management.tests.test_api import make_user

KEYS = {
	"razorpay_key_id": "rzp_test_key",
	"razorpay_key_secret": "secret",
	"razorpay_webhook_secret": "whsec",
}
PLANS = {
	"small": {"title": "Small", "monthly": 300, "yearly": 3000, "max_rooms": 2, "max_users": 1},
	"big": {"title": "Big", "monthly": 900, "yearly": 9000, "max_rooms": 0, "max_users": 0},
}


def today():
	return getdate(nowdate())


def sign(message: str, secret: str) -> str:
	return hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()


class FakeRazorpay:
	"""Stands in for the Razorpay API: orders are created locally and paid with pay()."""

	def __init__(self):
		self.orders, self.payments = {}, {}

	def create_order(self, amount, currency, receipt, notes=None):
		order = {
			"id": f"order_{len(self.orders) + 1}",
			"amount": razorpay.to_subunits(amount),
			"currency": currency,
		}
		self.orders[order["id"]] = order
		return order

	def pay(self, order_id, status="captured", amount=None):
		order = self.orders[order_id]
		payment_id = f"pay_{len(self.payments) + 1}"
		self.payments[payment_id] = {
			"id": payment_id,
			"order_id": order_id,
			"amount": order["amount"] if amount is None else amount,
			"currency": order["currency"],
			"status": status,
		}
		return payment_id

	def get_payment(self, payment_id):
		return dict(self.payments[payment_id])

	def capture_payment(self, payment_id, amount, currency):
		self.payments[payment_id]["status"] = "captured"
		return dict(self.payments[payment_id])

	def get_order_payments(self, order_id):
		return [p for p in self.payments.values() if p["order_id"] == order_id]


class TestSubscription(IntegrationTestCase):
	def setUp(self):
		self.manager = make_user("sub.manager@example.com", ["Rent Manager"])
		frappe.flags.enforce_rent_subscription = True
		self.enterContext(
			patch.dict(frappe.conf, {**KEYS, "rent_subscription_plans": PLANS, "rent_trial_plan": "small"})
		)
		self.gateway = FakeRazorpay()
		for name in ("create_order", "get_payment", "capture_payment", "get_order_payments"):
			self.enterContext(patch.object(razorpay, name, getattr(self.gateway, name)))

		frappe.db.delete(subscription.PAYMENT)
		self.set_subscription(trial_ends_on=add_days(today(), 10))
		self.set_limits(rooms=100, users=100)
		frappe.set_user(self.manager)

	def set_limits(self, plan="small", rooms=0, users=0):
		"""Limits relative to what the test database already holds."""
		usage = subscription.get_usage()
		self.enterContext(
			patch.dict(
				PLANS[plan],
				{
					"max_rooms": usage["rooms"] + rooms if rooms else 0,
					"max_users": usage["users"] + users if users else 0,
				},
			)
		)

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.flags.enforce_rent_subscription = False

	def set_subscription(self, **values):
		values = {
			"plan": "small",
			"billing_cycle": None,
			"trial_ends_on": None,
			"current_period_start": None,
			"current_period_end": None,
			**values,
		}
		subscription.update_subscription(**values)

	def checkout_and_pay(self, plan, cycle, **pay_kwargs):
		options = api.create_subscription_checkout(plan, cycle)
		payment_id = self.gateway.pay(options["order_id"], **pay_kwargs)
		signature = sign(f"{options['order_id']}|{payment_id}", KEYS["razorpay_key_secret"])
		return options, payment_id, signature

	# ------------------------------------------------------------ status

	def test_status(self):
		sub = frappe._dict(trial_ends_on=add_days(today(), 1))
		self.assertEqual(subscription.get_status(sub), "Trial")
		sub.trial_ends_on = add_days(today(), -1)
		self.assertEqual(subscription.get_status(sub), "Expired")

		sub.current_period_end = today()
		self.assertEqual(subscription.get_status(sub), "Active")
		sub.current_period_end = add_days(today(), -subscription.grace_days())
		self.assertEqual(subscription.get_status(sub), "Past Due")
		sub.current_period_end = add_days(today(), -subscription.grace_days() - 1)
		self.assertEqual(subscription.get_status(sub), "Expired")

	def test_boot_has_subscription(self):
		state = api.get_boot()["subscription"]
		self.assertEqual(state["status"], "Trial")
		self.assertEqual(state["days_left"], 10)
		self.assertEqual(state["plan_title"], "Small")
		self.assertEqual(state["usage"], subscription.get_usage())

	# ------------------------------------------------------------ enforcement

	def test_lapsed_site_is_read_only(self):
		tenant = make_tenant()
		self.set_subscription(trial_ends_on=add_days(today(), -1))

		self.assertRaises(subscription.SubscriptionExpiredError, make_tenant)
		tenant.reload()
		tenant.occupation = "Engineer"
		self.assertRaises(subscription.SubscriptionExpiredError, tenant.save)
		self.assertRaises(subscription.SubscriptionExpiredError, tenant.delete)
		# reading still works
		self.assertTrue(api.get_tenants())

		# Administrator (you, for support) is never blocked
		frappe.set_user("Administrator")
		make_tenant()

	def test_past_due_is_still_usable(self):
		self.set_subscription(current_period_end=add_days(today(), -1))
		self.assertEqual(subscription.get_state()["status"], "Past Due")
		make_tenant()

	def test_room_limit(self):
		self.set_limits(rooms=2)
		make_room()
		make_room()
		with self.assertRaises(subscription.PlanLimitError):
			make_room()

	def test_user_limit(self):
		frappe.set_user("Administrator")
		user = frappe.get_doc("User", make_user("sub.second@example.com"))
		usage = subscription.get_usage()
		self.enterContext(patch.dict(PLANS["small"], {"max_users": usage["users"]}))
		# Administrator skips every check, so enforce them here as if a customer added the user
		self.enterContext(patch.object(subscription, "skip_enforcement", return_value=False))

		self.assertRaises(subscription.PlanLimitError, user.add_roles, "Rent Manager")

		# disabling a manager frees a seat; existing managers can still be edited
		frappe.db.set_value("User", self.manager, "enabled", 0)
		user.reload()
		user.add_roles("Rent Manager")
		frappe.get_doc("User", user.name).save()

	def test_customer_cannot_edit_subscription(self):
		sub = frappe.get_single(subscription.SUBSCRIPTION)
		sub.current_period_end = add_days(today(), 365)
		sub.flags.ignore_permissions = True
		self.assertRaises(frappe.PermissionError, sub.save)

	def test_monthly_invoicing_skipped_when_lapsed(self):
		self.set_subscription(trial_ends_on=add_days(today(), -1))
		self.assertTrue(subscription.skip_if_lapsed())

	# ------------------------------------------------------------ checkout

	def test_pay_from_trial(self):
		options, payment_id, signature = self.checkout_and_pay("small", "Monthly")
		self.assertEqual(options["amount"], 30000)
		self.assertEqual(options["key"], "rzp_test_key")

		state = api.verify_subscription_payment(options["order_id"], payment_id, signature)
		self.assertEqual(state["status"], "Active")
		self.assertEqual(getdate(state["current_period_end"]), add_days(add_months(today(), 1), -1))

		payment = frappe.get_doc(subscription.PAYMENT, options["payment"])
		self.assertEqual(payment.status, "Paid")
		self.assertEqual(payment.razorpay_payment_id, payment_id)

		# the checkout callback and the webhook may both arrive: nothing is applied twice
		api.verify_subscription_payment(options["order_id"], payment_id, signature)
		self.assertEqual(getdate(subscription.get_state()["current_period_end"]), getdate(payment.period_end))

	def test_bad_signature_is_rejected(self):
		options, payment_id, _signature = self.checkout_and_pay("small", "Monthly")
		self.assertRaises(
			frappe.ValidationError,
			api.verify_subscription_payment,
			options["order_id"],
			payment_id,
			sign(f"{options['order_id']}|{payment_id}", "wrong secret"),
		)
		self.assertEqual(subscription.get_state()["status"], "Trial")

	def test_wrong_amount_is_rejected(self):
		options, payment_id, signature = self.checkout_and_pay("small", "Monthly", amount=100)
		self.assertRaises(
			frappe.ValidationError,
			api.verify_subscription_payment,
			options["order_id"],
			payment_id,
			signature,
		)

	def test_authorized_payment_is_captured(self):
		options, payment_id, signature = self.checkout_and_pay("small", "Monthly", status="authorized")
		api.verify_subscription_payment(options["order_id"], payment_id, signature)
		self.assertEqual(self.gateway.payments[payment_id]["status"], "captured")

	def test_early_renewal_stacks(self):
		end = add_days(today(), 5)
		self.set_subscription(
			billing_cycle="Yearly", current_period_start=add_days(end, -364), current_period_end=end
		)
		options, payment_id, signature = self.checkout_and_pay("small", "Yearly")
		state = api.verify_subscription_payment(options["order_id"], payment_id, signature)
		self.assertEqual(getdate(state["current_period_end"]), add_days(add_months(add_days(end, 1), 12), -1))

	def test_upgrade_converts_unused_days(self):
		start = today()
		end = add_days(add_months(start, 1), -1)
		self.set_subscription(billing_cycle="Monthly", current_period_start=start, current_period_end=end)

		options, payment_id, signature = self.checkout_and_pay("big", "Monthly")
		api.verify_subscription_payment(options["order_id"], payment_id, signature)

		payment = frappe.get_doc(subscription.PAYMENT, options["payment"])
		# small is a third of the price of big, so the unused days are worth about a third as many
		self.assertAlmostEqual(payment.bonus_days, (getdate(end) - start).days / 3, delta=1)
		self.assertEqual(getdate(payment.period_start), start)
		self.assertEqual(
			getdate(payment.period_end), add_days(add_days(add_months(start, 1), -1), payment.bonus_days)
		)
		self.assertEqual(subscription.get_state()["plan"], "big")

	def test_downgrade_blocked_when_over_limit(self):
		self.set_limits(rooms=1)
		self.set_subscription(plan="big", trial_ends_on=add_days(today(), 5))
		make_room()
		make_room()
		self.assertRaises(subscription.PlanLimitError, api.create_subscription_checkout, "small", "Monthly")
		api.create_subscription_checkout("big", "Monthly")

	def test_unknown_plan(self):
		self.assertRaises(frappe.ValidationError, api.create_subscription_checkout, "gold", "Monthly")
		self.assertRaises(frappe.ValidationError, api.create_subscription_checkout, "small", "Weekly")

	def test_outsider_cannot_pay(self):
		frappe.set_user("Administrator")
		frappe.set_user(make_user("sub.outsider@example.com"))
		self.assertRaises(frappe.PermissionError, api.create_subscription_checkout, "small", "Monthly")
		self.assertRaises(frappe.PermissionError, api.get_billing)

	# ------------------------------------------------------------ webhook & reconcile

	def call_webhook(self, event, secret=KEYS["razorpay_webhook_secret"]):
		body = json.dumps(event)
		frappe.set_user("Guest")
		with (
			patch.object(frappe, "request", frappe._dict(get_data=lambda: body.encode()), create=True),
			patch.object(frappe, "get_request_header", lambda name, default=None: sign(body, secret)),
		):
			return subscription.razorpay_webhook()

	def test_webhook(self):
		options = api.create_subscription_checkout("small", "Monthly")
		payment_id = self.gateway.pay(options["order_id"])
		event = {
			"event": "order.paid",
			"payload": {"payment": {"entity": {"id": payment_id, "order_id": options["order_id"]}}},
		}

		self.assertRaises(frappe.AuthenticationError, self.call_webhook, event, secret="forged")
		self.assertEqual(self.call_webhook(event)["status"], "ok")
		self.assertEqual(frappe.db.get_value(subscription.PAYMENT, options["payment"], "status"), "Paid")

		# orders of other customer sites are ignored
		event["payload"]["payment"]["entity"]["order_id"] = "order_of_another_site"
		self.assertEqual(self.call_webhook(event)["status"], "ignored")

	def test_reconcile_pending_orders(self):
		options = api.create_subscription_checkout("small", "Monthly")
		self.gateway.pay(options["order_id"])
		frappe.set_user("Administrator")
		subscription.reconcile_pending_orders()
		self.assertEqual(frappe.db.get_value(subscription.PAYMENT, options["payment"], "status"), "Paid")
		self.assertEqual(subscription.get_state()["status"], "Active")

	def test_manual_payment(self):
		frappe.set_user("Administrator")
		until = add_days(today(), 90)
		payment = subscription.record_manual_payment("big", "Yearly", 9000, "NEFT-1", today(), until)
		self.assertEqual(payment.payment_method, "Manual")
		state = subscription.get_state()
		self.assertEqual((state["status"], state["plan"]), ("Active", "big"))
		self.assertEqual(getdate(state["current_period_end"]), until)

	def test_billing_page(self):
		self.checkout_and_pay("small", "Monthly")
		billing = api.get_billing()
		self.assertEqual([p["key"] for p in billing["plans"]], ["small", "big"])
		self.assertTrue(billing["online_payments"])
		self.assertEqual(billing["payments"], [])  # unpaid orders are not listed

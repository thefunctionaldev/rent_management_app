# Copyright (c) 2026, Shashank Dixit and Contributors
# See license.txt

import hashlib
import hmac
import json
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import frappe
from frappe.tests import IntegrationTestCase

from rent_management import api, razorpay, rent_collection, subscription
from rent_management.rent_management_system.doctype.tenant_rent_invoice.test_tenant_rent_invoice import (
	make_invoice,
)
from rent_management.rent_management_system.doctype.tenant_space_allotment.test_tenant_space_allotment import (
	make_allotment,
	make_room,
)
from rent_management.tests.test_api import make_user


class FakeLandlordRazorpay:
	"""Payment links on the landlord's Razorpay account."""

	def __init__(self):
		# ids are unique across tests: the database is only rolled back per test class
		self.links, self.calls, self.prefix = {}, [], frappe.generate_hash(length=6)

	def create_payment_link(self, payload, auth):
		self.calls.append(("create", auth))
		link_id = f"plink_{self.prefix}_{len(self.links) + 1}"
		self.links[link_id] = {
			"id": link_id,
			"short_url": f"https://rzp.io/i/{link_id}",
			"status": "created",
			"payments": [],
			**payload,
		}
		return self.links[link_id]

	def get_payment_link(self, link_id, auth):
		return self.links[link_id]

	def cancel_payment_link(self, link_id, auth):
		self.links[link_id]["status"] = "cancelled"
		return self.links[link_id]

	def pay(self, link_id, amount=None, method="upi"):
		link = self.links[link_id]
		payment = {
			"payment_id": f"pay_{link_id}_{len(link['payments']) + 1}",
			"amount": link["amount"] if amount is None else amount,
			"method": method,
			"status": "captured",
		}
		link["payments"].append(payment)
		link["status"] = "paid"
		return payment


class TestRentCollection(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		settings = frappe.get_single("Rent Management Settings")
		settings.update(
			{
				"upi_id": "sharmapg@okhdfcbank",
				"upi_payee_name": "Sharma PG",
				"razorpay_enabled": 1,
				"razorpay_key_id": "rzp_test_landlord",
				"razorpay_key_secret": "landlord-secret",
				"razorpay_webhook_secret": "landlord-webhook",
			}
		)
		settings.save()
		self.gateway = FakeLandlordRazorpay()
		for name in ("create_payment_link", "get_payment_link", "cancel_payment_link"):
			self.enterContext(patch.object(razorpay, name, getattr(self.gateway, name)))

		self.invoice = make_invoice(allotment=make_allotment(room=make_room(rent=3000)), submit=True)

	def link(self, n):
		return f"plink_{self.gateway.prefix}_{n}"

	def test_upi_qr(self):
		link = rent_collection.get_upi_link(self.invoice)
		params = parse_qs(urlparse(link).query)
		self.assertTrue(link.startswith("upi://pay?"))
		self.assertEqual(params["pa"], ["sharmapg@okhdfcbank"])
		self.assertEqual(params["am"], ["3000.00"])
		self.assertIn(self.invoice.name, params["tn"][0])
		self.assertTrue(rent_collection.qr_data_uri(link).startswith("data:image/svg+xml;base64,"))

		data = api.get_invoice(self.invoice.name)
		self.assertEqual(data["online"], {"upi": True, "razorpay": True})
		self.assertTrue(data["upi_qr"])

	def test_payment_link_is_reused_and_renewed(self):
		url = api.get_payment_link(self.invoice.name)
		self.assertEqual(self.gateway.calls, [("create", ("rzp_test_landlord", "landlord-secret"))])
		link = self.gateway.links[self.link(1)]
		self.assertEqual((link["amount"], link["notes"]["invoice"]), (300000, self.invoice.name))
		self.assertEqual(api.get_payment_link(self.invoice.name), url)  # same balance: same link
		self.assertEqual(len(self.gateway.links), 1)

		# the tenant pays part in cash: a new link for the new balance replaces the old one
		api.record_payment(self.invoice.name, 1000, "Cash")
		new_url = api.get_payment_link(self.invoice.name)
		self.assertNotEqual(new_url, url)
		self.assertEqual(self.gateway.links[self.link(1)]["status"], "cancelled")
		self.assertEqual(self.gateway.links[self.link(2)]["amount"], 200000)

	def test_paid_link_is_recorded_once(self):
		api.get_payment_link(self.invoice.name)
		payment = self.gateway.pay(self.link(1), method="card")
		recorded = api.check_online_payment(self.invoice.name)
		self.assertEqual(len(recorded), 1)
		rent_payment = frappe.get_doc("Rent Payment", recorded[0])
		self.assertEqual(
			(
				rent_payment.amount,
				rent_payment.mode_of_payment,
				rent_payment.reference_no,
				rent_payment.docstatus,
			),
			(3000, "Card", payment["payment_id"], 1),
		)
		self.invoice.reload()
		self.assertEqual(self.invoice.status, "Paid")
		self.assertEqual(api.check_online_payment(self.invoice.name), [])  # idempotent

	def test_overpayment_is_capped(self):
		api.get_payment_link(self.invoice.name)
		api.record_payment(self.invoice.name, 500, "Cash")  # paid in cash after the link was sent
		self.gateway.pay(self.link(1))  # tenant still pays the full 3000 online
		recorded = api.check_online_payment(self.invoice.name)
		rent_payment = frappe.get_doc("Rent Payment", recorded[0])
		self.assertEqual(rent_payment.amount, 2500)
		self.assertIn("refund", rent_payment.remarks)

	def test_webhook(self):
		api.get_payment_link(self.invoice.name)
		payment = self.gateway.pay(self.link(1))
		event = {
			"event": "payment_link.paid",
			"payload": {
				"payment_link": {"entity": {"id": self.link(1)}},
				"payment": {"entity": {"id": payment["payment_id"], "amount": 300000, "method": "upi"}},
			},
		}
		self.assertRaises(frappe.AuthenticationError, self.call_webhook, event, "forged")
		self.assertEqual(self.call_webhook(event, "landlord-webhook")["status"], "ok")
		self.assertEqual(frappe.db.get_value("Tenant Rent Invoice", self.invoice.name, "status"), "Paid")
		event["payload"]["payment_link"]["entity"]["id"] = "plink_other"
		self.assertEqual(self.call_webhook(event, "landlord-webhook")["status"], "ignored")

	def call_webhook(self, event, secret):
		body = json.dumps(event)
		signature = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
		frappe.set_user("Guest")
		try:
			with (
				patch.object(frappe, "request", frappe._dict(get_data=lambda: body.encode()), create=True),
				patch.object(frappe, "get_request_header", lambda name, default=None: signature),
			):
				return rent_collection.razorpay_webhook()
		finally:
			frappe.set_user("Administrator")

	def test_recorded_even_when_subscription_lapsed(self):
		"""The money is in the landlord's account already, so it is recorded on a read-only site too."""
		api.get_payment_link(self.invoice.name)
		self.gateway.pay(self.link(1))
		manager = make_user("collect.manager@example.com", ["Rent Manager"])
		frappe.flags.enforce_rent_subscription = True
		try:
			with patch.object(subscription, "get_status", return_value="Expired"):
				frappe.set_user(manager)
				self.assertRaises(
					subscription.SubscriptionExpiredError, api.record_payment, self.invoice.name, 1, "Cash"
				)
				api.check_online_payment(self.invoice.name)
		finally:
			frappe.flags.enforce_rent_subscription = False
			frappe.set_user("Administrator")
		self.assertEqual(frappe.db.get_value("Tenant Rent Invoice", self.invoice.name, "status"), "Paid")

	def test_requires_razorpay_settings(self):
		frappe.db.set_single_value("Rent Management Settings", "razorpay_enabled", 0)
		self.assertRaises(frappe.ValidationError, api.get_payment_link, self.invoice.name)
		self.assertEqual(api.get_invoice(self.invoice.name)["online"]["razorpay"], False)

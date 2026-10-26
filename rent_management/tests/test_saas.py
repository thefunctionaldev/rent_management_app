# Copyright (c) 2026, Shashank Dixit and Contributors
# See license.txt

import json
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, nowdate

from rent_management import saas, subscription
from rent_management.tests.test_subscription import PLANS

CONTROL = {"rent_control_site": 1, "rent_control_secret": "control-secret", "rent_subscription_plans": PLANS}


def beat(site, **values):
	return {
		"site": site,
		"status": "Active",
		"plan": "small",
		"billing_cycle": "Yearly",
		"beds": 20,
		"rooms": 8,
		"properties": 1,
		"users": 1,
		"tenants": 15,
		"total_paid": 3000,
		**values,
	}


class TestSaas(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		frappe.db.delete(saas.CUSTOMER)
		self.enterContext(patch.dict(frappe.conf, CONTROL))

	def call_heartbeat(self, data, secret="control-secret"):
		body = json.dumps(data).encode()
		signature = saas.sign(body) if secret == "control-secret" else "forged"
		frappe.set_user("Guest")
		try:
			with (
				patch.object(frappe, "request", frappe._dict(get_data=lambda: body), create=True),
				patch.object(frappe, "get_request_header", lambda name, default=None: signature),
			):
				return saas.heartbeat()
		finally:
			frappe.set_user("Administrator")

	def test_heartbeat_is_recorded(self):
		self.assertEqual(
			self.call_heartbeat(beat("sharma.example.com", billing_name="Sharma PG"))["status"], "ok"
		)
		customer = frappe.get_doc(saas.CUSTOMER, "sharma.example.com")
		self.assertEqual((customer.status, customer.billing_name, customer.beds), ("Active", "Sharma PG", 20))
		self.assertEqual(customer.mrr, 250)  # 3000 a year

		# the next heartbeat updates the same record
		self.call_heartbeat(beat("sharma.example.com", status="Expired"))
		customer.reload()
		self.assertEqual((customer.status, customer.mrr, customer.billing_name), ("Expired", 0, "Sharma PG"))

	def test_heartbeat_needs_signature_and_control_site(self):
		self.assertRaises(
			frappe.AuthenticationError, self.call_heartbeat, beat("x.example.com"), secret="wrong"
		)
		with patch.dict(frappe.conf, {"rent_control_site": 0}):
			self.assertRaises(frappe.PermissionError, self.call_heartbeat, beat("x.example.com"))
		self.assertRaises(frappe.ValidationError, saas.record_heartbeat, beat("bad site/../x"))

	def test_dashboard(self):
		saas.record_heartbeat(
			beat(
				"a.example.com",
				billing_cycle="Monthly",
				first_paid_on=nowdate(),
				trial_ends_on=add_days(nowdate(), -20),
			)
		)
		saas.record_heartbeat(
			beat("b.example.com", status="Trial", trial_ends_on=add_days(nowdate(), 3), billing_cycle=None)
		)
		saas.record_heartbeat(beat("c.example.com", status="Expired", trial_ends_on=add_days(nowdate(), -5)))
		saas.record_heartbeat(beat("d.example.com", current_period_end=add_days(nowdate(), 4)))
		data = saas.get_dashboard()
		self.assertEqual(data["mrr"], 300 + 250)
		self.assertEqual(data["paying"], 2)
		self.assertEqual([c.site for c in data["trials_ending"]], ["b.example.com"])
		self.assertEqual([c.site for c in data["renewals_due"]], ["d.example.com"])
		self.assertEqual(data["conversion"], 50)  # a paid after its trial, c didn't

	def test_customer_site_sends_heartbeat(self):
		subscription.update_subscription(
			plan="small", trial_ends_on=add_days(nowdate(), 5), current_period_end=None
		)
		with patch.dict(
			frappe.conf, {"rent_control_site": 0, "rent_control_url": "https://admin.example.com"}
		):
			with patch.object(saas.requests, "post", return_value=MagicMock()) as post:
				saas.send_heartbeat()
			url = post.call_args.args[0]
			body = post.call_args.kwargs["data"]
			self.assertEqual(url, "https://admin.example.com/api/method/rent_management.saas.heartbeat")
			self.assertEqual(json.loads(body)["status"], "Trial")
			self.assertEqual(post.call_args.kwargs["headers"][saas.SIGNATURE_HEADER], saas.sign(body))

		with patch.dict(frappe.conf, {"rent_control_site": 0, "rent_control_url": None}):
			with patch.object(saas.requests, "post") as post:
				saas.send_heartbeat()
			post.assert_not_called()

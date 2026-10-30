# Copyright (c) 2026, Shashank Dixit and Contributors
# See license.txt

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, nowdate

from rent_management import activity, api, register
from rent_management.rent_management_system.doctype.tenant_rent_invoice.test_tenant_rent_invoice import (
	make_invoice,
)
from rent_management.rent_management_system.doctype.tenant_space_allotment.test_tenant_space_allotment import (
	make_allotment,
	make_property,
	make_room,
)


class TestActivityLog(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		frappe.db.delete(activity.ACTIVITY)
		self.building = make_property()
		self.stay = make_allotment(
			room=make_room(rent=6000, property=self.building), allotment_date="2026-01-01"
		)
		staff = api.save_staff(
			{"staff_name": "Gopal", "role": "Warden", "property": self.building, "monthly_salary": 10000}
		)
		self.warden = f"gopal.{frappe.generate_hash(length=5)}@staff.example"
		api.give_staff_login(staff, self.warden, ["payments", "register"])

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.local.rent_staff_access = {}

	def entries(self, **filters):
		return frappe.get_all(
			activity.ACTIVITY,
			filters=filters,
			fields=["user", "category", "summary", "property", "amount"],
			order_by="creation desc",
		)

	def test_who_did_what(self):
		self.assertIn("gave Gopal a login", self.entries(category="Staff")[0].summary)
		self.assertIn(f"moved {self.stay.tenant_name} into room", self.entries(category="Stays")[0].summary)

		invoice = make_invoice(self.stay, submit=True)
		frappe.set_user(self.warden)
		frappe.local.rent_staff_access = {}
		api.record_payment(invoice.name, 5000, "Cash")
		frappe.set_user("Administrator")
		paid = self.entries(category="Payments")[0]
		self.assertEqual(paid.user, self.warden)
		self.assertEqual(
			paid.summary, f"recorded ₹5,000 in cash from {self.stay.tenant_name} for January 2026"
		)
		self.assertEqual((paid.property, paid.amount), (self.building, 5000))

		payment = frappe.get_last_doc("Rent Payment", {"rent_invoice": invoice.name})
		payment.cancel()  # still possible with an activity entry naming it
		self.assertIn("cancelled the ₹5,000 payment", self.entries(category="Payments")[0].summary)

		api.revise_rent(self.stay.name, 6500)
		self.assertIn("from ₹6,000 to ₹6,500", self.entries(category="Stays")[0].summary)

		leave = register.request_leave(self.stay.name, nowdate(), add_days(nowdate(), 2))
		api.decide_leave(leave, 1)
		self.assertIn("approved the leave of", self.entries(category="Register")[0].summary)

	def test_settings_without_secrets(self):
		settings = frappe.get_single("Rent Management Settings")
		settings.late_fee_amount = (settings.late_fee_amount or 0) + 100
		settings.razorpay_key_secret = "very-secret-value"
		settings.save()
		summary = self.entries(category="Settings")[0].summary
		self.assertIn("Late Fee Amount:", summary)
		self.assertIn("(changed)", summary)
		self.assertNotIn("very-secret-value", summary)

	def test_aadhaar_views_and_invoice_runs(self):
		with patch(
			"rent_management.rent_management_system.doctype.tenant.tenant.Tenant.reveal_aadhar",
			return_value="234123412346",
		):
			api.reveal_aadhaar(self.stay.tenant)
		self.assertIn("viewed the Aadhaar number of", self.entries(category="Privacy")[0].summary)

		frappe.db.delete(activity.ACTIVITY, {"category": "Invoices"})
		api.generate_invoices("February", 2026, submit=1)
		runs = self.entries(category="Invoices")
		self.assertEqual(len(runs), 1)  # one for the run, not one per invoice
		self.assertIn("issued", runs[0].summary)

	def test_only_managers_read_it(self):
		self.assertTrue(api.get_activity()["rows"])
		frappe.set_user(self.warden)
		frappe.local.rent_staff_access = {}
		self.assertRaises(frappe.PermissionError, api.get_activity)
		self.assertFalse(frappe.has_permission(activity.ACTIVITY, "read"))

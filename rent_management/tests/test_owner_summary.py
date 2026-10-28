# Copyright (c) 2026, Shashank Dixit and Contributors
# See license.txt

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, add_months, get_first_day, getdate, nowdate

from rent_management import api, notifications, owner_summary
from rent_management.rent_management_system.doctype.tenant_rent_invoice.tenant_rent_invoice import MONTHS
from rent_management.rent_management_system.doctype.tenant_rent_invoice.test_tenant_rent_invoice import (
	make_invoice,
)
from rent_management.rent_management_system.doctype.tenant_space_allotment.test_tenant_space_allotment import (
	make_allotment,
	make_property,
	make_room,
)


class TestOwnerSummary(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.building = make_property()
		self.start = get_first_day(add_months(nowdate(), -1))
		self.month, self.year = MONTHS[self.start.month - 1], self.start.year
		room = make_room(rent=8000, capacity=2, property=self.building)
		self.stay = make_allotment(room=room, allotment_date=add_days(self.start, 4))
		self.invoice = make_invoice(
			self.stay, billing_month=self.month, billing_year=self.year, posting_date=self.start, submit=True
		)
		frappe.get_doc(
			{"doctype": "Rent Payment", "tenant": self.stay.tenant, "rent_invoice": self.invoice.name,
				"amount": 5000, "payment_date": add_days(self.start, 6), "mode_of_payment": "UPI"}
		).insert().submit()  # fmt: skip
		frappe.get_doc(
			{"doctype": "Property Expense", "property": self.building, "expense_date": add_days(self.start, 9),
				"category": "Electricity Bill", "amount": 1200}
		).insert()  # fmt: skip

	def test_summary_of_a_building(self):
		s = owner_summary.build(self.month, self.year, self.building)
		self.assertEqual((s["collected"], s["expenses"], s["profit"]), (5000, 1200, 3800))
		self.assertEqual(s["invoiced"], self.invoice.final_amount)
		self.assertEqual((s["beds"], s["taken"], s["occupancy"]), (2, 1, 50))
		self.assertEqual(len(s["moved_in"]), 1)
		self.assertEqual(s["outstanding"], self.invoice.final_amount - 5000)
		self.assertEqual(s["top_expenses"][0]["category"], "Electricity Bill")
		if getdate(self.invoice.due_date) < getdate(nowdate()):
			self.assertEqual(s["defaulters"][0]["tenant_name"], self.stay.tenant_name)

		self.assertEqual(
			[owner_summary.money(v) for v in (214265.85, 999, 1000, -52036.8)],
			["₹2,14,266", "₹999", "₹1,000", "-₹52,037"],
		)
		text = owner_summary.text(s)
		self.assertIn(f"*{self.month} {self.year} at {self.building}*", text)
		self.assertIn("Beds: 1 of 2 taken (50%)", text)
		params = owner_summary.template_params(s)
		self.assertEqual(len(params), 11)
		self.assertFalse(any("\\n" in p for p in params))  # WhatsApp template params are one line

		data = api.get_owner_summary(self.month, self.year, self.building)
		self.assertTrue(data["whatsapp_url"].startswith("https://wa.me/"))

	def test_sent_once_on_the_day(self):
		frappe.db.set_single_value(
			"Rent Management Settings",
			{"owner_summary_enabled": 1, "owner_summary_day": min(getdate(nowdate()).day, 28),
				"owner_summary_email": "owner@example.com", "notify_by_email": 1, "notify_by_whatsapp": 0},
		)  # fmt: skip
		frappe.clear_document_cache("Rent Management Settings", "Rent Management Settings")
		frappe.db.delete(notifications.LOG, {"message_type": "Owner Summary"})
		sent = []
		with (
			patch.object(notifications, "email_configured", return_value=True),
			patch.object(frappe, "sendmail", lambda **kw: sent.append(kw)),
		):
			owner_summary.send_monthly()
			owner_summary.send_monthly()  # not twice
		if getdate(nowdate()).day <= 28:
			self.assertEqual(len(sent), 1)
			self.assertEqual(sent[0]["recipients"], ["owner@example.com"])
			self.assertIn("profit", sent[0]["subject"])
			if self.invoice.outstanding_amount:
				self.assertIn("Who still owes", sent[0]["message"])
		frappe.db.set_single_value("Rent Management Settings", "owner_summary_enabled", 0)

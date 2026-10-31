# Copyright (c) 2026, Shashank Dixit and Contributors
# See license.txt

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import flt

from rent_management import api, bulk, notifications
from rent_management.rent_management_system.doctype.tenant_rent_invoice.test_tenant_rent_invoice import (
	make_invoice,
)
from rent_management.rent_management_system.doctype.tenant_space_allotment.test_tenant_space_allotment import (
	make_allotment,
	make_property,
	make_room,
)

SETTINGS = "Rent Management Settings"


class TestBulk(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		frappe.db.set_single_value(SETTINGS, {"notify_by_email": 1, "notify_by_whatsapp": 0})
		self.building = make_property()
		self.bills = []
		for first, email in (("Asha", "asha.b@example.com"), ("Bilal", None)):
			tenant = frappe.get_doc({"doctype": "Tenant", "first_name": first, "email_id": email}).insert()
			stay = make_allotment(room=make_room(rent=6000, property=self.building), tenant=tenant,
				allotment_date="2026-01-01")  # fmt: skip
			self.bills.append(make_invoice(stay, submit=True))

	def tearDown(self):
		frappe.db.rollback()

	def row(self, data, bill):
		return next(r for r in data["rows"] if r["invoice"] == bill.name)

	def test_remind_all(self):
		with patch.object(notifications, "email_configured", return_value=True):
			data = api.get_reminder_list(self.building)
			asha, bilal = self.row(data, self.bills[0]), self.row(data, self.bills[1])
			self.assertEqual((asha["reach"], bilal["reach"]), (["Email"], []))
			self.assertTrue(asha["overdue"])  # January's bill, long overdue
			with patch("frappe.sendmail"):
				result = api.send_bulk_reminders([b.name for b in self.bills])
			self.assertEqual(result["sent"], 1)
			self.assertEqual([s["why"] for s in result["skipped"]], ["no WhatsApp number or email"])

			# again the same day: nobody twice
			self.assertTrue(self.row(api.get_reminder_list(self.building), self.bills[0])["reminded_today"])
			with patch("frappe.sendmail") as mail:
				result = api.send_bulk_reminders([self.bills[0].name])
			mail.assert_not_called()
			self.assertEqual((result["sent"], result["skipped"][0]["why"]), (0, "reminded today already"))

	def test_mark_paid(self):
		result = api.mark_invoices_paid([b.name for b in self.bills], "Cash", "2026-01-10")
		self.assertEqual((result["paid"], result["failed"]), (2, []))
		self.assertEqual(result["amount"], flt(sum(b.outstanding_amount for b in self.bills), 2))
		for bill in self.bills:
			self.assertEqual(frappe.db.get_value("Tenant Rent Invoice", bill.name, "outstanding_amount"), 0)
		# paid already: nothing more
		self.assertEqual(api.mark_invoices_paid([self.bills[0].name])["paid"], 0)
		self.assertRaises(frappe.ValidationError, bulk.mark_paid, [self.bills[0].name], "Cash", "2999-01-01")

	def test_invoices_for_one_building(self):
		other = make_allotment(
			room=make_room(rent=5000, property=make_property()), allotment_date="2026-01-01"
		)
		created = api.generate_invoices("February", 2026, property=self.building)["created"]
		buildings = set(
			frappe.get_all("Tenant Rent Invoice", filters={"name": ("in", created)}, pluck="property")
		)
		self.assertEqual(buildings, {self.building})
		self.assertFalse(
			frappe.db.exists(
				"Tenant Rent Invoice", {"tenant_space_allotment": other.name, "billing_month": "February"}
			)
		)

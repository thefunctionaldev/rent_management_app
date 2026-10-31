# Copyright (c) 2026, Shashank Dixit and Contributors
# See license.txt

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import flt

from rent_management import api, demo, subscription


class TestDemo(IntegrationTestCase):
	def test_demo_data_adds_up(self):
		frappe.set_user("Administrator")
		# this site has data already: refused, the demo is for new sites
		self.assertRaises(frappe.ValidationError, demo.make_demo_data)

		# run it next to the existing data, under building names of its own
		prefix = frappe.generate_hash(length=4).upper()
		names = {b[0]: f"{prefix} {b[0]}" for b in demo.BUILDINGS}
		with (
			patch.object(demo, "BUILDINGS", [(names[b[0]], prefix + b[1], *b[2:]) for b in demo.BUILDINGS]),
			patch.object(demo, "ROOMS", [(names[r[0]], *r[1:]) for r in demo.ROOMS]),
			patch.object(demo, "RENOVATION", {(names[b], room) for b, room in demo.RENOVATION}),
			patch.object(subscription, "skip_enforcement", return_value=True),
			patch.object(demo, "set_picture"),  # files on disk aren't rolled back; tested in test_pictures
			patch("rent_management.pictures.set_document"),  # the same for documents
		):
			summary = demo.Demo("demo@1234").run()
		self.assertTrue(frappe.db.exists("User", summary["tenant_login"]))

		buildings = list(names.values())
		invoices = frappe.get_all(
			"Tenant Rent Invoice",
			filters={"property": ("in", buildings), "docstatus": 1},
			fields=["final_amount", "paid_amount", "outstanding_amount", "status"],
		)
		self.assertGreater(len(invoices), 50)
		for invoice in invoices:
			self.assertAlmostEqual(
				flt(invoice.paid_amount) + flt(invoice.outstanding_amount), flt(invoice.final_amount), 2
			)
		self.assertIn("Overdue", {i.status for i in invoices})

		for room in frappe.get_all(
			"Tenant Space", filters={"property": ("in", buildings)}, fields=["capacity", "occupied_beds"]
		):
			self.assertLessEqual(room.occupied_beds, room.capacity)

		for doctype in ("Meter Reading", "Property Expense", "Maintenance Request"):
			self.assertTrue(frappe.db.count(doctype, {"property": ("in", buildings)}), doctype)
		self.assertTrue(
			frappe.db.count("Security Deposit Settlement", {"property": ("in", buildings), "docstatus": 1})
		)
		on_notice = frappe.get_all(
			"Tenant Space Allotment",
			filters={
				"property": ("in", buildings),
				"status": "Active",
				"expected_vacate_date": ("is", "set"),
			},
			pluck="name",
		)
		self.assertEqual(len(on_notice), 1)
		self.assertIn(on_notice[0], [a.name for a in api.get_dashboard()["moving_out"]])

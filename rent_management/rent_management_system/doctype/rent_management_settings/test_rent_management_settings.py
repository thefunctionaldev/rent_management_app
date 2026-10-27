# Copyright (c) 2026, Shashank Dixit and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase

from rent_management.rent_management_system.billing import generate_invoices, mark_overdue_invoices
from rent_management.rent_management_system.doctype.tenant_space_allotment.test_tenant_space_allotment import (
	make_allotment,
)

EXTRA_TEST_RECORD_DEPENDENCIES = []
IGNORE_TEST_RECORD_DEPENDENCIES = []


class IntegrationTestRentManagementSettings(IntegrationTestCase):
	def test_generate_invoices(self):
		active = make_allotment(allotment_date="2026-01-01")
		moved_in_mid_month = make_allotment(allotment_date="2026-03-20")
		moved_out_earlier = make_allotment(allotment_date="2026-01-01")
		moved_out_earlier.vacate("2026-02-10")
		not_yet_moved_in = make_allotment(allotment_date="2026-04-01")
		draft = make_allotment(allotment_date="2026-01-01", submit=False)

		created = generate_invoices("March", 2026)
		billed = set(
			frappe.get_all(
				"Tenant Rent Invoice", filters={"name": ("in", created)}, pluck="tenant_space_allotment"
			)
		)
		self.assertIn(active.name, billed)
		self.assertIn(moved_in_mid_month.name, billed)
		self.assertNotIn(moved_out_earlier.name, billed)
		self.assertNotIn(not_yet_moved_in.name, billed)
		self.assertNotIn(draft.name, billed)

		# running again does not create duplicates
		self.assertEqual(generate_invoices("March", 2026), [])

	def test_generate_and_submit(self):
		allotment = make_allotment(allotment_date="2026-01-01")
		created = generate_invoices("February", 2026, submit=True)
		invoice = frappe.get_value(
			"Tenant Rent Invoice",
			{"name": ("in", created), "tenant_space_allotment": allotment.name},
			["docstatus", "outstanding_amount"],
			as_dict=True,
		)
		self.assertEqual(invoice.docstatus, 1)
		self.assertGreater(invoice.outstanding_amount, 0)

	def test_mark_overdue(self):
		allotment = make_allotment(allotment_date="2026-01-01")
		created = generate_invoices("January", 2026, submit=True)
		name = frappe.get_value(
			"Tenant Rent Invoice", {"name": ("in", created), "tenant_space_allotment": allotment.name}
		)
		frappe.db.set_value(
			"Tenant Rent Invoice",
			name,
			{"status": "Unpaid", "due_date": "2026-01-05", "next_due_date": "2026-01-05"},
		)
		mark_overdue_invoices()
		self.assertEqual(frappe.db.get_value("Tenant Rent Invoice", name, "status"), "Overdue")

	def test_due_day_limit(self):
		settings = frappe.get_single("Rent Management Settings")
		settings.rent_due_day = 40
		self.assertRaises(frappe.ValidationError, settings.save)

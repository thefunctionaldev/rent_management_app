# Copyright (c) 2026, Shashank Dixit and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase

from rent_management import api, duplicates
from rent_management.rent_management_system.doctype.tenant_rent_invoice.test_tenant_rent_invoice import (
	make_invoice,
)
from rent_management.rent_management_system.doctype.tenant_space_allotment.test_tenant_space_allotment import (
	make_allotment,
	make_room,
)


class TestDuplicatePayments(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.stay = make_allotment(room=make_room(rent=9000), allotment_date="2026-01-01")
		self.invoice = make_invoice(self.stay, submit=True)
		self.ref = "4" + frappe.generate_hash(length=11).upper()

	def tearDown(self):
		frappe.db.rollback()

	def test_same_reference(self):
		api.record_payment(self.invoice.name, 3000, "UPI", "2026-01-05", self.ref)
		with self.assertRaises(duplicates.DuplicatePaymentError) as e:
			api.record_payment(self.invoice.name, 2000, "UPI", "2026-01-20", self.ref)
		self.assertIn("is already on a payment", str(e.exception))
		# the bank pads it with zeros: still the same
		self.assertRaises(duplicates.DuplicatePaymentError, api.record_payment, self.invoice.name, 2000,
			"UPI", "2026-01-20", "0000" + self.ref)  # fmt: skip
		# the manager says it's really another payment
		api.record_payment(self.invoice.name, 2000, "UPI", "2026-01-20", self.ref, allow_duplicate=1)
		self.assertEqual(frappe.db.count("Rent Payment", {"reference_no": self.ref, "docstatus": 1}), 2)

	def test_same_amount_days_apart(self):
		api.record_payment(self.invoice.name, 3000, "Cash", "2026-01-05")
		self.assertRaises(duplicates.DuplicatePaymentError, api.record_payment, self.invoice.name, 3000, "Cash", "2026-01-06")  # fmt: skip
		api.record_payment(self.invoice.name, 3000, "Cash", "2026-01-12")  # a week later: fine
		api.record_payment(self.invoice.name, 1500, "Cash", "2026-01-05")  # another amount: fine
		api.record_payment(self.invoice.name, 1500, "Cash", "2026-01-06", allow_duplicate=1)

	def test_short_references_are_ignored(self):
		api.record_payment(self.invoice.name, 3000, "Cash", "2026-01-05", "-")
		api.record_payment(self.invoice.name, 2000, "Cash", "2026-01-20", "-")

# Copyright (c) 2026, Shashank Dixit and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase

from rent_management import api, portal, receipts
from rent_management.rent_management_system.doctype.tenant_rent_invoice.test_tenant_rent_invoice import (
	make_invoice,
)
from rent_management.rent_management_system.doctype.tenant_space_allotment.test_tenant_space_allotment import (
	make_allotment,
	make_property,
	make_room,
)

SETTINGS = "Rent Management Settings"


def pay(invoice, amount, mode="UPI", on=None):
	doc = frappe.get_doc(
		{"doctype": "Rent Payment", "tenant": invoice.tenant, "rent_invoice": invoice.name, "amount": amount,
			"mode_of_payment": mode, "payment_date": on or invoice.posting_date, "reference_no": f"UTR123{frappe.generate_hash(length=5)}" if mode == "UPI" else None}
	).insert()  # fmt: skip
	doc.submit()


class TestRentReceipts(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		settings = frappe.get_single(SETTINGS)
		settings.update({"landlord_name": "Ravi Kumar", "landlord_pan": "abcde1234f", "landlord_address": "14, 5th Cross",
			"late_fee_enabled": 0, "early_discount_enabled": 0})  # fmt: skip
		settings.save()
		self.building = make_property()
		email = f"neha.{frappe.generate_hash(length=5)}@tenant.example"
		self.tenant = frappe.get_doc(
			{"doctype": "Tenant", "first_name": "Neha", "last_name": "Rao", "email_id": email}
		).insert()
		self.stay = make_allotment(
			room=make_room(rent=8000, property=self.building), tenant=self.tenant, allotment_date="2026-01-01"
		)
		jan = make_invoice(self.stay, charges=[{"charge_type": "Electricity", "amount": 500}])
		jan.submit()
		pay(jan, jan.outstanding_amount)  # rent and electricity
		feb = make_invoice(self.stay, billing_month="February", posting_date="2026-02-01", submit=True)
		pay(feb, 3000, "Cash")
		make_invoice(self.stay, billing_month="March", posting_date="2026-03-01", submit=True)  # unpaid
		self.april = make_invoice(self.stay, billing_month="April", posting_date="2026-04-01", submit=True)
		pay(self.april, 8000, "Cash")

	def test_rent_only_by_financial_year(self):
		self.assertEqual(frappe.db.get_single_value(SETTINGS, "landlord_pan"), "ABCDE1234F")  # tidied
		self.assertRaises(
			frappe.ValidationError, frappe.get_single(SETTINGS).update({"landlord_pan": "1234"}).save
		)

		data = api.get_rent_receipts(self.tenant.name, "2025-26")
		self.assertEqual([(m["label"], m["paid"], m["fully_paid"]) for m in data["months"]],
			[("January 2026", 8000, True), ("February 2026", 3000, False)])  # fmt: skip
		self.assertEqual(data["total"], 11000)  # no electricity, nothing for unpaid March
		self.assertIn("2026-27", data["years"])
		self.assertEqual(
			api.get_rent_receipts(self.tenant.name, "2026-27")["total"], 8000
		)  # April starts a new year

		r = receipts.receipt(self.tenant.name, "2025-26")
		self.assertEqual(
			(r.payee.name, r.payee.pan, r.period),
			("Ravi Kumar", "ABCDE1234F", "January 2026 to February 2026"),
		)
		self.assertFalse(r.stamp)  # ₹3,000 in cash needs no revenue stamp
		self.assertTrue(
			receipts.receipt(self.tenant.name, "2026-27", self.april.name).stamp
		)  # ₹8,000 in cash does

		page = receipts.html(self.tenant.name, "2025-26")
		for text in (
			"Rent Receipt",
			"Neha Rao",
			"ABCDE1234F",
			"₹8,000",
			"₹11,000",
			"Eleven Thousand",
			"UTR123",
		):
			self.assertIn(text, page)

	def test_building_owner_and_pan_warning(self):
		frappe.db.set_value("Rent Property", self.building, {"owner_name": "Sunita Iyer", "owner_pan": None})
		r = receipts.receipt(self.tenant.name, "2025-26")
		self.assertEqual((r.payee.name, r.payee.pan), ("Sunita Iyer", None))
		self.assertFalse(r.pan_missing)  # ₹11,000 a year: no PAN needed
		frappe.db.set_value(
			"Tenant Rent Invoice",
			{"tenant": self.tenant.name, "billing_month": "January"},
			{"pro_rated_rent": 120000, "paid_amount": 120000},
		)
		self.assertTrue(receipts.receipt(self.tenant.name, "2025-26").pan_missing)

	def test_pdf_and_tenant_app(self):
		receipts.send_pdf(self.tenant.name, "2025-26")
		self.assertTrue(frappe.local.response.filecontent.startswith(b"%PDF"))
		self.assertEqual(frappe.local.response.filename, "Rent-receipt-2025-26.pdf")

		api.invite_tenant(self.tenant.name)
		frappe.set_user(frappe.db.get_value("Tenant", self.tenant.name, "user"))
		try:
			self.assertEqual(portal.get_rent_receipts("2025-26")["total"], 11000)
			portal.download_rent_receipt("2026-27", self.april.name)
			self.assertTrue(frappe.local.response.filename.endswith("-April.pdf"))
		finally:
			frappe.set_user("Administrator")
		other_stay = make_allotment(room=make_room(rent=5000), allotment_date="2026-01-01")
		other = make_invoice(other_stay, submit=True)
		frappe.set_user(frappe.db.get_value("Tenant", self.tenant.name, "user"))
		try:
			self.assertRaises(frappe.PermissionError, portal.download_rent_receipt, "2025-26", other.name)
		finally:
			frappe.set_user("Administrator")

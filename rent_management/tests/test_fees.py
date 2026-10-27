# Copyright (c) 2026, Shashank Dixit and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, getdate, nowdate

from rent_management import api, fees, rent_collection
from rent_management.rent_management_system.doctype.tenant_rent_invoice.tenant_rent_invoice import MONTHS
from rent_management.rent_management_system.doctype.tenant_rent_invoice.test_tenant_rent_invoice import (
	make_invoice,
)
from rent_management.rent_management_system.doctype.tenant_space_allotment.test_tenant_space_allotment import (
	make_allotment,
	make_room,
)

SETTINGS = "Rent Management Settings"
OFF = {
	"late_fee_enabled": 0,
	"early_discount_enabled": 0,
	"late_fee_grace_days": 3,
	"late_fee_max": 0,
	"early_discount_days": 0,
	"upi_id": None,
}


def settings(**values):
	for field, value in values.items():
		frappe.db.set_single_value(SETTINGS, field, value)
	frappe.clear_document_cache(SETTINGS, SETTINGS)


def pay(invoice, amount, on):
	payment = frappe.get_doc(
		{
			"doctype": "Rent Payment",
			"tenant": invoice.tenant,
			"rent_invoice": invoice.name,
			"amount": amount,
			"payment_date": on,
			"mode_of_payment": "UPI",
		}
	).insert()
	payment.submit()
	invoice.reload()
	return payment


class TestFees(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		settings(**OFF)
		self.stay = make_allotment(room=make_room(rent=9000), allotment_date="2026-01-01")

	def tearDown(self):
		settings(**OFF)

	def january(self, **kwargs):
		return make_invoice(self.stay, submit=True, due_date="2026-01-05", **kwargs)

	def test_early_payment_discount(self):
		settings(early_discount_enabled=1, early_discount_type="Amount", early_discount_value=500)
		invoice = self.january()
		self.assertEqual(
			(invoice.early_discount_offer, str(invoice.early_discount_until)), (500, "2026-01-05")
		)
		self.assertEqual(fees.discount_available(invoice, on="2026-01-03"), 500)
		self.assertEqual(fees.discount_available(invoice, on="2026-01-06"), 0)

		payment = pay(invoice, 8500, "2026-01-04")  # in full, less the discount, in time
		self.assertEqual(
			(invoice.early_discount, invoice.final_amount, invoice.outstanding_amount), (500, 8500, 0)
		)
		self.assertEqual(invoice.status, "Paid")

		payment.cancel()  # the discount goes with it
		invoice.reload()
		self.assertEqual((invoice.early_discount, invoice.outstanding_amount), (0, 9000))
		pay(invoice, 8500, "2026-01-07")  # too late for the discount
		self.assertEqual((invoice.early_discount, invoice.outstanding_amount), (0, 500))

	def test_discount_on_the_payment_page(self):
		settings(
			early_discount_enabled=1,
			early_discount_type="Percent of Rent",
			early_discount_value=5,
			early_discount_days=2,
			upi_id="landlord@upi",
		)
		today = getdate(nowdate())
		invoice = make_invoice(
			self.stay,
			billing_month=MONTHS[today.month - 1],
			billing_year=today.year,
			posting_date=nowdate(),
			due_date=add_days(nowdate(), 10),
			submit=True,
		)
		self.assertEqual(invoice.early_discount_until, add_days(today, 8))
		offer = invoice.early_discount_offer
		self.assertEqual(offer, round(invoice.pro_rated_rent * 0.05))
		self.assertEqual(fees.payable_now(invoice), invoice.outstanding_amount - offer)
		self.assertIn(f"am={invoice.outstanding_amount - offer:.2f}", rent_collection.get_upi_link(invoice))
		self.assertEqual(api.get_invoice(invoice.name)["discount_now"], offer)

	def test_late_fee(self):
		settings(late_fee_enabled=1, late_fee_type="Flat", late_fee_amount=200)
		invoice = self.january()
		fees.apply_late_fees()
		invoice.reload()
		self.assertEqual((invoice.late_fee, invoice.outstanding_amount), (200, 9200))
		fees.apply_late_fees()  # a flat fee is charged once
		self.assertEqual(frappe.db.get_value(fees.INVOICE, invoice.name, "late_fee"), 200)

		api.waive_late_fee(invoice.name)
		invoice.reload()
		self.assertEqual(
			(invoice.late_fee, invoice.outstanding_amount, invoice.late_fee_waived), (0, 9000, 1)
		)
		fees.apply_late_fees()
		self.assertEqual(frappe.db.get_value(fees.INVOICE, invoice.name, "late_fee"), 0)
		api.waive_late_fee(invoice.name, 0)
		self.assertEqual(frappe.db.get_value(fees.INVOICE, invoice.name, "outstanding_amount"), 9200)

		# per day, up to the maximum
		settings(late_fee_type="Per Day", late_fee_amount=50, late_fee_max=1000)
		other = make_invoice(self.stay, billing_month="February", submit=True, due_date="2026-02-05")
		fees.apply_late_fees()
		self.assertEqual(frappe.db.get_value(fees.INVOICE, other.name, "late_fee"), 1000)
		# not before the grace days are over
		self.assertEqual(fees.late_fee_due(other, today="2026-02-08"), 0)
		self.assertEqual(fees.late_fee_due(other, today="2026-02-10"), 100)

	def test_instalments(self):
		invoice = self.january()
		self.assertRaises(
			frappe.ValidationError,
			api.split_invoice,
			invoice.name,
			[{"due_date": "2026-01-05", "amount": 9000}],
		)
		self.assertRaises(
			frappe.ValidationError,
			api.split_invoice,
			invoice.name,
			[{"due_date": "2026-01-05", "amount": 4000}, {"due_date": "2026-01-20", "amount": 4000}],
		)  # doesn't add up
		api.split_invoice(
			invoice.name,
			[{"due_date": "2026-01-20", "amount": 4500}, {"due_date": "2026-01-05", "amount": 4500}],
		)
		invoice.reload()
		self.assertEqual(str(invoice.next_due_date), "2026-01-05")
		self.assertEqual(fees.payable_now(invoice), 4500)  # the first part
		pay(invoice, 5000, "2026-01-05")
		self.assertEqual(fees.payable_now(invoice), 4000)  # what's left of the second
		self.assertEqual(str(invoice.next_due_date), "2026-01-20")
		schedule = fees.schedule(invoice)
		self.assertEqual([r["status"] for r in schedule], ["Paid", "Overdue"])
		self.assertEqual(schedule[1]["paid"], 500)

		api.split_invoice(invoice.name, [])  # back to one due date
		invoice.reload()
		self.assertEqual((len(invoice.instalments), str(invoice.next_due_date)), (0, "2026-01-05"))

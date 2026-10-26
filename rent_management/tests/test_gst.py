# Copyright (c) 2026, Shashank Dixit and Contributors
# See license.txt

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, nowdate

from rent_management import api, gst, subscription
from rent_management.tests.test_subscription import KEYS, PLANS


def make_gstin(state_code="27", pan="ABCDE1234F"):
	first_14 = f"{state_code}{pan}1Z"
	return first_14 + gst.gstin_check_digit(first_14)


VENDOR = {
	"name": "Acme Software",
	"gstin": make_gstin("27", "AAACA1234A"),
	"address": "Pune",
	"sac": "998314",
}


class TestGst(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.enterContext(
			patch.dict(
				frappe.conf,
				{
					**KEYS,
					"rent_subscription_plans": PLANS,
					"rent_vendor": VENDOR,
					"rent_invoice_prefix": "TEST",
				},
			)
		)
		frappe.db.delete(subscription.PAYMENT)
		subscription.update_subscription(
			plan="small",
			billing_cycle=None,
			trial_ends_on=add_days(nowdate(), 5),
			current_period_start=None,
			current_period_end=None,
			billing_name=None,
			billing_gstin=None,
			billing_state=None,
		)

	def test_gstin(self):
		gstin = make_gstin("29")
		self.assertEqual(gst.validate_gstin(gstin.lower()), gstin)
		self.assertEqual(gst.state_from_gstin(gstin), "Karnataka")
		wrong = gstin[:14] + ("A" if gstin[14] != "A" else "B")
		self.assertRaises(frappe.ValidationError, gst.validate_gstin, wrong)
		self.assertRaises(frappe.ValidationError, gst.validate_gstin, "27ABCDE1234")
		self.assertEqual(gst.validate_gstin(""), "")

	def test_breakup(self):
		same = gst.get_breakup(1180, "Maharashtra")
		self.assertEqual(
			(same["taxable_value"], same["cgst_amount"], same["sgst_amount"], same["igst_amount"]),
			(1000, 90, 90, 0),
		)
		other = gst.get_breakup(1180, "Karnataka")
		self.assertEqual((other["igst_amount"], other["cgst_amount"]), (180, 0))
		# no customer state: place of supply is the supplier's state
		self.assertEqual(gst.get_breakup(1180, None)["cgst_amount"], 90)

	def test_not_registered(self):
		with patch.dict(frappe.conf, {"rent_vendor": {"name": "Small Biz"}}):
			breakup = gst.get_breakup(499, "Maharashtra")
			self.assertEqual((breakup["taxable_value"], breakup["tax_amount"]), (499, 0))
			self.assertEqual(gst.payable_amount(499), 499)

	def test_prices_exclusive_of_gst(self):
		with patch.dict(frappe.conf, {"rent_prices_include_gst": 0}):
			self.assertEqual(gst.payable_amount(1000), 1180)

	def test_invoice_on_payment(self):
		api.save_billing_details(
			{
				"billing_name": "Sharma PG",
				"billing_gstin": make_gstin("29"),
				"billing_email": "accounts@sharma.example",
			}
		)
		self.assertEqual(frappe.db.get_single_value("Rent Subscription", "billing_state"), "Karnataka")

		first = subscription.record_manual_payment("small", "Monthly", 354, "NEFT-1")
		second = subscription.record_manual_payment("small", "Monthly", 354, "NEFT-2")
		fy = subscription.financial_year(nowdate())
		self.assertEqual(first.invoice_number, f"TEST/{fy}/0001")
		self.assertEqual(second.invoice_number, f"TEST/{fy}/0002")
		self.assertEqual((first.billing_name, first.place_of_supply), ("Sharma PG", "Karnataka"))
		self.assertEqual((first.taxable_value, first.igst_amount, first.cgst_amount), (300, 54, 0))

		from frappe.www.printview import get_rendered_template

		html = get_rendered_template(
			frappe.get_doc(subscription.PAYMENT, first.name),
			print_format=frappe.get_doc("Print Format", subscription.INVOICE_PRINT_FORMAT),
		)
		for text in ("Tax Invoice", first.invoice_number, "Sharma PG", VENDOR["gstin"], "IGST", "998314"):
			self.assertIn(text, html)

		# free months don't get an invoice
		self.assertFalse(subscription.record_manual_payment("small", "Monthly", 0).invoice_number)

	def test_financial_year(self):
		self.assertEqual(subscription.financial_year("2026-04-01"), "2627")
		self.assertEqual(subscription.financial_year("2027-03-31"), "2627")

	def test_bad_billing_details(self):
		self.assertRaises(frappe.ValidationError, api.save_billing_details, {"billing_gstin": "XX"})
		self.assertRaises(frappe.ValidationError, api.save_billing_details, {"billing_email": "not-an-email"})

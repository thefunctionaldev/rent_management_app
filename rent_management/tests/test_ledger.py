# Copyright (c) 2026, Shashank Dixit and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import flt

from rent_management import api, ledger, portal
from rent_management.rent_management_system.doctype.tenant_rent_invoice.test_tenant_rent_invoice import (
	make_invoice,
)
from rent_management.rent_management_system.doctype.tenant_space_allotment.test_tenant_space_allotment import (
	make_allotment,
	make_room,
)


class TestLedger(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		email = f"anita.{frappe.generate_hash(length=5)}@tenant.example"
		self.tenant = frappe.get_doc({"doctype": "Tenant", "first_name": "Anita", "last_name": "Rao", "email_id": email}).insert()  # fmt: skip
		self.stay = make_allotment(room=make_room(rent=6000, deposit=12000), tenant=self.tenant,
			allotment_date="2026-01-01", security_deposit=12000, deposit_collected=1)  # fmt: skip
		self.jan = make_invoice(self.stay, submit=True)
		self.feb = make_invoice(self.stay, billing_month="February", posting_date="2026-02-01", submit=True)
		api.record_payment(self.jan.name, 6000, "UPI", "2026-01-05", "UTR111")
		api.record_payment(self.feb.name, 2000, "Cash", "2026-02-06")

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_statement(self):
		s = ledger.statement(self.tenant.name, to_date="2026-03-01")
		self.assertEqual([r["kind"] for r in s["rows"]], ["bill", "payment", "bill", "payment"])
		self.assertEqual([r["balance"] for r in s["rows"]], [6000, 0, 6000, 4000])
		self.assertEqual((s["billed"], s["paid"], s["balance"]), (12000, 8000, 4000))
		self.assertIn("Ref. UTR111", s["rows"][1]["detail"])
		self.assertEqual(s["deposits"][0]["amount"], 12000)

		# from February: January is the opening balance
		s = ledger.statement(self.tenant.name, from_date="2026-02-01", to_date="2026-03-01")
		self.assertEqual((s["opening"], len(s["rows"]), s["balance"]), (0, 2, 4000))
		s = ledger.statement(self.tenant.name, from_date="2026-01-03", to_date="2026-03-01")
		self.assertEqual(s["opening"], 6000)

		# the PDF is made
		ledger.statement_pdf(self.tenant.name)
		self.assertTrue(frappe.local.response.filename.startswith("Statement-Anita"))
		self.assertEqual(frappe.local.response.filecontent[:4], b"%PDF")

	def test_no_dues(self):
		status = ledger.no_dues(self.tenant.name)
		self.assertFalse(status["eligible"])
		self.assertIn("4,000 is unpaid", status["reasons"][0])
		self.assertRaises(frappe.ValidationError, ledger.certificate, self.tenant.name)

		api.record_payment(self.feb.name, 4000, "UPI", "2026-02-20")
		self.assertTrue(ledger.no_dues(self.tenant.name)["eligible"])  # still staying: no dues as of today

		# moved out: not until the deposit is settled
		api.vacate_room(self.stay.name, "2026-02-28")
		self.assertEqual(ledger.no_dues(self.tenant.name)["reasons"], ["the deposit isn't settled yet"])
		api.settle_deposit(
			self.stay.name, deductions=[{"reason": "Cleaning", "amount": 500}], mode_of_refund="UPI"
		)
		c = ledger.certificate(self.tenant.name)
		self.assertFalse(c.stay["active"])
		self.assertEqual((flt(c.paid), c.deposit["refund"]), (12000, 11500))
		self.assertTrue(c.number.startswith("ND/"))
		ledger.certificate_pdf(self.tenant.name)
		self.assertEqual(frappe.local.response.filecontent[:4], b"%PDF")

	def test_tenant_sees_only_theirs(self):
		api.invite_tenant(self.tenant.name)
		frappe.set_user(frappe.db.get_value("Tenant", self.tenant.name, "user"))
		data = portal.get_statement()
		self.assertEqual(str(data["tenant"].name), str(self.tenant.name))
		self.assertFalse(data["no_dues"]["eligible"])
		self.assertRaises(frappe.ValidationError, portal.download_no_dues)

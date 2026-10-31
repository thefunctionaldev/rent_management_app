# Copyright (c) 2026, Shashank Dixit and Contributors
# See license.txt

import base64

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import flt

from rent_management import api, statements
from rent_management.rent_management_system.doctype.tenant_rent_invoice.test_tenant_rent_invoice import (
	make_invoice,
)
from rent_management.rent_management_system.doctype.tenant_space_allotment.test_tenant_space_allotment import (
	make_allotment,
	make_room,
)


def csv_upload(text) -> str:
	return "data:text/csv;base64," + base64.b64encode(text.encode()).decode()


def make_tenant(first, last, mobile=None):
	tenant = frappe.get_doc(
		{"doctype": "Tenant", "first_name": first, "last_name": last, "mobile_no": mobile}
	).insert()
	stay = make_allotment(room=make_room(rent=7000), tenant=tenant, allotment_date="2026-01-01")
	return tenant, make_invoice(stay, submit=True)


# an HDFC-style export: account details above the table, deposits and withdrawals in two columns
HDFC = """HDFC BANK Ltd.,,,,,,
Account No :,50100123456789,,,,,
,,,,,,
Date,Narration,Chq./Ref.No.,Value Dt,Withdrawal Amt.,Deposit Amt.,Closing Balance
03/01/26,UPI-KAVYA NAMBIAR-kavya.n@okaxis-UTIB0001234-412345678901-RENT JAN,0000412345678901,03/01/26,,"7,000.00","1,07,000.00"
04/01/26,NEFT CR-ICIC0000123-ROHAN DESAI-RENT,ICICN52026010412345,04/01/26,,7000.00,114000.00
05/01/26,UPI/CR/512345678902/SOMEONE ELSE/YESB/xyz@ybl/gift,0000512345678902,05/01/26,,7000.00,121000.00
06/01/26,POS 4123XXXX AMAZON,0000000000,06/01/26,1499.00,,119501.00
07/01/26,IMPS-612345678903-9876501234-HDFC,612345678903,07/01/26,,3500.00,123001.00
,,,,,,
Closing balance,,,,,,123001.00
"""


class TestBankStatements(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		frappe.db.delete("Bank Statement")
		# other tests' unpaid bills would change which amounts are unique: settle them out of the way
		frappe.db.sql(
			"update `tabTenant Rent Invoice` set outstanding_amount = 0 where docstatus = 1 and outstanding_amount > 0"
		)
		self.kavya, self.kavya_bill = make_tenant("Kavya", "Nambiar")
		self.rohan, self.rohan_bill = make_tenant("Rohan", "Desai")
		self.priya, self.priya_bill = make_tenant("Priya", "Menon", mobile="9876501234")

	def tearDown(self):
		frappe.db.rollback()  # each test starts from the same bills and payments (UTRs are unique)
		frappe.set_user("Administrator")

	def upload(self, text=HDFC, name="statement.csv"):
		return api.get_bank_statement(api.upload_bank_statement(name, csv_upload(text), "HDFC savings"))

	def line(self, statement, amount, contains):
		return next(l for l in statement["lines"] if l["amount"] == amount and contains in l["description"])

	def test_reading(self):
		lines, debits = statements.parse("s.csv", csv_upload(HDFC))
		self.assertEqual(len(lines), 4)  # the closing balance and the card payment aren't credits
		self.assertEqual(debits, 1)
		self.assertEqual(str(lines[0]["line_date"]), "2026-01-03")
		self.assertEqual(lines[0]["amount"], 7000)
		self.assertEqual(lines[0]["reference"], "412345678901")  # without the bank's padding
		self.assertEqual(lines[0]["payer"], "kavya.n@okaxis")
		self.assertEqual((lines[1]["payer"], lines[1]["reference"]), ("Rohan Desai", "ICICN52026010412345"))

		# a statement with one amount column and Cr/Dr
		sbi = 'Txn Date,Description,Ref No./Cheque No.,Amount,Cr/Dr\n1 Jan 2026,BY TRANSFER-UPI/CR/412345678999/ARJUN,412345678999,"5,000.00",CR\n2 Jan 2026,ATM WDL,,2000,DR\n'
		lines, debits = statements.parse("sbi.csv", csv_upload(sbi))
		self.assertEqual([(l["amount"], l["reference"]) for l in lines], [(5000, "412345678999")])
		self.assertEqual(debits, 1)

		# Excel, with real dates and numbers in the cells
		from datetime import date

		from frappe.utils.xlsxutils import make_xlsx

		book = make_xlsx([["Statement of account"], ["Transaction Date", "Particulars", "Debit", "Credit"],
			[date(2026, 1, 2), "UPI/CR/412345678777/KAVYA NAMBIAR/UTIB/kavya.n@okaxis", None, 7000],
			[date(2026, 1, 3), "ATM", 500, None]], "Statement").getvalue()  # fmt: skip
		xlsx = "data:;base64," + base64.b64encode(book).decode()
		lines, debits = statements.parse("s.xlsx", xlsx)
		self.assertEqual([(str(l["line_date"]), l["amount"], l["payer"]) for l in lines],
			[("2026-01-02", 7000, "kavya.n@okaxis")])  # fmt: skip
		self.assertEqual(debits, 1)

		self.assertRaises(frappe.ValidationError, statements.parse, "x.csv", csv_upload("a,b\n1,2\n"))
		self.assertRaises(frappe.ValidationError, statements.parse, "x.pdf", csv_upload("x"))

	def test_matching_and_confirming(self):
		s = self.upload()
		kavya = self.line(s, 7000, "KAVYA")
		self.assertEqual((kavya["status"], kavya["confidence"]), ("Suggested", "High"))
		self.assertEqual(kavya["tenant_name"], "Kavya Nambiar")
		listed = next(r for r in api.get_bank_statements() if r.name == s["name"])
		self.assertEqual((listed.credits, listed.counts), (4, {"Suggested": 4}))
		self.assertEqual(
			(str(kavya["tenant"]), kavya["rent_invoice"]), (str(self.kavya.name), self.kavya_bill.name)
		)
		rohan = self.line(s, 7000, "ROHAN")
		self.assertEqual(str(rohan["tenant"]), str(self.rohan.name))
		priya = self.line(s, 3500, "IMPS")  # by her mobile number, part of her bill
		self.assertEqual((str(priya["tenant"]), priya["confidence"]), (str(self.priya.name), "Medium"))
		other = self.line(s, 7000, "SOMEONE")
		# 7000 is also Priya's bill, the only one left of that amount
		self.assertEqual((other["status"], str(other["tenant"])), ("Suggested", str(self.priya.name)))
		self.assertEqual(other["confidence"], "Medium")

		# not rent after all
		api.set_bank_statement_line(s["name"], other["name"], status="Ignored")
		result = api.confirm_bank_statement(s["name"], [kavya["name"], rohan["name"], priya["name"]])
		self.assertEqual((result["confirmed"], result["errors"]), (3, []))
		self.assertEqual(
			frappe.db.get_value("Tenant Rent Invoice", self.kavya_bill.name, "outstanding_amount"), 0
		)
		payment = frappe.get_doc("Rent Payment", {"rent_invoice": self.kavya_bill.name, "docstatus": 1})
		self.assertEqual((payment.mode_of_payment, payment.reference_no, str(payment.payment_date)),
			("UPI", "412345678901", "2026-01-03"))  # fmt: skip
		self.assertEqual(
			flt(frappe.db.get_value("Tenant Rent Invoice", self.priya_bill.name, "outstanding_amount")), 3500
		)
		self.assertIn("kavya.n@okaxis", frappe.db.get_value("Tenant", self.kavya.name, "statement_names"))

		# the same statement again: nothing new to record
		again = self.upload()
		self.assertEqual(
			{
				l["status"]
				for l in again["lines"]
				if l["amount"] == 7000 and "SOMEONE" not in l["description"]
			},
			{"Already Recorded"},
		)

	def test_reported_payment_and_learning(self):
		# Rohan reported his payment with the UTR in the tenant app
		draft = frappe.get_doc({"doctype": "Rent Payment", "tenant": self.rohan.name, "rent_invoice": self.rohan_bill.name,
			"amount": 7000, "mode_of_payment": "Bank Transfer", "payment_date": "2026-01-04",
			"reference_no": "ICICN52026010412345"}).insert()  # fmt: skip
		s = self.upload()
		rohan = self.line(s, 7000, "ROHAN")
		self.assertEqual(rohan["rent_payment"], draft.name)
		self.assertIn("reported", rohan["match_reason"])
		api.confirm_bank_statement(s["name"], [rohan["name"]])
		self.assertEqual(frappe.db.get_value("Rent Payment", draft.name, "docstatus"), 1)
		self.assertEqual(frappe.db.count("Rent Payment", {"rent_invoice": self.rohan_bill.name}), 1)

		# picked by hand: learned for next time
		other = self.line(s, 7000, "SOMEONE")
		api.set_bank_statement_line(s["name"], other["name"], tenant=self.kavya.name)
		self.assertEqual(self.line(api.get_bank_statement(s["name"]), 7000, "SOMEONE")["status"], "Suggested")
		kavya = self.line(api.get_bank_statement(s["name"]), 7000, "KAVYA")
		api.set_bank_statement_line(s["name"], kavya["name"], status="Ignored")
		api.confirm_bank_statement(s["name"], [other["name"]])
		self.assertIn("xyz@ybl", frappe.db.get_value("Tenant", self.kavya.name, "statement_names"))

		# too much for what they owe now: reported, not recorded
		march = "Date,Narration,Deposit Amt.\n03/03/26,UPI/CR/712345678905/ANYONE/YESB/xyz@ybl/rent,9000\n"
		s = self.upload(march, "march.csv")
		line = s["lines"][0]
		self.assertEqual(str(line["tenant"]), str(self.kavya.name))  # from the UPI ID learned
		self.assertEqual(line["status"], "Unmatched")  # Kavya has nothing unpaid now
		self.assertRaises(
			frappe.ValidationError,
			api.set_bank_statement_line,
			s["name"],
			line["name"],
			tenant=self.kavya.name,
		)

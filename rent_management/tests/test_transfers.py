# Copyright (c) 2026, Shashank Dixit and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, flt, get_first_day, get_last_day, getdate, nowdate

from rent_management import api, ledger, move_out, transfers
from rent_management.rent_management_system.doctype.tenant_rent_invoice.tenant_rent_invoice import MONTHS
from rent_management.rent_management_system.doctype.tenant_rent_invoice.test_tenant_rent_invoice import (
	make_invoice,
)
from rent_management.rent_management_system.doctype.tenant_space_allotment.test_tenant_space_allotment import (
	make_allotment,
	make_property,
	make_room,
)

ALLOTMENT = "Tenant Space Allotment"
INVOICE = "Tenant Rent Invoice"


class TestTransfers(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.today = getdate(nowdate())
		self.month = get_first_day(self.today)
		self.building = make_property()
		self.old_room = make_room(rent=6000, deposit=12000, property=self.building)
		self.new_room = make_room(rent=9000, deposit=18000, property=self.building)
		tenant = frappe.get_doc({"doctype": "Tenant", "first_name": "Divya", "last_name": "Pai"}).insert()
		self.stay = make_allotment(room=self.old_room, tenant=tenant, allotment_date=add_days(self.month, -40),
			security_deposit=12000, deposit_collected=1, lock_in_months=3, rent_increase_percent=5,
			police_verification="Verified", police_station="HSR PS")  # fmt: skip

	def tearDown(self):
		frappe.db.rollback()

	def bill(self, stay, submit):
		return make_invoice(stay, billing_month=MONTHS[self.month.month - 1], billing_year=self.month.year,
			posting_date=str(self.month), submit=submit)  # fmt: skip

	def move_day(self):
		# the middle of this month, or today if that's earlier
		return min(add_days(self.month, 14), self.today) if self.today > self.month else None

	def test_move_with_the_month_already_billed(self):
		on = self.move_day()
		if not on:
			return  # the 1st of the month: no days before the move this month
		old_bill = self.bill(self.stay, submit=True)
		self.assertEqual(flt(old_bill.final_amount), 6000)

		options = api.get_transfer_options(self.stay.name)
		self.assertIn(self.new_room.name, [r["name"] for r in options["rooms"]])
		result = api.transfer_stay(self.stay.name, self.new_room.name, transfer_date=str(on))

		old, new = frappe.get_doc(ALLOTMENT, self.stay.name), frappe.get_doc(ALLOTMENT, result["stay"])
		self.assertEqual(
			(old.status, getdate(old.vacate_date), old.transferred_to),
			("Vacated", add_days(on, -1), new.name),
		)
		self.assertEqual(
			(new.status, new.transferred_from, getdate(new.allotment_date)), ("Active", old.name, on)
		)
		self.assertEqual(
			(flt(new.rent_amount), flt(new.security_deposit), new.deposit_collected), (9000, 18000, 1)
		)
		self.assertEqual(
			(new.police_verification, new.police_station), ("Verified", "HSR PS")
		)  # same building
		self.assertEqual(getdate(new.agreement_end_date), getdate(old.agreement_end_date))
		self.assertEqual(result["top_up"], 6000)

		# the new room's bill: its nights at 9,000, less what the old bill already charged, plus the top-up
		bill = frappe.get_doc(INVOICE, result["bill"])
		days = (get_last_day(on) - on).days + 1
		total_days = get_last_day(on).day
		self.assertEqual(bill.docstatus, 1)
		self.assertAlmostEqual(flt(bill.pro_rated_rent), round(9000 / total_days * days, 2), places=1)
		self.assertAlmostEqual(
			flt(bill.final_amount),
			round(9000 / total_days * days, 2) - round(6000 / total_days * days, 2) + 6000,
			places=0,
		)

		# one deposit, not two: nothing to settle for the old room
		self.assertNotIn(old.name, [p.name for p in api.get_pending_settlements()])
		self.assertEqual(len(ledger.deposits(old.tenant)), 1)
		self.assertEqual(move_out.stay_for(old.tenant).name, new.name)

	def test_move_with_a_draft_bill(self):
		on = self.move_day()
		if not on:
			return
		old_bill = self.bill(self.stay, submit=False)
		cheaper = make_room(rent=4000, deposit=8000, property=self.building)
		result = api.transfer_stay(self.stay.name, cheaper.name, transfer_date=str(on))
		self.assertEqual(
			getdate(frappe.db.get_value(INVOICE, old_bill.name, "to_date")), add_days(on, -1)
		)  # re-worked out
		self.assertEqual(
			frappe.db.get_value(INVOICE, result["bill"], "docstatus"), 0
		)  # drafts like the old one
		self.assertEqual((result["deposit"], result["refund_later"], result["top_up"]), (12000, 4000, 0))

	def test_rules(self):
		self.assertRaises(frappe.ValidationError, api.transfer_stay, self.stay.name, self.new_room.name,
			transfer_date=str(add_days(self.today, 3)))  # fmt: skip
		self.assertRaises(frappe.ValidationError, api.transfer_stay, self.stay.name, self.old_room.name,
			bed_no=1, transfer_date=str(self.today))  # fmt: skip
		other = make_property()
		far = make_room(rent=7000, property=other)
		result = transfers.transfer(self.stay.name, far.name, transfer_date=str(self.today))
		new = frappe.get_doc(ALLOTMENT, result["stay"])
		enabled = frappe.db.get_single_value("Rent Management Settings", "police_verification_enabled")
		self.assertEqual(new.police_verification or None, "Pending" if enabled else None)  # a new building

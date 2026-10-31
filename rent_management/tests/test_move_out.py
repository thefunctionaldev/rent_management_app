# Copyright (c) 2026, Shashank Dixit and Contributors
# See license.txt

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, flt, getdate, nowdate

from rent_management import api, move_out, portal
from rent_management.rent_management_system.doctype.tenant_rent_invoice.tenant_rent_invoice import MONTHS
from rent_management.rent_management_system.doctype.tenant_rent_invoice.test_tenant_rent_invoice import (
	make_invoice,
)
from rent_management.rent_management_system.doctype.tenant_space_allotment.test_tenant_space_allotment import (
	make_allotment,
	make_room,
)

ITEMS = [
	{"item": "Bed", "quantity": 1, "replacement_cost": 3000},
	{"item": "Room key", "quantity": 1, "replacement_cost": 300},
]


class TestMoveOut(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		frappe.db.set_single_value("Rent Management Settings", "deposit_refund_days", 7)
		room = make_room(rent=6000, deposit=12000)
		api.save_room({"name": room.name, "items": ITEMS})
		email = f"meera.{frappe.generate_hash(length=5)}@tenant.example"
		self.tenant = frappe.get_doc({"doctype": "Tenant", "first_name": "Meera", "email_id": email}).insert()
		self.stay = make_allotment(room=frappe.get_doc("Tenant Space", room.name), tenant=self.tenant,
			allotment_date=add_days(nowdate(), -70), security_deposit=12000, deposit_collected=1,
			notice_period_days=30, lock_in_months=3)  # fmt: skip
		month = getdate(add_days(nowdate(), -30))  # a month they stayed all of
		self.invoice = make_invoice(self.stay, billing_month=MONTHS[month.month - 1],
			billing_year=month.year, posting_date=str(month), submit=True)  # fmt: skip
		api.invite_tenant(self.tenant.name)
		self.user = frappe.db.get_value("Tenant", self.tenant.name, "user")

	def tearDown(self):
		frappe.set_user("Administrator")

	def page(self):
		frappe.set_user(self.user)
		try:
			return portal.get_move_out()
		finally:
			frappe.set_user("Administrator")

	def checklist(self, charge_bed=0):
		for kind in ("Move-in", "Move-out"):
			data = api.get_room_inspection(self.stay.name, kind)
			if kind == "Move-out" and charge_bed:
				data["items"][0].update(condition="Damaged", charge=charge_bed)
			api.save_room_inspection({**data, "complete": 1})

	def tenant_alerts(self):
		return frappe.get_all(
			"Notification Log",
			filters={"for_user": self.user},
			fields=["subject", "link"],
			order_by="creation",
		)

	def test_before_notice(self):
		data = self.page()
		self.assertEqual(data["stage"], "staying")
		self.assertEqual(getdate(data["earliest_date"]), getdate(add_days(nowdate(), 30)))
		self.assertFalse(data["breaks_lock_in"])  # 70 days in, 30 days' notice: past the 3-month lock-in
		frappe.set_user(self.user)
		self.assertIsNone(portal.get_home()["moving_out"])

	def test_notice_to_settlement(self):
		frappe.set_user(self.user)
		portal.give_notice(add_days(nowdate(), 30))
		home = portal.get_home()["moving_out"]
		self.assertEqual((home["stage"], home["days_left"]), ("notice", 30))

		data = self.page()
		unpaid = flt(frappe.db.get_value("Tenant Rent Invoice", self.invoice.name, "outstanding_amount"))
		self.assertGreater(unpaid, 0)
		self.assertEqual(
			data["estimate"], {"unpaid": unpaid, "charges": 0, "refund": 12000 - unpaid, "owes": 0}
		)
		self.assertEqual(getdate(data["refund_due_on"]), getdate(add_days(nowdate(), 37)))
		self.assertEqual([r["item"] for r in data["move_in_items"]], [])  # no move-in checklist was done

		# where to send it
		frappe.set_user(self.user)
		self.assertRaises(frappe.ValidationError, portal.save_refund_details, "not a upi id")
		self.assertRaises(frappe.ValidationError, portal.save_refund_details)
		portal.save_refund_details("meera@okhdfc")
		self.assertEqual(self.page()["refund_upi_id"], "meera@okhdfc")

		# the room is checked: the tenant hears, and the charge is in the estimate
		frappe.set_user("Administrator")
		self.checklist(charge_bed=1500)
		self.assertEqual(self.tenant_alerts()[-1].subject, "Your move-out checklist is done")
		self.assertEqual(self.tenant_alerts()[-1].link, "/tenant/moving-out")
		data = self.page()
		self.assertEqual(data["checklist"]["charges"], 1500)
		self.assertTrue(data["checklist"]["items"][0]["changed"])
		self.assertEqual(data["estimate"]["refund"], 12000 - unpaid - 1500)

		# moved out: still on their page, and on the manager's list with where to refund
		api.vacate_room(self.stay.name, nowdate())
		self.assertEqual(self.page()["stage"], "moved_out")
		pending = next(p for p in api.get_pending_settlements() if p.name == self.stay.name)
		self.assertEqual(pending.refund_upi_id, "meera@okhdfc")
		self.assertEqual(getdate(pending.refund_due_on), getdate(add_days(nowdate(), 7)))

		# settled: the breakdown, and the tenant is told
		deductions = api.get_checklist_deductions(self.stay.name)["deductions"]
		api.settle_deposit(self.stay.name, deductions=deductions, mode_of_refund="UPI", reference_no="UTR123")
		data = self.page()
		self.assertEqual(data["stage"], "settled")
		self.assertEqual(data["settlement"]["refund"], 12000 - unpaid - 1500)
		self.assertEqual(data["settlement"]["rent_adjusted"], unpaid)
		self.assertEqual((data["settlement"]["mode"], data["settlement"]["reference"]), ("UPI", "UTR123"))
		self.assertEqual(self.tenant_alerts()[-1].subject, "Your deposit is settled")
		frappe.set_user(self.user)
		self.assertRaises(frappe.ValidationError, portal.save_refund_details, "meera@okicici")

		# months later the page is gone
		frappe.set_user("Administrator")
		frappe.db.set_value(
			"Tenant Space Allotment", self.stay.name, "vacate_date", add_days(nowdate(), -200)
		)
		self.assertIsNone(self.page())

	def test_lock_in_and_late_refunds(self):
		self.assertTrue(self.page()["lock_in_ends"])
		frappe.db.set_value("Tenant Space Allotment", self.stay.name, "notice_period_days", 7)
		self.assertTrue(self.page()["breaks_lock_in"])  # 77 days in, the lock-in is 3 months

		api.vacate_room(self.stay.name, add_days(nowdate(), -7))
		with patch("rent_management.portal.notify_managers") as notify:
			move_out.remind()
		self.assertEqual(notify.call_args.args[0], f"Refund {self.tenant.full_name}'s deposit today")
		self.assertFalse(self.page()["refund_overdue"])

		frappe.db.set_value("Tenant Space Allotment", self.stay.name, "vacate_date", add_days(nowdate(), -9))
		self.assertTrue(self.page()["refund_overdue"])
		monday = getdate("2026-11-02")
		with (
			patch("rent_management.move_out.nowdate", return_value=str(monday)),
			patch("rent_management.portal.notify_managers") as notify,
		):
			frappe.db.set_value("Tenant Space Allotment", self.stay.name, "vacate_date", add_days(monday, -9))
			move_out.remind()
		self.assertIn("late", notify.call_args.args[0])

# Copyright (c) 2026, Shashank Dixit and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import nowdate

from rent_management import api, cash
from rent_management.rent_management_system.doctype.tenant_rent_invoice.test_tenant_rent_invoice import (
	make_invoice,
)
from rent_management.rent_management_system.doctype.tenant_space_allotment.test_tenant_space_allotment import (
	make_allotment,
	make_property,
	make_room,
)


def make_manager():
	email = f"owner.{frappe.generate_hash(length=5)}@example.com"
	user = frappe.get_doc({"doctype": "User", "email": email, "first_name": "Owner", "send_welcome_email": 0})
	user.append("roles", {"role": "Rent Manager"})
	user.insert(ignore_permissions=True)
	return email


class TestCashBook(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.building = make_property()
		self.stay = make_allotment(
			room=make_room(rent=8000, property=self.building), allotment_date="2026-01-01"
		)
		self.invoice = make_invoice(self.stay, submit=True)
		staff = api.save_staff(
			{"staff_name": "Gopal", "role": "Warden", "property": self.building, "monthly_salary": 10000}
		)
		self.warden = f"gopal.{frappe.generate_hash(length=5)}@staff.example"
		api.give_staff_login(staff, self.warden, ["payments", "expenses"])
		self.owner = make_manager()

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.local.rent_staff_access = {}

	def as_user(self, user):
		frappe.set_user(user)
		frappe.local.rent_staff_access = {}

	def held(self, user):
		return cash.balance_of(user)

	def test_collect_spend_and_hand_over(self):
		self.as_user(self.warden)
		payment = api.record_payment(self.invoice.name, 5000, "Cash")
		self.assertEqual(frappe.db.get_value("Rent Payment", payment, "collected_by"), self.warden)
		api.record_payment(self.invoice.name, 1000, "UPI")  # not cash
		api.save_expense({"property": self.building, "category": "Water", "amount": 300, "expense_date": nowdate(),
			"mode_of_payment": "Cash", "paid_to": "Water tanker"})  # fmt: skip
		self.assertEqual(self.held(self.warden), 4700)

		book = api.get_cash_book(self.building)
		self.assertFalse(book["manager"])
		self.assertEqual({e["user"] for e in book["entries"]}, {self.warden})  # their own only
		self.assertEqual([e["kind"] for e in book["entries"]], ["Collected", "Spent"])
		self.assertIn(self.owner, [r.name for r in book["receivers"]])

		self.assertRaises(frappe.ValidationError, api.hand_over_cash, self.owner, 5000)  # more than they hold
		handover = api.hand_over_cash(self.owner, 4000, "Rent for October")
		self.assertEqual(self.held(self.warden), 4700)  # until the owner confirms
		self.assertRaises(frappe.ValidationError, api.hand_over_cash, self.owner, 1000)  # 4,000 is on its way
		self.assertRaises(
			frappe.PermissionError, api.confirm_cash_handover, handover
		)  # not theirs to confirm

		self.as_user(self.owner)
		self.assertTrue(frappe.db.exists("Notification Log", {"for_user": self.owner, "link": "/rent/cash"}))
		book = api.get_cash_book()
		self.assertTrue(book["manager"])
		self.assertEqual(book["to_confirm"][0]["amount"], 4000)
		self.assertEqual(next(h for h in book["holders"] if h["user"] == self.warden)["pending"], 4000)
		api.confirm_cash_handover(handover)
		self.assertEqual((self.held(self.warden), self.held(self.owner)), (700, 4000))
		self.assertRaises(frappe.ValidationError, api.confirm_cash_handover, handover)  # once

	def test_reject_and_cancel(self):
		self.as_user(self.warden)
		api.record_payment(self.invoice.name, 2000, "Cash")
		first = api.hand_over_cash(self.owner, 2000)
		self.as_user(self.owner)
		api.confirm_cash_handover(first, 0)  # "I didn't get it"
		self.assertEqual(self.held(self.warden), 2000)
		self.as_user(self.warden)
		second = api.hand_over_cash(self.owner, 1500)
		api.cancel_cash_handover(second)
		self.assertFalse(frappe.db.exists(cash.HANDOVER, second))

	def test_staff_see_only_their_handovers(self):
		self.as_user(self.warden)
		api.record_payment(self.invoice.name, 2000, "Cash")
		mine = api.hand_over_cash(self.owner, 1000)
		frappe.set_user("Administrator")
		other = frappe.get_doc({"doctype": cash.HANDOVER, "from_user": self.owner, "to_user": "Administrator",
			"amount": 10, "handed_on": nowdate()}).insert()  # fmt: skip
		self.as_user(self.warden)
		self.assertEqual([h.name for h in frappe.get_list(cash.HANDOVER)], [mine])
		self.assertFalse(frappe.has_permission(cash.HANDOVER, "read", doc=other.name))

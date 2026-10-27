# Copyright (c) 2026, Shashank Dixit and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_months, getdate, nowdate

from rent_management import api, profit, salaries
from rent_management.rent_management_system.doctype.tenant_space_allotment.test_tenant_space_allotment import (
	make_property,
)
from rent_management.tests.test_pictures import data_url


class TestSalaries(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.building = make_property()
		self.month, self.year = salaries.last_month()
		start, _end = salaries.month_range(self.month, self.year)
		self.start = start
		self.cook = api.save_staff(
			{"staff_name": "Lakshmamma", "role": "Cook", "property": self.building, "monthly_salary": 15000,
				"joining_date": add_months(start, -3), "payment_mode": "UPI", "picture": data_url("red")}
		)  # fmt: skip

	def tearDown(self):
		frappe.set_user("Administrator")

	def slip(self, staff=None):
		return frappe.get_doc(
			salaries.SLIP, {"staff": staff or self.cook, "salary_month": self.month, "salary_year": self.year}
		)

	def test_staff_record(self):
		staff = frappe.get_doc(salaries.STAFF, self.cook)
		self.assertTrue(staff.display_picture.startswith("/private/files/lakshmamma-"))
		self.assertRaises(frappe.ValidationError, api.save_staff, {"name": self.cook, "pay_day": 31})
		data = api.get_staff(self.building)
		self.assertEqual((data["monthly_total"], data["staff"][0]["role"]), (15000, "Cook"))

	def test_salary_with_days_off_bonus_and_advance(self):
		# an advance in the month, recovered 2,000 a month
		advance = api.give_advance(self.cook, 5000, self.start, recover_per_month=2000)
		expense = frappe.db.get_value(salaries.ADVANCE, advance, "expense")
		self.assertEqual(
			frappe.db.get_value("Property Expense", expense, ["category", "amount"]), ("Salaries", 5000)
		)

		self.assertEqual(api.prepare_salaries(self.month, self.year, self.building), 1)
		self.assertEqual(api.prepare_salaries(self.month, self.year, self.building), 0)  # not twice
		slip = self.slip()
		api.save_salary_slip(slip.name, {"unpaid_days": 2, "bonus": 500, "other_deduction": 100})
		slip.reload()
		days = slip.days_in_month
		earned = round(15000 / days * (days - 2))
		self.assertEqual((slip.earned, slip.advance_recovery), (earned, 2000))
		self.assertEqual(slip.net_pay, earned + 500 - 100 - 2000)

		api.pay_salary(slip.name, nowdate(), "UPI", "UTR123")
		slip.reload()
		self.assertEqual(slip.status, "Paid")
		self.assertEqual(frappe.db.get_value("Property Expense", slip.expense, "amount"), slip.net_pay)
		self.assertEqual(
			frappe.db.get_value(salaries.ADVANCE, advance, ["recovered", "status"]), (2000, "Open")
		)
		self.assertRaises(frappe.ValidationError, api.save_salary_slip, slip.name, {"bonus": 1000})
		self.assertRaises(frappe.ValidationError, api.delete_advance, advance)  # partly recovered

		# what the building spent on her this month: the advance plus the net pay
		pl = profit.get_profit_and_loss(months=2, property=self.building)
		spent = {r["category"]: r["amount"] for r in pl["categories"]}
		self.assertEqual(spent["Salaries"], 5000 + slip.net_pay)

		api.undo_salary_payment(slip.name)
		slip.reload()
		self.assertEqual((slip.status, slip.expense), ("Draft", None))
		self.assertEqual(frappe.db.get_value(salaries.ADVANCE, advance, "recovered"), 0)
		self.assertFalse(
			frappe.db.exists("Property Expense", {"paid_to": "Lakshmamma", "amount": slip.net_pay})
		)
		api.delete_advance(advance)
		self.assertFalse(frappe.db.exists("Property Expense", expense))

	def test_joining_mid_month_and_full_recovery(self):
		guard = api.save_staff(
			{"staff_name": "Ramu", "role": "Security Guard", "property": self.building, "monthly_salary": 12000,
				"joining_date": self.start.replace(day=11)}
		)  # fmt: skip
		api.give_advance(guard, 20000, self.start.replace(day=12))  # more than one salary
		api.prepare_salaries(self.month, self.year, self.building)
		slip = self.slip(guard)
		self.assertEqual(slip.days_employed, slip.days_in_month - 10)
		self.assertEqual(slip.earned, round(12000 / slip.days_in_month * slip.days_employed))
		self.assertEqual((slip.advance_recovery, slip.net_pay), (slip.earned, 0))  # never below zero
		api.pay_salary(slip.name)
		self.assertIsNone(frappe.db.get_value(salaries.SLIP, slip.name, "expense"))  # nothing paid out

		# not on the list for a month before they joined
		before = getdate(add_months(self.start, -1))
		month = salaries.MONTHS[before.month - 1]
		self.assertNotIn(guard, salaries.staff_for(month, before.year, self.building))

	def test_pay_day_reminder(self):
		frappe.db.set_value(salaries.STAFF, self.cook, "pay_day", min(getdate(nowdate()).day, 28))
		frappe.db.delete("Notification Log", {"subject": ("like", "Salaries due%")})
		salaries.remind_due()
		if getdate(nowdate()).day <= 28:
			self.assertTrue(frappe.db.exists("Notification Log", {"subject": ("like", "Salaries due%")}))

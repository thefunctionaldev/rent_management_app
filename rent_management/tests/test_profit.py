# Copyright (c) 2026, Shashank Dixit and Contributors
# See license.txt

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from rent_management import api, profit, subscription
from rent_management.rent_management_system.doctype.tenant_rent_invoice.test_tenant_rent_invoice import (
	make_invoice,
)
from rent_management.rent_management_system.doctype.tenant_space_allotment.test_tenant_space_allotment import (
	make_allotment,
	make_property,
	make_room,
)


class TestProfit(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.building = make_property()
		allotment = make_allotment(
			room=make_room(rent=6000, property=self.building), allotment_date="2026-01-01"
		)
		self.invoice = make_invoice(
			allotment, billing_month="February", posting_date="2026-02-01", submit=True
		)
		api.record_payment(self.invoice.name, 6000, "UPI", payment_date="2026-02-05")
		for category, amount, day in (
			("Salaries", 8000, "2026-02-01"),
			("Electricity Bill", 1500, "2026-02-20"),
		):
			api.save_expense(
				{"property": self.building, "category": category, "amount": amount, "expense_date": day}
			)

	def test_month_totals(self):
		report = profit.get_profit_and_loss(months=2, property=self.building, end="2026-02-28")
		feb = report["months"][-1]
		self.assertEqual(feb["month"], "2026-02")
		self.assertEqual(
			(feb["invoiced"], feb["collected"], feb["expenses"], feb["profit"]), (6000, 6000, 9500, -3500)
		)
		self.assertEqual(report["months"][0]["collected"], 0)
		self.assertEqual([c["category"] for c in report["categories"]], ["Salaries", "Electricity Bill"])
		self.assertEqual(report["properties"][0]["property"], self.building)

	def test_deposit_payments_are_not_income(self):
		self.assertEqual(
			frappe.get_all(
				"Rent Payment", filters={"rent_invoice": self.invoice.name}, pluck="mode_of_payment"
			),
			["UPI"],
		)
		report = profit.get_profit_and_loss(months=1, property=self.building, end="2026-02-28")
		self.assertEqual(report["totals"]["collected"], 6000)

	def test_expense_validation(self):
		self.assertRaises(
			frappe.ValidationError,
			api.save_expense,
			{"property": self.building, "category": "Other", "amount": 0},
		)
		listed = api.get_expenses(property=self.building)
		self.assertEqual(len(listed["expenses"]), 2)
		self.assertIn("Salaries", listed["categories"])

	def test_report_needs_plan(self):
		frappe.flags.enforce_rent_subscription = True
		try:
			with patch.object(subscription, "get_current_plan", return_value={"profit_report": 0}):
				self.assertRaises(subscription.PlanLimitError, api.get_profit_and_loss)
			with patch.object(subscription, "get_current_plan", return_value={"profit_report": 1}):
				self.assertIn("months", api.get_profit_and_loss(months=3))
		finally:
			frappe.flags.enforce_rent_subscription = False

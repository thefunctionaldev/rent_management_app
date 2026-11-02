"""Run with bench --site SITE run-tests --app rent_management --module rent_management.tests.test_operations."""

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import nowdate

from rent_management import api, approvals
from rent_management.rent_management_system.doctype.tenant_space_allotment.test_tenant_space_allotment import (
	make_property,
	make_room,
)
from rent_management.tests.test_api import make_user


class TestOperations(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.property = make_property()
		self.requester = make_user("approval.requester@example.com", ["Rent Manager"])
		self.reviewer = make_user("approval.reviewer@example.com", ["Rent Manager"])
		self.outsider = make_user("approval.outsider@example.com")
		api.save_approval_rules(
			{
				"enabled": 1,
				"rules": [
					{
						"action": "Expense",
						"requester_role": "Rent Manager",
						"threshold": 5000,
						"approver_role": "Rent Manager",
					}
				],
			}
		)
		frappe.set_user(self.requester)

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.local.rent_approval_execution = None
		api.save_approval_rules({"enabled": 0, "rules": []})

	def expense(self, amount=5000):
		return {
			"property": self.property,
			"amount": amount,
			"category": "Other",
			"expense_date": nowdate(),
			"mode_of_payment": "Cash",
		}

	def test_pending_does_not_write_and_cannot_self_approve(self):
		before = frappe.db.count("Property Expense")
		result = api.save_expense(self.expense())
		self.assertTrue(result["approval_pending"])
		self.assertEqual(frappe.db.count("Property Expense"), before)
		self.assertRaises(frappe.PermissionError, api.decide_approval, result["request"], "approve")
		frappe.set_user(self.reviewer)
		api.decide_approval(result["request"], "approve")
		self.assertEqual(frappe.db.count("Property Expense"), before + 1)
		self.assertEqual(frappe.db.get_value(approvals.REQUEST, result["request"], "status"), "Executed")
		self.assertRaises(frappe.ValidationError, api.decide_approval, result["request"], "approve")

	def test_rejection_and_direct_write_bypass(self):
		result = api.save_expense(self.expense())
		self.assertRaises(
			frappe.PermissionError, frappe.get_doc({"doctype": "Property Expense", **self.expense()}).insert
		)
		frappe.set_user(self.reviewer)
		self.assertRaises(frappe.ValidationError, api.decide_approval, result["request"], "reject")
		api.decide_approval(result["request"], "reject", "Quote needs review")
		self.assertEqual(frappe.db.get_value(approvals.REQUEST, result["request"], "status"), "Rejected")

	def test_below_threshold_and_source_change(self):
		name = api.save_expense(self.expense(100))
		self.assertIsInstance(name, str)
		result = api.save_expense({**self.expense(6000), "name": name})
		api.save_expense({**self.expense(200), "name": name})
		frappe.set_user(self.reviewer)
		self.assertRaises(frappe.ValidationError, api.decide_approval, result["request"], "approve")
		self.assertEqual(frappe.db.get_value("Property Expense", name, "amount"), 200)

	def test_authorization_and_policy_edit(self):
		self.assertRaises(frappe.PermissionError, api.save_approval_rules, {"enabled": 0})
		frappe.set_user(self.outsider)
		for fn in (api.get_setup_progress, api.get_approvals):
			self.assertRaises(frappe.PermissionError, fn)
		self.assertRaises(frappe.PermissionError, api.get_occupancy_calendar, "2026-11-01", "2026-11-14")

	def test_calendar_range_and_setup_progress(self):
		make_room(property=self.property)
		data = api.get_occupancy_calendar("2026-11-01", "2026-11-14", self.property)
		self.assertTrue(data["rooms"])
		self.assertTrue(all(r.property == self.property for r in data["rooms"]))
		self.assertRaises(frappe.ValidationError, api.get_occupancy_calendar, "2026-11-14", "2026-11-01")
		self.assertRaises(frappe.ValidationError, api.get_occupancy_calendar, "2026-01-01", "2026-12-31")
		progress = api.get_setup_progress()
		self.assertTrue(progress["steps"][0]["done"])
		api.save_setup_rules({"rent_due_day": 5, "default_notice_days": 30, "default_agreement_months": 11})
		self.assertTrue(api.get_setup_progress()["steps"][2]["done"])

	def enable_rule(self, action):
		frappe.set_user("Administrator")
		api.save_approval_rules(
			{
				"enabled": 1,
				"rules": [
					{
						"action": action,
						"requester_role": "Rent Manager",
						"threshold": 0,
						"approver_role": "Rent Manager",
					}
				],
			}
		)
		frappe.set_user(self.requester)

	def test_invoice_discount_waits_for_review(self):
		from rent_management.rent_management_system.doctype.tenant_space_allotment.test_tenant_space_allotment import (
			make_allotment,
		)

		stay = make_allotment(room=make_room(property=self.property, rent=3000))
		self.enable_rule("Invoice discount")
		result = api.create_invoice(
			stay.name, "January", 2026, discount_amount=100, posting_date="2026-01-01", submit=1
		)
		self.assertFalse(frappe.db.exists("Tenant Rent Invoice", {"tenant_space_allotment": stay.name}))
		frappe.set_user(self.reviewer)
		api.decide_approval(result["request"], "approve")
		invoice = frappe.db.get_value(
			"Tenant Rent Invoice",
			{"tenant_space_allotment": stay.name},
			["discount_amount", "docstatus"],
			as_dict=True,
		)
		self.assertEqual(invoice.discount_amount, 100)
		self.assertEqual(invoice.docstatus, 1)

	def test_payment_reversal_updates_invoice_only_after_review(self):
		from rent_management.rent_management_system.doctype.tenant_space_allotment.test_tenant_space_allotment import (
			make_allotment,
		)

		stay = make_allotment(room=make_room(property=self.property, rent=3000))
		invoice = api.create_invoice(stay.name, "January", 2026, posting_date="2026-01-01", submit=1)
		payment = api.record_payment(invoice, 500, "Cash")
		self.enable_rule("Payment reversal")
		result = api.reverse_payment(payment, "Entered twice")
		self.assertEqual(frappe.db.get_value("Rent Payment", payment, "docstatus"), 1)
		frappe.set_user(self.reviewer)
		api.decide_approval(result["request"], "approve")
		self.assertEqual(frappe.db.get_value("Rent Payment", payment, "docstatus"), 2)
		self.assertEqual(frappe.db.get_value("Tenant Rent Invoice", invoice, "paid_amount"), 0)

	def test_refund_is_not_recorded_while_pending(self):
		from rent_management.rent_management_system.doctype.tenant_space_allotment.test_tenant_space_allotment import (
			make_allotment,
		)

		stay = make_allotment(
			room=make_room(property=self.property, rent=3000, deposit=6000), deposit_collected=1
		)
		api.vacate_room(stay.name, "2026-01-31")
		self.enable_rule("Deposit refund")
		result = api.settle_deposit(stay.name, mode_of_refund="Bank Transfer")
		self.assertFalse(
			frappe.db.exists("Security Deposit Settlement", {"tenant_space_allotment": stay.name})
		)
		frappe.set_user(self.reviewer)
		api.decide_approval(result["request"], "approve")
		settlement = frappe.db.get_value(
			"Security Deposit Settlement",
			{"tenant_space_allotment": stay.name},
			["docstatus", "refund_amount"],
			as_dict=True,
		)
		self.assertEqual(settlement.docstatus, 1)
		self.assertEqual(settlement.refund_amount, 6000)

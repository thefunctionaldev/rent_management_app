"""Isolated policy tests; no Frappe database required. Integration tests live in rent_management/tests."""

import importlib.util
import sys
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch


class PermissionDenied(Exception):
	pass


class InvalidOperation(Exception):
	pass


class ApprovalPolicyTest(unittest.TestCase):
	def setUp(self):
		self.frappe = ModuleType("frappe")
		self.frappe._ = lambda text: text
		self.frappe.PermissionError = PermissionDenied
		self.frappe.local = SimpleNamespace()
		self.frappe.session = SimpleNamespace(user="reviewer")
		self.frappe.get_roles = Mock(return_value=["Rent Manager"])
		self.frappe.db = Mock()
		self.frappe.get_doc = Mock()
		self.frappe.set_user = lambda user: setattr(self.frappe.session, "user", user)
		self.frappe.throw = lambda message, error=InvalidOperation: (_ for _ in ()).throw(error(message))
		utils = ModuleType("frappe.utils")
		utils.flt = lambda v: float(v or 0)
		utils.now_datetime = Mock()
		access = ModuleType("rent_management.access")
		access.is_manager = Mock(return_value=True)
		subscription = ModuleType("rent_management.subscription")
		subscription.check_writable = Mock()
		package = ModuleType("rent_management")
		package.access, package.subscription = access, subscription
		modules = {
			"frappe": self.frappe,
			"frappe.utils": utils,
			"rent_management": package,
			"rent_management.access": access,
			"rent_management.subscription": subscription,
		}
		with patch.dict(sys.modules, modules):
			spec = importlib.util.spec_from_file_location(
				"policy_under_test", Path(__file__).parents[2] / "rent_management/approvals.py"
			)
			self.policy = importlib.util.module_from_spec(spec)
			spec.loader.exec_module(self.policy)
		self.access = access

	def test_boundary_and_strictest_role(self):
		rules = [
			SimpleNamespace(
				action="Expense", requester_role="Rent Staff", threshold=5000, approver_role="Rent Manager"
			),
			SimpleNamespace(
				action="Expense",
				requester_role="Rent Manager",
				threshold=2000,
				approver_role="System Manager",
			),
		]
		self.assertIsNone(self.policy.matching_rule(rules, ["Rent Staff"], "Expense", 4999.99))
		self.assertIs(self.policy.matching_rule(rules, ["Rent Staff"], "Expense", 5000), rules[0])
		self.assertIs(
			self.policy.matching_rule(rules, ["Rent Staff", "Rent Manager"], "Expense", 5000), rules[1]
		)
		self.assertIsNone(self.policy.matching_rule(rules, ["Guest"], "Expense", 999999))

	def request(self, **changes):
		values = dict(status="Pending", requested_by="requester", approver_role="Rent Manager")
		values.update(changes)
		self.frappe.get_doc.return_value = SimpleNamespace(**values)

	def test_self_approval_is_denied(self):
		self.request(requested_by="reviewer")
		with self.assertRaises(PermissionDenied):
			self.policy.decide("A", "approve")

	def test_wrong_role_and_non_manager_are_denied(self):
		self.request(approver_role="System Manager")
		with self.assertRaises(PermissionDenied):
			self.policy.decide("A", "approve")
		self.access.is_manager.return_value = False
		with self.assertRaises(PermissionDenied):
			self.policy.decide("A", "reject", "No")

	def test_replay_is_denied_before_execution(self):
		for state in ["Executed", "Rejected", "Withdrawn"]:
			self.request(status=state)
			with self.assertRaises(InvalidOperation):
				self.policy.decide("A", "approve")

	def test_reject_requires_reason_and_never_executes(self):
		self.request()
		with self.assertRaises(InvalidOperation):
			self.policy.decide("A", "reject", "  ")
		self.frappe.set_user = Mock()
		self.policy.write_request = Mock()
		self.frappe.get_doc.return_value.name = "A"
		self.policy.decide("A", "reject", "Missing invoice")
		self.assertEqual(self.frappe.get_doc.return_value.status, "Rejected")
		self.frappe.set_user.assert_not_called()

	def test_guard_blocks_direct_payment_reversal(self):
		self.policy.rule_for = Mock(return_value=True)
		doc = SimpleNamespace(doctype="Rent Payment", amount=5000, get_doc_before_save=lambda: None)
		with self.assertRaises(PermissionDenied):
			self.policy.guard(doc, "before_cancel")
		self.frappe.local.rent_approval_execution = SimpleNamespace(action="Payment reversal", amount=5000)
		self.policy.guard(doc, "before_cancel")
		doc.amount = 6000
		with self.assertRaises(InvalidOperation):
			self.policy.guard(doc, "before_cancel")

	def test_guard_cannot_reuse_other_action_approval(self):
		self.policy.rule_for = Mock(return_value=True)
		self.frappe.local.rent_approval_execution = SimpleNamespace(action="Expense", amount=5000)
		doc = SimpleNamespace(doctype="Rent Payment", amount=5000, get_doc_before_save=lambda: None)
		with self.assertRaises(PermissionDenied):
			self.policy.guard(doc, "before_cancel")


if __name__ == "__main__":
	unittest.main()

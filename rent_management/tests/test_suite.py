"""Run on a migrated Frappe test site; no live outbound integration calls."""

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import nowdate

from rent_management import api
from rent_management.rent_management_system.doctype.tenant_space_allotment.test_tenant_space_allotment import (
	make_property,
	make_room,
)
from rent_management.suite import (
	common,
	erp_sync,
	housekeeping,
	language,
	owners,
	recurring,
	waitlist,
	workorders,
)
from rent_management.tests.test_api import make_user


class TestOperationsSuite(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.a, self.b = make_property(), make_property()
		self.requester = make_user("suite.manager@example.com", ["Rent Manager"])
		self.reviewer = make_user("suite.reviewer@example.com", ["Rent Manager"])
		self.owner = make_user(f"suite.owner.{frappe.generate_hash(length=10)}@example.com")
		api.save_approval_rules({"enabled": 0, "rules": []})

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.local.rent_staff_access = {}
		frappe.local.rent_approval_execution = None
		api.save_approval_rules({"enabled": 0, "rules": []})

	def bill_schedule(self):
		return recurring.save_schedule(
			dict(
				title="Monthly internet",
				property=self.a,
				category="Internet & Cable",
				amount=800,
				frequency="Monthly",
				start_date=nowdate(),
				active=1,
			)
		)

	def test_bill_generation_payment_and_duplicate_prevention(self):
		schedule = self.bill_schedule()
		before = frappe.db.count("Property Expense")
		recurring.generate()
		recurring.generate()
		bills = frappe.get_all(recurring.BILL, filters={"schedule": schedule}, pluck="name")
		self.assertEqual(len(bills), 1)
		self.assertEqual(frappe.db.count("Property Expense"), before)
		expense = api.pay_operating_bill(bills[0], "Bank Transfer", "TEST-1")
		self.assertEqual(frappe.db.get_value(recurring.BILL, bills[0], "status"), "Paid")
		self.assertEqual(frappe.db.get_value("Property Expense", expense, "amount"), 800)
		self.assertRaises(frappe.ValidationError, api.pay_operating_bill, bills[0])
		self.assertRaises(frappe.ValidationError, api.save_expense, {"name": expense, "amount": 900})

	def test_bill_payment_uses_existing_second_person_approval(self):
		schedule = self.bill_schedule()
		recurring.generate()
		bill = frappe.db.get_value(recurring.BILL, {"schedule": schedule}, "name")
		api.save_approval_rules(
			{
				"enabled": 1,
				"rules": [
					{
						"action": "Expense",
						"requester_role": "Rent Manager",
						"threshold": 0,
						"approver_role": "Rent Manager",
					}
				],
			}
		)
		frappe.set_user(self.requester)
		result = api.pay_operating_bill(bill)
		self.assertTrue(result["approval_pending"])
		self.assertFalse(frappe.db.get_value(recurring.BILL, bill, "expense"))
		self.assertRaises(frappe.PermissionError, api.decide_approval, result["request"], "approve")
		frappe.set_user(self.reviewer)
		api.decide_approval(result["request"], "approve")
		self.assertEqual(frappe.db.get_value(recurring.BILL, bill, "status"), "Paid")

	def test_owner_scope_and_revocation(self):
		owners.grant(self.owner, self.a)
		frappe.set_user(self.owner)
		self.assertEqual(owners.dashboard()["properties"], [self.a])
		self.assertRaises(frappe.PermissionError, owners.dashboard, self.b)
		self.assertRaises(frappe.PermissionError, owners.grants)
		frappe.set_user("Administrator")
		owners.grant(self.owner, self.a, 0)
		frappe.set_user(self.owner)
		self.assertEqual(owners.dashboard()["properties"], [])

	def test_owner_quote_approval_and_replay(self):
		owners.grant(self.owner, self.a)
		frappe.set_user(self.requester)
		order = workorders.save_order(
			dict(
				subject="Repair fan",
				property=self.a,
				assigned_to=self.requester,
				due_date=nowdate(),
				quote_amount=500,
			)
		)
		workorders.transition(order, "request")
		self.assertRaises(frappe.PermissionError, workorders.transition, order, "approve")
		frappe.set_user(self.owner)
		owners.review_quote(order, 1, "Approved")
		self.assertEqual(frappe.db.get_value(workorders.DT, order, "status"), "Approved")
		self.assertRaises(frappe.PermissionError, owners.review_quote, order, 1)

	def test_guard_blocks_direct_rest_or_desk_writes(self):
		self.assertRaises(
			frappe.PermissionError, frappe.get_doc({"doctype": "Rent Vendor", "vendor_name": "Bypass"}).insert
		)
		self.assertRaises(frappe.PermissionError, frappe.get_single(erp_sync.SETTINGS).save)

	def test_cleaning_checklist_and_idempotence(self):
		schedule = housekeeping.save_schedule(
			dict(
				title="Lobby",
				property=self.a,
				assigned_to=self.requester,
				frequency="Daily",
				start_date=nowdate(),
				active=1,
				require_photo=0,
				checklist="Sweep\nMop",
			)
		)
		housekeeping.generate()
		housekeeping.generate()
		tasks = frappe.get_all(housekeeping.TASK, filters={"schedule": schedule}, pluck="name")
		self.assertEqual(len(tasks), 1)
		self.assertRaises(frappe.ValidationError, housekeeping.update_task, tasks[0], "complete", [0])
		housekeeping.update_task(tasks[0], "complete", [0, 1], "Done")
		housekeeping.update_task(tasks[0], "verify")
		self.assertEqual(frappe.db.get_value(housekeeping.TASK, tasks[0], "status"), "Verified")

	def test_waitlist_budget_matching_and_convert_once(self):
		room = make_room(rent=3000, property=self.a)
		make_room(rent=9000, property=self.a)
		entry = waitlist.save_entry(
			dict(
				full_name="Applicant",
				phone="9876543210",
				property=self.a,
				budget=4000,
				move_in_date=nowdate(),
			)
		)
		self.assertEqual([r.name for r in waitlist.matches(entry)], [room.name])
		waitlist.offer(entry, room.name)
		waitlist.act(entry, "accept")
		lead = frappe.db.get_value(waitlist.DT, entry, "lead")
		self.assertEqual(frappe.db.get_value("Rent Lead", lead, "status"), "Contacted")
		self.assertRaises(frappe.ValidationError, waitlist.act, entry, "accept")

	def test_language_preference_is_per_user(self):
		frappe.set_user(self.owner)
		language.set_preference("hi")
		self.assertEqual(language.preference(), "hi")
		frappe.set_user(self.requester)
		language.set_preference("en")
		self.assertEqual(language.preference(), "en")
		self.assertEqual(frappe.db.get_value("User", self.owner, "language"), "hi")
		self.assertRaises(frappe.PermissionError, language.set_preference, "xx")

	def test_disabled_erp_cannot_queue_or_call_remote(self):
		settings = frappe.get_single(erp_sync.SETTINGS)
		settings.enabled = 0
		common.save(settings)
		with patch.object(erp_sync, "remote") as remote:
			self.assertRaises(frappe.ValidationError, erp_sync.queue, "Property Expense", "missing")
			erp_sync.process_queue()
			remote.assert_not_called()

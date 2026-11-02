"""Behavior tests with isolated service dependencies; no live Frappe or external API."""

import base64
import importlib.util
import sys
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

ROOT = Path(__file__).parents[2] / "rent_management" / "suite"


def pure(name):
	spec = importlib.util.spec_from_file_location("suite_test_" + name, ROOT / (name + ".py"))
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


dates, accounting, messages = pure("dates"), pure("erp_payloads"), pure("messages")


class TestDates(unittest.TestCase):
	def test_month_end_does_not_drift(self):
		feb = dates.next_occurrence("2026-01-31", "Monthly", "2026-01-31")
		self.assertEqual(feb, date(2026, 2, 28))
		self.assertEqual(dates.next_occurrence(feb, "Monthly", "2026-01-31"), date(2026, 3, 31))

	def test_leap_year_and_year_rollover(self):
		self.assertEqual(dates.next_occurrence("2024-02-29", "Yearly", "2024-02-29"), date(2025, 2, 28))
		self.assertEqual(dates.next_occurrence("2026-11-30", "Quarterly", "2026-11-30"), date(2027, 2, 28))

	def test_daily_weekly(self):
		self.assertEqual(dates.next_occurrence("2026-12-31", "Daily", "2026-01-01"), date(2027, 1, 1))
		self.assertEqual(dates.next_occurrence("2026-12-31", "Weekly", "2026-01-01"), date(2027, 1, 7))

	def test_no_unapproved_completion_or_reopening(self):
		for status in ("Draft", "Pending Approval", "Approved", "Cancelled", "Completed", "Confirmed"):
			self.assertFalse(dates.can_transition(status, "complete"))
		self.assertTrue(dates.can_transition("In Progress", "complete"))
		self.assertFalse(dates.can_transition("Completed", "start"))
		self.assertFalse(dates.can_transition("Confirmed", "confirm"))


class TestAccounting(unittest.TestCase):
	def setUp(self):
		self.s = dict(
			company="Company",
			currency="INR",
			rent_item="Rent",
			income_account="Rent Income",
			expense_account="Expenses",
			deposit_account="Deposits",
			receivable_account="Receivable",
			bank_account="Bank",
			cash_account="Cash",
			cost_center="Main",
		)
		self.payment = dict(name="PAY-1", payment_date="2026-11-01", amount=1234.50, mode_of_payment="Cash")

	def test_cash_receipt_routes_to_cash_and_references_invoice(self):
		body = accounting.receipt(self.s, "unique", self.payment, "Customer", "INV-1")
		self.assertEqual(body["paid_to"], "Cash")
		self.assertEqual(body["paid_from"], "Receivable")
		self.assertEqual(body["references"][0]["allocated_amount"], 1234.50)
		self.assertEqual(body.get("docstatus", 0), 0)

	def test_deposit_application_does_not_create_cash(self):
		body = accounting.receipt(
			self.s, "unique", {**self.payment, "mode_of_payment": "Security Deposit"}, "Customer", "INV-1"
		)
		self.assertEqual(body["doctype"], "Journal Entry")
		rows = body["accounts"]
		self.assertEqual([r["account"] for r in rows], ["Deposits", "Receivable"])
		self.assertEqual(
			sum(r["debit_in_account_currency"] for r in rows),
			sum(r["credit_in_account_currency"] for r in rows),
		)
		self.assertEqual(rows[1]["reference_name"], "INV-1")
		self.assertEqual(rows[1]["party"], "Customer")

	def test_invoice_draft_uses_final_amount_without_private_data(self):
		source = dict(
			name="INV-1", posting_date="2026-11-01", final_amount=5000, aadhaar="secret", mobile_no="private"
		)
		body = accounting.invoice(self.s, "key", source, "Customer")
		self.assertEqual(body["items"][0]["rate"], 5000)
		self.assertEqual(body["due_date"], "2026-11-01")
		self.assertEqual(body.get("docstatus", 0), 0)
		self.assertNotIn("secret", str(body))
		self.assertNotIn("private", str(body))

	def test_deposit_and_expense_journals_balance(self):
		for debit, credit in [("Bank", "Deposits"), ("Expenses", "Bank")]:
			body = accounting.journal(self.s, "key", "2026-11-01", debit, credit, 55.25, "Audit reference")
			self.assertEqual(body["custom_rent_sync_key"], "key")
			self.assertEqual(
				sum(
					r["debit_in_account_currency"] - r["credit_in_account_currency"] for r in body["accounts"]
				),
				0,
			)


class TestMessages(unittest.TestCase):
	def test_hindi_keeps_names_amounts_and_payment_link(self):
		text, params = messages.render_hindi(
			"Reminder",
			["Asha", "₹5,000", "November 2026", "Building A", "5 Nov", "Pay online: https://pay.example/x"],
		)
		self.assertIn("नमस्ते Asha", text)
		self.assertIn("₹5,000", text)
		self.assertIn("https://pay.example/x", params[5])
		self.assertNotIn("Pay online:", text)

	def test_templates_accept_same_parameter_counts(self):
		counts = {
			"Reminder": 6,
			"Due Today": 6,
			"Overdue": 6,
			"Receipt": 5,
			"Request Update": 4,
			"Notice": 4,
			"Referral": 3,
			"Deposit": 4,
		}
		for kind, count in counts.items():
			values = [f"value-{i}" for i in range(count)]
			text, rendered = messages.render_hindi(kind, values)
			self.assertEqual(len(rendered), count)
			for value in values:
				self.assertIn(value, text)


class Denied(Exception):
	pass


class Invalid(Exception):
	pass


class Row(dict):
	__getattr__ = dict.get
	__setattr__ = dict.__setitem__


class TestServices(unittest.TestCase):
	def setUp(self):
		self.f = ModuleType("frappe")
		self.f._ = lambda text: text
		self.f.whitelist = lambda *a, **k: lambda fn: fn
		self.f.PermissionError, self.f.ValidationError, self.f.DoesNotExistError = Denied, Invalid, Invalid
		self.f.throw = lambda text, error=Invalid: (_ for _ in ()).throw(error(text))
		self.f.local = SimpleNamespace(site="site-a")
		self.f.session = SimpleNamespace(user="manager")
		self.f.db = Mock()
		self.f.get_roles = Mock(return_value=["Rent Manager"])
		self.f.get_all = Mock(return_value=[])
		self.f.get_doc = Mock()
		self.f.parse_json = lambda value: __import__("json").loads(value) if isinstance(value, str) else value
		self.f.generate_hash = Mock(return_value="test")
		utils = ModuleType("frappe.utils")
		utils.flt = lambda value: float(value or 0)
		utils.cint = lambda value: int(value or 0)
		utils.getdate = lambda value=None: date.fromisoformat(str(value or "2026-11-02")[:10])
		utils.nowdate = lambda: "2026-11-02"
		utils.now_datetime = lambda: datetime(2026, 11, 2)
		utils.get_datetime = lambda value: datetime.fromisoformat(str(value))
		utils.add_days = lambda value, n: utils.get_datetime(value) + timedelta(days=n)
		document = ModuleType("frappe.model.document")
		document.Document = type("Document", (), {})
		package = ModuleType("rent_management")
		package.__path__ = []
		self.access = ModuleType("rent_management.access")
		self.access.is_manager = Mock(return_value=True)
		self.access.staff_access = Mock(return_value=None)
		self.subscription = ModuleType("rent_management.subscription")
		self.subscription.check_writable = Mock()
		self.portal = ModuleType("rent_management.portal")
		self.portal.get_tenant = Mock(return_value=None)
		self.portal.current_tenant = Mock(return_value=Row(name="tenant-a"))
		self.approvals = ModuleType("rent_management.approvals")
		self.approvals.stage = Mock(return_value=None)
		for key, obj in dict(
			access=self.access, subscription=self.subscription, portal=self.portal, approvals=self.approvals
		).items():
			setattr(package, key, obj)
		suite = ModuleType("rent_management.suite")
		suite.__path__ = [str(ROOT)]
		suite.erp_payloads = accounting
		modules = {
			"frappe": self.f,
			"frappe.utils": utils,
			"frappe.model": ModuleType("frappe.model"),
			"frappe.model.document": document,
			"rent_management": package,
			"rent_management.suite": suite,
			"rent_management.suite.dates": dates,
			"rent_management.suite.erp_payloads": accounting,
		}
		modules.update(
			{
				"rent_management." + key: getattr(package, key)
				for key in ["access", "subscription", "portal", "approvals"]
			}
		)
		requests = ModuleType("requests")
		requests.RequestException = type("RequestException", (Exception,), {})
		requests.request = Mock()
		modules["requests"] = requests
		self.patch = patch.dict(sys.modules, modules)
		self.patch.start()
		self.addCleanup(self.patch.stop)
		self.common = self.load("common")
		sys.modules["rent_management.suite.common"] = self.common

	def load(self, name):
		return pure(name)

	def test_staff_scope_and_missing_area(self):
		self.access.is_manager.return_value = False
		self.access.staff_access.return_value = Row(areas={"housekeeping"}, building="A")
		self.assertEqual(self.common.scoped("housekeeping"), {"property": "A"})
		with self.assertRaises(Denied):
			self.common.scoped("housekeeping", "B")
		with self.assertRaises(Denied):
			self.common.scoped("expenses", "A")

	def test_document_write_guard_and_cleanup(self):
		doc = self.common.SuiteDocument()
		doc.doctype = "Rent Work Order"
		with self.assertRaises(Denied):
			doc.validate()
		with self.assertRaises(RuntimeError):
			with self.common.service_write():
				doc.validate()
				raise RuntimeError("failed")
		self.assertFalse(self.f.local.rent_suite_write)
		self.subscription.check_writable.assert_called_once_with(doc)

	def test_positive_rejects_nan_negative_and_zero(self):
		for amount in [float("nan"), float("inf"), -1, 0]:
			with self.assertRaises(Invalid):
				self.common.positive(amount)
		self.assertEqual(self.common.positive(0, allow_zero=True), 0)

	def test_file_type_and_size_restrictions(self):
		for content in [b"<script>alert(1)</script>", b"", b"\x89PNG\r\n\x1a\n" + b"x" * (5 * 1024 * 1024)]:
			with self.assertRaises(Invalid):
				self.common.file_bytes("photo.png", base64.b64encode(content).decode())
		name, content = self.common.file_bytes(
			"../../bad.png", base64.b64encode(b"\x89PNG\r\n\x1a\ncontent").decode()
		)
		self.assertEqual(name, "evidence-test.png")

	def test_owner_cannot_read_other_property(self):
		owners = self.load("owners")
		self.f.get_all.return_value = ["A"]
		owners.check("A")
		with self.assertRaises(Denied):
			owners.check("B")

	def test_quote_requires_second_person_and_pending_status(self):
		work = self.load("workorders")
		row = Row(status="Pending Approval", requested_by="manager")
		with self.assertRaises(Denied):
			work.approve(row)
		row.requested_by = "someone"
		row.status = "Draft"
		with self.assertRaises(Denied):
			work.approve(row)

	def test_tenant_cannot_confirm_other_tenants_work(self):
		work = self.load("workorders")
		work.locked = Mock(return_value=Row(tenant="tenant-b", status="Completed"))
		with self.assertRaises(Denied):
			work.confirm("order")

	def test_staff_cannot_upload_other_assignees_evidence(self):
		files = self.load("files")
		self.access.is_manager.return_value = False
		self.access.staff_access.return_value = Row(areas={"requests"}, building="A")
		with self.assertRaises(Denied):
			files.permitted(Row(doctype="Rent Work Order", property="A", assigned_to="other"), write=True)

	def test_recurring_generation_is_idempotent_and_not_an_expense(self):
		recurring = self.load("recurring")
		schedule = Row(
			name="S",
			title="Internet",
			property="A",
			vendor=None,
			category="Internet & Cable",
			amount=500,
			next_due="2026-11-01",
			start_date="2026-11-01",
			frequency="Monthly",
			end_date=None,
			active=1,
			notes="",
		)
		recurring.locked = Mock(return_value=schedule)
		self.f.get_all.return_value = ["S"]
		created = []
		keys = set()
		self.f.db.exists.side_effect = lambda dt, filters: filters["generation_key"] in keys
		self.f.get_doc.side_effect = lambda value: Row(value)

		def save(doc):
			if doc.get("doctype"):
				created.append(doc)
				keys.add(doc.generation_key)
			return doc

		recurring.save = save
		recurring.generate()
		recurring.generate()
		self.assertEqual(len(created), 1)
		self.assertEqual(created[0].doctype, "Rent Operating Bill")
		self.assertEqual(created[0].status, "Due")
		self.assertEqual(schedule.next_due, date(2026, 12, 1))

	def test_paused_and_ended_schedules_do_not_generate(self):
		recurring = self.load("recurring")
		self.f.get_all.return_value = ["S"]
		recurring.save = Mock()
		for values in [dict(active=0), dict(active=1, next_due="2026-11-01", end_date="2026-10-31")]:
			recurring.locked = Mock(return_value=Row(values))
			recurring.generate()
		self.f.get_doc.assert_not_called()

	def test_housekeeping_requires_all_checks_and_photo(self):
		module = self.load("housekeeping")
		row = Row(
			property="A",
			status="Open",
			checklist='[{"label":"Clean","done":false}]',
			require_photo=1,
			photo=None,
			due_date="2026-11-01",
		)
		module.locked = Mock(return_value=row)
		with self.assertRaises(Invalid):
			module.update_task("T", "complete", [])
		with self.assertRaises(Invalid):
			module.update_task("T", "complete", [0])

	def test_erp_disabled_cannot_queue(self):
		module = self.load("erp_sync")
		self.f.get_single = Mock(return_value=Row(enabled=0))
		with self.assertRaises(Invalid):
			module.queue("Property Expense", "E")
		self.f.get_doc.assert_not_called()

	def test_erp_rejects_private_targets_and_redirect_shapes(self):
		module = self.load("erp_sync")
		for url in [
			"http://example.com",
			"https://user:pass@example.com",
			"https://example.com/path",
			"https://example.com:8443",
		]:
			with self.assertRaises(ValueError):
				module.validate_url(url, resolve=False)
		with patch.object(module.socket, "getaddrinfo", return_value=[(0, 0, 0, "", ("127.0.0.1", 443))]):
			with self.assertRaises(ValueError):
				module.validate_url("https://erp.example.com")

	def test_erp_stale_source_never_posts(self):
		module = self.load("erp_sync")
		self.f.get_single = Mock(return_value=Row(enabled=1))
		row = Row(
			status="Queued",
			attempts=0,
			requested_by="manager",
			source_doctype="Property Expense",
			source_name="E",
			source_modified="old",
		)
		module.locked = Mock(return_value=row)
		module.source_doc = Mock(return_value=Row(modified="new"))
		module.save = Mock()
		module.remote = Mock()
		module.process("S")
		self.assertEqual(row.status, "Failed")
		module.remote.assert_not_called()

	def test_erp_retry_reconciles_lost_response_without_duplicate_post(self):
		module = self.load("erp_sync")
		self.f.get_single = Mock(return_value=Row(enabled=1))
		row = Row(
			status="Failed",
			attempts=1,
			requested_by="manager",
			source_doctype="Tenant Rent Invoice",
			source_name="I",
			source_modified="same",
			sync_key="key",
		)
		module.locked = Mock(return_value=row)
		module.source_doc = Mock(return_value=Row(doctype="Tenant Rent Invoice", modified="same"))
		module.find_remote = Mock(return_value={"name": "REMOTE-I", "docstatus": 0})
		module.remote = Mock()
		module.save = Mock()
		module.process("S")
		self.assertEqual(row.status, "Synced")
		self.assertEqual(row.remote_name, "REMOTE-I")
		module.remote.assert_not_called()
		module.find_remote.assert_called_once_with(self.f.get_single.return_value, "Sales Invoice", "key")

	def test_health_surfaces_partial_failures_and_resets_counter(self):
		from contextlib import nullcontext

		module = self.load("health")
		self.f.cache = SimpleNamespace(lock=lambda *args, **kwargs: nullcontext())
		self.subscription.skip_if_lapsed = Mock(return_value=False)
		self.f.get_doc.side_effect = lambda value: Row(value)
		self.f.get_attr = Mock(return_value=self.common.note_failure)
		records = []

		def save(doc):
			records.append(doc)
			return doc

		module.save = save
		module.run("monthly-invoices")
		self.assertEqual(records[-1].status, "Partial Failure")
		self.assertIn("1 items failed", records[-1].summary)
		self.assertIsNone(self.f.local.rent_suite_failures)
		self.assertEqual(self.f.db.commit.call_count, 2)


if __name__ == "__main__":
	unittest.main()

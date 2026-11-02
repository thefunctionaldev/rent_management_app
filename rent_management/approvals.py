"""Staged financial operations. No ledger mutation until a second person approves.

Only known API operations are executable. Request rows are immutable outside this
service. Document hooks also block Desk/REST paths while a configured rule applies.
"""

import hashlib
import math

import frappe
from frappe import _
from frappe.utils import flt, now_datetime

from rent_management import access, subscription

REQUEST = "Rent Approval Request"
SETTINGS = "Rent Approval Settings"
METHODS = {
	"pay_work_order": "Expense",
	"pay_operating_bill": "Expense",
	"save_expense": "Expense",
	"delete_expense": "Expense",
	"pay_salary": "Expense",
	"undo_salary_payment": "Expense",
	"give_advance": "Expense",
	"delete_advance": "Expense",
	"settle_deposit": "Deposit refund",
	"create_invoice": "Invoice discount",
	"reverse_payment": "Payment reversal",
}


def matching_rule(rules, roles, action, amount):
	"""The strictest matching role wins. Limits are inclusive, zero means every amount."""
	matches = [
		r for r in rules if r.action == action and r.requester_role in roles and amount >= flt(r.threshold)
	]
	return (
		min(matches, key=lambda r: (flt(r.threshold), r.approver_role != "System Manager"))
		if matches
		else None
	)


def rule_for(action, amount):
	settings = frappe.get_single(SETTINGS)
	if not settings.enabled:
		return None
	return matching_rule(settings.rules, frappe.get_roles(), action, amount)


def write_request(doc):
	previous = getattr(frappe.local, "writing_rent_approval", False)
	try:
		frappe.local.writing_rent_approval = True
		if doc.status != "Pending":
			doc.pending_key = None
		doc.save(ignore_permissions=True)
	finally:
		frappe.local.writing_rent_approval = previous


def stage(method, payload, amount, property=None, target=None):
	"""Called after API access checks, before the operation's first write."""
	if getattr(frappe.local, "rent_approval_execution", None):
		return None
	action = METHODS[method]
	amount = flt(amount)
	if not math.isfinite(amount) or amount < 0:
		frappe.throw(_("Enter a valid non-negative amount."))
	rule = rule_for(action, amount)
	if not rule:
		return None
	subscription.check_writable(frappe._dict(doctype=REQUEST))
	if target:
		target.check_permission("read")
	staff = access.staff_access()
	if staff and staff.building and property != staff.building:
		frappe.throw(_("This building is outside your access."), frappe.PermissionError)
	payload_json = frappe.as_json(payload)
	pending_key = hashlib.sha256(f"{frappe.session.user}:{method}:{payload_json}".encode()).hexdigest()
	# A repeated click reuses the pending intent. Execution itself is locked below.
	existing = frappe.get_all(
		REQUEST,
		filters={"requested_by": frappe.session.user, "status": "Pending", "method": method},
		fields=["name", "payload"],
	)
	for row in existing:
		if row.payload == payload_json:
			return {"approval_pending": True, "request": row.name}
	doc = frappe.get_doc(
		{
			"doctype": REQUEST,
			"status": "Pending",
			"action": action,
			"method": method,
			"payload": payload_json,
			"pending_key": pending_key,
			"amount": amount,
			"property": property,
			"requested_by": frappe.session.user,
			"approver_role": rule.approver_role,
			"target_doctype": target.doctype if target else None,
			"target_name": target.name if target else None,
			"target_modified": target.modified if target else None,
		}
	)
	write_request(doc)
	return {"approval_pending": True, "request": doc.name}


def guard(doc, event=None):
	"""No blanket flag from the browser can grant approval: context is server-local."""
	action, amount = None, 0
	before = doc.get_doc_before_save()
	if doc.doctype == "Property Expense":
		if (
			event == "on_trash"
			or doc.is_new()
			or not before
			or any(
				doc.get(k) != before.get(k)
				for k in (
					"amount",
					"property",
					"paid_to",
					"mode_of_payment",
					"expense_date",
					"reference_no",
					"description",
					"category",
				)
			)
		):
			action, amount = "Expense", max(flt(doc.amount), flt(before.amount) if before else 0)
	elif doc.doctype == "Security Deposit Settlement":
		action, amount = "Deposit refund", flt(doc.refund_amount)
	elif doc.doctype == "Tenant Rent Invoice":
		if flt(doc.discount_amount) > 0 and (
			doc.is_new() or not before or flt(before.discount_amount) != flt(doc.discount_amount)
		):
			action, amount = "Invoice discount", flt(doc.discount_amount)
	elif doc.doctype == "Rent Payment":
		action, amount = "Payment reversal", flt(doc.amount)
	if not action:
		return
	context = getattr(frappe.local, "rent_approval_execution", None)
	if context and context.action == action:
		if amount != flt(context.amount):
			frappe.throw(_("The financial amount changed. Submit a new approval request."))
		return
	if not rule_for(action, amount):
		return
	frappe.throw(
		_("Approval required. Use the Rent app to request this change; direct changes are blocked."),
		frappe.PermissionError,
	)


def decide(name, decision, note=None):
	if not access.is_manager():
		frappe.throw(_("Only managers can review approvals."), frappe.PermissionError)
	if decision not in ("approve", "reject"):
		frappe.throw(_("Choose approve or reject."))
	# Row lock prevents two reviewers executing the same financial operation.
	frappe.db.sql("select name from `tabRent Approval Request` where name=%s for update", name)
	doc = frappe.get_doc(REQUEST, name)
	if doc.status != "Pending":
		frappe.throw(_("This request has already been decided."))
	actor = frappe.session.user
	if doc.requested_by == actor:
		frappe.throw(_("Someone else must review your request."), frappe.PermissionError)
	if doc.approver_role not in frappe.get_roles():
		frappe.throw(_("You do not have the required approver role."), frappe.PermissionError)
	subscription.check_writable(doc)
	if decision == "reject":
		if not (note or "").strip():
			frappe.throw(_("Enter a reason for rejecting the request."))
		doc.status = "Rejected"
	else:
		if not frappe.db.get_value("User", doc.requested_by, "enabled"):
			frappe.throw(_("The requester no longer has an active account."))
		if doc.target_name:
			frappe.db.sql(
				f"select name from `tab{doc.target_doctype}` where name=%s for update", doc.target_name
			)
			modified = frappe.db.get_value(doc.target_doctype, doc.target_name, "modified")
			if str(modified) != str(doc.target_modified):
				frappe.throw(_("The source record changed. Withdraw this request and submit a fresh one."))
		from rent_management import api

		if doc.method not in METHODS:
			frappe.throw(_("Unsupported approval operation."))
		try:
			frappe.local.rent_approval_execution = doc
			frappe.set_user(doc.requested_by)
			# Re-check the requester's current permissions, and all normal validations.
			result = getattr(api, doc.method)(**frappe.parse_json(doc.payload))
			doc.result = str(result or "Completed")
		finally:
			frappe.set_user(actor)
			frappe.local.rent_approval_execution = None
		doc.status = "Executed"
	doc.decided_by, doc.decided_on, doc.decision_note = actor, now_datetime(), note
	write_request(doc)
	return doc.name

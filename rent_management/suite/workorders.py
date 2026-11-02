import frappe
from frappe import _
from frappe.utils import flt, getdate, now_datetime, nowdate

from rent_management import access, approvals, portal
from rent_management.suite.common import (
	area,
	locked,
	manager,
	own_fields,
	positive,
	save,
	scoped,
	validate_assignee,
	validate_property,
)
from rent_management.suite.dates import can_transition

DT = "Rent Work Order"


@frappe.whitelist()
def list_orders(property=None):
	filters = scoped("requests", property)
	return frappe.get_all(DT, filters=filters, fields=["*"], order_by="due_date asc", limit_page_length=500)


@frappe.whitelist()
def vendors():
	area("requests")
	return frappe.get_all(
		"Rent Vendor",
		fields=["name", "vendor_name", "phone", "email", "speciality", "is_active"],
		order_by="vendor_name",
	)


@frappe.whitelist(methods=["POST"])
def save_vendor(data):
	manager()
	data = frappe.parse_json(data)
	doc = frappe.get_doc("Rent Vendor", data["name"]) if data.get("name") else frappe.new_doc("Rent Vendor")
	doc.update(own_fields(data, ("vendor_name", "phone", "email", "speciality", "is_active")))
	return save(doc).name


@frappe.whitelist(methods=["POST"])
def save_order(data):
	manager()
	data = frappe.parse_json(data)
	doc = locked(DT, data["name"]) if data.get("name") else frappe.new_doc(DT)
	if not doc.is_new() and doc.status != "Draft":
		frappe.throw(_("Only draft work orders can be edited. Reject the quote to request changes."))
	doc.update(
		own_fields(
			data,
			(
				"subject",
				"property",
				"room",
				"request",
				"vendor",
				"assigned_to",
				"due_date",
				"description",
				"quote_amount",
				"quote_note",
			),
		)
	)
	validate_property(doc.property, doc.room)
	validate_assignee(doc.assigned_to, doc.property, "requests")
	doc.quote_amount = positive(doc.quote_amount, allow_zero=True)
	if doc.vendor and not frappe.db.get_value("Rent Vendor", doc.vendor, "is_active"):
		frappe.throw(_("Choose an active vendor."))
	if doc.request:
		request = frappe.get_doc("Maintenance Request", doc.request)
		if request.property != doc.property or (doc.room and request.room != doc.room):
			frappe.throw(_("The maintenance request must belong to this building and room."))
		doc.tenant = request.tenant
	else:
		doc.tenant = None
	doc.status, doc.requested_by = "Draft", frappe.session.user
	return save(doc).name


@frappe.whitelist(methods=["POST"])
def transition(name, action, note=None, actual_cost=None):
	doc = locked(DT, name)
	# Owner review has its own property-scoped path. Staff can only execute assigned work.
	area("requests", doc.property)
	if not can_transition(doc.status, action):
		frappe.throw(_("This action is not available in the current status."))
	if action in ("request", "approve", "reject", "cancel"):
		manager()
	elif action in ("start", "complete"):
		if not access.is_manager() and doc.assigned_to != frappe.session.user:
			frappe.throw(_("Only the assigned staff member can update this work."), frappe.PermissionError)
	else:
		frappe.throw(_("Use the tenant confirmation action."))
	if action == "approve":
		return approve(doc, note)
	if action == "reject":
		if not (note or "").strip():
			frappe.throw(_("Enter the reason for rejecting the quote."))
		doc.status, doc.quote_note = "Draft", note
	elif action == "request":
		doc.requested_by, doc.status = frappe.session.user, "Pending Approval"
	elif action == "start":
		doc.status = "In Progress"
	elif action == "complete":
		doc.actual_cost = positive(actual_cost, allow_zero=True)
		if doc.actual_cost > flt(doc.quote_amount):
			frappe.throw(
				_("Actual cost cannot exceed the approved quote. Create a separate order for extra work.")
			)
		if not doc.after_photo or not (note or "").strip():
			frappe.throw(_("Add completion notes and an after photo before completing."))
		doc.status, doc.completion_note = "Completed", note
		doc.completed_on, doc.completed_by = now_datetime(), frappe.session.user
	elif action == "cancel":
		doc.status = "Cancelled"
	return save(doc).name


def approve(doc, note=None):
	if doc.status != "Pending Approval" or doc.requested_by == frappe.session.user:
		frappe.throw(_("A different reviewer must approve a pending quote."), frappe.PermissionError)
	doc.status, doc.approved_by, doc.approved_on = "Approved", frappe.session.user, now_datetime()
	if note:
		doc.quote_note = note
	return save(doc).name


@frappe.whitelist()
def tenant_orders():
	tenant = portal.current_tenant()
	return frappe.get_all(
		DT,
		filters={"tenant": tenant.name, "status": ["in", ["Completed", "Confirmed"]]},
		fields=["name", "subject", "completion_note", "completed_on", "status", "after_photo"],
		order_by="modified desc",
	)


@frappe.whitelist(methods=["POST"])
def confirm(name):
	tenant = portal.current_tenant()
	doc = locked(DT, name)
	if str(doc.tenant) != str(tenant.name) or doc.status != "Completed":
		frappe.throw(_("Only the tenant on this completed request can confirm it."), frappe.PermissionError)
	doc.status, doc.confirmed_by, doc.confirmed_on = "Confirmed", frappe.session.user, now_datetime()
	return save(doc).name


def pay(name, mode_of_payment="Bank Transfer", reference_no=None):
	manager()
	doc = locked(DT, name)
	if doc.status not in ("Completed", "Confirmed") or doc.expense:
		frappe.throw(_("Only completed, unpaid work can be recorded as paid."))
	amount = positive(doc.actual_cost)
	pending = approvals.stage(
		"pay_work_order",
		{"name": name, "mode_of_payment": mode_of_payment, "reference_no": reference_no},
		amount,
		doc.property,
		doc,
	)
	if pending:
		return pending
	from rent_management import api

	expense = api.save_expense(
		{
			"property": doc.property,
			"amount": amount,
			"category": "Repairs & Maintenance",
			"expense_date": nowdate(),
			"mode_of_payment": mode_of_payment,
			"reference_no": reference_no,
			"paid_to": frappe.db.get_value("Rent Vendor", doc.vendor, "vendor_name")
			if doc.vendor
			else doc.assigned_to,
			"description": f"Work order {doc.name}: {doc.subject}",
		}
	)
	# Expense categories differ between installations; the caller validates below through the normal DocType.
	doc.expense = expense
	save(doc)
	return expense

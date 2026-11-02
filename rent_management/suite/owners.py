import hashlib

import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate

from rent_management.suite.common import locked, manager, save, validate_property

GRANT = "Rent Owner Access"


def properties():
	if frappe.session.user == "Guest":
		frappe.throw(_("Sign in to view your properties."), frappe.PermissionError)
	return frappe.get_all(GRANT, filters={"user": frappe.session.user, "active": 1}, pluck="property")


def check(property):
	if property not in properties():
		frappe.throw(_("This property is not assigned to your owner login."), frappe.PermissionError)


@frappe.whitelist()
def dashboard(property=None, from_date=None, to_date=None):
	allowed = properties()
	if property:
		check(property)
		allowed = [property]
	start, end = getdate(from_date or nowdate()[:7] + "-01"), getdate(to_date or nowdate())
	if end < start or (end - start).days > 366:
		frappe.throw(_("Choose a reporting period of up to one year."))
	rows = []
	for prop in allowed:
		rooms = frappe.get_all(
			"Tenant Space", filters={"property": prop}, fields=["capacity", "occupied_beds"]
		)
		collected = sum(
			flt(x.amount)
			for x in frappe.get_all(
				"Rent Payment",
				filters={
					"property": prop,
					"docstatus": 1,
					"payment_date": ["between", [start, end]],
					"mode_of_payment": ["!=", "Security Deposit"],
				},
				fields=["amount"],
			)
		)
		expenses = sum(
			flt(x.amount)
			for x in frappe.get_all(
				"Property Expense",
				filters={"property": prop, "expense_date": ["between", [start, end]]},
				fields=["amount"],
			)
		)
		outstanding = sum(
			flt(x.outstanding_amount)
			for x in frappe.get_all(
				"Tenant Rent Invoice",
				filters={"property": prop, "docstatus": 1},
				fields=["outstanding_amount"],
			)
		)
		rows.append(
			{
				"property": prop,
				"beds": sum(max(int(x.capacity or 1), 1) for x in rooms),
				"occupied": sum(int(x.occupied_beds or 0) for x in rooms),
				"collected": collected,
				"expenses": expenses,
				"net_cash": collected - expenses,
				"outstanding": outstanding,
			}
		)
	return {
		"properties": allowed,
		"currency": frappe.db.get_default("currency") or "INR",
		"summary": rows,
		"from_date": str(start),
		"to_date": str(end),
		"work_orders": frappe.get_all(
			"Rent Work Order",
			filters={"property": ["in", allowed]},
			fields=[
				"name",
				"subject",
				"property",
				"status",
				"quote_amount",
				"actual_cost",
				"due_date",
				"quote_note",
				"completion_note",
				"requested_by",
			],
			order_by="creation desc",
			limit_page_length=100,
		)
		if allowed
		else [],
		"documents": frappe.get_all(
			"Rent Owner Document",
			filters={"property": ["in", allowed]},
			fields=["name", "property", "title", "description", "file"],
			order_by="creation desc",
		)
		if allowed
		else [],
	}


@frappe.whitelist(methods=["POST"])
def review_quote(name, approve, note=None):
	from rent_management.suite.workorders import approve as approve_order

	doc = locked("Rent Work Order", name)
	check(doc.property)
	if doc.status != "Pending Approval" or doc.requested_by == frappe.session.user:
		frappe.throw(_("A different owner must review a pending quote."), frappe.PermissionError)
	if int(approve):
		return approve_order(doc, note)
	if not (note or "").strip():
		frappe.throw(_("Enter the reason for rejecting the quote."))
	doc.status, doc.quote_note = "Draft", note
	return save(doc).name


@frappe.whitelist()
def grants():
	manager()
	return frappe.get_all(GRANT, fields=["name", "user", "property", "active"], order_by="user, property")


@frappe.whitelist(methods=["POST"])
def grant(user, property, active=1):
	manager()
	validate_property(property)
	if not frappe.db.get_value("User", user, "enabled") or user in ("Guest", "Administrator"):
		frappe.throw(_("Create an enabled User account first, then assign its email here."))
	key = hashlib.sha256(f"{user}:{property}".encode()).hexdigest()
	name = frappe.db.get_value(GRANT, {"access_key": key}, "name")
	doc = (
		locked(GRANT, name)
		if name
		else frappe.get_doc({"doctype": GRANT, "user": user, "property": property, "access_key": key})
	)
	doc.active = int(bool(int(active)))
	return save(doc).name


@frappe.whitelist(methods=["POST"])
def add_document(property, title, description=None):
	manager()
	validate_property(property)
	return save(
		frappe.get_doc(
			{
				"doctype": "Rent Owner Document",
				"property": property,
				"title": title,
				"description": description,
			}
		)
	).name

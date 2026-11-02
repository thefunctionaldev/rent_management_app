import json

import frappe
from frappe import _
from frappe.utils import getdate, now_datetime, nowdate

from rent_management import access
from rent_management.suite.common import (
	area,
	locked,
	manager,
	own_fields,
	save,
	scoped,
	validate_assignee,
	validate_property,
)
from rent_management.suite.dates import next_occurrence

SCHEDULE = "Rent Housekeeping Schedule"
TASK = "Rent Housekeeping Task"


@frappe.whitelist()
def overview(property=None):
	filters = scoped("housekeeping", property)
	if not access.is_manager():
		filters["assigned_to"] = frappe.session.user
	return {
		"tasks": frappe.get_all(
			TASK, filters=filters, fields=["*"], order_by="due_date desc", limit_page_length=500
		),
		"schedules": frappe.get_all(SCHEDULE, filters=filters, fields=["*"], order_by="title")
		if access.is_manager()
		else [],
	}


@frappe.whitelist(methods=["POST"])
def save_schedule(data):
	manager()
	data = frappe.parse_json(data)
	doc = locked(SCHEDULE, data["name"]) if data.get("name") else frappe.new_doc(SCHEDULE)
	old_start = doc.start_date
	doc.update(
		own_fields(
			data,
			(
				"title",
				"property",
				"room",
				"assigned_to",
				"frequency",
				"start_date",
				"active",
				"require_photo",
				"checklist",
			),
		)
	)
	validate_property(doc.property, doc.room)
	validate_assignee(doc.assigned_to, doc.property, "housekeeping")
	items = [line.strip() for line in (doc.checklist or "").splitlines() if line.strip()]
	if not items or len(items) > 30:
		frappe.throw(_("Enter 1 to 30 checklist items, one per line."))
	doc.checklist = "\n".join(items)
	if not doc.is_new() and str(old_start) != str(doc.start_date):
		frappe.throw(_("Create a new schedule to change the start date."))
	if doc.is_new():
		doc.next_due = doc.start_date
	return save(doc).name


def generate():
	for name in frappe.get_all(SCHEDULE, filters={"active": 1, "next_due": ["<=", nowdate()]}, pluck="name"):
		doc = locked(SCHEDULE, name)
		if not doc.active:
			continue
		for _index in range(31):
			day = getdate(doc.next_due)
			if day > getdate(nowdate()):
				break
			key = f"{doc.name}:{day}"
			if not frappe.db.exists(TASK, {"generation_key": key}):
				save(
					frappe.get_doc(
						{
							"doctype": TASK,
							"title": doc.title,
							"property": doc.property,
							"room": doc.room,
							"schedule": doc.name,
							"assigned_to": doc.assigned_to,
							"due_date": day,
							"generation_key": key,
							"status": "Open",
							"require_photo": doc.require_photo,
							"checklist": json.dumps(
								[{"label": line, "done": False} for line in doc.checklist.splitlines()]
							),
						}
					)
				)
			doc.next_due = next_occurrence(day, doc.frequency, doc.start_date)
		save(doc)


@frappe.whitelist(methods=["POST"])
def generate_now():
	manager()
	generate()


@frappe.whitelist(methods=["POST"])
def update_task(name, action, checked=None, notes=None):
	doc = locked(TASK, name)
	area("housekeeping", doc.property)
	if not access.is_manager() and doc.assigned_to != frappe.session.user:
		frappe.throw(_("This task is assigned to someone else."), frappe.PermissionError)
	if action == "complete" and doc.status == "Open":
		items = json.loads(doc.checklist)
		selected = frappe.parse_json(checked) or []
		if selected != list(range(len(items))):
			frappe.throw(_("Complete every checklist item before finishing."))
		if doc.require_photo and not doc.photo:
			frappe.throw(_("Upload a completion photo first."))
		if getdate(doc.due_date) > getdate(nowdate()):
			frappe.throw(_("Future tasks cannot be completed yet."))
		doc.checklist = json.dumps([{**row, "done": True} for row in items])
		doc.status, doc.completed_by, doc.completed_on = "Completed", frappe.session.user, now_datetime()
	elif action in ("verify", "reopen") and doc.status in ("Completed", "Verified"):
		manager()
		doc.status = "Verified" if action == "verify" else "Open"
		doc.verified_by = frappe.session.user if action == "verify" else None
		if action == "reopen":
			doc.checklist = json.dumps([{**row, "done": False} for row in json.loads(doc.checklist)])
			doc.completed_by = doc.completed_on = None
			doc.photo = None
	else:
		frappe.throw(_("This task action is not available."))
	doc.notes = notes
	return save(doc).name

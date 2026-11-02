import frappe
from frappe import _
from frappe.utils import cint, getdate, nowdate

from rent_management import approvals
from rent_management.suite.common import (
	area,
	locked,
	manager,
	own_fields,
	positive,
	save,
	scoped,
	validate_property,
)
from rent_management.suite.dates import next_occurrence

SCHEDULE = "Rent Recurring Bill"
BILL = "Rent Operating Bill"


@frappe.whitelist()
def overview(property=None):
	filters = scoped("expenses", property)
	return {
		"schedules": frappe.get_all(SCHEDULE, filters=filters, fields=["*"], order_by="title"),
		"bills": frappe.get_all(
			BILL, filters=filters, fields=["*"], order_by="due_date desc", limit_page_length=500
		),
		"categories": frappe.get_meta("Property Expense").get_field("category").options.split("\n"),
		"vendors": frappe.get_all("Rent Vendor", filters={"is_active": 1}, fields=["name", "vendor_name"]),
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
				"vendor",
				"category",
				"amount",
				"frequency",
				"start_date",
				"end_date",
				"active",
				"notes",
			),
		)
	)
	validate_property(doc.property)
	doc.amount = positive(doc.amount)
	if doc.category not in frappe.get_meta("Property Expense").get_field("category").options.split("\n"):
		frappe.throw(_("Choose a valid expense category."))
	if doc.end_date and getdate(doc.end_date) < getdate(doc.start_date):
		frappe.throw(_("End date must follow the start date."))
	if not doc.is_new() and str(old_start) != str(doc.start_date):
		frappe.throw(_("Pause this schedule and create another to change its start date."))
	if doc.is_new():
		doc.next_due = doc.start_date
	return save(doc).name


def generate():
	for name in frappe.get_all(SCHEDULE, filters={"active": 1, "next_due": ["<=", nowdate()]}, pluck="name"):
		doc = locked(SCHEDULE, name)
		if not doc.active:
			continue
		for _index in range(24):
			day = getdate(doc.next_due)
			if day > getdate(nowdate()) or (doc.end_date and day > getdate(doc.end_date)):
				break
			key = f"{doc.name}:{day}"
			if not frappe.db.exists(BILL, {"generation_key": key}):
				save(
					frappe.get_doc(
						{
							"doctype": BILL,
							"title": doc.title,
							"property": doc.property,
							"schedule": doc.name,
							"vendor": doc.vendor,
							"category": doc.category,
							"amount": doc.amount,
							"due_date": day,
							"generation_key": key,
							"status": "Due",
							"notes": doc.notes,
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
def cancel_bill(name, reason):
	manager()
	doc = locked(BILL, name)
	if doc.status != "Due" or not (reason or "").strip():
		frappe.throw(_("Only an unpaid bill can be cancelled; enter a reason."))
	doc.status, doc.notes = "Cancelled", reason
	return save(doc).name


def pay(name, mode_of_payment="Bank Transfer", reference_no=None):
	manager()
	doc = locked(BILL, name)
	area("expenses", doc.property)
	if doc.status != "Due" or doc.expense:
		frappe.throw(_("This bill is no longer unpaid."))
	pending = approvals.stage(
		"pay_operating_bill",
		{"name": name, "mode_of_payment": mode_of_payment, "reference_no": reference_no},
		doc.amount,
		doc.property,
		doc,
	)
	if pending:
		return pending
	from rent_management import api

	expense = api.save_expense(
		{
			"property": doc.property,
			"amount": doc.amount,
			"category": doc.category or "Other",
			"expense_date": nowdate(),
			"mode_of_payment": mode_of_payment,
			"reference_no": reference_no,
			"paid_to": frappe.db.get_value("Rent Vendor", doc.vendor, "vendor_name") if doc.vendor else None,
			"description": f"Bill {doc.name}: {doc.title}",
		}
	)
	doc.expense, doc.paid_on, doc.status = expense, nowdate(), "Paid"
	save(doc)
	return expense

# Copyright (c) 2026, Shashank Dixit and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import date_diff, flt, getdate, nowdate

AGING_BUCKETS = (
	("not_due", _("Not Due"), None),
	("range_0_30", _("0-30 Days"), 30),
	("range_31_60", _("31-60 Days"), 60),
	("range_61_90", _("61-90 Days"), 90),
	("range_90_above", _("90+ Days"), float("inf")),
)


def execute(filters: dict | None = None):
	filters = frappe._dict(filters or {})
	as_on_date = getdate(filters.as_on_date or nowdate())

	data = get_data(filters, as_on_date)
	return get_columns(), data, None, get_chart(data), get_summary(data)


def get_columns() -> list[dict]:
	return [
		{
			"label": _("Rent Invoice"),
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "Tenant Rent Invoice",
			"width": 120,
		},
		{"label": _("Tenant"), "fieldname": "tenant", "fieldtype": "Link", "options": "Tenant", "width": 160},
		{
			"label": _("Room"),
			"fieldname": "room",
			"fieldtype": "Link",
			"options": "Tenant Space",
			"width": 80,
		},
		{"label": _("Billing Period"), "fieldname": "billing_period", "fieldtype": "Data", "width": 130},
		{"label": _("Due Date"), "fieldname": "due_date", "fieldtype": "Date", "width": 100},
		{"label": _("Days Overdue"), "fieldname": "days_overdue", "fieldtype": "Int", "width": 100},
		{"label": _("Grand Total"), "fieldname": "final_amount", "fieldtype": "Currency", "width": 120},
		{"label": _("Paid"), "fieldname": "paid_amount", "fieldtype": "Currency", "width": 120},
		{"label": _("Outstanding"), "fieldname": "outstanding_amount", "fieldtype": "Currency", "width": 120},
		*(
			{"label": label, "fieldname": fieldname, "fieldtype": "Currency", "width": 110}
			for fieldname, label, _limit in AGING_BUCKETS
		),
		{"label": _("Mobile No"), "fieldname": "mobile_no", "fieldtype": "Data", "width": 130},
	]


def get_data(filters, as_on_date) -> list[dict]:
	invoice_filters = {
		"docstatus": 1,
		"outstanding_amount": (">", 0),
		"posting_date": ("<=", as_on_date),
	}
	for field in ("tenant", "room", "property"):
		if filters.get(field):
			invoice_filters[field] = filters.get(field)
	if filters.overdue_only:
		invoice_filters["due_date"] = ("<", as_on_date)

	invoices = frappe.get_all(
		"Tenant Rent Invoice",
		filters=invoice_filters,
		fields=[
			"name",
			"tenant",
			"tenant_name",
			"room",
			"billing_month",
			"billing_year",
			"due_date",
			"final_amount",
			"paid_amount",
			"outstanding_amount",
		],
		order_by="due_date asc, name asc",
	)
	# Tenant is autoincrement-named, so compare names as strings
	mobile_nos = {
		str(name): mobile_no
		for name, mobile_no in frappe.get_all(
			"Tenant",
			filters={"name": ("in", list({row.tenant for row in invoices}) or [""])},
			fields=["name", "mobile_no"],
			as_list=True,
		)
	}

	for row in invoices:
		row.billing_period = f"{row.billing_month} {row.billing_year}"
		row.mobile_no = mobile_nos.get(str(row.tenant))
		row.days_overdue = max(date_diff(as_on_date, row.due_date), 0) if row.due_date else 0
		for fieldname, _label, _limit in AGING_BUCKETS:
			row[fieldname] = 0.0
		row[get_bucket(row)] = flt(row.outstanding_amount)

	return invoices


def get_bucket(row) -> str:
	if not row.days_overdue:
		return "not_due"
	return next(
		fieldname for fieldname, _label, limit in AGING_BUCKETS if limit and row.days_overdue <= limit
	)


def get_chart(data):
	if not data:
		return None
	return {
		"data": {
			"labels": [str(label) for _fieldname, label, _limit in AGING_BUCKETS],
			"datasets": [
				{
					"name": _("Outstanding"),
					"values": [
						sum(row[fieldname] for row in data) for fieldname, _label, _limit in AGING_BUCKETS
					],
				}
			],
		},
		"type": "bar",
		"fieldtype": "Currency",
	}


def get_summary(data):
	total = sum(flt(row.outstanding_amount) for row in data)
	overdue = sum(flt(row.outstanding_amount) for row in data if row.days_overdue)
	return [
		{"value": total, "label": _("Total Outstanding"), "datatype": "Currency", "indicator": "Blue"},
		{"value": overdue, "label": _("Overdue"), "datatype": "Currency", "indicator": "Red"},
		{
			"value": len({row.tenant for row in data}),
			"label": _("Tenants with Dues"),
			"datatype": "Int",
			"indicator": "Orange",
		},
	]

# Copyright (c) 2026, Shashank Dixit and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import get_last_day, getdate, nowdate

from rent_management.rent_management_system.doctype.tenant_rent_invoice.tenant_rent_invoice import MONTHS


def generate_monthly_invoices():
	"""Scheduler (monthly): create rent invoices for the current month."""
	from rent_management.subscription import skip_if_lapsed

	if skip_if_lapsed():
		return

	settings = frappe.get_single("Rent Management Settings")
	if not settings.auto_generate_invoices:
		return

	posting_date = getdate(nowdate())
	generate_invoices(
		MONTHS[posting_date.month - 1],
		posting_date.year,
		submit=settings.auto_submit_invoices,
	)


def generate_invoices(billing_month: str, billing_year: int, submit: bool = False) -> list[str]:
	"""Create a rent invoice for every allotment that was occupied during the given month.

	Allotments that already have an invoice for that month are skipped.
	Returns the names of the invoices created.
	"""
	billing_year = int(billing_year)
	month_start = getdate(f"{billing_year}-{MONTHS.index(billing_month) + 1:02d}-01")
	month_end = get_last_day(month_start)

	allotments = frappe.get_all(
		"Tenant Space Allotment",
		filters={
			"docstatus": 1,
			"status": ("in", ("Active", "Vacated")),
			"allotment_date": ("<=", month_end),
		},
		or_filters=[["vacate_date", "is", "not set"], ["vacate_date", ">=", month_start]],
		pluck="name",
	)
	already_billed = set(
		frappe.get_all(
			"Tenant Rent Invoice",
			filters={
				"tenant_space_allotment": ("in", allotments or [""]),
				"billing_month": billing_month,
				"billing_year": billing_year,
				"docstatus": ("<", 2),
			},
			pluck="tenant_space_allotment",
		)
	)

	created = []
	for allotment in allotments:
		if allotment in already_billed:
			continue
		frappe.db.savepoint("rent_invoice")
		try:
			invoice = frappe.get_doc(
				{
					"doctype": "Tenant Rent Invoice",
					"tenant_space_allotment": allotment,
					"billing_month": billing_month,
					"billing_year": billing_year,
					"posting_date": max(month_start, getdate(nowdate())),
				}
			)
			invoice.insert()
			if submit:
				invoice.submit()
			created.append(invoice.name)
		except Exception:
			# skip just this allotment, keep the invoices already created
			frappe.db.rollback(save_point="rent_invoice")
			frappe.log_error(title=_("Rent Invoice generation failed for {0}").format(allotment))

	return created


def mark_overdue_invoices():
	"""Scheduler (daily): flag unpaid invoices whose due date has passed."""
	invoices = frappe.get_all(
		"Tenant Rent Invoice",
		filters={
			"docstatus": 1,
			"status": ("in", ("Unpaid", "Partly Paid")),
			"outstanding_amount": (">", 0),
			"due_date": ("<", nowdate()),
		},
		pluck="name",
	)
	for name in invoices:
		frappe.db.set_value("Tenant Rent Invoice", name, "status", "Overdue", update_modified=False)

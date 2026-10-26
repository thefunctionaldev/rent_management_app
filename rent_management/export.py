# Copyright (c) 2026, Shashank Dixit and contributors
# For license information, please see license.txt

"""Everything a landlord has entered, as one Excel workbook (Settings > Download all data).

Aadhaar numbers are left out (only the last 4 digits are exported): the workbook is meant to
be opened on any laptop, and the full numbers stay encrypted on the server.
"""

from io import BytesIO

import frappe
import xlsxwriter
from frappe.utils.xlsxutils import make_xlsx

SHEETS = (
	("Buildings", "Rent Property", ["name", "abbr", "address", "city", "state", "pincode", "is_active"], {}),
	(
		"Rooms",
		"Tenant Space",
		[
			"name",
			"property",
			"room_number",
			"floor",
			"room_type",
			"capacity",
			"occupied_beds",
			"status",
			"room_rent",
			"has_meter",
			"electricity_rate",
		],
		{},
	),
	(
		"Room Types",
		"Tenant Space Type",
		[
			"name",
			"description",
			"standard_rent",
			"deposit_applicable",
			"security_deposit",
			"is_furnished",
			"has_attached_bathroom",
		],
		{},
	),
	(
		"Tenants",
		"Tenant",
		[
			"name",
			"first_name",
			"middle_name",
			"last_name",
			"status",
			"mobile_no",
			"email_id",
			"gender",
			"aadhar_last4",
			"occupation",
			"workspace",
			"salary",
			"permanent_address",
		],
		{},
	),
	(
		"Stays",
		"Tenant Space Allotment",
		[
			"name",
			"tenant",
			"tenant_name",
			"property",
			"room",
			"bed_no",
			"status",
			"allotment_date",
			"vacate_date",
			"rent_amount",
			"security_deposit",
			"deposit_collected",
			"deposit_collected_on",
			"agreement_months",
			"agreement_end_date",
			"lock_in_months",
			"notice_period_days",
			"rent_increase_percent",
			"notice_given_on",
			"expected_vacate_date",
		],
		{"docstatus": 1},
	),
	(
		"Rent Invoices",
		"Tenant Rent Invoice",
		[
			"name",
			"tenant",
			"tenant_name",
			"property",
			"room",
			"billing_month",
			"billing_year",
			"posting_date",
			"due_date",
			"monthly_rent",
			"pro_rated_rent",
			"total_charges",
			"discount_amount",
			"final_amount",
			"paid_amount",
			"outstanding_amount",
			"status",
		],
		{"docstatus": 1},
	),
	(
		"Payments",
		"Rent Payment",
		[
			"name",
			"tenant",
			"tenant_name",
			"property",
			"rent_invoice",
			"payment_date",
			"mode_of_payment",
			"amount",
			"reference_no",
			"remarks",
		],
		{"docstatus": 1},
	),
	(
		"Deposit Settlements",
		"Security Deposit Settlement",
		[
			"name",
			"tenant",
			"tenant_name",
			"property",
			"room",
			"settlement_date",
			"security_deposit",
			"total_deductions",
			"rent_adjusted",
			"refund_amount",
			"balance_payable_by_tenant",
			"mode_of_refund",
		],
		{"docstatus": 1},
	),
	(
		"Meter Readings",
		"Meter Reading",
		[
			"name",
			"room",
			"property",
			"reading_date",
			"previous_reading",
			"reading",
			"units",
			"rate",
			"amount",
			"status",
		],
		{},
	),
	(
		"Expenses",
		"Property Expense",
		[
			"name",
			"property",
			"expense_date",
			"category",
			"amount",
			"paid_to",
			"mode_of_payment",
			"reference_no",
			"description",
		],
		{},
	),
	(
		"Requests",
		"Maintenance Request",
		[
			"name",
			"creation",
			"tenant",
			"tenant_name",
			"room",
			"property",
			"category",
			"subject",
			"priority",
			"status",
			"description",
			"resolution",
			"resolved_on",
		],
		{},
	),
)


def get_workbook() -> bytes:
	output = BytesIO()
	workbook = xlsxwriter.Workbook(output, {"in_memory": True})
	for title, doctype, fields, filters in SHEETS:
		rows = frappe.get_all(doctype, filters=filters, fields=fields, as_list=True, order_by="creation asc")
		header = [
			frappe.get_meta(doctype).get_label(f)
			if f not in ("name", "creation")
			else ("ID" if f == "name" else "Created")
			for f in fields
		]
		make_xlsx([header, *[list(row) for row in rows]], title, wb=workbook)
	workbook.close()
	return output.getvalue()

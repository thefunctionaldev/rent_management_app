# Copyright (c) 2026, Shashank Dixit and contributors
# For license information, please see license.txt

"""Catching a payment recorded twice, before it counts twice.

- The same UTR or reference number as another payment: refused everywhere (manual entry, the
  tenant's "I've paid", bank statements, online payments), unless a manager confirms it
  really is a second payment.
- The same tenant and amount within 2 days, which is how cash gets entered twice: a manager
  recording it by hand is asked to confirm.
"""

import frappe
from frappe import _
from frappe.utils import add_days, cstr, flt, fmt_money, formatdate, getdate

PAYMENT = "Rent Payment"
NEAR_DAYS = 2


class DuplicatePaymentError(frappe.ValidationError):
	"""The app asks "record it anyway?" and sends allow_duplicate=1."""


def same_reference(reference_no, exclude=None) -> frappe._dict | None:
	ref = cstr(reference_no).strip()
	if len(ref) < 4:
		return None  # "cash", "-", "1": not a reference
	variants = {ref, ref.lstrip("0")} - {""}
	rows = frappe.get_all(
		PAYMENT,
		filters={
			"reference_no": ("in", list(variants)),
			"docstatus": ("<", 2),
			"name": ("!=", exclude or ""),
		},
		fields=["name", "tenant_name", "amount", "payment_date", "docstatus"],
		limit=1,
	)
	return rows[0] if rows else None


def near(tenant, amount, payment_date, exclude=None) -> frappe._dict | None:
	day = getdate(payment_date)
	rows = frappe.get_all(
		PAYMENT,
		filters={
			"tenant": tenant,
			"docstatus": ("<", 2),
			"amount": flt(amount, 2),
			"payment_date": ("between", (add_days(day, -NEAR_DAYS), add_days(day, NEAR_DAYS))),
			"name": ("!=", exclude or ""),
			"mode_of_payment": ("!=", "Security Deposit"),
		},
		fields=["name", "tenant_name", "amount", "payment_date", "mode_of_payment", "docstatus"],
		limit=1,
	)
	return rows[0] if rows else None


def describe(row) -> str:
	return _("{0} from {1} on {2} ({3}{4})").format(
		fmt_money(row.amount, currency="INR"),
		row.tenant_name,
		formatdate(row.payment_date),
		row.name,
		_(", waiting to be confirmed") if row.docstatus == 0 else "",
	)


def check(doc, method=None):
	"""Rent Payment validate: the same reference number twice."""
	if doc.flags.allow_duplicate or doc.mode_of_payment == "Security Deposit":
		return
	row = same_reference(doc.reference_no, exclude=doc.name)
	if row:
		frappe.throw(
			_("Reference {0} is already on a payment: {1}.").format(
				frappe.bold(doc.reference_no), describe(row)
			),
			DuplicatePaymentError,
			title=_("Recorded already?"),
		)


def check_near(tenant, amount, payment_date):
	"""Recording by hand: the same tenant and amount a day or two apart."""
	row = near(tenant, amount, payment_date)
	if row:
		frappe.throw(
			_("A payment of the same amount was recorded {0} days around this one: {1}.").format(
				NEAR_DAYS, describe(row)
			),
			DuplicatePaymentError,
			title=_("Recorded already?"),
		)

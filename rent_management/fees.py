# Copyright (c) 2026, Shashank Dixit and contributors
# For license information, please see license.txt

"""Late fees, a discount for paying early, and paying an invoice in instalments.

- Late fee: once an invoice is unpaid a few days (the grace days) after it was due, a daily
  job adds a late fee: a flat amount once, or an amount for every day late (up to a maximum).
  It only grows while the invoice is unpaid, and a manager can waive it.
- Early payment discount: offered on each invoice when it's made (an amount, or a percent of
  the rent). Paying the rest in full by the date takes it off.
- Instalments: a manager can split an invoice into parts with their own due dates. Payments go
  to them in order; the next unpaid one sets when the invoice is overdue, the reminders and
  the late fee. Split invoices get no early payment discount.

The invoice keeps its amounts so everything else works unchanged: final_amount = rent +
charges - discount + late fee - early payment discount, and outstanding = final - paid.
"""

import frappe
import frappe.model.document
from frappe import _
from frappe.utils import add_days, cint, date_diff, flt, getdate, nowdate

INVOICE = "Tenant Rent Invoice"
SETTINGS = "Rent Management Settings"


def base_amount(invoice) -> float:
	return flt(flt(invoice.pro_rated_rent) + flt(invoice.total_charges) - flt(invoice.discount_amount), 2)


# ---------------------------------------------------------------- early payment discount


def set_offer(invoice):
	"""While the invoice is a draft: the discount for paying early, from the settings."""
	settings = frappe.get_cached_doc(SETTINGS)
	invoice.early_discount_offer, invoice.early_discount_until = 0, None
	if (
		not cint(settings.early_discount_enabled)
		or not flt(settings.early_discount_value)
		or not invoice.due_date
	):
		return
	if settings.early_discount_type == "Percent of Rent":
		offer = flt(invoice.pro_rated_rent) * flt(settings.early_discount_value) / 100
	else:
		offer = flt(settings.early_discount_value)
	until = getdate(add_days(invoice.due_date, -cint(settings.early_discount_days)))
	if until < getdate(invoice.posting_date):
		return  # too late to offer it
	invoice.early_discount_offer = flt(min(offer, base_amount(invoice)), 0)
	invoice.early_discount_until = until


def discount_available(invoice, on=None) -> float:
	"""The discount if the rest is paid in full on the day (today by default)."""
	if (
		not flt(invoice.early_discount_offer)
		or invoice.get("instalments")
		or flt(invoice.late_fee)
		or not invoice.early_discount_until
		or getdate(on or nowdate()) > getdate(invoice.early_discount_until)
		or flt(invoice.outstanding_amount) <= 0
	):
		return 0
	return min(flt(invoice.early_discount_offer), flt(invoice.outstanding_amount))


def payable_now(invoice) -> float:
	"""What to ask for today: the next instalment, or the balance less the discount for paying early."""
	outstanding = flt(invoice.outstanding_amount)
	rows = instalment_rows(invoice)
	if rows and outstanding > 0:
		paid = flt(invoice.paid_amount)
		for row in rows:
			if paid + 0.005 < flt(row.amount):
				return flt(min(flt(row.amount) - paid, outstanding), 2)
			paid -= flt(row.amount)
		return outstanding  # all parts paid, a late fee is left
	return flt(outstanding - discount_available(invoice), 2)


def instalment_rows(invoice) -> list:
	if isinstance(invoice, frappe.model.document.Document):
		rows = invoice.get("instalments") or []
	else:  # a row from a list
		rows = frappe.get_all(
			"Tenant Rent Invoice Instalment",
			filters={"parent": invoice.name, "parenttype": INVOICE},
			fields=["due_date", "amount"],
		)
	return sorted(rows, key=lambda r: getdate(r.due_date))


# ---------------------------------------------------------------- totals


def recalculate(invoice, update=False):
	"""Late fee, early discount, instalments paid and the next due date, from the payments."""
	payments = (
		frappe.get_all(
			"Rent Payment",
			filters={"rent_invoice": invoice.name, "docstatus": 1},
			fields=["amount", "payment_date"],
		)
		if invoice.docstatus == 1
		else []
	)
	paid = flt(sum(flt(p.amount) for p in payments), 2)
	last_paid = max((getdate(p.payment_date) for p in payments), default=None)
	base = base_amount(invoice)
	late = 0 if cint(invoice.late_fee_waived) else flt(invoice.late_fee)

	early = 0
	remaining = flt(base + late - paid, 2)
	if (
		flt(invoice.early_discount_offer)
		and not invoice.get("instalments")
		and not late
		and 0 < remaining <= flt(invoice.early_discount_offer)
		and last_paid
		and invoice.early_discount_until
		and last_paid <= getdate(invoice.early_discount_until)
	):
		early = remaining  # paid in full, less the discount, in time

	final = flt(base + late - early, 2)
	values = {
		"late_fee": late,
		"early_discount": early,
		"final_amount": final,
		"paid_amount": paid,
		"outstanding_amount": flt(final - paid, 2),
		"next_due_date": next_due(invoice, paid),
	}
	allocate(invoice, paid, update)
	if update:
		invoice.db_set(values, update_modified=False)
	else:
		invoice.update(values)


def allocate(invoice, paid, update):
	"""Payments go to the instalments in order."""
	for row in invoice.get("instalments") or []:
		row.paid = min(flt(row.amount), max(paid, 0))
		paid -= row.paid
		if update:
			row.db_set("paid", row.paid, update_modified=False)


def next_due(invoice, paid):
	rows = sorted(invoice.get("instalments") or [], key=lambda r: getdate(r.due_date))
	if not rows:
		return invoice.due_date
	for row in rows:
		if paid + 0.005 < flt(row.amount):
			return row.due_date
		paid -= flt(row.amount)
	return rows[-1].due_date


# ---------------------------------------------------------------- late fees


def late_fee_due(invoice, today=None) -> float:
	settings = frappe.get_cached_doc(SETTINGS)
	if not cint(settings.late_fee_enabled) or not flt(settings.late_fee_amount):
		return 0
	due = invoice.next_due_date or invoice.due_date
	if not due:
		return 0
	days_late = date_diff(today or nowdate(), add_days(due, cint(settings.late_fee_grace_days)))
	if days_late <= 0:
		return 0
	if settings.late_fee_type == "Per Day":
		fee = flt(settings.late_fee_amount) * days_late
		return min(fee, flt(settings.late_fee_max)) if flt(settings.late_fee_max) else fee
	return flt(settings.late_fee_amount)


def apply_late_fees():
	"""Daily: add (or grow) the late fee of invoices unpaid past their due date and grace."""
	if not cint(frappe.db.get_single_value(SETTINGS, "late_fee_enabled")):
		return
	grace = cint(frappe.db.get_single_value(SETTINGS, "late_fee_grace_days"))
	for name in frappe.get_all(
		INVOICE,
		filters={
			"docstatus": 1,
			"outstanding_amount": (">", 0),
			"late_fee_waived": 0,
			"next_due_date": ("<", add_days(nowdate(), -grace)),
		},
		pluck="name",
	):
		invoice = frappe.get_doc(INVOICE, name)
		fee = flt(late_fee_due(invoice), 2)
		if fee > flt(invoice.late_fee):
			invoice.late_fee = fee
			recalculate(invoice, update=True)
			invoice.set_status(update=True)


def waive_late_fee(name, waive=1):
	invoice = frappe.get_doc(INVOICE, name)
	invoice.check_permission("write")
	if invoice.docstatus != 1:
		frappe.throw(_("Submit the invoice first."))
	invoice.late_fee_waived = cint(waive)
	if not cint(waive):
		invoice.late_fee = late_fee_due(invoice)  # what it would be today
	recalculate(invoice, update=True)
	invoice.db_set("late_fee_waived", cint(waive), update_modified=False)
	invoice.set_status(update=True)
	invoice.add_comment("Info", _("Late fee waived") if cint(waive) else _("Late fee charged again"))


# ---------------------------------------------------------------- instalments


def split(name, instalments):
	"""Split what is left to pay into instalments: [{due_date, amount}, ...]."""
	invoice = frappe.get_doc(INVOICE, name)
	invoice.check_permission("write")
	if invoice.docstatus != 1 or flt(invoice.outstanding_amount) <= 0:
		frappe.throw(_("Only an unpaid invoice can be split into instalments."))
	rows = sorted(
		(
			{"due_date": getdate(r["due_date"]), "amount": flt(r["amount"], 2)}
			for r in frappe.parse_json(instalments)
		),
		key=lambda r: r["due_date"],
	)
	if not rows:
		return clear_instalments(invoice)
	if len(rows) < 2:
		frappe.throw(_("Split it into at least two instalments."))
	if any(r["amount"] <= 0 for r in rows):
		frappe.throw(_("Every instalment needs an amount."))
	if len({r["due_date"] for r in rows}) < len(rows):
		frappe.throw(_("Give each instalment its own date."))
	if rows[0]["due_date"] < getdate(invoice.posting_date):
		frappe.throw(_("An instalment can't be due before the invoice date."))
	# the instalments cover the whole invoice: what was paid counts towards the first ones
	total = flt(base_amount(invoice) + (0 if cint(invoice.late_fee_waived) else flt(invoice.late_fee)), 2)
	if abs(sum(r["amount"] for r in rows) - total) > 0.5:
		frappe.throw(
			_("The instalments add up to {0}, but the invoice is {1}.").format(
				frappe.format_value(sum(r["amount"] for r in rows), {"fieldtype": "Currency"}),
				frappe.format_value(total, {"fieldtype": "Currency"}),
			)
		)
	frappe.db.delete("Tenant Rent Invoice Instalment", {"parent": invoice.name, "parenttype": INVOICE})
	invoice.set("instalments", [])
	for i, row in enumerate(rows, 1):
		invoice.append("instalments", {**row, "idx": i}).db_insert()
	invoice.db_set("early_discount_offer", 0, update_modified=False)  # no discount on top
	invoice.early_discount_offer = 0
	recalculate(invoice, update=True)
	invoice.set_status(update=True)
	invoice.add_comment(
		"Info",
		_("Split into {0} instalments: {1}").format(
			len(rows),
			", ".join(
				f"{frappe.format_value(r['amount'], {'fieldtype': 'Currency'})} by {frappe.utils.formatdate(r['due_date'])}"
				for r in rows
			),
		),
	)


def clear_instalments(invoice):
	frappe.db.delete("Tenant Rent Invoice Instalment", {"parent": invoice.name, "parenttype": INVOICE})
	invoice.set("instalments", [])
	recalculate(invoice, update=True)
	invoice.set_status(update=True)
	invoice.add_comment("Info", _("Instalments removed"))


def schedule(invoice) -> list[dict]:
	"""For the apps: each instalment and whether it's paid."""
	today = getdate(nowdate())
	return [
		{
			"due_date": str(r.due_date),
			"amount": flt(r.amount),
			"paid": flt(r.paid),
			"status": "Paid"
			if flt(r.paid) >= flt(r.amount) - 0.005
			else "Overdue"
			if getdate(r.due_date) < today
			else "Partly Paid"
			if flt(r.paid)
			else "Due",
		}
		for r in sorted(invoice.get("instalments") or [], key=lambda r: getdate(r.due_date))
	]

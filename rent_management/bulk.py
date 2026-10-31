# Copyright (c) 2026, Shashank Dixit and contributors
# For license information, please see license.txt

"""Doing the month's rent work in one go: reminding everyone who owes rent, and marking several
bills paid.

Reminders: one per tenant, for their oldest unpaid bill, on WhatsApp and email (whichever are
on, see notifications.py). The list shows who can't be reached (no number or email) and who
was already reminded today; nobody is reminded twice on the same day, so sending again is
harmless.
"""

import frappe
from frappe import _
from frappe.utils import cint, date_diff, flt, getdate, nowdate

from rent_management import notifications

INVOICE = "Tenant Rent Invoice"
LOG = "Rent Message Log"
REMINDERS = ("Reminder", "Due Today", "Overdue")


def channels() -> dict:
	settings = frappe.get_single(notifications.SETTINGS)
	return {
		"whatsapp": bool(cint(settings.notify_by_whatsapp) and notifications.get_whatsapp_account()),
		"email": bool(cint(settings.notify_by_email) and notifications.email_configured()),
	}


def reminded_today(invoices) -> set:
	return set(
		frappe.get_all(
			LOG,
			filters={
				"rent_invoice": ("in", list(invoices) or [""]),
				"message_type": ("in", REMINDERS),
				"status": "Sent",
				"creation": (">=", nowdate()),
			},
			pluck="rent_invoice",
		)
	)


def reminder_list(property=None) -> dict:
	"""Everyone who owes rent: their oldest unpaid bill, what they owe, and whether they can be
	reached and were already reminded today."""
	today = getdate(nowdate())
	filters = {"docstatus": 1, "outstanding_amount": (">", 0)}
	if property:
		filters["property"] = property
	bills = frappe.get_all(
		INVOICE,
		filters=filters,
		fields=["name", "tenant", "tenant_name", "room", "property", "billing_month", "billing_year",
			"due_date", "next_due_date", "outstanding_amount"],
		order_by="posting_date asc, name asc",
	)  # fmt: skip
	by_tenant = {}
	for bill in bills:
		row = by_tenant.setdefault(str(bill.tenant), {"bill": bill, "owed": 0, "bills": 0})
		row["owed"] += flt(bill.outstanding_amount)
		row["bills"] += 1
	tenants = {
		str(t.name): t
		for t in frappe.get_all(
			"Tenant",
			filters={"name": ("in", list(by_tenant) or [""])},
			fields=["name", "mobile_no", "email_id", "status"],
		)
	}
	on = channels()
	sent = reminded_today(r["bill"].name for r in by_tenant.values())
	rows = []
	for tenant, r in by_tenant.items():
		bill, t = r["bill"], tenants.get(tenant) or frappe._dict()
		due = notifications.due_on(bill)
		reach = []
		if on["whatsapp"] and notifications.whatsapp_number(t.mobile_no):
			reach.append("WhatsApp")
		if on["email"] and t.email_id:
			reach.append("Email")
		days = date_diff(today, due) if due else 0
		rows.append(
			{
				"tenant": bill.tenant,
				"tenant_name": bill.tenant_name,
				"room": frappe.db.get_value("Tenant Space", bill.room, "room_number") or bill.room,
				"property": bill.property,
				"invoice": bill.name,
				"period": f"{bill.billing_month} {bill.billing_year}",
				"due_on": due,
				"days_overdue": max(days, 0),
				"overdue": days > 0,
				"owed": flt(r["owed"], 2),
				"bill_outstanding": flt(bill.outstanding_amount),
				"bills": r["bills"],
				"reach": reach,
				"mobile_no": t.mobile_no,
				"reminded_today": bill.name in sent,
				"inactive": t.status == "Inactive",
			}
		)
	rows.sort(key=lambda r: (-r["days_overdue"], r["tenant_name"] or ""))
	return {"rows": rows, "channels": on}


def send_reminders(invoices) -> dict:
	"""Remind the tenants of these bills now. Each stands alone; nobody twice in a day."""
	invoices = list(dict.fromkeys(frappe.parse_json(invoices) or []))
	sent_before = reminded_today(invoices)
	result = {"sent": 0, "skipped": [], "failed": []}
	for name in invoices:
		bill = frappe.db.get_value(INVOICE, name, ["name", "tenant_name", "outstanding_amount", "docstatus"], as_dict=True)  # fmt: skip
		if not bill or bill.docstatus != 1 or flt(bill.outstanding_amount) <= 0:
			result["skipped"].append(
				{"tenant_name": bill.tenant_name if bill else name, "why": _("paid already")}
			)
			continue
		if name in sent_before:
			result["skipped"].append({"tenant_name": bill.tenant_name, "why": _("reminded today already")})
			continue
		frappe.db.savepoint("bulk_reminder")
		try:
			statuses = notifications.send_reminder(name)
		except Exception as e:
			frappe.db.rollback(save_point="bulk_reminder")
			frappe.clear_last_message()
			result["failed"].append({"tenant_name": bill.tenant_name, "why": frappe.utils.strip_html(str(e))})
			continue
		if "Sent" in statuses:
			result["sent"] += 1
		elif statuses:
			result["failed"].append({"tenant_name": bill.tenant_name, "why": _("the message didn't go")})
		else:
			result["skipped"].append(
				{"tenant_name": bill.tenant_name, "why": _("no WhatsApp number or email")}
			)
	return result


def mark_paid(invoices, mode_of_payment="Cash", payment_date=None, reference_no=None) -> dict:
	"""Record each bill's balance as paid (cash collected, a batch of transfers checked)."""
	invoices = list(dict.fromkeys(frappe.parse_json(invoices) or []))
	payment_date = payment_date or nowdate()
	if getdate(payment_date) > getdate(nowdate()):
		frappe.throw(_("The payment date can't be in the future."))
	result = {"paid": 0, "amount": 0.0, "failed": []}
	for name in invoices:
		bill = frappe.db.get_value(INVOICE, name, ["name", "tenant", "tenant_name", "outstanding_amount", "docstatus"], as_dict=True)  # fmt: skip
		if not bill or bill.docstatus != 1 or flt(bill.outstanding_amount) <= 0:
			continue
		frappe.db.savepoint("bulk_payment")
		try:
			doc = frappe.get_doc(
				{
					"doctype": "Rent Payment",
					"tenant": bill.tenant,
					"rent_invoice": bill.name,
					"amount": flt(bill.outstanding_amount),
					"mode_of_payment": mode_of_payment,
					"payment_date": payment_date,
					"reference_no": reference_no if len(invoices) == 1 else None,
					"remarks": _("Marked paid with other bills"),
				}
			)
			doc.insert()
			doc.submit()
			result["paid"] += 1
			result["amount"] += flt(doc.amount)
		except Exception as e:
			frappe.db.rollback(save_point="bulk_payment")
			frappe.clear_last_message()
			result["failed"].append({"tenant_name": bill.tenant_name, "why": frappe.utils.strip_html(str(e))})
	result["amount"] = flt(result["amount"], 2)
	return result

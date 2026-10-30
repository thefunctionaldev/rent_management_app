# Copyright (c) 2026, Shashank Dixit and contributors
# For license information, please see license.txt

"""The activity log: who did what, in plain words, for owners.

"Manjunath recorded ₹5,000 in cash from Deepak Reddy for October." Entries come from document
events (on_event, wired in hooks.py) and from a few actions that aren't document events (log(),
called where they happen: waiving a late fee, viewing an Aadhaar number, giving a staff login...).
Entries can't be edited, and only a System Manager can delete them.
"""

import frappe
from frappe import _
from frappe.utils import flt

ACTIVITY = "Rent Activity"
SETTINGS = "Rent Management Settings"
# settings whose values aren't written into the log
SECRET_SETTINGS = {
	"razorpay_key_secret",
	"razorpay_webhook_secret",
	"whatsapp_token",
	"vapid_private_key",
	"vapid_public_key",
}


def money(amount) -> str:
	from rent_management.owner_summary import money as rupees

	return rupees(amount)


def log(category, summary, doc=None, amount=None, property=None, tenant=None, user=None):
	"""Write one entry. `summary` reads after the person's name: "recorded ₹5,000 ..."."""
	if frappe.flags.no_activity_log or frappe.flags.in_install or frappe.flags.in_migrate:
		return
	user = user or frappe.session.user
	entry = frappe.get_doc(
		{
			"doctype": ACTIVITY,
			"user": user,
			"user_name": "System"
			if user in ("Administrator", "Guest")
			else frappe.db.get_value("User", user, "full_name"),
			"category": category,
			"summary": summary[:1000],
			"property": property or (doc.get("property") if doc and doc.meta.has_field("property") else None),
			"tenant": tenant or (doc.get("tenant") if doc and doc.meta.has_field("tenant") else None),
			"amount": amount,
			"reference_doctype": doc.doctype if doc else None,
			"reference_name": doc.name if doc else None,
		}
	)
	entry.flags.ignore_permissions = True
	entry.flags.ignore_links = True
	entry.insert()


def day(value) -> str:
	"""3 Nov, as people write it (the site's date format can be 2026-11-03)."""
	from frappe.utils import getdate

	return getdate(value).strftime("%-d %b") if value else ""


def period(invoice_name) -> str:
	if not invoice_name:
		return ""
	month, year = frappe.db.get_value(
		"Tenant Rent Invoice", invoice_name, ["billing_month", "billing_year"]
	) or (None, None)
	return f" for {month} {year}" if month else ""


# ---------------------------------------------------------------- document events


def on_event(doc, method=None):
	handler = HANDLERS.get((doc.doctype, method))
	if handler:
		handler(doc)


def payment_submitted(doc):
	if doc.mode_of_payment == "Security Deposit":
		return  # logged with the settlement
	how = _("in cash") if doc.mode_of_payment == "Cash" else _("by {0}").format(doc.mode_of_payment)
	online = (doc.remarks or "").startswith(_("Paid online"))
	summary = (
		_("received {0} online from {1}{2}").format(
			money(doc.amount), doc.tenant_name, period(doc.rent_invoice)
		)
		if online
		else _("recorded {0} {1} from {2}{3}").format(
			money(doc.amount), how, doc.tenant_name, period(doc.rent_invoice)
		)
	)
	log("Payments", summary, doc, doc.amount)


def payment_cancelled(doc):
	log(
		"Payments",
		_("cancelled the {0} payment of {1}{2}").format(
			money(doc.amount), doc.tenant_name, period(doc.rent_invoice)
		),
		doc,
		doc.amount,
	)


def payment_deleted(doc):
	if doc.docstatus == 0:  # a payment the tenant reported, turned down
		log(
			"Payments",
			_("turned down the {0} payment {1} reported{2}").format(
				money(doc.amount), doc.tenant_name, period(doc.rent_invoice)
			),
			doc,
			doc.amount,
		)


def invoice_submitted(doc):
	if frappe.flags.generating_invoices:
		return  # one entry for the whole run, see api.generate_invoices
	log(
		"Invoices",
		_("issued the {0} {1} invoice of {2}: {3}").format(
			doc.billing_month, doc.billing_year, doc.tenant_name, money(doc.final_amount)
		),
		doc,
		doc.final_amount,
	)


def invoice_cancelled(doc):
	log(
		"Invoices",
		_("cancelled the {0} {1} invoice of {2} ({3})").format(
			doc.billing_month, doc.billing_year, doc.tenant_name, money(doc.final_amount)
		),
		doc,
		doc.final_amount,
	)


def invoice_deleted(doc):
	log(
		"Invoices",
		_("deleted the draft {0} {1} invoice of {2}").format(
			doc.billing_month, doc.billing_year, doc.tenant_name
		),
		None,
		property=doc.property,
		tenant=doc.tenant,
	)


def stay_submitted(doc):
	log(
		"Stays",
		_("moved {0} into room {1} at {2} a month").format(doc.tenant_name, doc.room, money(doc.rent_amount)),
		doc,
		doc.rent_amount,
	)


def stay_updated(doc):
	before = doc.get_doc_before_save()
	if not before:
		return
	if flt(before.rent_amount) != flt(doc.rent_amount):
		log(
			"Stays",
			_("changed the rent of {0} from {1} to {2}").format(
				doc.tenant_name, money(before.rent_amount), money(doc.rent_amount)
			),
			doc,
			doc.rent_amount,
		)
	if before.status != "Vacated" and doc.status == "Vacated":
		log("Stays", _("moved {0} out of room {1}").format(doc.tenant_name, doc.room), doc)
	if not before.notice_given_on and doc.notice_given_on:
		log(
			"Stays",
			_("noted that {0} leaves on {1}").format(doc.tenant_name, day(doc.expected_vacate_date)),
			doc,
		)
	elif before.notice_given_on and not doc.notice_given_on:
		log("Stays", _("withdrew the notice of {0}").format(doc.tenant_name), doc)
	if not before.deposit_collected and doc.deposit_collected:
		log(
			"Deposits",
			_("noted the {0} deposit of {1} as collected").format(
				money(doc.security_deposit), doc.tenant_name
			),
			doc,
			doc.security_deposit,
		)


def settlement_submitted(doc):
	log(
		"Deposits",
		_("settled the deposit of {0}: {1} deducted, {2} refunded").format(
			doc.get("tenant_name") or doc.tenant,
			money(doc.get("total_deductions")),
			money(doc.get("refund_amount")),
		),
		doc,
		doc.get("refund_amount"),
	)


def settlement_cancelled(doc):
	log(
		"Deposits",
		_("cancelled the deposit settlement of {0}").format(doc.get("tenant_name") or doc.tenant),
		doc,
	)


def expense_added(doc):
	log(
		"Expenses",
		_("added a {0} expense: {1}{2}").format(
			doc.category, money(doc.amount), f" to {doc.paid_to}" if doc.paid_to else ""
		),
		doc,
		doc.amount,
	)


def expense_updated(doc):
	before = doc.get_doc_before_save()
	if before and flt(before.amount) != flt(doc.amount):
		log(
			"Expenses",
			_("changed a {0} expense from {1} to {2}").format(
				doc.category, money(before.amount), money(doc.amount)
			),
			doc,
			doc.amount,
		)


def expense_deleted(doc):
	log(
		"Expenses",
		_("deleted a {0} expense of {1}").format(doc.category, money(doc.amount)),
		None,
		doc.amount,
		property=doc.property,
	)


def salary_updated(doc):
	before = doc.get_doc_before_save()
	if not before or before.status == doc.status:
		return
	if doc.status == "Paid":
		log(
			"Staff",
			_("paid {0} the {1} salary: {2}").format(doc.staff_name, doc.salary_month, money(doc.net_pay)),
			doc,
			doc.net_pay,
		)
	else:
		log(
			"Staff",
			_("undid the {0} salary payment of {1}").format(doc.salary_month, doc.staff_name),
			doc,
			doc.net_pay,
		)


def advance_added(doc):
	log("Staff", _("gave {0} an advance of {1}").format(doc.staff_name, money(doc.amount)), doc, doc.amount)


def leave_updated(doc):
	before = doc.get_doc_before_save()
	if before and before.status == "Requested" and doc.status in ("Approved", "Rejected"):
		log("Register", _("{0} the leave of {1} ({2} to {3})").format(
			_("approved") if doc.status == "Approved" else _("turned down"), doc.tenant_name,
			day(doc.from_date), day(doc.to_date)), doc)  # fmt: skip


def handover_added(doc):
	log(
		"Cash",
		_("handed {0} in cash to {1}").format(money(doc.amount), doc.to_name or doc.to_user),
		doc,
		doc.amount,
		user=doc.from_user,
	)


def handover_updated(doc):
	before = doc.get_doc_before_save()
	if before and before.status == "Pending" and doc.status in ("Confirmed", "Rejected"):
		what = (
			_("confirmed getting {0} in cash from {1}")
			if doc.status == "Confirmed"
			else _("said they didn't get {0} in cash from {1}")
		)
		log("Cash", what.format(money(doc.amount), doc.from_name or doc.from_user), doc, doc.amount)


def tenant_added(doc):
	log("Tenants", _("added the tenant {0}").format(doc.full_name), doc, tenant=doc.name)


def tenant_deleted(doc):
	log("Tenants", _("deleted the tenant {0}").format(doc.full_name), None)


def settings_updated(doc):
	before = doc.get_doc_before_save()
	if not before:
		return
	changes = []
	for field in doc.meta.fields:
		name = field.fieldname
		if field.fieldtype in ("Section Break", "Column Break", "Tab Break", "Table") or name in (
			"modified",
		):
			continue
		old, new = before.get(name), doc.get(name)
		if (old or None) == (new or None) or str(old) == str(new):
			continue
		label = _(field.label or name)
		if name in SECRET_SETTINGS or field.fieldtype == "Password":
			changes.append(_("{0} (changed)").format(label))
		elif field.fieldtype == "Check":
			changes.append(f"{label}: {_('on') if new else _('off')}")
		elif field.fieldtype in ("Text Editor", "Small Text", "Text", "Long Text"):
			changes.append(_("{0} (edited)").format(label))
		else:
			changes.append(
				f"{label}: {old if old not in (None, '') else _('(empty)')} → {new if new not in (None, '') else _('(empty)')}"
			)
	if changes:
		log("Settings", _("changed the settings: {0}").format("; ".join(changes)), doc)


def notice_deleted(doc):
	log("Notices", _('deleted the notice "{0}"').format(doc.title), None, property=doc.property)


HANDLERS = {
	("Rent Payment", "on_submit"): payment_submitted,
	("Rent Payment", "on_cancel"): payment_cancelled,
	("Rent Payment", "on_trash"): payment_deleted,
	("Tenant Rent Invoice", "on_submit"): invoice_submitted,
	("Tenant Rent Invoice", "on_cancel"): invoice_cancelled,
	("Tenant Rent Invoice", "on_trash"): invoice_deleted,
	("Tenant Space Allotment", "on_submit"): stay_submitted,
	("Tenant Space Allotment", "on_update_after_submit"): stay_updated,
	("Security Deposit Settlement", "on_submit"): settlement_submitted,
	("Security Deposit Settlement", "on_cancel"): settlement_cancelled,
	("Property Expense", "after_insert"): expense_added,
	("Property Expense", "on_update"): expense_updated,
	("Property Expense", "on_trash"): expense_deleted,
	("Salary Slip", "on_update"): salary_updated,
	("Staff Advance", "after_insert"): advance_added,
	("Tenant Leave", "on_update"): leave_updated,
	("Cash Handover", "after_insert"): handover_added,
	("Cash Handover", "on_update"): handover_updated,
	("Tenant", "after_insert"): tenant_added,
	("Tenant", "on_trash"): tenant_deleted,
	(SETTINGS, "on_update"): settings_updated,
	("Rent Notice", "on_trash"): notice_deleted,
}


# ---------------------------------------------------------------- the page


CATEGORIES = (
	"Payments",
	"Invoices",
	"Stays",
	"Tenants",
	"Deposits",
	"Expenses",
	"Cash",
	"Staff",
	"Register",
	"Notices",
	"Settings",
	"Privacy",
)


def get_activity(property=None, user=None, category=None, from_date=None, to_date=None, limit=300) -> dict:
	from frappe.utils import add_days, getdate, nowdate

	from_date = getdate(from_date or add_days(nowdate(), -6))
	to_date = getdate(to_date or nowdate())
	filters = {"creation": ("between", (f"{from_date} 00:00:00", f"{to_date} 23:59:59"))}
	if property:
		filters["property"] = property
	if user:
		filters["user"] = user
	if category:
		filters["category"] = category
	rows = frappe.get_all(
		ACTIVITY,
		filters=filters,
		fields=["name", "user", "user_name", "category", "summary", "property", "tenant", "amount",
			"reference_doctype", "reference_name", "creation"],
		order_by="creation desc",
		limit=limit,
	)  # fmt: skip
	people = frappe.get_all(
		ACTIVITY,
		filters={"creation": (">=", add_days(nowdate(), -90))},
		fields=["user", "user_name"],
		distinct=True,
	)
	return {
		"rows": rows,
		"from_date": str(from_date),
		"to_date": str(to_date),
		"people": sorted({(p.user, p.user_name) for p in people if p.user}, key=lambda p: p[1] or ""),
		"categories": CATEGORIES,
		"more": len(rows) == limit,
	}

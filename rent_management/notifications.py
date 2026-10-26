# Copyright (c) 2026, Shashank Dixit and contributors
# For license information, please see license.txt

"""Rent reminders and payment receipts for tenants, on WhatsApp and by email.

WhatsApp uses the WhatsApp Cloud API with message templates, which Meta must approve first.
Either you provide it for all customer sites (in common_site_config.json, for plans that
include WhatsApp) or a landlord enters their own WhatsApp Business credentials in Rent
Management Settings. Email uses the site's outgoing email account.

Templates (create them in WhatsApp Manager, category Utility, language as configured):

	rent_reminder  Hello {{1}}, your rent of {{2}} for {{3}} at {{4}} is due on {{5}}. {{6}}
	rent_overdue   Hello {{1}}, your rent of {{2}} for {{3}} at {{4}} was due on {{5}} and is still unpaid. {{6}}
	rent_receipt   Hello {{1}}, we have received {{2}} for your rent for {{3}} at {{4}}. Balance due: {{5}}. Thank you!
	rent_request_update  Hello {{1}}, your request "{{2}}" is now {{3}}. {{4}}
"""

import re

import frappe
import requests
from frappe import _
from frappe.utils import cint, date_diff, flt, fmt_money, formatdate, getdate, nowdate

from rent_management import rent_collection, subscription

SETTINGS = "Rent Management Settings"
LOG = "Rent Message Log"
TEMPLATES = {
	"Reminder": "rent_reminder",
	"Due Today": "rent_reminder",
	"Overdue": "rent_overdue",
	"Receipt": "rent_receipt",
	"Request Update": "rent_request_update",
}
GRAPH_URL = "https://graph.facebook.com"


# ---------------------------------------------------------------- channels


def get_whatsapp_account():
	"""(phone_number_id, token) to send from: the landlord's own account, or yours when their
	plan includes WhatsApp. None when WhatsApp isn't available."""
	settings = frappe.get_single(SETTINGS)
	token = settings.get_password("whatsapp_token", raise_exception=False)
	if settings.whatsapp_phone_number_id and token:
		return settings.whatsapp_phone_number_id, token
	conf = frappe.conf
	if (
		conf.get("whatsapp_phone_number_id")
		and conf.get("whatsapp_token")
		and subscription.has_feature("whatsapp")
	):
		return conf.whatsapp_phone_number_id, conf.whatsapp_token
	return None


def email_configured() -> bool:
	"""Frappe sends through the default outgoing Email Account, or the mail server in site config."""
	return bool(
		frappe.db.exists("Email Account", {"enable_outgoing": 1, "default_outgoing": 1})
		or frappe.conf.get("mail_server")
	)


def whatsapp_number(mobile) -> str | None:
	"""E.164 digits for WhatsApp; 10 digit numbers are taken as Indian."""
	digits = re.sub(r"\D", "", str(mobile or ""))
	if len(digits) == 11 and digits.startswith("0"):
		digits = digits[1:]
	if len(digits) == 10:
		digits = "91" + digits
	return digits if 11 <= len(digits) <= 15 else None


def send_whatsapp(to: str, template: str, params: list[str]) -> str:
	phone_number_id, token = get_whatsapp_account()
	response = requests.post(
		f"{GRAPH_URL}/{frappe.conf.get('whatsapp_api_version') or 'v21.0'}/{phone_number_id}/messages",
		json={
			"messaging_product": "whatsapp",
			"to": to,
			"type": "template",
			"template": {
				"name": (frappe.conf.get("whatsapp_templates") or {}).get(template, template),
				"language": {"code": frappe.conf.get("whatsapp_language") or "en"},
				"components": [
					{"type": "body", "parameters": [{"type": "text", "text": str(p)[:1000]} for p in params]}
				],
			},
		},
		headers={"Authorization": f"Bearer {token}"},
		timeout=20,
	)
	body = response.json() if response.content else {}
	if not response.ok:
		raise frappe.ValidationError((body.get("error") or {}).get("message") or response.reason)
	return ((body.get("messages") or [{}])[0]).get("id") or ""


# ---------------------------------------------------------------- messages


def money(amount) -> str:
	return fmt_money(flt(amount), currency=frappe.db.get_default("currency") or "INR")


def invoice_context(invoice) -> frappe._dict:
	tenant = frappe.db.get_value(
		"Tenant",
		invoice.tenant,
		["name", "first_name", "full_name", "mobile_no", "email_id", "status"],
		as_dict=True,
	)
	return frappe._dict(
		tenant=tenant,
		period=f"{invoice.billing_month} {invoice.billing_year}",
		place=frappe.db.get_value("Rent Property", invoice.property, "property_name")
		or _("room {0}").format(invoice.room),
		due=formatdate(invoice.due_date) if invoice.due_date else _("today"),
		balance=money(invoice.outstanding_amount),
	)


def pay_hint(invoice) -> str:
	"""How to pay: a Razorpay link (made now if needed) or the UPI ID."""
	if rent_collection.get_auth():
		try:
			return _("Pay online: {0}").format(rent_collection.get_payment_link(invoice.name))
		except Exception:
			frappe.clear_last_message()
			frappe.log_error(title=f"Could not make a payment link for {invoice.name}")
	upi_id = frappe.db.get_single_value(SETTINGS, "upi_id")
	if upi_id:
		return _("Pay by UPI to {0}.").format(upi_id)
	return _("Please pay your landlord.")


def reminder_text(message_type, ctx, hint) -> tuple[str, list[str]]:
	first = ctx.tenant.first_name or ctx.tenant.full_name
	if message_type == "Overdue":
		text = _("Hello {0}, your rent of {1} for {2} at {3} was due on {4} and is still unpaid. {5}")
	else:
		text = _("Hello {0}, your rent of {1} for {2} at {3} is due on {4}. {5}")
	params = [first, ctx.balance, ctx.period, ctx.place, ctx.due, hint]
	return text.format(*params), params


def send(message_type, tenant, text, params, invoice=None, payment=None, subject=None) -> list[str]:
	"""Send one message on every enabled channel and log each attempt."""
	settings = frappe.get_single(SETTINGS)
	statuses = []
	channels = []
	if cint(settings.notify_by_whatsapp) and get_whatsapp_account():
		channels.append("WhatsApp")
	if cint(settings.notify_by_email) and email_configured():
		channels.append("Email")

	for channel in channels:
		recipient = whatsapp_number(tenant.mobile_no) if channel == "WhatsApp" else tenant.email_id
		if not recipient:
			continue
		log = {
			"doctype": LOG,
			"message_type": message_type,
			"channel": channel,
			"recipient": recipient,
			"tenant": tenant.name,
			"rent_invoice": invoice,
			"rent_payment": payment,
			"message": text,
		}
		try:
			if channel == "WhatsApp":
				log["provider_message_id"] = send_whatsapp(recipient, TEMPLATES[message_type], params)
			else:
				frappe.sendmail(
					recipients=[recipient], subject=subject or text[:120], message=f"<p>{text}</p>"
				)
			log["status"] = "Sent"
		except Exception as e:
			log.update(status="Failed", error=str(e)[:1000])
		frappe.get_doc(log).insert(ignore_permissions=True)
		statuses.append(log["status"])
	return statuses


# ---------------------------------------------------------------- reminders


def get_reminder_type(invoice, settings, today) -> str | None:
	if not invoice.due_date:
		return None
	days_left = date_diff(invoice.due_date, today)
	if days_left > 0:
		return "Reminder" if days_left == cint(settings.remind_days_before) else None
	if days_left == 0:
		return "Due Today" if cint(settings.remind_on_due_date) else None

	interval = cint(settings.overdue_reminder_interval)
	if not interval or -days_left % interval:
		return None
	sent = frappe.db.count(LOG, {"rent_invoice": invoice.name, "message_type": "Overdue", "status": "Sent"})
	return "Overdue" if sent < cint(settings.overdue_reminder_limit) else None


def already_sent_today(invoice_name, message_type) -> bool:
	return bool(
		frappe.db.exists(
			LOG,
			{
				"rent_invoice": invoice_name,
				"message_type": message_type,
				"status": "Sent",
				"creation": (">=", nowdate()),
			},
		)
	)


def send_reminder(invoice, message_type=None) -> list[str]:
	"""Remind the tenant of an unpaid invoice now. Returns the status per channel."""
	if isinstance(invoice, str):
		invoice = frappe.get_doc("Tenant Rent Invoice", invoice)
	if invoice.docstatus != 1 or flt(invoice.outstanding_amount) <= 0:
		frappe.throw(_("Invoice {0} has nothing left to pay.").format(invoice.name))
	if not message_type:
		message_type = (
			"Overdue" if invoice.due_date and getdate(invoice.due_date) < getdate(nowdate()) else "Reminder"
		)
	ctx = invoice_context(invoice)
	text, params = reminder_text(message_type, ctx, pay_hint(invoice))
	return send(
		message_type,
		ctx.tenant,
		text,
		params,
		invoice=invoice.name,
		subject=_("Rent reminder: {0} for {1}").format(ctx.balance, ctx.period),
	)


def send_due_reminders():
	"""Scheduler (daily): reminders before the due date, on it, and while overdue."""
	settings = frappe.get_single(SETTINGS)
	if not cint(settings.send_reminders) or subscription.skip_if_lapsed():
		return
	today = getdate(nowdate())
	for name in frappe.get_all(
		"Tenant Rent Invoice",
		filters={"docstatus": 1, "outstanding_amount": (">", 0)},
		pluck="name",
	):
		invoice = frappe.get_doc("Tenant Rent Invoice", name)
		message_type = get_reminder_type(invoice, settings, today)
		if not message_type or already_sent_today(name, message_type):
			continue
		if frappe.db.get_value("Tenant", invoice.tenant, "status") == "Inactive":
			continue
		frappe.db.savepoint("rent_reminder")
		try:
			send_reminder(invoice, message_type)
		except Exception:
			frappe.db.rollback(save_point="rent_reminder")
			frappe.log_error(title=f"Rent reminder for {name} failed")


# ---------------------------------------------------------------- receipts


def on_payment_submit(doc, method=None):
	"""Rent Payment on_submit: send the receipt after the transaction commits."""
	if doc.mode_of_payment == "Security Deposit" or frappe.flags.in_import:
		return
	if cint(frappe.db.get_single_value(SETTINGS, "send_receipts")):
		frappe.enqueue(send_receipt, payment=doc.name, enqueue_after_commit=True, now=frappe.flags.in_test)


def send_receipt(payment: str) -> list[str]:
	payment = frappe.get_doc("Rent Payment", payment)
	if payment.docstatus != 1:
		return []
	invoice = frappe.get_doc("Tenant Rent Invoice", payment.rent_invoice)
	ctx = invoice_context(invoice)
	first = ctx.tenant.first_name or ctx.tenant.full_name
	params = [first, money(payment.amount), ctx.period, ctx.place, ctx.balance]
	text = _(
		"Hello {0}, we have received {1} for your rent for {2} at {3}. Balance due: {4}. Thank you!"
	).format(*params)
	return send(
		"Receipt",
		ctx.tenant,
		text,
		params,
		invoice=invoice.name,
		payment=payment.name,
		subject=_("Rent receipt: {0} for {1}").format(money(payment.amount), ctx.period),
	)


# ---------------------------------------------------------------- tenant requests


def send_request_update(request: str) -> list[str]:
	"""Tell the tenant their maintenance request moved on (In Progress, Resolved...)."""
	request = frappe.get_doc("Maintenance Request", request)
	tenant = frappe.db.get_value(
		"Tenant", request.tenant, ["name", "first_name", "full_name", "mobile_no", "email_id"], as_dict=True
	)
	note = request.resolution or _("See the tenant app for details.")
	params = [tenant.first_name or tenant.full_name, request.subject, _(request.status).lower(), note]
	text = _('Hello {0}, your request "{1}" is now {2}. {3}').format(*params)
	return send(
		"Request Update", tenant, text, params, subject=_("Your request: {0}").format(request.subject)
	)

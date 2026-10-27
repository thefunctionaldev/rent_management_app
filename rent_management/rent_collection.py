# Copyright (c) 2026, Shashank Dixit and contributors
# For license information, please see license.txt

"""Tenants paying rent online, straight into the landlord's own account.

- UPI QR: needs only the landlord's UPI ID. The QR on the invoice carries the exact amount;
  the landlord confirms the payment (or the tenant reports it from the tenant app).
- Razorpay payment links: the landlord's own Razorpay keys. Each invoice gets a link for its
  balance; payments are recorded as Rent Payments automatically, from the webhook, when the
  tenant returns to the tenant app, or by the daily reconcile job.
"""

import base64
import io
from urllib.parse import quote, urlencode

import frappe
from frappe import _
from frappe.utils import flt, get_url, nowdate

from rent_management import razorpay

SETTINGS = "Rent Management Settings"
INVOICE = "Tenant Rent Invoice"

RAZORPAY_METHODS = {
	"upi": "UPI",
	"card": "Card",
	"netbanking": "Bank Transfer",
	"wallet": "Other",
	"emi": "Card",
}


# ---------------------------------------------------------------- settings


def get_auth():
	"""The landlord's Razorpay credentials, or None when online collection is off."""
	settings = frappe.get_single(SETTINGS)
	if not (settings.razorpay_enabled and settings.razorpay_key_id):
		return None
	secret = settings.get_password("razorpay_key_secret", raise_exception=False)
	return (settings.razorpay_key_id, secret) if secret else None


def get_payment_options() -> dict:
	settings = frappe.get_single(SETTINGS)
	return {"upi": bool(settings.upi_id), "razorpay": bool(get_auth())}


# ---------------------------------------------------------------- UPI


def get_upi_link(invoice) -> str | None:
	settings = frappe.get_single(SETTINGS)
	amount = flt(invoice.outstanding_amount)
	if not settings.upi_id or amount <= 0 or invoice.docstatus != 1:
		return None
	params = {
		"pa": settings.upi_id.strip(),
		"pn": settings.upi_payee_name
		or frappe.db.get_value("Rent Property", invoice.property, "property_name")
		or "",
		"am": f"{amount:.2f}",
		"cu": "INR",
		"tn": f"Rent {invoice.name} {invoice.billing_month} {invoice.billing_year}"[:50],
	}
	return "upi://pay?" + urlencode(params, quote_via=quote)


def qr_data_uri(value: str) -> str:
	from pyqrcode import create

	stream = io.BytesIO()
	create(value).svg(stream, scale=4, quiet_zone=2)
	return "data:image/svg+xml;base64," + base64.b64encode(stream.getvalue()).decode()


def get_rent_payment_options(doc) -> dict:
	"""For the rent invoice print format (Jinja method): UPI QR and payment link."""
	upi = get_upi_link(doc)
	return {
		"upi_link": upi,
		"upi_qr": qr_data_uri(upi) if upi else None,
		"upi_id": frappe.db.get_single_value(SETTINGS, "upi_id"),
		"payment_link": doc.payment_link_url if flt(doc.outstanding_amount) > 0 else None,
	}


# ---------------------------------------------------------------- Razorpay payment links


def get_payment_link(invoice_name: str) -> str:
	"""A Razorpay payment link for the invoice's current balance (made or refreshed as needed)."""
	auth = get_auth()
	if not auth:
		frappe.throw(_("Turn on Collect Rent with Razorpay in Rent Management Settings first."))

	invoice = frappe.get_doc(INVOICE, invoice_name)
	if invoice.docstatus != 1:
		frappe.throw(_("Submit the invoice first."))
	if invoice.payment_link_id:
		sync_payment_link(invoice)  # it may have been paid in the meantime
		invoice.reload()
	if flt(invoice.outstanding_amount) <= 0:
		frappe.throw(_("Invoice {0} is already paid.").format(invoice.name))
	if invoice.payment_link_id and flt(invoice.payment_link_amount) == flt(invoice.outstanding_amount):
		return invoice.payment_link_url

	if invoice.payment_link_id:
		try:
			razorpay.cancel_payment_link(invoice.payment_link_id, auth)  # for the old balance
		except frappe.ValidationError:
			frappe.clear_last_message()  # already expired or cancelled

	tenant = frappe.db.get_value(
		"Tenant", invoice.tenant, ["full_name", "mobile_no", "email_id"], as_dict=True
	)
	customer = {"name": tenant.full_name}
	if tenant.mobile_no:
		customer["contact"] = tenant.mobile_no.replace(" ", "")
	if tenant.email_id:
		customer["email"] = tenant.email_id
	link = razorpay.create_payment_link(
		{
			"amount": razorpay.to_subunits(invoice.outstanding_amount),
			"currency": "INR",
			"accept_partial": False,
			"description": _("Rent {0} {1}, room {2}").format(
				invoice.billing_month, invoice.billing_year, invoice.room
			)[:2048],
			# reference_id must be unique in the Razorpay account, also when the link is renewed
			"reference_id": f"{invoice.name}-{frappe.generate_hash(length=5)}",
			"customer": customer,
			"notify": {"sms": False, "email": False},
			"reminder_enable": False,
			"notes": {"site": frappe.local.site, "invoice": invoice.name},
			"callback_url": get_url(f"/tenant/invoices?paid={quote(invoice.name)}"),
			"callback_method": "get",
		},
		auth,
	)
	invoice.db_set(
		{
			"payment_link_id": link["id"],
			"payment_link_url": link["short_url"],
			"payment_link_amount": invoice.outstanding_amount,
		},
		update_modified=False,
	)
	return link["short_url"]


def sync_payment_link(invoice) -> list[str]:
	"""Record the captured payments of an invoice's payment link that we haven't recorded yet."""
	auth = get_auth()
	if not (auth and invoice.payment_link_id):
		return []
	link = razorpay.get_payment_link(invoice.payment_link_id, auth)
	recorded = []
	for payment in link.get("payments") or []:
		if payment.get("status") == "captured":
			name = record_online_payment(
				invoice.name,
				payment["payment_id"],
				flt(payment.get("amount")) / 100,
				payment.get("method"),
			)
			if name:
				recorded.append(name)
	return recorded


def record_online_payment(invoice_name: str, payment_id: str, amount: float, method=None) -> str | None:
	"""Turn money received online into a Rent Payment. Idempotent per Razorpay payment id.

	The money is already in the landlord's account, so this is recorded even if their
	subscription has lapsed (see subscription.skip_enforcement)."""
	if frappe.db.exists("Rent Payment", {"reference_no": payment_id, "docstatus": 1}):
		return None

	invoice = frappe.get_doc(INVOICE, invoice_name, for_update=True)
	outstanding = flt(invoice.outstanding_amount)
	amount = flt(amount, 2)
	if outstanding <= 0:
		invoice.add_comment(
			"Info",
			_("Received {0} online ({1}) after the invoice was fully paid. Refund it from Razorpay.").format(
				amount, payment_id
			),
		)
		frappe.log_error(title=f"Extra online payment {payment_id} for {invoice_name}")
		return None

	remarks = _("Paid online via Razorpay")
	if amount > outstanding:
		remarks += _(". {0} more than the balance was paid; refund it from Razorpay.").format(
			flt(amount - outstanding, 2)
		)
		amount = outstanding

	frappe.flags.recording_online_payment = True
	try:
		payment = frappe.get_doc(
			{
				"doctype": "Rent Payment",
				"tenant": invoice.tenant,
				"rent_invoice": invoice.name,
				"amount": amount,
				"mode_of_payment": RAZORPAY_METHODS.get(method or "", "UPI"),
				"payment_date": nowdate(),
				"reference_no": payment_id,
				"reference_date": nowdate(),
				"remarks": remarks,
			}
		)
		payment.flags.ignore_permissions = True
		payment.insert()
		payment.submit()
	finally:
		frappe.flags.recording_online_payment = False
	return payment.name


@frappe.whitelist(allow_guest=True, methods=["POST"])
def razorpay_webhook():
	"""Webhook from the landlord's Razorpay account (event: payment_link.paid)."""
	body = frappe.request.get_data()
	settings = frappe.get_single(SETTINGS)
	secret = settings.get_password("razorpay_webhook_secret", raise_exception=False)
	if not razorpay.verify_webhook_signature(
		body, frappe.get_request_header("X-Razorpay-Signature") or "", secret
	):
		frappe.throw(_("Invalid signature"), frappe.AuthenticationError)

	event = frappe.parse_json(body.decode() or "{}")
	payload = event.get("payload") or {}
	link = (payload.get("payment_link") or {}).get("entity") or {}
	payment = (payload.get("payment") or {}).get("entity") or {}
	if event.get("event") != "payment_link.paid" or not link.get("id") or not payment.get("id"):
		return {"status": "ignored"}

	invoice = frappe.db.get_value(INVOICE, {"payment_link_id": link["id"]})
	if not invoice:
		lead = frappe.db.get_value("Rent Lead", {"payment_link_id": link["id"]})
		if not lead:
			return {"status": "ignored"}
		from rent_management import leads

		frappe.set_user("Administrator")
		leads.record_token_payment(
			frappe.get_doc("Rent Lead", lead), payment["id"], flt(payment.get("amount")) / 100
		)
		return {"status": "ok"}
	frappe.set_user("Administrator")
	record_online_payment(invoice, payment["id"], flt(payment.get("amount")) / 100, payment.get("method"))
	return {"status": "ok"}


def reconcile_payment_links():
	"""Scheduler (daily): pick up link payments the webhook didn't deliver."""
	if not get_auth():
		return
	for name in frappe.get_all(
		INVOICE,
		filters={"docstatus": 1, "outstanding_amount": (">", 0), "payment_link_id": ("is", "set")},
		pluck="name",
	):
		frappe.db.savepoint("payment_link")
		try:
			sync_payment_link(frappe.get_doc(INVOICE, name))
		except Exception:
			frappe.db.rollback(save_point="payment_link")
			frappe.log_error(title=f"Could not check payment link of {name}")
